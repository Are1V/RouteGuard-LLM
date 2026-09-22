import math

import numpy as np
import pytest

from routeguard.evaluation.calibration import (
    aurc,
    brier_score,
    error_detection_auprc,
    error_detection_auroc,
    expected_calibration_error,
    reliability_bins,
)
from routeguard.evaluation.errors import analyze_errors, label_record
from routeguard.evaluation.metrics import (
    escalation_metrics,
    quality_metrics,
    routing_confusion,
    routing_metrics,
)
from routeguard.evaluation.stats import (
    aggregate_seeds,
    mcnemar_exact,
    paired_bootstrap,
)
from routeguard.evaluation.tables import MeanStd, Table


def test_calibration_metrics_hand_computed():
    conf = np.array([0.9, 0.9, 0.1, 0.1])
    correct = np.array([True, False, False, False])
    # bins: 0.9 bin -> acc 0.5 (gap 0.4, weight .5); 0.1 bin -> acc 0 (gap .1, weight .5)
    assert expected_calibration_error(conf, correct) == pytest.approx(0.25)
    assert brier_score(conf, correct) == pytest.approx((0.01 + 0.81 + 0.01 + 0.01) / 4)
    assert sum(b.count for b in reliability_bins(conf, correct)) == 4
    perfect = np.array([0.9, 0.8, 0.2, 0.1])
    labels = np.array([True, True, False, False])
    assert error_detection_auroc(perfect, labels) == 1.0
    assert error_detection_auprc(perfect, labels) == pytest.approx(1.0)
    assert math.isnan(error_detection_auroc(perfect, np.ones(4, bool)))
    assert aurc(perfect, labels) < aurc(1 - perfect, labels)


def _rec(
    system="s",
    seed=0,
    correct=True,
    initial=True,
    routed=0,
    outcomes=(True, True, True),
    escalated=False,
    lang="en",
    pid=None,
    conf=0.9,
    verified=None,
    triggers=(),
):
    order = ["small", "medium", "large"]
    return {
        "system": system,
        "seed": seed,
        "item_id": f"i{pid}{lang}",
        "language": lang,
        "language_variant": lang,
        "category": "math",
        "answer_type": "numeric",
        "parallel_id": pid,
        "correct": correct,
        "initial_correct": initial,
        "exact_match": float(correct),
        "f1": float(correct),
        "extraction_failed": False,
        "routed_tier": routed,
        "model_order": order,
        "model_outcomes": dict(zip(order, outcomes, strict=True)),
        "oracle_tier": next((i for i, o in enumerate(outcomes) if o), 0),
        "any_model_correct": any(outcomes),
        "escalated": escalated,
        "n_stages": int(escalated),
        "cost_usd": 0.0,
        "tflops": 1.0,
        "escalation_cost_usd": 0.0,
        "escalation_tflops": 0.5 if escalated else 0.0,
        "escalation_latency_s": 0.0,
        "final_answer": "1",
        "gold": "1",
        "attempts": [
            {
                "stage": "initial",
                "correct": initial,
                "confidence": conf,
                "verified": verified,
                "triggers": list(triggers),
                "calibrated": True,
                "answer": "1",
                "info": {},
            }
        ]
        + (
            [
                {
                    "stage": "stronger_model",
                    "correct": correct,
                    "confidence": 0.9,
                    "verified": verified,
                    "triggers": [],
                    "calibrated": True,
                    "answer": "1",
                    "info": {},
                }
            ]
            if escalated
            else []
        ),
    }


def test_routing_metrics():
    recs = [
        _rec(routed=0, outcomes=(True, True, True)),  # optimal
        _rec(routed=2, outcomes=(True, True, True)),  # unnecessary large
        _rec(routed=0, outcomes=(False, True, True), correct=False),  # incorrect small routing
        _rec(
            routed=1, outcomes=(False, False, False), correct=False
        ),  # none correct -> tier 0 optimal
    ]
    m = routing_metrics(recs, 3)
    assert m["routing_accuracy"] == pytest.approx(0.25)
    assert m["unnecessary_large_model_rate"] == pytest.approx(0.5)
    assert m["incorrect_small_model_rate"] == pytest.approx(0.25)
    assert m["oracle_accuracy"] == pytest.approx(0.75)
    cm = routing_confusion(recs, 3)
    assert cm.sum() == 4 and cm[1, 0] == 1


