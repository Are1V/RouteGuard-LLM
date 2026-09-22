"""Risk-controlled acceptance thresholds (selective prediction).

Given calibration-split confidences and correctness, find the lowest threshold
``lambda`` such that, with probability at least ``1 - delta``, the error rate among
answers with confidence ``>= lambda`` is at most ``target_risk``.

For each candidate threshold the number of errors among accepted answers is
binomial, so a one-sided Clopper-Pearson upper bound is valid for that threshold
(cf. Geifman & El-Yaniv, 2017). Candidates are tested in a fixed order, from the
most to the least conservative, stopping at the first failure; fixed-sequence
testing controls the family-wise error rate without a multiplicity correction
(the "Learn then Test" framework, Angelopoulos et al., 2021).

The guarantee is marginal over queries exchangeable with the calibration split.
It does not hold under distribution shift, e.g. a language absent from calibration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import beta


@dataclass
class ThresholdResult:
    threshold: float
    coverage: float
    empirical_risk: float
    risk_upper_bound: float
    valid: bool
    n_calibration: int


def clopper_pearson_upper(errors: int, n: int, delta: float) -> float:
    if n == 0:
        return 1.0
    if errors >= n:
        return 1.0
    return float(beta.ppf(1 - delta, errors + 1, n - errors))


def risk_controlled_threshold(
    confidence: np.ndarray,
    correct: np.ndarray,
    target_risk: float,
    delta: float = 0.1,
    min_accepted: int = 10,
) -> ThresholdResult:
    confidence = np.asarray(confidence, dtype=float)
    correct = np.asarray(correct, dtype=bool)
    n = len(confidence)
    # The fixed sequence starts at the smallest coverage at which the target is attainable at
    # all (zero errors among n_acc answers gives a bound of 1 - delta**(1/n_acc)). The start
    # depends only on counts, never on labels, so the sequence remains fixed a priori.
    attainable = math.ceil(math.log(delta) / math.log(1 - target_risk))
    n_start = max(min_accepted, attainable)
    candidates = np.unique(confidence)[::-1]  # most conservative first
    best: ThresholdResult | None = None
    for lam in candidates:
        accepted = confidence >= lam
        n_acc = int(accepted.sum())
        if n_acc < n_start:
            continue
        errors = int((~correct[accepted]).sum())
        ucb = clopper_pearson_upper(errors, n_acc, delta)
        if ucb > target_risk:
            break
        best = ThresholdResult(float(lam), n_acc / n, errors / n_acc, ucb, True, n)
    if best is None:
        # No threshold certifiable: accept nothing (everything is escalated).
        return ThresholdResult(float("inf"), 0.0, 0.0, 1.0, False, n)
    return best
