"""Baseline D: a (small) LLM rates query difficulty before generation.

The judge call is recorded like any other call, so its cost is charged to the
system that uses it. Unparseable ratings fall back to the midpoint and are
flagged in the details rather than silently dropped.
"""

from __future__ import annotations

import re

from routeguard.complexity.base import BaseDifficultyEstimator, DifficultyThresholds
from routeguard.context import CallContext
from routeguard.prompts import difficulty_judge_messages
from routeguard.types import Query, QueryAnalysis
from routeguard.utils.text import normalize_digits


class LLMJudgeDifficultyEstimator(BaseDifficultyEstimator):
    name = "llm_judge"

    def __init__(self, thresholds: DifficultyThresholds | None = None, model: str | None = None):
        super().__init__(thresholds)
        self.model = model

    def score(self, query: Query, analysis: QueryAnalysis, ctx: CallContext) -> tuple[float, dict]:
        model = self.model or ctx.pool.cheapest
        out = ctx.generate(
            model, difficulty_judge_messages(query), purpose="difficulty_judge", max_new_tokens=8
        )
        m = re.search(r"\d+", normalize_digits(out.text))
        if not m:
            return 0.5, {"judge": model, "parse_failed": True, "raw": out.text[:50]}
        rating = min(10, max(1, int(m.group())))
        return (rating - 1) / 9, {"judge": model, "rating": rating}