def test_escalation_and_quality_metrics():
    recs = [
        _rec(initial=False, correct=True, escalated=True),  # corrected
        _rec(initial=True, correct=False, escalated=True),  # harmed
        _rec(initial=False, correct=False, escalated=False),  # missed
        _rec(initial=True, correct=True, escalated=False),
    ]
    e = escalation_metrics(recs)
    assert e["escalation_rate"] == 0.5
    assert e["corrected_rate"] == 1.0 and e["harmed_rate"] == 1.0
    assert e["escalation_recall"] == 0.5 and e["escalation_precision"] == 0.5
    assert e["initial_errors_corrected"] == 0.5
    q = quality_metrics(recs)
    assert q["accuracy"] == 0.5 and q["initial_accuracy"] == 0.5


def test_error_labels():
    english = _rec(lang="en", pid="p1", correct=True)
    kazakh = _rec(
        lang="kk",
        pid="p1",
        correct=False,
        initial=False,
        routed=0,
        outcomes=(False, True, True),
        conf=0.95,
        verified=True,
    )
    labels = label_record(kazakh, {("s", 0, "p1"): True})
    assert {
        "incorrect_routing",
        "high_confidence_wrong",
        "verifier_false_pass",
        "language_related_failure",
    } <= set(labels)
    fixed_but_flagged = _rec(initial=True, correct=True, triggers=("low_confidence",))
    assert "low_confidence_correct" in label_record(fixed_but_flagged, {})
    none = _rec(correct=False, initial=False, outcomes=(False, False, False))
    assert "model_capability_failure" in label_record(none, {})
    report = analyze_errors([english, kazakh])
    assert report["n_wrong"]["s"] == 1 and report["per_language"]["kk"]["incorrect_routing"] == 1


def test_stats():
    agg = aggregate_seeds({0: {"a": 0.5}, 1: {"a": 0.7}})
    assert agg["a"]["mean"] == pytest.approx(0.6) and agg["a"]["std"] == pytest.approx(0.1414, 1e-3)
    a = np.array([1] * 30 + [0] * 70, dtype=float)
    b = np.zeros(100)
    res = paired_bootstrap(a, b)
    assert res["diff"] == pytest.approx(0.3) and res["p_value"] < 0.01 and res["ci_low"] > 0
    assert mcnemar_exact(a.astype(bool), b.astype(bool)) < 1e-6
    assert mcnemar_exact(a.astype(bool), a.astype(bool)) == 1.0
    with pytest.raises(ValueError):
        paired_bootstrap(a, b[:3])


def test_table_renderers(tmp_path):
    t = Table("t", "Caption with 50% & more_stuff", ["System", "Acc"], note="note")
    t.add("routeguard_full", MeanStd(0.812, 0.021, 3, percent=True))
    t.add("x", float("nan"))
    md, csv_text, tex = t.to_markdown(), t.to_csv(), t.to_latex()
    assert "81.2 ± 2.1" in md and "| x | – |" in md
    assert "81.2 ± 2.1" in csv_text
    assert "81.2 $\\pm$ 2.1" in tex and "50\\% \\& more\\_stuff" in tex and "\\toprule" in tex
    with pytest.raises(ValueError):
        t.add("too", "many", "values")
    t.save(tmp_path)
    assert {p.suffix for p in tmp_path.iterdir()} == {".md", ".csv", ".tex"}


def test_mixture_frontier_and_gaps():
    from routeguard.evaluation.report import mixture_frontier, mixture_gaps

    # (cost, accuracy): the middle point lies below the chord and is not on the hull.
    front = mixture_frontier([(1.0, 0.5), (2.0, 0.55), (4.0, 0.8)])
    assert front == [(1.0, 0.5), (4.0, 0.8)]
    summary = {
        "small": {
            "group": "baseline",
            "fixed_model": "s",
            "per_seed": {0: {"tflops_mean": 1.0, "accuracy": 0.5}},
        },
        "large": {
            "group": "baseline",
            "fixed_model": "l",
            "per_seed": {0: {"tflops_mean": 4.0, "accuracy": 0.8}},
        },
        "router": {
            "group": "routeguard",
            "fixed_model": None,
            "per_seed": {0: {"tflops_mean": 2.5, "accuracy": 0.70}},
        },
    }
    gaps = mixture_gaps(summary, "tflops_mean")
    assert gaps["router"]["mean"] == pytest.approx(5.0)  # 0.70 vs mixture 0.65 at cost 2.5
    assert gaps["small"]["mean"] == pytest.approx(0.0)


def test_acceptance_metrics():
    from routeguard.evaluation.metrics import acceptance_metrics

    recs = [
        _rec(correct=True, initial=True),
        _rec(correct=False, initial=False),
        _rec(initial=False, correct=False, triggers=("low_confidence",)),
    ]
    m = acceptance_metrics(recs)
    assert m["acceptance_rate"] == pytest.approx(2 / 3)
    assert m["accepted_error_rate"] == pytest.approx(0.5)
