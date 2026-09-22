import json

import pytest

from routeguard.config import EscalationConfig
from routeguard.escalation import EscalationPolicy, build_stage
from routeguard.pipeline import RouteGuardPipeline
from routeguard.types import (
    Attempt,
    ConfidenceResult,
    DifficultyEstimate,
    DifficultyLabel,
    VerificationResult,
)
from tests.conftest import make_config, numeric_query


def _attempt(model="small", conf=0.9, verified=True, answer="1"):
    return Attempt(
        "initial", model, "", answer, ConfidenceResult(conf, "m"), VerificationResult(verified, "v")
    )


def test_policy_triggers():
    policy = EscalationPolicy(
        EscalationConfig.model_validate(
            {"triggers": {"confidence_below": 0.5, "difficulty_above": 0.8}}
        ),
        "large",
    )
    hard = DifficultyEstimate(0.9, DifficultyLabel.HARD, "h")
    assert policy.triggers(_attempt(conf=0.9), None, True) == []
    assert policy.triggers(_attempt(conf=0.2), None, True) == ["low_confidence"]
    assert policy.triggers(_attempt(verified=False), None, True) == ["verification_failed"]
    assert policy.triggers(_attempt(), hard, True) == ["high_difficulty"]
    assert policy.triggers(_attempt(model="large"), hard, True) == []
    assert policy.triggers(_attempt(), hard, False) == []  # difficulty only gates the first attempt


def test_select_final():
    cfg = EscalationConfig.model_validate({"final_selection": "most_confident"})
    policy = EscalationPolicy(cfg, "large")
    a, b = _attempt(conf=0.8, answer="a"), _attempt(conf=0.3, answer="b")
    assert policy.select_final([a, b]).answer == "a"
    b.reliable = True
    assert policy.select_final([a, b]).answer == "b"
    last = EscalationPolicy(EscalationConfig(), "large")
    assert last.select_final([_attempt(answer="x"), _attempt(answer=None)]).answer == "x"


def test_pipeline_escalates_until_reliable_and_accounts_every_call():
    cfg = make_config(
        escalation={
            "triggers": {"confidence_below": 1.01},  # never reliable
            "stages": [
                {"type": "reprompt"},
                {"type": "stronger_model"},
                {"type": "stronger_model"},
                {"type": "self_consistency", "options": {"n": 3}},
            ],
            "max_stages": 3,
        },
        router={"type": "fixed", "options": {"model": "small"}},
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    assert [a.stage for a in result.attempts] == [
        "initial",
        "reprompt",
        "stronger_model",
        "stronger_model",
    ]
    assert result.attempts[-1].model == "large" and result.escalated
    assert result.escalation_causes == ["low_confidence"]
    assert len(result.calls) == 4 and result.initial_call_count == 1
    assert result.escalation_overhead()["n_calls"] == 3
    json.dumps(result.to_dict())  # fully serialisable


def test_stronger_model_stage_is_skipped_at_the_top():
    cfg = make_config(
        escalation={"triggers": {"confidence_below": 1.01}, "stages": [{"type": "stronger_model"}]},
        router={"type": "fixed", "options": {"model": "large"}},
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    assert len(result.attempts) == 1 and not result.escalated
    assert result.escalation_causes == ["low_confidence"]


def test_escalation_disabled_and_confidence_none():
    cfg = make_config(
        escalation={"enabled": False, "triggers": {"confidence_below": 1.01}},
        confidence={"method": "none", "calibration": "none"},
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    assert not result.escalated and result.initial.confidence is None


def test_self_consistency_and_judge_select_stages():
    cfg = make_config(
        escalation={
            "triggers": {"confidence_below": 1.01},
            "stages": [{"type": "self_consistency", "options": {"n": 4}}, {"type": "judge_select"}],
            "max_stages": 2,
        }
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    sc = result.attempts[1]
    assert sc.stage == "self_consistency" and sc.confidence.method == "vote_share"
    assert result.attempts[2].stage == "judge_select" and result.attempts[2].model == "large"
    assert sum(c.purpose == "escalation_self_consistency" for c in result.calls) == 4


def test_tool_stage_only_for_numeric():
    stage = build_stage("tool", {})
    cfg = make_config(
        escalation={"triggers": {"confidence_below": 1.01}, "stages": [{"type": "tool"}]}
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    assert result.attempts[1].stage == "tool" and "tool_calls" in result.attempts[1].info
    with pytest.raises(ValueError):
        build_stage("tool", {"tools": ["web_search"]})
    with pytest.raises(ValueError):
        build_stage("teleport", {})
    assert stage.name == "tool"


def test_retrieval_stage(tmp_path):
    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        '{"id": "d1", "text": "Nineteen: 12 plus 7 equals 19."}\n'
        '{"id": "d2", "text": "Unrelated text about rivers."}\n',
        encoding="utf-8",
    )
    cfg = make_config(
        retrieval={"corpus": str(corpus), "k": 1},
        escalation={"triggers": {"confidence_below": 1.01}, "stages": [{"type": "retrieval"}]},
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    assert result.attempts[1].info["retrieved"][0]["id"] == "d1"


def test_run_requires_fitted_router():
    cfg = make_config(router={"type": "learned"})
    with pytest.raises(RuntimeError, match="fitted"):
        RouteGuardPipeline(cfg).run(numeric_query())


def test_routing_conditional_risk_control_uses_only_routed_items():
    from routeguard.confidence import CalibrationRecord

    cfg = make_config(
        confidence={"calibration": "none"},
        escalation={
            "triggers": {
                "confidence_below": None,
                "risk_control": {
                    "target_risk": 0.2,
                    "delta": 0.1,
                    "min_accepted": 5,
                    "conditional_on_routing": True,
                },
            }
        },
    )
    pipe = RouteGuardPipeline(cfg)
    # Unrouted items are easy (always right); routed items are hard (often wrong).
    easy = [CalibrationRecord("large", "en", 0.9, True, routed=False) for _ in range(200)]
    hard = [CalibrationRecord("large", "en", 0.9, i % 2 == 0, routed=True) for i in range(60)]
    pipe.fit_calibration(easy + hard)
    assert pipe.policy.thresholds["large"].valid  # certifiable on the full population ...
    assert not pipe.policy.initial_thresholds["large"].valid  # ... but not on the routed one
    assert pipe.policy.threshold_for("large", initial=True) == float("inf")
    assert pipe.policy.threshold_for("large", initial=False) < 1.0
