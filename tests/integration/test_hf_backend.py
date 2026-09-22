"""Real Hugging Face backend test (never runs in CI).

Enable with ``RG_TEST_HF=1 pytest -m gpu``; downloads Qwen3-0.6B (~1.5 GB) if not cached.
"""

import os

import pytest

pytestmark = pytest.mark.gpu


@pytest.mark.skipif(os.environ.get("RG_TEST_HF") != "1", reason="set RG_TEST_HF=1 to run")
def test_hf_backend_generates_with_logprobs():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from routeguard.models import ModelSpec, build_llm
    from routeguard.prompts import build_messages
    from routeguard.types import AnswerType, GenerationRequest, Query

    spec = ModelSpec(
        "small",
        "huggingface",
        "Qwen/Qwen3-0.6B",
        max_new_tokens=128,
        options={"batch_size": 2, "chat_template_kwargs": {"enable_thinking": False}},
    )
    llm = build_llm(spec)
    queries = [
        Query(text="What is 17 multiplied by 23?", answer_type=AnswerType.NUMERIC),
        Query(text="Сколько будет 12 плюс 7?", answer_type=AnswerType.NUMERIC),
    ]
    outs = llm.generate_batch(
        [GenerationRequest(build_messages(q, "math"), max_new_tokens=128) for q in queries]
    )
    for out in outs:
        assert out.text and out.output_tokens > 0 and out.input_tokens > 0
        assert out.token_logprobs is not None and len(out.token_logprobs) == out.output_tokens
        assert all(lp <= 0 for lp in out.token_logprobs)
    assert "Final answer" in outs[0].text
    assert llm.resource_stats()["params_b"] > 0.5
