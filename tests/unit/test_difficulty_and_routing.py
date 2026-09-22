import random

import numpy as np
import pytest

from routeguard.analysis import LanguageDetector, QueryAnalyzer, build_task_classifier
from routeguard.complexity import (
    DifficultyThresholds,
    TrainingExample,
    build_difficulty_estimator,
    cheapest_correct_tier,
)
from routeguard.context import CallContext
from routeguard.models import ModelPool, ModelSpec
from routeguard.router import build_router
from routeguard.router.oracle import OracleRouter, oracle_tier
from routeguard.types import AnswerType, DifficultyEstimate, DifficultyLabel, Query
from tests.conftest import sim_models

ANALYZER = QueryAnalyzer(LanguageDetector(), build_task_classifier("rules"))


def _estimate(score: float) -> DifficultyEstimate:
    return DifficultyEstimate(score, DifficultyThresholds().label(score), "test")


def test_thresholds_and_targets():
    th = DifficultyThresholds(0.3, 0.7)
    assert [th.label(x) for x in (0.1, 0.5, 0.9)] == [
        DifficultyLabel.EASY,
        DifficultyLabel.MEDIUM,
        DifficultyLabel.HARD,
    ]
    order = ["s", "m", "l"]
    assert cheapest_correct_tier({"s": False, "m": True, "l": True}, order) == 1
    assert cheapest_correct_tier({"s": False, "m": False, "l": False}, order) == 3
    assert oracle_tier({"s": False, "m": False, "l": False}, order) == 0


def test_heuristic_difficulty_orders_simple_before_complex(sim_pool):
    est = build_difficulty_estimator("heuristic", DifficultyThresholds(), {})
    easy = Query(text="Capital of France?")
    hard = Query(
        text=(
            "Prove step by step that for every integer n >= 1 the sum 1 + 2 + ... + n "
            "equals n(n+1)/2, then explain why the formula must hold exactly for all "
            "n and compare it with the sum of squares."
        ),
        answer_type=AnswerType.TEXT,
    )
    s_easy = est.estimate(easy, ANALYZER.analyze(easy), CallContext(sim_pool, easy)).score
    s_hard = est.estimate(hard, ANALYZER.analyze(hard), CallContext(sim_pool, hard)).score
    assert 0 <= s_easy < s_hard <= 1


