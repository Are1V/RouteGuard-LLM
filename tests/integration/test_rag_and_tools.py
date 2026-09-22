"""RAG-eval and tool-eval runners end to end on the simulated backend."""

import json

import yaml

from routeguard.cli import main
from routeguard.evaluation.records import annotate_retrieval
from tests.conftest import ROOT


def _config(tmp_path, name, source):
    data = yaml.safe_load((ROOT / source).read_text())
    data["pipeline"] = {"extends": str(ROOT / "configs" / "demo.yaml"), "cache": {"enabled": False}}
    data["output_dir"] = str(tmp_path / "runs")
    for ds in data.get("data", []):
        ds["path"] = str(ROOT / ds["path"])
    if "cases" in data:
        data["cases"] = str(ROOT / data["cases"])
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def test_rag_eval_cli(tmp_path, capsys):
    cfg = _config(tmp_path, "rag", "experiments/rag/rag_smoke.yaml")
    assert main(["rag-eval", "--config", str(cfg)]) == 0
    run = next((tmp_path / "runs").iterdir())
    summary = json.loads((run / "processed" / "rag_summary.json").read_text())
    assert set(summary["by_language"]) == {"en", "ru", "kk", "fa"}
    assert (run / "tables" / "rag_reliability.tex").exists()
    assert "SIMULATED" in capsys.readouterr().out


def test_tool_eval_cli(tmp_path):
    cfg = _config(tmp_path, "tools", "experiments/tools/tool_use_smoke.yaml")
    assert main(["tool-eval", "--config", str(cfg)]) == 0
    run = next((tmp_path / "runs").iterdir())
    summary = json.loads((run / "processed" / "tool_use_summary.json").read_text())
    assert set(summary) == {"small", "large"}
    assert 0 <= summary["large"]["accuracy"] <= 1


def test_retrieval_annotation_uses_gold_only_at_evaluation_time():
    from routeguard.benchmarks import Item

    item = Item(
        id="x",
        question="q",
        answer="B",
        answer_type="choice",
        category="c",
        language="en",
        choices=["Paris", "Astana", "Rome"],
        metadata={"gold_doc_ids": ["d1"]},
    )
    attempt = {"info": {"retrieved": [{"id": "d1", "score": 1.0}, {"id": "d2", "score": 0.5}]}}
    annotate_retrieval(attempt, item, {"d1": "Astana is the capital.", "d2": "x"}.__getitem__)
    assert attempt["info"]["gold_in_evidence"] is True
    assert attempt["info"]["gold_doc_recall"] == 1.0
