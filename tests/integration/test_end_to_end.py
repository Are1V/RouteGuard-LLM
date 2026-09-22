"""End-to-end tests on the simulated backend (no downloads, no GPU)."""

import json
from pathlib import Path
from typing import ClassVar

import pytest

from routeguard.cli import main
from routeguard.config import load_experiment_config
from routeguard.experiments.runner import BenchmarkRunner, LeakageError
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("runs")
    cfg = load_experiment_config(ROOT / "experiments" / "smoke" / "smoke.yaml")
    cfg.pipeline["cache"] = {"enabled": False}
    return BenchmarkRunner(cfg, output_dir=str(out), seeds=[0]).run()


def test_smoke_benchmark_writes_a_complete_run(smoke_run: Path):
    manifest = json.loads((smoke_run / "manifest.json").read_text())
    assert manifest["status"] == "completed" and manifest["simulated"] is True
    assert (smoke_run / "config.yaml").exists()
    raw = sorted(p.name for p in (smoke_run / "raw").glob("*.jsonl"))
    assert "routeguard_full_seed0.jsonl" in raw and "oracle_seed0.jsonl" in raw
    metrics = json.loads((smoke_run / "processed" / "metrics.json").read_text())
    assert metrics["simulated"]
    full = metrics["systems"]["routeguard_full"]["metrics"]
    for key in (
        "accuracy",
        "tflops_mean",
        "latency_p95_s",
        "routing_accuracy",
        "escalation_rate",
        "rel_auroc_error_detection",
    ):
        assert key in full
    for table in (
        "main_results",
        "routing",
        "calibration",
        "language_breakdown",
        "ablations",
        "error_analysis",
        "significance",
    ):
        for ext in ("md", "csv", "tex"):
            assert (smoke_run / "tables" / f"{table}.{ext}").exists()
    assert "SIMULATED" in (smoke_run / "tables" / "main_results.md").read_text()
    figures = {p.stem for p in (smoke_run / "figures").glob("*.png")}
    assert {
        "pareto_accuracy_vs_cost",
        "reliability_diagram",
        "router_confusion_matrix",
        "accuracy_by_language",
        "model_selection_distribution",
    } <= figures


def test_records_are_complete_and_consistent(smoke_run: Path):
    rows = [json.loads(line) for line in (smoke_run / "raw" / "routeguard_full_seed0.jsonl").open()]
    assert rows
    for r in rows:
        assert r["routed_model"] in r["model_order"]
        assert r["n_calls"] >= 1 and r["latency_s"] > 0
        assert r["escalated"] == (len(r["attempts"]) > 1)
        assert r["simulated"] is True
    fixed = [json.loads(line) for line in (smoke_run / "raw" / "always_large_seed0.jsonl").open()]
    assert {r["routed_model"] for r in fixed} == {"large"}
    assert all(not r["escalated"] for r in fixed)


def test_evaluate_reproduces_metrics_from_raw_records(smoke_run: Path, tmp_path: Path):
    before = json.loads((smoke_run / "processed" / "metrics.json").read_text())
    assert main(["evaluate", str(smoke_run), "--out", str(tmp_path)]) == 0
    after = json.loads((tmp_path / "processed" / "metrics.json").read_text())
    for system, data in before["systems"].items():
        assert after["systems"][system]["metrics"]["accuracy"] == data["metrics"]["accuracy"]
    assert main(["plot", str(smoke_run), "--out", str(tmp_path / "figs"), "--formats", "png"]) == 0
    assert any((tmp_path / "figs").glob("*.png"))


def test_leakage_guard(smoke_run):
    from routeguard.experiments.runner import BenchmarkRunner as R

    class Fake:
        name = "fake"
        trained_ids: ClassVar[set[str]] = {"x"}

    class Pipe:
        difficulty = Fake()
        router = Fake()

    with pytest.raises(LeakageError):
        R._check_leakage(Pipe(), {"x", "y"})


def test_cli_commands(capsys, tmp_path):
    assert main(["components"]) == 0
    assert "quality_cost" in capsys.readouterr().out
    assert main(["validate", str(ROOT / "experiments" / "smoke" / "smoke.yaml")]) == 0
    assert main(["validate", str(ROOT / "configs" / "demo.yaml")]) == 0
    out = tmp_path / "traces.jsonl"
    assert (
        main(
            [
                "run",
                "--config",
                str(ROOT / "configs" / "demo.yaml"),
                "--input",
                str(ROOT / "benchmarks" / "samples" / "smoke.jsonl"),
                "--limit",
                "1",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    assert len(out.read_text().splitlines()) == 4  # one item per language
    assert (
        main(
            [
                "run",
                "--config",
                str(ROOT / "configs" / "demo.yaml"),
                "--query",
                "2+2?",
                "--answer-type",
                "numeric",
            ]
        )
        == 0
    )
    assert main(["validate", str(tmp_path / "missing.yaml")]) == 2
    with pytest.raises(SystemExit):
        main(["--version"])


def test_confidence_samples_are_pregenerated_in_batch(tmp_path):
    from routeguard.config import SystemConfig

    cfg = load_experiment_config(ROOT / "experiments" / "smoke" / "smoke.yaml")
    cfg.pipeline["cache"] = {"enabled": True, "path": str(tmp_path / "c.sqlite")}
    cfg.systems = [
        SystemConfig(
            name="sc",
            overrides={
                "router": {"type": "fixed", "options": {"model": "small"}},
                "confidence": {
                    "method": "self_consistency",
                    "options": {"n_samples": 3},
                    "calibration": "isotonic",
                    "min_samples": 10,
                },
                "escalation": {"enabled": False},
            },
        )
    ]
    run = BenchmarkRunner(cfg, output_dir=str(tmp_path / "runs"), seeds=[0], figures=False).run()
    rows = [json.loads(line) for line in (run / "raw" / "sc_seed0.jsonl").open()]
    assert all(r["calls_by_purpose"].get("confidence_sample") == 3 for r in rows)
    assert all(r["cached_calls"] == r["n_calls"] for r in rows)  # nothing generated per query


def test_missing_optional_dependency_is_a_clean_cli_error(monkeypatch, caplog):
    import routeguard.dashboard as dashboard
    from routeguard.utils.imports import MissingDependencyError

    def fail(*args, **kwargs):
        raise MissingDependencyError("needs gradio: pip install -e '.[dashboard]'")

    monkeypatch.setattr(dashboard, "launch", fail)
    assert main(["demo"]) == 2
    assert "pip install" in caplog.text
