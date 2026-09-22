import math

import numpy as np
import pytest

from routeguard.confidence import (
    CalibrationBank,
    CalibrationRecord,
    ConfidenceInput,
    MissingLogprobsError,
    build_confidence_estimator,
    risk_controlled_threshold,
)
from routeguard.confidence.calibration import (
    HistogramCalibrator,
    IsotonicCalibrator,
    PlattCalibrator,
)
from routeguard.confidence.consistency import cluster_answers
from routeguard.confidence.selective import clopper_pearson_upper
from routeguard.context import CallContext
from routeguard.prompts import build_messages
from routeguard.types import AnswerType, GenerationOutput, Query
from tests.conftest import numeric_query


def _inp(lps, tops=None, answer="4"):
    out = GenerationOutput(
        "Final answer: 4", "small", 10, len(lps or []), 0.1, token_logprobs=lps, top_logprobs=tops
    )
    q = Query(text="2+2?", answer_type=AnswerType.NUMERIC)
    return ConfidenceInput(q, "small", [], out, answer, AnswerType.NUMERIC)


def test_logprob_estimators_known_values(sim_pool):
    lps = [math.log(0.9), math.log(0.5)]
    ctx = CallContext(sim_pool, Query(text="x"))
    assert build_confidence_estimator("mean_token_prob").score(_inp(lps), ctx)[0] == pytest.approx(
        0.7
    )
    assert build_confidence_estimator("sequence_logprob").score(_inp(lps), ctx)[0] == pytest.approx(
        math.sqrt(0.45)
    )
    assert build_confidence_estimator("min_token_prob").score(_inp(lps), ctx)[0] == pytest.approx(
        0.5
    )


def test_entropy_estimator(sim_pool):
    ctx = CallContext(sim_pool, Query(text="x"))
    certain = [[0.0, -50.0, -50.0]]
    uniform = [[math.log(1 / 3)] * 3]
    est = build_confidence_estimator("entropy")
    assert est.score(_inp([0.0], certain), ctx)[0] == pytest.approx(1.0, abs=1e-6)
    assert est.score(_inp([0.0], uniform), ctx)[0] == pytest.approx(0.0, abs=1e-6)


def test_missing_logprobs_raise_instead_of_guessing(sim_pool):
    ctx = CallContext(sim_pool, Query(text="x"))
    with pytest.raises(MissingLogprobsError):
        build_confidence_estimator("mean_token_prob").score(_inp(None), ctx)


def test_sampling_estimators_charge_their_samples(sim_pool):
    q = numeric_query(difficulty=0.1)
    ctx = CallContext(sim_pool, q)
    msgs = build_messages(q, "math")
    out = ctx.generate("large", msgs, "initial")
    inp = ConfidenceInput(q, "large", msgs, out, "19", AnswerType.NUMERIC)
    sc, details = build_confidence_estimator("self_consistency", {"n_samples": 4}).score(inp, ctx)
    assert 0 <= sc <= 1 and len(details["samples"]) == 4
    se, _ = build_confidence_estimator("semantic_entropy", {"n_samples": 4}).score(inp, ctx)
    assert 0 <= se <= 1
    assert sum(c.purpose == "confidence_sample" for c in ctx.calls) == 8
    ens = build_confidence_estimator(
        "ensemble",
        {
            "components": [
                {"method": "mean_token_prob"},
                {"method": "self_consistency", "options": {"n_samples": 2}},
            ]
        },
    )
    assert 0 <= ens.score(inp, ctx)[0] <= 1
    with pytest.raises(ValueError):
        build_confidence_estimator("nope")


def test_cluster_answers():
    assert cluster_answers(["19", "19.0", "20", None, None], AnswerType.NUMERIC) == [0, 0, 1, 2, 3]
    assert cluster_answers(["Paris, France", "paris france", "Rome"], AnswerType.TEXT) == [0, 0, 1]


@pytest.mark.parametrize("cls", [IsotonicCalibrator, PlattCalibrator, HistogramCalibrator])
def test_calibrators_are_bounded_and_increasing(cls):
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 400)
    labels = (rng.uniform(0, 1, 400) < raw**2).astype(float)
    cal = cls().fit(raw, labels)
    grid = np.linspace(0, 1, 50)
    pred = cal.predict(grid)
    assert np.all((pred >= 0) & (pred <= 1))
    assert pred[0] < pred[-1]
    if cls is not HistogramCalibrator:  # histogram binning is not monotone by construction
        assert np.all(np.diff(pred) >= -1e-9)


def test_calibration_bank_per_model_language_and_fallbacks():
    rng = np.random.default_rng(1)
    recs = []
    for _ in range(200):
        raw = float(rng.uniform())
        recs.append(CalibrationRecord("small", "en", raw, bool(rng.uniform() < raw)))
    for _ in range(5):  # too few Kazakh examples -> falls back to model level
        recs.append(CalibrationRecord("small", "kk", 0.5, True))
    for _ in range(3):  # too few examples for the whole model -> constant base rate
        recs.append(CalibrationRecord("large", "en", 0.9, True))
    bank = CalibrationBank("isotonic", per_language=True, min_samples=30).fit(recs)
    assert bank.predict("small", "kk", 0.9) == bank.predict("small", "zz", 0.9)
    assert bank.predict("large", "en", 0.1) == pytest.approx((3 + 1) / (3 + 2))
    assert any("large" in f for f in bank.fallbacks)
    assert bank.predict("missing", "en", 0.5) is None
    with pytest.raises(ValueError):
        CalibrationBank("magic")


def test_clopper_pearson():
    assert clopper_pearson_upper(0, 0, 0.1) == 1.0
    assert clopper_pearson_upper(5, 5, 0.1) == 1.0
    assert 0.0 < clopper_pearson_upper(0, 100, 0.1) < 0.03


def test_risk_controlled_threshold_meets_target_on_calibration_data():
    rng = np.random.default_rng(2)
    conf = rng.uniform(0, 1, 2000)
    correct = rng.uniform(0, 1, 2000) < conf
    res = risk_controlled_threshold(conf, correct, target_risk=0.1, delta=0.1)
    assert res.valid and res.risk_upper_bound <= 0.1
    accepted = conf >= res.threshold
    assert (~correct[accepted]).mean() <= 0.1
    impossible = risk_controlled_threshold(conf, np.zeros(2000, bool), target_risk=0.05)
    assert not impossible.valid and math.isinf(impossible.threshold)
