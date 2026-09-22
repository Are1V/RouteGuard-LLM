"""Second-model judge verifier (LLM-as-a-judge).

Used only where deterministic checks are unavailable, and never for scoring.
The judge call is charged to the query. Judges share failure modes with the
models they judge, so the error analysis reports verifier accuracy separately.
"""

from __future__ import annotations

import re

from routeguard.context import CallContext
from routeguard.prompts import verification_judge_messages
from routeguard.types import VerificationResult
from routeguard.verification.base import BaseVerifier, VerificationInput

_YES = re.compile(r"^\W*(yes|да|иә|бәлі|بله|آری|درست)", re.IGNORECASE)
_NO = re.compile(r"^\W*(no|нет|жоқ|خیر|نه|نادرست)", re.IGNORECASE)


class JudgeVerifier(BaseVerifier):
    name = "judge"

    def __init__(self, model: str | None = None, answer_types: list[str] | None = None):
        self.model = model
        self.answer_types = set(answer_types) if answer_types else None

    def verify(self, inp: VerificationInput, ctx: CallContext) -> VerificationResult:
        if self.answer_types and inp.query.answer_type.value not in self.answer_types:
            return self.skip()
        model = self.model or ctx.pool.strongest
        out = ctx.generate(
            model,
            verification_judge_messages(inp.query, inp.output.text),
            purpose="verify_judge",
            max_new_tokens=4,
            metadata={"candidate_answer": inp.answer},
        )
        if _YES.search(out.text):
            return VerificationResult(True, self.name, details={"judge": model})
        if _NO.search(out.text):
            return VerificationResult(
                False, self.name, reason="judge rejected answer", details={"judge": model}
            )
        return VerificationResult(
            None,
            self.name,
            reason=f"unparseable verdict: {out.text[:30]!r}",
            details={"judge": model},
        )
