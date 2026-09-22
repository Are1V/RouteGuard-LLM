from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from routeguard.config import (
    ExperimentConfig,
    PipelineConfig,
    SplitConfig,
    deep_merge,
    load_experiment_config,
    load_pipeline_config,
    load_yaml,
)
from tests.conftest import ROOT, sim_models


def test_all_shipped_configs_validate():
    pipelines = list((ROOT / "configs").glob("*.yaml"))
    experiments = list((ROOT / "experiments").rglob("*.yaml"))
    assert pipelines and experiments
    for p in pipelines:
        load_pipeline_config(p)
    for p in experiments:
        data = load_yaml(p)
        if "systems" in data:
            load_experiment_config(p)


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate({"models": sim_models(), "routr": {}})


def test_secrets_in_config_are_rejected():
    models = sim_models()
    models[0]["options"]["api_key"] = "sk-123"
    with pytest.raises(ValidationError, match="secrets"):
        PipelineConfig.model_validate({"models": models})


def test_duplicate_model_names_rejected():
    models = sim_models()
    models[1]["name"] = "small"
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate({"models": models})


def test_retrieval_stage_requires_retrieval_section():
    with pytest.raises(ValidationError, match="retrieval"):
        PipelineConfig.model_validate(
            {"models": sim_models(), "escalation": {"stages": [{"type": "retrieval"}]}}
        )


def test_split_fractions_must_sum_to_one():
    with pytest.raises(ValidationError):
        SplitConfig(train=0.5, calibration=0.5, test=0.5)


def test_deep_merge_replaces_mapping_when_component_kind_changes():
    base = {"router": {"type": "threshold", "options": {"thresholds": [0.3, 0.6]}}, "a": [1, 2]}
    merged = deep_merge(
        base, {"router": {"type": "fixed", "options": {"model": "small"}}, "a": [3]}
    )
    assert merged["router"] == {"type": "fixed", "options": {"model": "small"}}
    assert merged["a"] == [3]
    same = deep_merge(base, {"router": {"options": {"thresholds": [0.1, 0.2]}}})
    assert same["router"]["type"] == "threshold"
    assert base["router"]["options"]["thresholds"] == [0.3, 0.6]  # input untouched


def test_extends_resolution_and_cycles(tmp_path: Path):
    (tmp_path / "base.yaml").write_text(yaml.safe_dump({"models": sim_models(), "seed": 3}))
    (tmp_path / "child.yaml").write_text(yaml.safe_dump({"extends": "base.yaml", "seed": 5}))
    cfg = load_pipeline_config(tmp_path / "child.yaml")
    assert cfg.seed == 5 and len(cfg.models) == 3
    (tmp_path / "a.yaml").write_text("extends: b.yaml\n")
    (tmp_path / "b.yaml").write_text("extends: a.yaml\n")
    with pytest.raises(ValueError, match="Circular"):
        load_yaml(tmp_path / "a.yaml")


def test_experiment_systems_validated_eagerly():
    base = {
        "name": "x",
        "pipeline": {"models": sim_models()},
        "data": [{"loader": "jsonl", "path": "p"}],
    }
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(
            {**base, "systems": [{"name": "a", "overrides": {"router": {"typo": 1}}}]}
        )
    with pytest.raises(ValidationError, match="same model pool"):
        ExperimentConfig.model_validate(
            {
                **base,
                "systems": [
                    {"name": "a"},
                    {"name": "b", "overrides": {"models": sim_models((0.2, 0.9))}},
                ],
            }
        )
    ok = ExperimentConfig.model_validate(
        {
            **base,
            "systems": [
                {
                    "name": "a",
                    "overrides": {"router": {"type": "fixed", "options": {"model": "large"}}},
                }
            ],
        }
    )
    assert ok.system_pipeline(ok.systems[0]).router.options == {"model": "large"}
