"""Confidence / uncertainty estimation."""

from __future__ import annotations

from typing import Any

from routeguard.confidence.base import BaseConfidenceEstimator, ConfidenceInput
from routeguard.confidence.calibration import CalibrationBank, CalibrationRecord
from routeguard.confidence.consistency import SelfConsistency, SemanticEntropy
from routeguard.confidence.logprob import (
    MeanTokenProb,
    MinTokenProb,
    MissingLogprobsError,
    SequenceLogProb,
    TokenEntropy,
)
from routeguard.confidence.selective import ThresholdResult, risk_controlled_threshold
from routeguard.context import CallContext


class EnsembleConfidence(BaseConfidenceEstimator):
    """Weighted mean of several estimators' raw scores (calibrate the result)."""

    name = "ensemble"

    def __init__(self, components: list[dict[str, Any]]):
        if not components:
            raise ValueError("ensemble confidence needs at least one component")
        self.members = [
            (
                build_confidence_estimator(c["method"], c.get("options", {})),
                float(c.get("weight", 1.0)),
            )
            for c in components
        ]

    def score(self, inp: ConfidenceInput, ctx: CallContext) -> tuple[float, dict]:
        parts = {}
        total, weight_sum = 0.0, 0.0
        for est, w in self.members:
            raw, _ = est.score(inp, ctx)
            parts[est.name] = raw
            total += w * raw
            weight_sum += w
        return total / weight_sum, {"components": parts}


ESTIMATORS: dict[str, type[BaseConfidenceEstimator]] = {
    "mean_token_prob": MeanTokenProb,
    "sequence_logprob": SequenceLogProb,
    "min_token_prob": MinTokenProb,
    "entropy": TokenEntropy,
    "self_consistency": SelfConsistency,
    "semantic_entropy": SemanticEntropy,
    "ensemble": EnsembleConfidence,
}


def build_confidence_estimator(
    method: str,
    options: dict[str, Any] | None = None,
) -> BaseConfidenceEstimator:
    if method not in ESTIMATORS:
        raise ValueError(f"Unknown confidence method '{method}'. Available: {sorted(ESTIMATORS)}")
    return ESTIMATORS[method](**(options or {}))


__all__ = [
    "ESTIMATORS",
    "BaseConfidenceEstimator",
    "CalibrationBank",
    "CalibrationRecord",
    "ConfidenceInput",
    "MissingLogprobsError",
    "ThresholdResult",
    "build_confidence_estimator",
    "risk_controlled_threshold",
]
