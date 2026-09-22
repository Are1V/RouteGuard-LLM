"""Baseline A: transparent heuristic complexity score.

``score = sigmoid(bias + sum_i w_i * clip(feature_i))``. The default weights are
hand-set, documented priors — *not* tuned on any evaluation data — so this
baseline measures how far surface complexity alone predicts difficulty. They can
be overridden from the configuration (``difficulty.options.weights``).
"""

from __future__ import annotations

import math

from routeguard.complexity.base import BaseDifficultyEstimator, DifficultyThresholds
from routeguard.context import CallContext
from routeguard.types import Query, QueryAnalysis

DEFAULT_WEIGHTS: dict[str, float] = {
    "log_chars": 0.45,  # longer queries tend to require more work
    "n_numbers": 0.15,  # quantities to track
    "n_math_ops": 0.20,  # explicit arithmetic / algebra
    "has_code": 0.90,  # code understanding / generation
    "n_entities": 0.08,  # multi-entity questions
    "step_cues": 0.35,  # "explain", "prove", "step by step", ...
    "constraint_cues": 0.25,  # "exactly", "at least", "without", ...
    "n_question_marks": 0.15,  # multi-part questions
    "has_context": 0.30,  # passage must be read
    "non_latin_ratio": 0.40,  # non-English script (small models are weaker there)
}
DEFAULT_BIAS = -3.2
# Each feature is clipped so that a single extreme feature cannot saturate the score.
CLIP = {
    "n_numbers": 8.0,
    "n_math_ops": 8.0,
    "n_entities": 8.0,
    "step_cues": 4.0,
    "constraint_cues": 4.0,
    "n_question_marks": 3.0,
    "log_chars": 8.0,
}


class HeuristicDifficultyEstimator(BaseDifficultyEstimator):
    name = "heuristic"

    def __init__(
        self,
        thresholds: DifficultyThresholds | None = None,
        weights: dict[str, float] | None = None,
        bias: float = DEFAULT_BIAS,
    ):
        super().__init__(thresholds)
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.bias = bias

    def score(self, query: Query, analysis: QueryAnalysis, ctx: CallContext) -> tuple[float, dict]:
        contrib = {}
        for name, w in self.weights.items():
            value = min(analysis.features.get(name, 0.0), CLIP.get(name, math.inf))
            contrib[name] = w * value
        z = self.bias + sum(contrib.values())
        return 1.0 / (1.0 + math.exp(-z)), {"contributions": contrib}
