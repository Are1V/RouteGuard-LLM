"""Per-query execution context: the single place where LLM calls are made.

Routing research is only honest if *every* call a strategy makes is paid for:
difficulty judges, confidence samples, verifier judges, and escalation stages all
add tokens and latency. Components therefore never call a backend directly; they
go through :class:`CallContext`, which records a :class:`CallRecord` per call.

It is also the only place that may forward gold references, and it does so only
to backends that declare ``requires_reference`` (the simulator).
"""

from __future__ import annotations

from typing import Any

from routeguard.models.pool import ModelPool
from routeguard.types import CallRecord, GenerationOutput, GenerationRequest, Message, Query
from routeguard.utils.seeding import derive_seed


class CallContext:
    def __init__(self, pool: ModelPool, query: Query, seed: int = 0):
        self.pool = pool
        self.query = query
        self.seed = seed
        self.calls: list[CallRecord] = []

    def _request(
        self,
        model: str,
        messages: list[Message],
        purpose: str,
        temperature: float,
        sample: int,
        max_new_tokens: int | None,
        metadata: dict[str, Any] | None,
    ) -> GenerationRequest:
        spec = self.pool.spec(model)
        meta: dict[str, Any] = {"purpose": purpose, **(metadata or {})}
        if self.pool.requires_reference(model) and self.query.reference is not None:
            meta["reference"] = self.query.reference
        return GenerationRequest(
            messages=messages,
            max_new_tokens=max_new_tokens or spec.max_new_tokens,
            temperature=temperature,
            top_p=0.95 if temperature > 0 else 1.0,
            seed=derive_seed(self.seed, self.query.id, purpose, sample)
            if temperature > 0
            else None,
            metadata=meta,
        )

    def _record(self, model: str, out: GenerationOutput, purpose: str) -> None:
        spec = self.pool.spec(model)
        self.calls.append(
            CallRecord(
                model=model,
                purpose=purpose,
                input_tokens=out.input_tokens,
                output_tokens=out.output_tokens,
                latency_s=out.latency_s,
                cost_usd=spec.cost_usd(out.input_tokens, out.output_tokens),
                tflops=spec.tflops(out.input_tokens, out.output_tokens),
                cached=out.cached,
            )
        )

    def generate(
        self,
        model: str,
        messages: list[Message],
        purpose: str,
        temperature: float = 0.0,
        sample: int = 0,
        max_new_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationOutput:
        return self.generate_samples(
            model, messages, purpose, 1, temperature, max_new_tokens, metadata, first_sample=sample
        )[0]

    def generate_samples(
        self,
        model: str,
        messages: list[Message],
        purpose: str,
        n: int,
        temperature: float,
        max_new_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
        first_sample: int = 0,
    ) -> list[GenerationOutput]:
        requests = [
            self._request(
                model, messages, purpose, temperature, first_sample + i, max_new_tokens, metadata
            )
            for i in range(n)
        ]
        outputs = self.pool.get(model).generate_batch(requests)
        for out in outputs:
            self._record(model, out, purpose)
        return outputs
