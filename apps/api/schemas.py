"""Public API schemas. Core dataclasses remain independent of FastAPI."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(StrictModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(StrictModel):
    error: ErrorBody


class HealthResponse(StrictModel):
    status: Literal["ok", "not_ready"]
    version: str
    simulated: bool | None = None


class ModelInfo(StrictModel):
    name: str
    backend: str
    model_id: str
    params_b: float
    simulated: bool
    max_new_tokens: int
    priced: bool


class ConfigurationInfo(StrictModel):
    id: str
    name: str
    models: list[str]
    simulated: bool
    ready_for_inference: bool


class ExampleQuery(StrictModel):
    """A bundled demo question the simulated backend has a reference answer for."""

    query: str
    answer_type: Literal["text", "numeric", "choice", "code"]
    language: str
    category: str


class InferenceRequest(StrictModel):
    query: str = Field(min_length=1, max_length=20_000)
    config: str = "demo"
    routing: Literal["automatic", "manual"] = "automatic"
    model: str | None = None
    language: Literal["auto", "en", "kk", "ru", "fa", "prs_Arab"] = "auto"
    answer_type: Literal["text", "numeric", "choice", "code"] = "text"
    choices: list[str] | None = Field(default=None, max_length=20)
    context: str | None = Field(default=None, max_length=50_000)
    verification: bool = True
    escalation: bool = True

    @model_validator(mode="after")
    def validate_manual_model(self) -> InferenceRequest:
        if self.routing == "manual" and not self.model:
            raise ValueError("model is required for manual routing")
        if self.answer_type == "choice" and not self.choices:
            raise ValueError("choices are required when answer_type is 'choice'")
        return self


class ConfidenceView(StrictModel):
    raw: float
    method: str
    calibrated: float | None
    calibrated_label: str


class VerificationView(StrictModel):
    passed: bool | None
    verifier: str
    reason: str


class AttemptView(StrictModel):
    stage: str
    model: str
    raw_text: str
    answer: str | None
    confidence: ConfidenceView | None
    verification: VerificationView | None
    reliable: bool | None
    triggers: list[str]


class TotalsView(StrictModel):
    input_tokens: int
    output_tokens: int
    latency_s: float
    cost_usd: float | None
    tflops: float | None
    calls: int


class InferenceResponse(StrictModel):
    trace_id: str
    simulated: bool
    query: str
    detected_language: str
    language_source: Literal["detected", "requested"]
    language_confidence: float
    task_category: str
    task_confidence: float
    difficulty_score: float
    difficulty_label: str
    selected_model: str
    routing_strategy: str
    routing_reason: str
    attempts: list[AttemptView]
    escalated: bool
    escalation_reasons: list[str]
    final_answer: str | None
    final_model: str
    totals: TotalsView


class ExperimentSummary(StrictModel):
    id: str
    name: str
    description: str
    started: str | None
    simulated: bool | None
    systems: list[str]
    seeds: list[int]
    item_count: int | None
    has_metrics: bool
    figure_count: int


class ExperimentList(StrictModel):
    experiments: list[ExperimentSummary]


class ExperimentDetail(StrictModel):
    summary: ExperimentSummary
    manifest: dict[str, Any]
    available_tables: list[str]
    available_figures: list[str]
