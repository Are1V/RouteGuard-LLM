"""Deterministic verifiers (no model calls)."""

from __future__ import annotations

import ast
import re

from routeguard.context import CallContext
from routeguard.types import AnswerType, VerificationResult
from routeguard.utils.text import normalize_digits, tokenize
from routeguard.verification.base import BaseVerifier, VerificationInput
from routeguard.verification.sandbox import run_python


class FormatVerifier(BaseVerifier):
    """The response is complete and contains an answer of the expected form."""

    name = "format"

    def __init__(self, max_text_words: int = 30):
        self.max_text_words = max_text_words

    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult:
        if inp.output.finish_reason == "length":
            return VerificationResult(
                False, self.name, reason="generation truncated at token limit"
            )
        if inp.answer is None:
            return VerificationResult(False, self.name, reason="no answer could be extracted")
        q = inp.query
        if q.answer_type == AnswerType.CHOICE:
            valid = "ABCDEFGHIJ"[: len(q.choices or "ABCD")]
            ok = inp.answer in valid
            return VerificationResult(ok, self.name, reason="" if ok else "invalid option letter")
        if q.answer_type == AnswerType.CODE:
            try:
                ast.parse(inp.answer)
            except SyntaxError as exc:
                return VerificationResult(False, self.name, reason=f"syntax error: {exc.msg}")
            if q.entry_point and not re.search(
                rf"def\s+{re.escape(q.entry_point)}\s*\(", inp.answer
            ):
                return VerificationResult(False, self.name, reason=f"missing def {q.entry_point}")
            return VerificationResult(True, self.name)
        if q.answer_type == AnswerType.TEXT and len(tokenize(inp.answer)) > self.max_text_words:
            return VerificationResult(False, self.name, reason="answer is not short-form")
        return VerificationResult(True, self.name)


_EQUATION = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)\s*([-+*/×x÷])\s*(\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)(?!\d|\.\d)"
)
_OPERATOR_BEFORE = re.compile(r"[-+*/×x÷(]\s*$")
_OPERATOR_AFTER = re.compile(r"^\s*[-+*/×x÷]\s*\d")


def binary_equations(text: str) -> list[tuple[str, str, str, str]]:
    """``a op b = c`` steps, skipping fragments of longer chains such as ``3 + 4 + 5 = 12``."""
    found = []
    for m in _EQUATION.finditer(text):
        before, after = text[max(0, m.start() - 3) : m.start()], text[m.end() : m.end() + 4]
        if _OPERATOR_BEFORE.search(before) or _OPERATOR_AFTER.search(after):
            continue
        found.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    return found


class ArithmeticVerifier(BaseVerifier):
    """Re-computes every ``a <op> b = c`` step written in a math response.

    A mismatch is strong evidence of a reasoning error. Responses without such
    steps are *not applicable* rather than passed.
    """

    name = "arithmetic"

    def __init__(self, rel_tol: float = 1e-4):
        self.rel_tol = rel_tol

    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult:
        if inp.query.answer_type != AnswerType.NUMERIC:
            return self.skip()
        text = normalize_digits(inp.output.text).replace(",", "")
        steps = binary_equations(text)
        if not steps:
            return self.skip("no explicit arithmetic steps")
        errors = []
        for a, op, b, c in steps:
            x, y, z = float(a), float(b), float(c)
            if op in "*×x":
                expected = x * y
            elif op in "/÷":
                if y == 0:
                    errors.append(f"{a}{op}{b}")
                    continue
                expected = x / y
            elif op == "+":
                expected = x + y
            else:
                expected = x - y
            if abs(expected - z) > self.rel_tol * max(1.0, abs(expected)):
                errors.append(f"{a} {op} {b} = {c} (expected {expected:g})")
        ok = not errors
        return VerificationResult(
            ok,
            self.name,
            score=1 - len(errors) / len(steps),
            reason="; ".join(errors[:3]),
            details={"n_steps": len(steps)},
        )


class CodeExecutionVerifier(BaseVerifier):
    """Runs generated code against the *public* tests shipped with the prompt.

    Public tests are part of the task statement (e.g. MBPP shows them to the
    model), so using them is not leakage. Hidden evaluation tests are used only by
    the scorer. Without public tests the code is executed once to catch crashes.
    """

    name = "code_execution"

    def __init__(self, timeout_s: float = 10.0):
        self.timeout_s = timeout_s

    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult:
        if inp.query.answer_type != AnswerType.CODE:
            return self.skip()
        if inp.answer is None:
            return VerificationResult(False, self.name, reason="no code extracted")
        result = run_python(inp.answer, inp.query.public_tests, timeout_s=self.timeout_s)
        last_line = (result.stderr.strip().splitlines() or [""])[-1]
        reason = "" if result.passed else ("timeout" if result.timed_out else last_line)
        return VerificationResult(
            result.passed,
            self.name,
            reason=reason,
            details={"n_public_tests": len(inp.query.public_tests or [])},
        )


class GroundingVerifier(BaseVerifier):
    """Short text answers must be lexically supported by the passage/evidence."""

    name = "grounding"

    def __init__(self, min_support: float = 0.5):
        self.min_support = min_support

    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult:
        sources = [*(inp.evidence or []), *([inp.query.context] if inp.query.context else [])]
        if inp.query.answer_type != AnswerType.TEXT or not sources or not inp.answer:
            return self.skip()
        answer_tokens = set(tokenize(inp.answer))
        if not answer_tokens:
            return VerificationResult(False, self.name, reason="empty answer")
        source_tokens = set(tokenize(" ".join(sources)))
        support = len(answer_tokens & source_tokens) / len(answer_tokens)
        ok = support >= self.min_support
        return VerificationResult(
            ok,
            self.name,
            score=support,
            reason="" if ok else f"only {support:.0%} of answer tokens in evidence",
        )
