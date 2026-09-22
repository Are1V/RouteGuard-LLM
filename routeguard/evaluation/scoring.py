"""Deterministic scoring of predictions against gold answers.

Where objective ground truth exists we never use an LLM judge:

* numeric – canonicalised number equality (relative tolerance 1e-6),
* choice  – option-letter equality,
* code    – execution of the gold test cases,
* text    – exact match / token F1 / guarded containment against all gold aliases.

``contains`` accepts a prediction if a normalised gold alias appears in it as a
contiguous token sequence *and* the prediction is at most ``max_extra_tokens``
longer than that alias, so listing many candidates is not rewarded.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from routeguard.answers import canonical_number
from routeguard.types import AnswerType
from routeguard.utils.text import tokenize
from routeguard.verification.sandbox import run_python

TEXT_MATCH_RULES = ("em", "f1", "contains")


@dataclass
class Score:
    correct: bool
    exact_match: float
    f1: float
    extraction_failed: bool = False
    details: dict[str, Any] = field(default_factory=dict)


def _aliases(gold: Any) -> list[str]:
    if isinstance(gold, list):
        return [str(g) for g in gold]
    return [str(gold)]


def token_f1(pred: str, gold: str) -> float:
    p, g = tokenize(pred), tokenize(gold)
    if not p or not g:
        return float(p == g)
    common = Counter(p) & Counter(g)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / len(p), overlap / len(g)
    return 2 * precision * recall / (precision + recall)


def _contains(pred: str, gold: str, max_extra_tokens: int) -> bool:
    p, g = tokenize(pred), tokenize(gold)
    if not g or len(p) - len(g) > max_extra_tokens:
        return False
    return any(p[i : i + len(g)] == g for i in range(len(p) - len(g) + 1))


def score_prediction(
    prediction: str | None,
    gold: Any,
    answer_type: AnswerType,
    *,
    text_match: str = "contains",
    f1_threshold: float = 0.5,
    max_extra_tokens: int = 8,
    eval_tests: list[str] | None = None,
    timeout_s: float = 10.0,
) -> Score:
    if prediction is None:
        return Score(False, 0.0, 0.0, extraction_failed=True)
    aliases = _aliases(gold)

    if answer_type == AnswerType.NUMERIC:
        p = canonical_number(prediction)
        ok = False
        for alias in aliases:
            g = canonical_number(alias)
            if p is not None and g is not None:
                pv, gv = float(p), float(g)
                ok = ok or abs(pv - gv) <= 1e-6 * max(1.0, abs(gv))
        return Score(ok, float(ok), float(ok))

    if answer_type == AnswerType.CHOICE:
        ok = prediction.strip().upper() in {a.strip().upper() for a in aliases}
        return Score(ok, float(ok), float(ok))

    if answer_type == AnswerType.CODE:
        if not eval_tests:
            raise ValueError("Scoring a code answer requires eval_tests")
        result = run_python(prediction, eval_tests, timeout_s=timeout_s)
        return Score(
            result.passed,
            float(result.passed),
            float(result.passed),
            details={"timed_out": result.timed_out, "stderr": result.stderr[-300:]},
        )

    if text_match not in TEXT_MATCH_RULES:
        raise ValueError(f"text_match must be one of {TEXT_MATCH_RULES}")
    em = max(float(tokenize(prediction) == tokenize(a)) for a in aliases)
    f1 = max(token_f1(prediction, a) for a in aliases)
    if text_match == "em":
        ok = em == 1.0
    elif text_match == "f1":
        ok = f1 >= f1_threshold
    else:
        ok = em == 1.0 or any(_contains(prediction, a, max_extra_tokens) for a in aliases)
    return Score(ok, em, f1)