def _examples(n: int = 120, seed: int = 0) -> list[TrainingExample]:
    """Synthetic data: short questions are solved by the small model, long ones only by large."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        hard = i % 2 == 0
        words = " ".join(
            rng.choice(["alpha", "beta", "gamma", "delta"]) for _ in range(40 if hard else 3)
        )
        q = Query(text=f"Question {i}: {words}?", id=f"t{i}")
        outcomes = {"small": not hard, "medium": not hard, "large": True}
        out.append(
            TrainingExample(
                q,
                ANALYZER.analyze(q),
                outcomes,
                latency={"small": 0.1, "medium": 0.3, "large": 1.0},
            )
        )
    return out


@pytest.mark.parametrize("kind", ["learned", "neural"])
def test_learned_difficulty_estimators_learn_the_signal(kind, sim_pool):
    est = build_difficulty_estimator(kind, DifficultyThresholds(), {}, seed=0)
    with pytest.raises(RuntimeError):
        est.estimate(
            Query(text="x"),
            ANALYZER.analyze(Query(text="x")),
            CallContext(sim_pool, Query(text="x")),
        )
    est.fit(_examples(), sim_pool.names)
    held_out = _examples(40, seed=1)  # same distribution, unseen queries
    scores = [
        est.estimate(e.query, e.analysis, CallContext(sim_pool, e.query)).score for e in held_out
    ]
    hard = [s for s, e in zip(scores, held_out, strict=True) if not e.outcomes["small"]]
    easy = [s for s, e in zip(scores, held_out, strict=True) if e.outcomes["small"]]
    assert np.mean(easy) < np.mean(hard)


def test_llm_judge_difficulty_is_charged(sim_pool):
    est = build_difficulty_estimator("llm_judge", DifficultyThresholds(), {})
    q = Query(text="What is 2+2?", id="j", reference={"id": "j", "answer": "4", "difficulty": 0.9})
    ctx = CallContext(sim_pool, q)
    d = est.estimate(q, ANALYZER.analyze(q), ctx)
    assert 0 <= d.score <= 1 and d.details["judge"] == "small"
    assert [c.purpose for c in ctx.calls] == ["difficulty_judge"]


def test_simple_routers(sim_pool):
    q = Query(text="hello", id="r1")
    a = ANALYZER.analyze(q)
    ctx = CallContext(sim_pool, q)
    assert (
        build_router("fixed", sim_pool, {"model": "medium"}).route(q, a, _estimate(0.9), ctx).model
        == "medium"
    )
    with pytest.raises(KeyError):
        build_router("fixed", sim_pool, {"model": "nope"})
    r1 = build_router("random", sim_pool, {}, seed=1)
    assert r1.route(q, a, _estimate(0.5), ctx).model == r1.route(q, a, _estimate(0.5), ctx).model
    rules = build_router("rules", sim_pool, {})
    assert rules.route(q, a, _estimate(0.9), ctx).model == "large"  # hard -> strongest
    assert rules.route(q, a, _estimate(0.1), ctx).model == "small"  # default cheapest
    with pytest.raises(ValueError):
        build_router(
            "rules", sim_pool, {"rules": [{"when": {"colour": ["red"]}, "model": "small"}]}
        )


def test_threshold_router_supports_n_models():
    pool = ModelPool([ModelSpec(**m) for m in sim_models((0.2, 0.4, 0.6, 0.8, 0.9))])
    router = build_router("threshold", pool, {})
    q = Query(text="x")
    a = ANALYZER.analyze(q)
    picks = [
        router.route(q, a, _estimate(s), CallContext(pool, q)).model
        for s in (0.05, 0.3, 0.5, 0.7, 0.95)
    ]
    assert picks == pool.names
    with pytest.raises(ValueError):
        build_router("threshold", pool, {"thresholds": [0.5]})


@pytest.mark.parametrize(
    "kind,opts",
    [("learned", {}), ("cost_aware", {"target": 0.6}), ("quality_cost", {"cost_weight": 0.2})],
)
def test_learned_routers_send_easy_to_small_and_hard_to_large(kind, opts, sim_pool):
    router = build_router(kind, sim_pool, opts, seed=0)
    q = Query(text="x")
    with pytest.raises(RuntimeError):
        router.route(q, ANALYZER.analyze(q), _estimate(0.5), CallContext(sim_pool, q))
    router.fit(_examples())
    held_out = _examples(20, seed=1)
    tiers = {True: [], False: []}
    for e in held_out:
        m = router.route(e.query, e.analysis, _estimate(0.0), CallContext(sim_pool, e.query)).model
        tiers[e.outcomes["small"]].append(sim_pool.tier(m))
    assert np.mean(tiers[True]) < np.mean(tiers[False])


def test_quality_cost_lambda_trades_quality_for_cost(sim_pool):
    cheap = build_router("quality_cost", sim_pool, {"cost_weight": 5.0}, seed=0)
    cheap.fit(_examples())
    hard = next(e for e in _examples(10, seed=1) if not e.outcomes["small"])
    ctx = CallContext(sim_pool, hard.query)
    assert cheap.route(hard.query, hard.analysis, _estimate(0), ctx).model == "small"


def test_oracle_router(sim_pool):
    router = OracleRouter(sim_pool)
    assert not router.deployable
    q = Query(text="x", id="o1")
    router.set_outcomes({"o1": {"small": False, "medium": True, "large": True}})
    assert (
        router.route(q, ANALYZER.analyze(q), _estimate(0), CallContext(sim_pool, q)).model
        == "medium"
    )
    with pytest.raises(KeyError):
        router.route(
            Query(text="y", id="zz"), ANALYZER.analyze(q), _estimate(0), CallContext(sim_pool, q)
        )


def test_learned_router_records_training_ids(sim_pool):
    router = build_router("learned", sim_pool, {}, seed=0)
    ex = _examples(40)
    router.fit(ex)
    assert router.trained_ids == {e.query.id for e in ex}
    assert np.isfinite(len(router.trained_ids))


def test_router_is_trained_on_out_of_fold_difficulty_scores():
    from routeguard.pipeline import RouteGuardPipeline
    from tests.conftest import make_config

    pipe = RouteGuardPipeline(
        make_config(difficulty={"estimator": "learned"}, router={"type": "cost_aware"})
    )
    examples = _examples(60)
    pipe.fit_difficulty_and_router(examples)
    in_sample = [
        pipe.difficulty.estimate(e.query, e.analysis, pipe.context(e.query)).score for e in examples
    ]
    oof = [e.difficulty for e in examples]
    assert oof != in_sample  # router features come from held-out folds, not the final estimator
    assert all(0.0 <= s <= 1.0 for s in oof)
