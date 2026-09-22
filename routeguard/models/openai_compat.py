"""Backend for any server implementing the OpenAI chat-completions protocol.

One implementation covers hosted APIs and local servers: vLLM
(``vllm serve``), llama.cpp (``llama-server``), Ollama (``/v1``), LM Studio, and
commercial providers. Only the standard library is used.

Configuration (``options``):

``base_url``      e.g. ``http://localhost:8000/v1``
``api_key_env``   name of the environment variable holding the key (never the key itself)
``timeout_s``     request timeout (default 120)
``max_retries``   retries on 429/5xx with exponential back-off (default 4)
``extra_body``    provider-specific fields merged into the request body
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from routeguard.models.base import BaseLLM, ModelSpec
from routeguard.types import GenerationOutput, GenerationRequest


class BackendError(RuntimeError):
    pass


class BackendConfigurationError(BackendError, ValueError):
    """The backend cannot be built from its configuration (missing URL or API key).

    Also a ``ValueError`` so that existing callers catching configuration mistakes
    keep working, while serving layers can treat it as a backend failure.
    """


class OpenAICompatibleLLM(BaseLLM):
    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        o = spec.options
        if "base_url" not in o:
            raise BackendConfigurationError(
                f"Model '{spec.name}': openai_compatible backend needs options.base_url"
            )
        self.base_url = str(o["base_url"]).rstrip("/")
        self.timeout_s = float(o.get("timeout_s", 120))
        self.max_retries = int(o.get("max_retries", 4))
        self.extra_body: dict[str, Any] = dict(o.get("extra_body", {}))
        key_env = o.get("api_key_env")
        self.api_key = os.environ.get(key_env) if key_env else None
        if key_env and not self.api_key:
            raise BackendConfigurationError(
                f"Model '{spec.name}': environment variable {key_env} is not set"
            )

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(body).encode("utf-8")
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions", data=data, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return dict(json.loads(resp.read().decode("utf-8")))
            except urllib.error.HTTPError as exc:
                retriable = exc.code == 429 or exc.code >= 500
                if not retriable or attempt == self.max_retries:
                    detail = exc.read().decode("utf-8", "replace")[:500]
                    raise BackendError(f"{self.spec.name}: HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt == self.max_retries:
                    raise BackendError(
                        f"{self.spec.name}: cannot reach {self.base_url}: {exc}"
                    ) from exc
            time.sleep(delay)
            delay *= 2
        raise BackendError(f"{self.spec.name}: exhausted retries")  # pragma: no cover

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        body: dict[str, Any] = {
            "model": self.spec.model_id,
            "messages": request.messages,
            "max_tokens": request.max_new_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.seed is not None:
            body["seed"] = request.seed
        if request.stop:
            body["stop"] = request.stop
        if request.logprobs:
            body["logprobs"] = True
            body["top_logprobs"] = request.top_logprobs
        body.update(self.extra_body)

        t0 = time.perf_counter()
        payload = self._post(body)
        latency = time.perf_counter() - t0
        return parse_chat_completion(payload, self.spec.name, latency)


def parse_chat_completion(
    payload: dict[str, Any], model_name: str, latency: float
) -> GenerationOutput:
    try:
        choice = payload["choices"][0]
        text = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise BackendError(f"{model_name}: malformed response: {str(payload)[:300]}") from exc
    token_lps: list[float] | None = None
    top_lps: list[list[float]] | None = None
    content = (choice.get("logprobs") or {}).get("content")
    if content:
        token_lps = [float(t["logprob"]) for t in content]
        top_lps = [
            [float(a["logprob"]) for a in t.get("top_logprobs", [])] or [float(t["logprob"])]
            for t in content
        ]
    usage = payload.get("usage") or {}
    return GenerationOutput(
        text=text.strip(),
        model=model_name,
        input_tokens=int(usage.get("prompt_tokens", 0)),
        output_tokens=int(usage.get("completion_tokens", len(token_lps or []))),
        latency_s=latency,
        token_logprobs=token_lps,
        top_logprobs=top_lps,
        finish_reason=str(choice.get("finish_reason") or "stop"),
    )
