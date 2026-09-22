"""Post-hoc calibration: raw confidence score -> estimated P(correct).

Calibrators are fitted on the **calibration split** (disjoint from both the
training split and the test split). Raw scores from different models live on
different scales, so a :class:`CalibrationBank` keeps one calibrator per model
and optionally per (model, language). Groups with too few examples or only one
outcome class fall back to the coarser group; this fallback is recorded so it can
be reported rather than hidden.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class Calibrator(Protocol):
    def fit(self, scores: np.ndarray, labels: np.ndarray) -> Calibrator: ...

    def predict(self, scores: np.ndarray) -> np.ndarray: ...


class IsotonicCalibrator:
    """Monotone, non-parametric (Zadrozny & Elkan, 2002)."""

    def __init__(self) -> None:
        from sklearn.isotonic import IsotonicRegression

        self.model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> IsotonicCalibrator:
        self.model.fit(scores, labels)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(scores), dtype=float)


class PlattCalibrator:
    """Logistic regression on the raw score (Platt, 1999)."""

    def __init__(self) -> None:
        from sklearn.linear_model import LogisticRegression

        self.model = LogisticRegression(C=1e4, max_iter=1000)

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> PlattCalibrator:
        self.model.fit(scores.reshape(-1, 1), labels)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict_proba(scores.reshape(-1, 1))[:, 1], dtype=float)


class HistogramCalibrator:
    """Equal-mass histogram binning with Beta(1, 1) smoothing."""

    def __init__(self, n_bins: int = 10) -> None:
        self.n_bins = n_bins
        self.edges = np.array([])
        self.values = np.array([])

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> HistogramCalibrator:
        qs = np.quantile(scores, np.linspace(0, 1, self.n_bins + 1))
        self.edges = np.unique(qs[1:-1])
        idx = np.searchsorted(self.edges, scores, side="right")
        k = len(self.edges) + 1
        pos = np.bincount(idx, weights=labels, minlength=k)
        tot = np.bincount(idx, minlength=k)
        self.values = (pos + 1) / (tot + 2)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        return np.asarray(
            self.values[np.searchsorted(self.edges, scores, side="right")], dtype=float
        )


class ConstantCalibrator:
    """Smoothed base rate; used when a group cannot support a real calibrator."""

    def __init__(self) -> None:
        self.rate = 0.5

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> ConstantCalibrator:
        self.rate = (float(labels.sum()) + 1) / (len(labels) + 2)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        return np.full(len(scores), self.rate)


CALIBRATORS: dict[str, type] = {
    "isotonic": IsotonicCalibrator,
    "platt": PlattCalibrator,
    "histogram": HistogramCalibrator,
}


@dataclass
class CalibrationRecord:
    model: str
    language: str
    raw: float
    correct: bool
    routed: bool = True  # would the router send this item to this model initially?


class CalibrationBank:
    def __init__(self, method: str = "isotonic", per_language: bool = False, min_samples: int = 30):
        if method not in CALIBRATORS:
            raise ValueError(
                f"Unknown calibration method '{method}'. Available: {sorted(CALIBRATORS)}"
            )
        self.method = method
        self.per_language = per_language
        self.min_samples = min_samples
        self.calibrators: dict[tuple[str, str | None], Calibrator] = {}
        self.fallbacks: list[str] = []

    def _fit_group(self, scores: np.ndarray, labels: np.ndarray) -> Calibrator | None:
        if len(scores) < self.min_samples:
            return None
        if labels.min() == labels.max():
            return ConstantCalibrator().fit(scores, labels)
        calibrator: Calibrator = CALIBRATORS[self.method]()
        return calibrator.fit(scores, labels)

    def fit(self, records: Sequence[CalibrationRecord]) -> CalibrationBank:
        groups: dict[tuple[str, str | None], list[CalibrationRecord]] = defaultdict(list)
        for r in records:
            groups[(r.model, None)].append(r)
            if self.per_language:
                groups[(r.model, r.language)].append(r)
        for key, rs in groups.items():
            scores = np.array([r.raw for r in rs], dtype=float)
            labels = np.array([r.correct for r in rs], dtype=float)
            cal = self._fit_group(scores, labels)
            if cal is None:
                if key[1] is None:
                    # Too little data even at model level: smoothed base rate, recorded.
                    cal = ConstantCalibrator().fit(scores, labels)
                    self.fallbacks.append(f"{key[0]}: constant (n={len(rs)})")
                else:
                    self.fallbacks.append(f"{key[0]}/{key[1]}: model-level (n={len(rs)})")
                    continue
            self.calibrators[key] = cal
        if self.fallbacks:
            logger.info("Calibration fallbacks: %s", "; ".join(self.fallbacks))
        return self

    def predict(self, model: str, language: str, raw: float) -> float | None:
        cal = self.calibrators.get((model, language)) if self.per_language else None
        cal = cal or self.calibrators.get((model, None))
        if cal is None:
            return None
        return float(cal.predict(np.array([raw], dtype=float))[0])
