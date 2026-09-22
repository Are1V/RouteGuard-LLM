"""RouteGuard-LLM: reliability-aware adaptive routing for LLM inference.

Typical use::

    from routeguard import RouteGuardPipeline, Query, load_pipeline_config

    pipeline = RouteGuardPipeline(load_pipeline_config("configs/demo.yaml"))
    result = pipeline.run(Query(text="What is 17 * 23?", answer_type="numeric"))
    print(result.final_answer, result.final_model, result.totals())

Public names are imported lazily so that ``import routeguard`` stays cheap.
"""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "0.1.0"

_EXPORTS = {
    "RouteGuardPipeline": "routeguard.pipeline",
    "build_pool": "routeguard.pipeline",
    "PipelineConfig": "routeguard.config",
    "ExperimentConfig": "routeguard.config",
    "load_pipeline_config": "routeguard.config",
    "load_experiment_config": "routeguard.config",
    "Query": "routeguard.types",
    "AnswerType": "routeguard.types",
    "PipelineResult": "routeguard.types",
    "BenchmarkRunner": "routeguard.experiments.runner",
}

__all__ = ["__version__", *_EXPORTS]


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        return getattr(importlib.import_module(_EXPORTS[name]), name)
    raise AttributeError(f"module 'routeguard' has no attribute {name!r}")
