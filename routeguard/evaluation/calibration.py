"""Calibration and error-detection metrics.

Conventions: ``confidence`` is the system's estimate that an answer is correct;
``correct`` is the gold outcome. For *error detection* the positive class is an
**incorrect** answer and the detector score is ``1 - confidence``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float


def reliability_bins(
    confidence: np.ndarray,
    correct: np.ndarray,
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Equal-width bins over [0, 1] (the standard reliability-diagram construction)."""
    confidence = np.clip(np.asarray(confidence, dtype=float), 0.0, 1.0)
    correct = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(confidence, edges[1:-1], right=True), 0, n_bins - 1)
    bins = []
    for b in range(n_bins):
        mask = idx == b
        n = int(mask.sum())
        bins.append(
            ReliabilityBin(
                float(edges[b]),
                float(edges[b + 1]),
                n,
                float(confidence[mask].mean()) if n else float("nan"),
                float(correct[mask].mean()) if n else float("nan"),
            )
        )
    return bins


def expected_calibration_error(
    confidence: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> float:
    """ECE with equal-width bins (Naeini et al., 2015; Guo et al., 2017)."""
    n = len(confidence)
    if n == 0:
        return float("nan")
    return float(
        sum(
            b.count / n * abs(b.accuracy - b.mean_confidence)
            for b in reliability_bins(confidence, correct, n_bins)
            if b.count
        )
    )


def brier_score(confidence: np.ndarray, correct: np.ndarray) -> float:
    if len(confidence) == 0:
        return float("nan")
    c = np.clip(np.asarray(confidence, dtype=float), 0.0, 1.0)
    return float(np.mean((c - np.asarray(correct, dtype=float)) ** 2))


def error_detection_auroc(confidence: np.ndarray, correct: np.ndarray) -> float:
    """AUROC of ``1 - confidence`` for detecting incorrect answers (NaN if one class only)."""
    from sklearn.metrics import roc_auc_score

    wrong = ~np.asarray(correct, dtype=bool)
    if wrong.all() or not wrong.any():
        return float("nan")
    return float(roc_auc_score(wrong, 1.0 - np.asarray(confidence, dtype=float)))


def error_detection_auprc(confidence: np.ndarray, correct: np.ndarray) -> float:
    """Average precision for detecting incorrect answers. Chance level = error rate."""
    from sklearn.metrics import average_precision_score

    wrong = ~np.asarray(correct, dtype=bool)
    if wrong.all() or not wrong.any():
        return float("nan")
    return float(average_precision_score(wrong, 1.0 - np.asarray(confidence, dtype=float)))


def risk_coverage_curve(
    confidence: np.ndarray,
    correct: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Selective risk (error rate among accepted) as coverage grows, most-confident first."""
    order = np.argsort(-np.asarray(confidence, dtype=float), kind="stable")
    errors = (~np.asarray(correct, dtype=bool))[order].astype(float)
    n = np.arange(1, len(order) + 1)
    return n / len(order), np.cumsum(errors) / n


def aurc(confidence: np.ndarray, correct: np.ndarray) -> float:
    """Area under the risk-coverage curve (lower is better; Geifman et al., 2019)."""
    if len(confidence) == 0:
        return float("nan")
    _, risk = risk_coverage_curve(confidence, correct)
    return float(risk.mean())


def calibration_summary(
    confidence: np.ndarray,
    correct: np.ndarray,
    n_bins: int = 10,
) -> dict[str, float]:
    confidence = np.asarray(confidence, dtype=float)
    correct = np.asarray(correct, dtype=bool)
    return {
        "ece": expected_calibration_error(confidence, correct, n_bins),
        "brier": brier_score(confidence, correct),
        "auroc_error_detection": error_detection_auroc(confidence, correct),
        "auprc_error_detection": error_detection_auprc(confidence, correct),
        "aurc": aurc(confidence, correct),
        "error_rate": float(1 - correct.mean()) if len(correct) else float("nan"),
        "n": float(len(correct)),
    }
