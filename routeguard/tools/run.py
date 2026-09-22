"""``routeguard tool-eval``: tool-use failure analysis for one pool model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from routeguard.config import PipelineConfig, load_yaml
from routeguard.context import CallContext
from routeguard.evaluation.tables import SIMULATED_NOTE, Table
from routeguard.pipeline import build_pool
from routeguard.tools.agent import ToolAgent
from routeguard.tools.base import BUILTIN_TOOLS
from routeguard.tools.evaluation import TOOL_FAILURES, ToolCase, label_trace, summarize_tool_eval
from routeguard.tracking.run import JsonlWriter, RunDirectory, environment, git_state


class ToolEvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    pipeline: dict[str, Any]
    models: list[str] = Field(description="pool models to evaluate")
    cases: str
    max_steps: int = 3
    output_dir: str = "results/runs"


def load_cases(path: str | Path) -> list[ToolCase]:
    with Path(path).open(encoding="utf-8") as f:
        return [ToolCase.model_validate(json.loads(line)) for line in f if line.strip()]


def run_tool_eval(config_path: str | Path) -> Path:
    cfg = ToolEvalConfig.model_validate(load_yaml(config_path))
    pool = build_pool(PipelineConfig.model_validate(cfg.pipeline))
    cases = load_cases(cfg.cases)
    run = RunDirectory(cfg.output_dir, cfg.name)
    run.write_json(
        "manifest.json",
        {
            "config": cfg.model_dump(),
            "n_cases": len(cases),
            "git": git_state(),
            "environment": environment(),
            "simulated": pool.simulated,
        },
    )
    table = Table(
        "tool_use",
        "Tool-use failure rates per model (share of cases).",
        ["Model", "n", "Accuracy", *TOOL_FAILURES],
        note=SIMULATED_NOTE if pool.simulated else "",
    )
    summaries = {}
    for model in cfg.models:
        rows = []
        with JsonlWriter(run.path / "raw" / f"tool_use_{model}.jsonl") as writer:
            for case in cases:
                tools = [BUILTIN_TOOLS[t] for t in case.tools]
                q = case.to_query()
                trace = ToolAgent(tools, cfg.max_steps).run(q, model, CallContext(pool, q))
                row = label_trace(case, trace)
                row["responses"] = trace.responses
                rows.append(row)
                writer.write(row)
        s = summarize_tool_eval(rows)
        summaries[model] = s
        table.add(model, s["n"], s["accuracy"], *[s["failure_rates"][k] for k in TOOL_FAILURES])
    run.write_json("processed/tool_use_summary.json", summaries)
    table.save(run.path / "tables")
    print(table.to_markdown())
    return run.path
