from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from routeguard.config import PipelineConfig
from routeguard.models import ModelPool, ModelSpec
from routeguard.pipeline import RouteGuardPipeline
from routeguard.types import AnswerType, Query

ROOT = Path(__file__).resolve().parents[1]


def sim_models(capabilities: tuple[float, ...] = (0.3, 0.55, 0.8)) -> list[dict[str, Any]]:
    names = ["small", "medium", "large", "xl", "xxl"]
    return [
        {
            "name": names[i],
            "backend": "simulated",
            "model_id": f"sim-{names[i]}",
            "params_b": [0.5, 1.5, 7.0, 14.0, 70.0][i],
            "max_new_tokens": 128,
            "options": {"capability": c},
        }
        for i, c in enumerate(capabilities)
    ]


def make_config(**overrides: Any) -> PipelineConfig:
    data: dict[str, Any] = {
        "models": sim_models(),
        "cache": {"enabled": False},
        "confidence": {"calibration": "none"},
    }
    data.update(overrides)
    return PipelineConfig.model_validate(data)


@pytest.fixture
def sim_config() -> PipelineConfig:
    return make_config()


@pytest.fixture
def sim_pool() -> ModelPool:
    return ModelPool([ModelSpec(**m) for m in sim_models()])


@pytest.fixture
def pipeline(sim_config: PipelineConfig) -> RouteGuardPipeline:
    return RouteGuardPipeline(sim_config)


def numeric_query(
    text: str = "What is 12 plus 7?",
    answer: str = "19",
    difficulty: float = 0.3,
    qid: str = "q1",
    language: str = "en",
) -> Query:
    return Query(
        text=text,
        id=qid,
        answer_type=AnswerType.NUMERIC,
        language=language,
        reference={
            "id": qid,
            "answer": answer,
            "answer_type": "numeric",
            "difficulty": difficulty,
            "language": language,
        },
    )
