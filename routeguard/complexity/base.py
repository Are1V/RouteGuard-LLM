"""Difficulty-estimator interface and difficulty-target definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from routeguard.context import CallContext
from routeguard.types import DifficultyEstimate, DifficultyLabel, Query, QueryAnalysis


@dataclass(frozen=True)
class DifficultyThresholds:
    """Maps a continuous score in [0, 1] to Easy / Medium / Hard."""

    easy_below: float = 0.34
    hard_above: float = 0.67

    def label(self, score: float) -> DifficultyLabel:
        if score < self.easy_below:
            return DifficultyLabel.EASY
        if score > self.hard_above:
            return DifficultyLabel.HARD
        return DifficultyLabel.MEDIUM


def cheapest_correct_tier(outcomes: Mapping[str, bool], model_order: Sequence[str]) -> int:
    """Index of the cheapest model that answered correctly; ``len(model_order)`` if none did.

    This is the empirical difficulty target used to train learned estimators and
    routers, and the "oracle tier" used to score routing decisions.
    """
    for tier, name in enumerate(model_order):
        if outcomes.get(name):
            return tier
    return len(model_order)


def tier_to_score(tier: int, n_models: int) -> float:
    return tier / n_models if n_models else 0.0


@dataclass
class TrainingExample:
    """One training-split query with its analysis and per-model correctness.

    ``difficulty`` is the score of the system's *own* difficulty estimator on this
    query (filled in before routers are fitted), and ``latency`` the measured
    per-model latency, used by latency-aware routers.
    """

    query: Query
    analysis: QueryAnalysis
    outcomes: dict[str, bool]
    latency: dict[str, float] = field(default_factory=dict)
    difficulty: float = 0.0


class BaseDifficultyEstimator(ABC):
    name: str = "base"
    requires_fit: bool = False

    def __init__(self, thresholds: DifficultyThresholds | None = None):
        self.thresholds = thresholds or DifficultyThresholds()

    def fit(  # noqa: B027 - intentional no-op hook for unsupervised estimators
        self, examples: Sequence[TrainingExample], model_order: Sequence[str]
    ) -> None:
        """Fit on training-split examples. No-op for unsupervised estimators."""

    @abstractmethod
    def score(self, query: Query, analysis: QueryAnalysis, ctx: CallContext) -> tuple[float, dict]:
        """Return a difficulty score in [0, 1] and optional details."""

    def estimate(
        self, query: Query, analysis: QueryAnalysis, ctx: CallContext
    ) -> DifficultyEstimate:
        value, details = self.score(query, analysis, ctx)
        value = min(1.0, max(0.0, value))
        return DifficultyEstimate(value, self.thresholds.label(value), self.name, details)
