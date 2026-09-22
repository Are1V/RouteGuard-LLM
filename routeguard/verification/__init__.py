"""Answer verification."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from routeguard.context import CallContext
from routeguard.types import VerificationResult
from routeguard.verification.base import BaseVerifier, VerificationInput
from routeguard.verification.checks import (
    ArithmeticVerifier,
    CodeExecutionVerifier,
    FormatVerifier,
    GroundingVerifier,
)
from routeguard.verification.judge import JudgeVerifier

VERIFIERS: dict[str, type[BaseVerifier]] = {
    "format": FormatVerifier,
    "arithmetic": ArithmeticVerifier,
    "code_execution": CodeExecutionVerifier,
    "grounding": GroundingVerifier,
    "judge": JudgeVerifier,
}


class CompositeVerifier(BaseVerifier):
    """Runs verifiers in order; fails on the first applicable failure.

    ``passed`` is ``None`` when no verifier was applicable. Later (possibly
    expensive, e.g. judge) verifiers are skipped once one has failed.
    """

    name = "composite"

    def __init__(self, verifiers: list[BaseVerifier]):
        self.verifiers = verifiers

    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult:
        results: list[VerificationResult] = []
        for v in self.verifiers:
            r = v.verify(inp, ctx)
            results.append(r)
            if r.passed is False:
                return VerificationResult(
                    False, r.verifier, r.score, r.reason, {"checks": _summaries(results)}
                )
        applicable = [r for r in results if r.passed is not None]
        passed = True if applicable else None
        return VerificationResult(passed, self.name, details={"checks": _summaries(results)})


def _summaries(results: list[VerificationResult]) -> list[dict[str, Any]]:
    return [{"verifier": r.verifier, "passed": r.passed, "reason": r.reason} for r in results]


def build_verifier(specs: Sequence[str | dict[str, Any]]) -> CompositeVerifier:
    verifiers: list[BaseVerifier] = []
    for spec in specs:
        name, options = (
            (spec, {}) if isinstance(spec, str) else (spec["name"], spec.get("options", {}))
        )
        if name not in VERIFIERS:
            raise ValueError(f"Unknown verifier '{name}'. Available: {sorted(VERIFIERS)}")
        verifiers.append(VERIFIERS[name](**options))
    return CompositeVerifier(verifiers)


__all__ = ["VERIFIERS", "BaseVerifier", "CompositeVerifier", "VerificationInput", "build_verifier"]
