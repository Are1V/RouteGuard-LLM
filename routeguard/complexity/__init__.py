"""Query difficulty estimators (Baselines A-D)."""

from __future__ import annotations

from typing import Any

from routeguard.complexity.base import (
    BaseDifficultyEstimator,
    DifficultyThresholds,
    TrainingExample,
    cheapest_correct_tier,
    tier_to_score,
)
from routeguard.complexity.heuristic import HeuristicDifficultyEstimator
from routeguard.complexity.learned import LearnedDifficultyEstimator, NeuralDifficultyEstimator
from routeguard.complexity.llm_judge import LLMJudgeDifficultyEstimator

ESTIMATORS: dict[str, type[BaseDifficultyEstimator]] = {
    "heuristic": HeuristicDifficultyEstimator,
    "learned": LearnedDifficultyEstimator,
    "neural": NeuralDifficultyEstimator,
    "llm_judge": LLMJudgeDifficultyEstimator,
}


def build_difficulty_estimator(
    kind: str, thresholds: DifficultyThresholds, options: dict[str, Any], seed: int = 0
) -> BaseDifficultyEstimator:
    if kind not in ESTIMATORS:
        raise ValueError(f"Unknown difficulty estimator '{kind}'. Available: {sorted(ESTIMATORS)}")
    cls = ESTIMATORS[kind]
    if cls in (LearnedDifficultyEstimator, NeuralDifficultyEstimator):
        return cls(thresholds, seed=seed, **options)
    return cls(thresholds, **options)


__all__ = [
    "ESTIMATORS",
    "BaseDifficultyEstimator",
    "DifficultyThresholds",
    "TrainingExample",
    "build_difficulty_estimator",
    "cheapest_correct_tier",
    "tier_to_score",
]
