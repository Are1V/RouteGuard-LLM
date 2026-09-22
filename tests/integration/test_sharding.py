"""Cluster workflow: sharded generation -> cache merge -> replayed benchmark."""

import json

import pytest

from routeguard.cli import main
from routeguard.config import load_experiment_config
from routeguard.experiments.runner import BenchmarkRunner
from routeguard.experiments.sharding import ShardSpec, generate_shard, merge_caches, plan_requests
from tests.conftest import ROOT


def _config():
    cfg = load_experiment_config(ROOT / "experiments" / "smoke" / "smoke.yaml")
    for ds in cfg.data:
        ds.path = str(ROOT / ds.path)
    return cfg


def test_shards_are_disjoint_and_merged_cache_is_complete(tmp_path):
    cfg = _config()
    plan = plan_requests(cfg)
    total = sum(len(v) for v in plan.values())
    counts = [generate_shard(cfg, ShardSpec(i, 3), tmp_path / f"s{i}.sqlite") for i in range(3)]
    assert sum(sum(c.values()) for c in counts) == total  # disjoint and exhaustive
    merged = tmp_path / "merged.sqlite"
    assert merge_caches([tmp_path / f"s{i}.sqlite" for i in range(3)], merged) == total

    cfg.pipeline["cache"] = {"enabled": True, "path": str(merged)}
    run = BenchmarkRunner(cfg, output_dir=str(tmp_path / "runs"), seeds=[0], figures=False).run()
    rows = [json.loads(line) for p in (run / "raw").glob("*.jsonl") for line in p.open()]
    assert rows
    # Every initial answer of every system was produced by the shard jobs.
    initial_calls = sum(r["calls_by_purpose"].get("initial", 0) for r in rows)
    assert initial_calls > 0
    uncached_initial = [
        r for r in rows if r["cached_calls"] < r["calls_by_purpose"].get("initial", 0)
    ]
    assert not uncached_initial


def test_shard_spec_parsing(monkeypatch):
    assert ShardSpec.parse("2/5") == ShardSpec(2, 5)
    for bad in ("5/5", "x", "1-2"):
        with pytest.raises(ValueError):
            ShardSpec.parse(bad)
    monkeypatch.setenv("SLURM_ARRAY_TASK_ID", "4")
    monkeypatch.setenv("SLURM_ARRAY_TASK_COUNT", "8")
    monkeypatch.setenv("SLURM_ARRAY_TASK_MIN", "1")
    assert ShardSpec.parse("auto") == ShardSpec(3, 8)


def test_generate_and_merge_cli(tmp_path):
    cfg_path = ROOT / "experiments" / "smoke" / "smoke.yaml"
    for i in range(2):
        assert (
            main(
                [
                    "generate",
                    "--config",
                    str(cfg_path),
                    "--shard",
                    f"{i}/2",
                    "--cache",
                    str(tmp_path / f"{i}.sqlite"),
                    "--models",
                    "small",
                ]
            )
            == 0
        )
    assert (
        main(
            [
                "cache-merge",
                str(tmp_path / "0.sqlite"),
                str(tmp_path / "1.sqlite"),
                "--out",
                str(tmp_path / "all.sqlite"),
            ]
        )
        == 0
    )
