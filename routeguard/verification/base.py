"""Verifier interface.

Verifiers run at inference time and therefore never see gold answers. A verifier
returns ``passed=None`` when it does not apply (e.g. the code executor on a math
question), which is different from passing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from routeguard.context import CallContext
from routeguard.types import GenerationOutput, Query, VerificationResult


@dataclass
class VerificationInput:
    query: Query
    model: str
    output: GenerationOutput
    answer: str | None
    evidence: list[str] | None = None


class BaseVerifier(ABC):
    name: str = "base"

    @abstractmethod
    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult: ...

    def skip(self, reason: str = "not applicable") -> VerificationResult:
        return VerificationResult(None, self.name, reason=reason)
