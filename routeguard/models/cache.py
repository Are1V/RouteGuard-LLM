"""Persistent generation cache.

Research on routing compares many systems on the same queries. Most of their
model calls are identical (``always-small`` and a router that picks ``small``
issue the same request), so every call is keyed by the backend identity and the
full request and stored in SQLite. Cached entries keep the *originally measured*
latency and token counts, so replayed runs report real costs rather than zero.

Greedy requests (``temperature == 0``) ignore the seed in the key; sampled
requests include it, so repeated samples stay distinct and reproducible.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from routeguard.models.base import BaseLLM, ModelSpec
from routeguard.types import GenerationOutput, GenerationRequest
from routeguard.utils.seeding import stable_hash

logger = logging.getLogger(__name__)


def request_key(identity: dict[str, Any], request: GenerationRequest) -> str:
    payload = {
        "identity": identity,
        "messages": request.messages,
        "max_new_tokens": request.max_new_tokens,
        "temperature": request.temperature,
        "top_p": request.top_p if request.temperature > 0 else 1.0,
        "seed": request.seed if request.temperature > 0 else None,
        "stop": request.stop,
        "logprobs": request.logprobs,
        "top_logprobs": request.top_logprobs if request.logprobs else 0,
        # Real backends do not read metadata, so omitting it lets equivalent calls from
        # different systems share generations. The simulator does read its trusted reference
        # and call-purpose fields; omitting those can collide with a no-reference demo request.
        "simulator_metadata": request.metadata if identity.get("backend") == "simulated" else None,
    }
    return stable_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False), length=40)


class GenerationCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS generations (key TEXT PRIMARY KEY, model TEXT, value TEXT)"
        )
        self._conn.commit()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> GenerationOutput | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM generations WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return GenerationOutput(**json.loads(row[0]))

    def put_many(self, entries: Sequence[tuple[str, GenerationOutput]]) -> None:
        rows = [
            (key, out.model, json.dumps(asdict(replace(out, cached=False)), ensure_ascii=False))
            for key, out in entries
        ]
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO generations (key, model, value) VALUES (?, ?, ?)", rows
            )
            self._conn.commit()

    def __len__(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class CachedLLM(BaseLLM):
    """Wraps a backend class with a :class:`GenerationCache`.

    The backend is instantiated only on the first cache miss, so fully cached replays
    (re-evaluations, demos over cached queries) never load model weights. Misses are
    generated in chunks of ``chunk_size`` and persisted after each chunk, so a long run
    that is interrupted keeps everything generated so far.
    """

    def __init__(
        self,
        spec: ModelSpec,
        backend_cls: type[BaseLLM],
        cache: GenerationCache,
        chunk_size: int = 256,
    ):
        super().__init__(spec)
        self.backend_cls = backend_cls
        self.cache = cache
        self.chunk_size = chunk_size
        self.requires_reference = backend_cls.requires_reference
        self._inner: BaseLLM | None = None

    @property
    def inner(self) -> BaseLLM:
        if self._inner is None:
            self._inner = self.backend_cls(self.spec)
        return self._inner

    def identity(self) -> dict[str, Any]:
        return self.backend_cls.spec_identity(self.spec)

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        return self.generate_batch([request])[0]

    def generate_batch(self, requests: Sequence[GenerationRequest]) -> list[GenerationOutput]:
        identity = self.identity()
        keys = [request_key(identity, r) for r in requests]
        results: list[GenerationOutput | None] = []
        missing: list[int] = []
        for i, key in enumerate(keys):
            hit = self.cache.get(key)
            # The pool name may differ from the one used when the entry was written.
            results.append(replace(hit, cached=True, model=self.spec.name) if hit else None)
            if hit is None:
                missing.append(i)
        for start in range(0, len(missing), self.chunk_size):
            chunk = missing[start : start + self.chunk_size]
            fresh = self.inner.generate_batch([requests[i] for i in chunk])
            self.cache.put_many([(keys[i], out) for i, out in zip(chunk, fresh, strict=True)])
            for i, out in zip(chunk, fresh, strict=True):
                results[i] = out
            if len(missing) > self.chunk_size:
                logger.info(
                    "  %s: generated %d/%d uncached requests",
                    self.spec.name,
                    min(start + self.chunk_size, len(missing)),
                    len(missing),
                )
        return [r for r in results if r is not None]

    def resource_stats(self) -> dict[str, Any]:
        return self._inner.resource_stats() if self._inner is not None else {"loaded": False}
