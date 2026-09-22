"""Statistical utilities: seed aggregation, bootstrap intervals, paired tests.

Seeds change the train/calibration/test partition and the sampling seeds, so
the seed standard deviation reflects both split and sampling variability.
Paired comparisons between systems use the *same* test items, which removes
item-difficulty variance from the comparison.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy.stats import binom


def mean_std(values: Sequence[float]) -> dict[str, float]:
    arr = np.array([v for v in values if not (isinstance(v, float) and math.isnan(v))], dtype=float)
    if len(arr) == 0:
        return {"mean": float("nan"), "std": float("nan"), "n": 0.0}
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    return {"mean": float(arr.mean()), "std": std, "n": float(len(arr))}


def aggregate_seeds(per_seed: dict[int, dict[str, float]]) -> dict[str, dict[str, float]]:
    metrics = sorted({k for m in per_seed.values() for k in m})
    return {k: mean_std([m[k] for m in per_seed.values() if k in m]) for k in metrics}


def paired_bootstrap(
    a: np.ndarray,
    b: np.ndarray,
    n_boot: int = 5000,
    seed: int = 0,
) -> dict[str, float]:
    """Mean difference ``a - b`` over paired items with a percentile CI and a two-sided
    bootstrap p-value (proportion of resampled differences on the other side of 0)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError("paired_bootstrap needs equally long arrays")
    diff = a - b
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    boots = diff[idx].mean(axis=1)
    observed = float(diff.mean())
    p = 2 * min((boots <= 0).mean(), (boots >= 0).mean())
    return {
        "diff": observed,
        "ci_low": float(np.quantile(boots, 0.025)),
        "ci_high": float(np.quantile(boots, 0.975)),
        "p_value": float(min(1.0, p)),
        "n": float(len(diff)),
    }


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> float:
    """Exact McNemar test on paired binary outcomes (two-sided p-value)."""
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    n01 = int((a & ~b).sum())
    n10 = int((~a & b).sum())
    n = n01 + n10
    if n == 0:
        return 1.0
    return float(min(1.0, 2 * binom.cdf(min(n01, n10), n, 0.5)))
