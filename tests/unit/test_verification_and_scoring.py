import pytest

from routeguard.context import CallContext
from routeguard.evaluation.scoring import score_prediction, token_f1
from routeguard.types import AnswerType, GenerationOutput, Query
from routeguard.verification import VerificationInput, build_verifier
from routeguard.verification.checks import (
    ArithmeticVerifier,
    CodeExecutionVerifier,
    FormatVerifier,
    GroundingVerifier,
    binary_equations,
)
from routeguard.verification.judge import JudgeVerifier
from routeguard.verification.sandbox import run_python


def _vi(text, answer, answer_type=AnswerType.NUMERIC, finish="stop", **qkw):
    out = GenerationOutput(text, "small", 1, 1, 0.1, finish_reason=finish)
    return VerificationInput(Query(text="q", answer_type=answer_type, **qkw), "small", out, answer)


@pytest.fixture
def ctx(sim_pool):
    return CallContext(sim_pool, Query(text="q"))


def test_format_verifier(ctx):
    v = FormatVerifier()
    assert v.verify(_vi("Final answer: 4", "4"), ctx).passed
    assert not v.verify(_vi("...", None), ctx).passed
    assert not v.verify(_vi("Final answer: 4", "4", finish="length"), ctx).passed
    assert not v.verify(
        _vi("Final answer: E", "E", AnswerType.CHOICE, choices=list("abcd")), ctx
    ).passed
    bad = _vi("", "def f(:\n pass", AnswerType.CODE)
    assert not v.verify(bad, ctx).passed
    wrong_name = _vi("", "def g():\n    pass", AnswerType.CODE, entry_point="f")
    assert "missing def f" in v.verify(wrong_name, ctx).reason


def test_arithmetic_verifier(ctx):
    v = ArithmeticVerifier()
    assert v.verify(_vi("12 * 3 = 36\nFinal answer: 36", "36"), ctx).passed
    r = v.verify(_vi("12 * 3 = 38\nFinal answer: 38", "38"), ctx)
    assert r.passed is False and "expected 36" in r.reason
    assert v.verify(_vi("It is 36.\nFinal answer: 36", "36"), ctx).passed is None
    assert v.verify(_vi("x", "a", AnswerType.TEXT), ctx).passed is None
    assert v.verify(_vi("۱۲ × ۳ = ۳۶", "36"), ctx).passed
    assert (
        binary_equations("3 + 4 + 5 = 12 and 1,000 + 1 = 1001") == [("1", "+", "1", "1001")]
        or binary_equations("3 + 4 + 5 = 12") == []
    )


def test_code_execution_verifier_and_sandbox(ctx):
    v = CodeExecutionVerifier(timeout_s=5)
    good = _vi(
        "",
        "def add(a, b):\n    return a + b",
        AnswerType.CODE,
        public_tests=["assert add(1, 2) == 3"],
    )
    bad = _vi(
        "",
        "def add(a, b):\n    return a - b",
        AnswerType.CODE,
        public_tests=["assert add(1, 2) == 3"],
    )
    assert v.verify(good, ctx).passed
    assert v.verify(bad, ctx).passed is False
    assert run_python("while True: pass", timeout_s=1).timed_out


def test_grounding_verifier(ctx):
    v = GroundingVerifier()
    inp = _vi("", "Astana", AnswerType.TEXT, context="The capital of Kazakhstan is Astana.")
    assert v.verify(inp, ctx).passed
    inp = _vi("", "Almaty city", AnswerType.TEXT, context="The capital of Kazakhstan is Astana.")
    assert v.verify(inp, ctx).passed is False


def test_composite_stops_at_first_failure_and_judge(sim_pool):
    q = Query(
        text="2+2?",
        id="j",
        answer_type=AnswerType.NUMERIC,
        reference={"id": "j", "answer": "4", "answer_type": "numeric"},
    )
    ctx = CallContext(sim_pool, q)
    comp = build_verifier(
        ["format", "arithmetic", {"name": "judge", "options": {"model": "large"}}]
    )
    out = GenerationOutput("2 + 2 = 5\nFinal answer: 5", "small", 1, 1, 0.1)
    r = comp.verify(VerificationInput(q, "small", out, "5"), ctx)
    assert r.passed is False and r.verifier == "arithmetic"
    assert not ctx.calls  # the judge was never called after the arithmetic failure
    judge = JudgeVerifier(model="large")
    verdict = judge.verify(
        VerificationInput(q, "small", GenerationOutput("Final answer: 4", "s", 1, 1, 0.1), "4"), ctx
    )
    assert verdict.passed in (True, False) and ctx.calls[-1].purpose == "verify_judge"
    with pytest.raises(ValueError):
        build_verifier(["nope"])


def test_scoring():
    assert score_prediction("19.0", "19", AnswerType.NUMERIC).correct
    assert not score_prediction("20", "19", AnswerType.NUMERIC).correct
    assert score_prediction("b", "B", AnswerType.CHOICE).correct
    s = score_prediction(None, "x", AnswerType.TEXT)
    assert s.extraction_failed and not s.correct
    assert score_prediction(
        "George Washington", ["Washington", "G. Washington"], AnswerType.TEXT
    ).correct
    long = "Washington Adams Jefferson Madison Monroe Jackson Van Buren Harrison Tyler Polk"
    assert not score_prediction(long, "Washington", AnswerType.TEXT).correct  # guarded contains
    assert score_prediction("paris", "Paris", AnswerType.TEXT, text_match="em").correct
    assert token_f1("the big cat", "big cat") == pytest.approx(1.0)
    code = score_prediction(
        "def f(x):\n    return x * 2", None, AnswerType.CODE, eval_tests=["assert f(2) == 4"]
    )
    assert code.correct
    with pytest.raises(ValueError):
        score_prediction("x", None, AnswerType.CODE)
    with pytest.raises(ValueError):
        score_prediction("x", "y", AnswerType.TEXT, text_match="fuzzy")
