"""Copy the reported tables and figures of finished runs into ``docs/results/``.

Run directories under ``results/runs/`` are git-ignored (raw records are large). This script
publishes the processed artefacts that the README cites, together with a provenance note
(run id, git commit, seeds, dataset fingerprint, simulated flag), so every number in the README
can be traced back to a run.

Usage:
    python scripts/publish_results.py results/runs/main_* results/runs/routing_* ...
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "docs" / "results"
FIGURES = [
    "pareto_accuracy_vs_cost",
    "pareto_accuracy_vs_latency",
    "accuracy_by_language",
    "reliability_diagram",
    "calibration_by_model",
    "router_confusion_matrix",
    "model_selection_distribution",
    "difficulty_distribution",
    "error_types",
    "accuracy_by_model",
    "cost_vs_escalation_rate",
    "rag_reliability_by_language",
]


def publish(run: Path) -> Path:
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status", "completed") != "completed":
        raise SystemExit(f"{run}: status is {manifest.get('status')}, refusing to publish")
    name = str(manifest.get("name") or manifest.get("config", {}).get("name") or run.name)
    out = DEST / name
    if out.exists():
        shutil.rmtree(out)
    (out / "tables").mkdir(parents=True)
    for table in sorted((run / "tables").glob("*")):
        shutil.copy2(table, out / "tables" / table.name)
    figs = run / "figures"
    if figs.exists():
        (out / "figures").mkdir()
        for stem in FIGURES:
            for ext in ("png", "pdf"):
                src = figs / f"{stem}.{ext}"
                if src.exists():
                    shutil.copy2(src, out / "figures" / src.name)
    for extra in (
        "processed/metrics.json",
        "processed/error_analysis.md",
        "processed/rag_summary.json",
        "processed/tool_use_summary.json",
    ):
        if (run / extra).exists():
            shutil.copy2(run / extra, out / Path(extra).name)
    provenance = {
        "run_id": run.name,
        "git": manifest.get("git"),
        "seeds": manifest.get("seeds"),
        "data_fingerprint": manifest.get("data_fingerprint"),
        "data": manifest.get("data"),
        "simulated": manifest.get("simulated"),
        "started": manifest.get("started"),
        "finished": manifest.get("finished"),
        "models": [m.get("model_id") for m in manifest.get("models", [])] or None,
    }
    (out / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or {"-h", "--help"} & set(args):
        raise SystemExit(__doc__)
    missing = [arg for arg in args if not (Path(arg) / "manifest.json").is_file()]
    if missing:
        raise SystemExit("Not a finished run directory (no manifest.json): " + ", ".join(missing))
    for arg in args:
        print("published", publish(Path(arg)))
