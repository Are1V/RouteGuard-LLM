import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from routeguard.models import CachedLLM, GenerationCache, ModelPool, ModelSpec, build_llm
from routeguard.models.cache import request_key
from routeguard.models.openai_compat import (
    BackendConfigurationError,
    BackendError,
    OpenAICompatibleLLM,
    parse_chat_completion,
)
from routeguard.types import GenerationRequest
from routeguard.utils.imports import MissingDependencyError, require
from tests.conftest import sim_models


def test_model_spec_costs():
    spec = ModelSpec(
        "m", "simulated", "x", params_b=1.0, price_input_per_1k=1.0, price_output_per_1k=2.0
    )
    assert spec.cost_usd(1000, 500) == pytest.approx(2.0)
    assert spec.tflops(500, 500) == pytest.approx(2.0)
    local = ModelSpec("l", "simulated", "x", params_b=2.0)
    assert local.relative_cost() == local.tflops(400, 200)


def test_pool_order_and_lookup():
    pool = ModelPool([ModelSpec(**m) for m in sim_models()])
    assert pool.names == ["small", "medium", "large"]
    assert pool.cheapest == "small" and pool.strongest == "large"
    assert pool.next_stronger("small") == "medium" and pool.next_stronger("large") is None
    assert pool.by_tier(99) == "large"
    assert pool.simulated
    with pytest.raises(KeyError):
        pool.spec("nope")
    with pytest.raises(ValueError):
        ModelPool([])
    with pytest.raises(ValueError):
        build_llm(ModelSpec("x", "unknown-backend", "x"))


def test_simulator_is_deterministic_and_reference_gated():
    llm = build_llm(ModelSpec(**sim_models()[2]))
    ref = {"id": "a", "answer": "42", "answer_type": "numeric", "difficulty": 0.1}
    req = GenerationRequest([{"role": "user", "content": "q"}], metadata={"reference": ref})
    assert llm.generate(req).text == llm.generate(req).text
    no_ref = llm.generate(GenerationRequest([{"role": "user", "content": "q"}]))
    assert "unknown" in no_ref.text


def test_generation_cache_roundtrip(tmp_path):
    cache = GenerationCache(tmp_path / "c.sqlite")
    from routeguard.models.simulated import SimulatedLLM

    llm = CachedLLM(ModelSpec(**sim_models()[0]), SimulatedLLM, cache)
    assert llm._inner is None  # nothing is instantiated before the first miss
    req = GenerationRequest([{"role": "user", "content": "hello"}])
    first = llm.generate(req)
    second = llm.generate(req)
    assert not first.cached and second.cached
    assert llm._inner is not None
    assert first.text == second.text and first.latency_s == second.latency_s
    assert len(cache) == 1
    # Greedy requests ignore the seed; sampled requests do not.
    ident = llm.identity()
    g1 = GenerationRequest([{"role": "user", "content": "x"}], seed=1)
    g2 = GenerationRequest([{"role": "user", "content": "x"}], seed=2)
    assert request_key(ident, g1) == request_key(ident, g2)
    s1 = GenerationRequest([{"role": "user", "content": "x"}], temperature=0.7, seed=1)
    s2 = GenerationRequest([{"role": "user", "content": "x"}], temperature=0.7, seed=2)
    assert request_key(ident, s1) != request_key(ident, s2)
    with_ref = GenerationRequest(
        [{"role": "user", "content": "x"}],
        metadata={"reference": {"answer": "1"}},
    )
    without_ref = GenerationRequest([{"role": "user", "content": "x"}])
    assert request_key(ident, with_ref) != request_key(ident, without_ref)
    cache.close()


def test_parse_chat_completion():
    payload = {
        "choices": [
            {
                "message": {"content": " Final answer: 4 "},
                "finish_reason": "stop",
                "logprobs": {
                    "content": [
                        {"logprob": -0.1, "top_logprobs": [{"logprob": -0.1}, {"logprob": -2.0}]}
                    ]
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 1},
    }
    out = parse_chat_completion(payload, "m", 0.5)
    assert out.text == "Final answer: 4" and out.input_tokens == 12
    assert out.token_logprobs == [-0.1] and out.top_logprobs == [[-0.1, -2.0]]
    with pytest.raises(BackendError):
        parse_chat_completion({"error": "x"}, "m", 0.1)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.headers["Authorization"] == "Bearer test-key"
        reply = {
            "choices": [{"message": {"content": f"echo {body['model']}"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def test_openai_compatible_backend_against_local_server(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("TEST_KEY", "test-key")
    spec = ModelSpec(
        "api",
        "openai_compatible",
        "my-model",
        options={
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "api_key_env": "TEST_KEY",
        },
    )
    out = OpenAICompatibleLLM(spec).generate(GenerationRequest([{"role": "user", "content": "hi"}]))
    server.shutdown()
    assert out.text == "echo my-model" and out.output_tokens == 2
    assert "api_key_env" not in OpenAICompatibleLLM(spec).identity()["options"]


def test_openai_compatible_requires_env_and_url(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(ValueError, match="MISSING_KEY"):
        OpenAICompatibleLLM(
            ModelSpec(
                "a",
                "openai_compatible",
                "m",
                options={"base_url": "http://x", "api_key_env": "MISSING_KEY"},
            )
        )
    with pytest.raises(ValueError, match="base_url"):
        OpenAICompatibleLLM(ModelSpec("a", "openai_compatible", "m"))


def test_unreachable_server_raises(monkeypatch):
    spec = ModelSpec(
        "a",
        "openai_compatible",
        "m",
        options={"base_url": "http://127.0.0.1:9", "max_retries": 0, "timeout_s": 1},
    )
    with pytest.raises(BackendError):
        OpenAICompatibleLLM(spec).generate(GenerationRequest([{"role": "user", "content": "x"}]))


def test_missing_optional_dependency_message():
    with pytest.raises(MissingDependencyError, match=r"pip install -e '\.\[hf\]'"):
        require("definitely_not_a_module_xyz", "hf", "Test feature")


def test_backend_configuration_errors_are_both_value_and_backend_errors(monkeypatch):
    """Serving layers catch BackendError; existing callers catch ValueError."""
    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(BackendConfigurationError) as info:
        OpenAICompatibleLLM(
            ModelSpec(
                "a",
                "openai_compatible",
                "m",
                options={"base_url": "http://x", "api_key_env": "MISSING_KEY"},
            )
        )
    assert isinstance(info.value, ValueError)
    assert isinstance(info.value, BackendError)
