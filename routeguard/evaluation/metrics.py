"""System-level metrics computed from evaluation records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import numpy as np

from routeguard.evaluation.calibration import calibration_summary

Record = dict[str, Any]


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else float("nan")


def _rate(flags: Sequence[bool]) -> float:
    return float(np.mean(flags)) if len(flags) else float("nan")


def quality_metrics(records: Sequence[Record]) -> dict[str, float]:
    by_lang: dict[str, list[bool]] = defaultdict(list)
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        by_lang[r["language_variant"]].append(r["correct"])
        by_cat[r["category"]].append(r["correct"])
    text = [r for r in records if r["answer_type"] == "text"]
    return {
        "accuracy": _rate([r["correct"] for r in records]),
        "initial_accuracy": _rate([r["initial_correct"] for r in records]),
        "exact_match": _mean([r["exact_match"] for r in records]),
        "f1": _mean([r["f1"] for r in records]),
        "text_f1": _mean([r["f1"] for r in text]) if text else float("nan"),
        "macro_accuracy_language": _mean([_rate(v) for v in by_lang.values()]),
        "macro_accuracy_category": _mean([_rate(v) for v in by_cat.values()]),
        "extraction_failure_rate": _rate([r["extraction_failed"] for r in records]),
        "n": float(len(records)),
    }


def efficiency_metrics(records: Sequence[Record]) -> dict[str, float]:
    lat = np.array([r["latency_s"] for r in records], dtype=float)
    total_lat = float(lat.sum())
    return {
        "latency_mean_s": float(lat.mean()) if len(lat) else float("nan"),
        "latency_p50_s": float(np.percentile(lat, 50)) if len(lat) else float("nan"),
        "latency_p95_s": float(np.percentile(lat, 95)) if len(lat) else float("nan"),
        "input_tokens_mean": _mean([r["input_tokens"] for r in records]),
        "output_tokens_mean": _mean([r["output_tokens"] for r in records]),
        "tokens_total": float(sum(r["input_tokens"] + r["output_tokens"] for r in records)),
        "cost_usd_mean": _mean([r["cost_usd"] for r in records]),
        "cost_usd_total": float(sum(r["cost_usd"] for r in records)),
        "tflops_mean": _mean([r["tflops"] for r in records]),
        "calls_mean": _mean([r["n_calls"] for r in records]),
        "throughput_qps": len(records) / total_lat if total_lat > 0 else float("nan"),
    }


def routing_metrics(records: Sequence[Record], n_models: int) -> dict[str, float]:
    """Requires per-model outcomes (``model_outcomes`` in each record)."""
    rs = [r for r in records if "oracle_tier" in r]
    if not rs:
        return {}
    unnecessary, under, exact = [], [], []
    for r in rs:
        routed, oracle = r["routed_tier"], r["oracle_tier"]
        outcomes, order = r["model_outcomes"], r["model_order"]
        exact.append(routed == oracle)
        # A larger model was used although a cheaper one would have been correct (or none is).
        unnecessary.append(routed > oracle)
        # The routed model failed although a stronger model would have succeeded.
        stronger_ok = any(outcomes[m] for m in order[routed + 1 :])
        under.append(not outcomes[order[routed]] and stronger_ok)
    tiers = np.array([r["routed_tier"] for r in rs])
    out = {
        "routing_accuracy": _rate(exact),
        "unnecessary_large_model_rate": _rate(unnecessary),
        "incorrect_small_model_rate": _rate(under),
        "oracle_accuracy": _rate([r["any_model_correct"] for r in rs]),
    }
    for t in range(n_models):
        out[f"share_tier_{t}"] = float((tiers == t).mean())
    return out


def escalation_metrics(records: Sequence[Record]) -> dict[str, float]:
    esc = [r for r in records if r["escalated"]]
    init_wrong = [r for r in records if not r["initial_correct"]]
    init_right = [r for r in records if r["initial_correct"]]
    esc_wrong = [r for r in esc if not r["initial_correct"]]
    esc_right = [r for r in esc if r["initial_correct"]]
    return {
        "escalation_rate": _rate([r["escalated"] for r in records]),
        "escalation_success_rate": _rate([r["correct"] for r in esc]),
        "escalation_precision": _rate([not r["initial_correct"] for r in esc]),
        "escalation_recall": _rate([r["escalated"] for r in init_wrong]),
        "corrected_rate": _rate([r["correct"] for r in esc_wrong]),
        "harmed_rate": _rate([not r["correct"] for r in esc_right]),
        "initial_errors_corrected": _rate([r["correct"] for r in init_wrong]),
        "initial_correct_broken": _rate([not r["correct"] for r in init_right]),
        "escalation_cost_share": (
            sum(r["escalation_cost_usd"] for r in records)
            / max(1e-12, sum(r["cost_usd"] for r in records))
            if any(r["cost_usd"] for r in records)
            else sum(r["escalation_tflops"] for r in records)
            / max(1e-12, sum(r["tflops"] for r in records))
        ),
        "escalation_latency_mean_s": _mean([r["escalation_latency_s"] for r in records]),
        "stages_mean": _mean([r["n_stages"] for r in records]),
    }


def reliability_metrics(records: Sequence[Record]) -> dict[str, float]:
    """Confidence quality of the *initial* attempt (the signal escalation acts on)."""
    rs = [r for r in records if r["attempts"][0]["confidence"] is not None]
    if not rs:
        return {}
    conf = np.array([r["attempts"][0]["confidence"] for r in rs], dtype=float)
    corr = np.array([r["initial_correct"] for r in rs], dtype=bool)
    out = calibration_summary(conf, corr)
    out["calibrated_fraction"] = _rate([r["attempts"][0]["calibrated"] for r in rs])
    verified = [r for r in records if r["attempts"][0]["verified"] is not None]
    if verified:
        passed = np.array([r["attempts"][0]["verified"] for r in verified], dtype=bool)
        ok = np.array([r["initial_correct"] for r in verified], dtype=bool)
        out["verifier_coverage"] = len(verified) / len(records)
        out["verifier_accuracy"] = float((passed == ok).mean())
        out["verifier_false_pass_rate"] = float((passed & ~ok).sum() / max(1, (~ok).sum()))
        out["verifier_false_fail_rate"] = float((~passed & ok).sum() / max(1, ok.sum()))
    return {f"rel_{k}": v for k, v in out.items()}


def acceptance_metrics(records: Sequence[Record]) -> dict[str, float]:
    """Realised risk of the acceptance rule on *initial* answers.

    An initial answer is accepted when its confidence did not fire ``low_confidence``.
    With risk control, ``accepted_error_rate`` is the test-time counterpart of the target
    risk alpha; exceeding alpha signals that the calibration data was not exchangeable with
    the answers the model actually receives (e.g. because of routing).
    """
    rs = [r for r in records if r["attempts"][0]["confidence"] is not None]
    if not rs:
        return {}
    accepted = [r for r in rs if "low_confidence" not in (r["attempts"][0]["triggers"] or [])]
    return {
        "acceptance_rate": len(accepted) / len(rs),
        "accepted_error_rate": _rate([not r["initial_correct"] for r in accepted]),
        "n_accepted": float(len(accepted)),
    }


def system_metrics(records: Sequence[Record], n_models: int) -> dict[str, float]:
    return {
        **quality_metrics(records),
        **efficiency_metrics(records),
        **routing_metrics(records, n_models),
        **escalation_metrics(records),
        **reliability_metrics(records),
    }


def routing_confusion(records: Sequence[Record], n_models: int) -> np.ndarray:
    """Rows: oracle tier; columns: routed tier."""
    m = np.zeros((n_models, n_models), dtype=int)
    for r in records:
        if "oracle_tier" in r:
            m[r["oracle_tier"], r["routed_tier"]] += 1
    return m
