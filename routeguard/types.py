"""Core data types shared across RouteGuard components.

These are plain dataclasses so that every intermediate decision of the pipeline
can be serialised to JSON and inspected after the fact. Nothing in this module
performs computation beyond trivial aggregation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class AnswerType(StrEnum):
    """How a response is parsed and scored."""

    NUMERIC = "numeric"
    CHOICE = "choice"
    TEXT = "text"
    CODE = "code"


class DifficultyLabel(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


Message = dict[str, str]


@dataclass
class Query:
    """A single request entering the pipeline.

    ``language``, ``category`` and ``answer_type`` are optional *hints*. When a
    benchmark provides them they describe the expected output format; the
    pipeline still runs its own detectors so that routing errors caused by
    misdetection can be studied.

    ``reference`` holds gold information and is **only** forwarded to backends
    that declare ``requires_reference`` (the simulated backend used for tests).
    No routing, confidence, verification, or escalation component reads it.
    """

    text: str
    id: str = ""
    language: str | None = None
    category: str | None = None
    answer_type: AnswerType = AnswerType.TEXT
    choices: list[str] | None = None
    context: str | None = None
    public_tests: list[str] | None = None
    entry_point: str | None = None
    reference: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationRequest:
    messages: list[Message]
    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int | None = None
    stop: list[str] | None = None
    logprobs: bool = True
    top_logprobs: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationOutput:
    """Raw backend output plus measured cost/latency."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    token_logprobs: list[float] | None = None
    top_logprobs: list[list[float]] | None = None
    finish_reason: str = "stop"
    cached: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CallRecord:
    """Accounting entry for one LLM call made while answering a query."""

    model: str
    purpose: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    cost_usd: float
    tflops: float
    cached: bool = False


@dataclass
class QueryAnalysis:
    language: str
    language_confidence: float
    scripts: dict[str, float]
    category: str
    category_confidence: float
    features: dict[str, float]


@dataclass
class DifficultyEstimate:
    score: float
    label: DifficultyLabel
    estimator: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    model: str
    router: str
    scores: dict[str, float] = field(default_factory=dict)
    reason: str = ""


@dataclass
class ConfidenceResult:
    """``raw`` is the estimator's native score; ``calibrated`` is an estimate of
    the empirical probability of correctness (``None`` if no calibrator is fitted).
    The two are deliberately kept separate: a raw score is *not* a probability."""

    raw: float
    method: str
    calibrated: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def value(self) -> float:
        return self.calibrated if self.calibrated is not None else self.raw


@dataclass
class VerificationResult:
    """``passed`` is ``None`` when no applicable verifier ran."""

    passed: bool | None
    verifier: str
    score: float | None = None
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Attempt:
    """One candidate answer, either the initial one or one produced by an escalation stage."""

    stage: str
    model: str
    raw_text: str
    answer: str | None
    confidence: ConfidenceResult | None = None
    verification: VerificationResult | None = None
    reliable: bool | None = None
    trigger: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Full trace of one query through the pipeline (serialised to the run logs)."""

    query_id: str
    query: str
    analysis: QueryAnalysis
    difficulty: DifficultyEstimate
    routing: RoutingDecision
    attempts: list[Attempt]
    calls: list[CallRecord]
    final_index: int
    escalation_causes: list[str]
    system: str = ""
    initial_call_count: int = 0  # calls made before any escalation stage

    @property
    def initial(self) -> Attempt:
        return self.attempts[0]

    @property
    def final(self) -> Attempt:
        return self.attempts[self.final_index]

    @property
    def final_answer(self) -> str | None:
        return self.final.answer

    @property
    def final_model(self) -> str:
        return self.final.model

    @property
    def escalated(self) -> bool:
        return len(self.attempts) > 1

    def totals(self, start: int = 0) -> dict[str, float]:
        calls = self.calls[start:]
        return {
            "input_tokens": float(sum(c.input_tokens for c in calls)),
            "output_tokens": float(sum(c.output_tokens for c in calls)),
            "latency_s": float(sum(c.latency_s for c in calls)),
            "cost_usd": float(sum(c.cost_usd for c in calls)),
            "tflops": float(sum(c.tflops for c in calls)),
            "n_calls": float(len(calls)),
        }

    def escalation_overhead(self) -> dict[str, float]:
        return self.totals(start=self.initial_call_count)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(
            final_answer=self.final_answer,
            final_model=self.final_model,
            escalated=self.escalated,
            totals=self.totals(),
            escalation_overhead=self.escalation_overhead(),
        )
        return d
