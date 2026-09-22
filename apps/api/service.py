"""Application service boundary around RouteGuard and stored experiment artifacts."""

from __future__ import annotations

import copy
import json
import logging
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.api.schemas import (
    AttemptView,
    ConfidenceView,
    ConfigurationInfo,
    ExampleQuery,
    ExperimentDetail,
    ExperimentSummary,
    InferenceRequest,
    InferenceResponse,
    ModelInfo,
    TotalsView,
    VerificationView,
)
from routeguard import __version__
from routeguard.benchmarks.loaders import load_jsonl
from routeguard.benchmarks.schema import Item
from routeguard.config import DatasetConfig, PipelineConfig, load_pipeline_config
from routeguard.models.openai_compat import BackendError
from routeguard.pipeline import RouteGuardPipeline
from routeguard.types import AnswerType, PipelineResult, Query
from routeguard.utils.imports import MissingDependencyError

# Failures that mean "the configured backend is not usable right now" rather than
# "RouteGuard has a bug". Kept narrow on purpose: anything else propagates.
BACKEND_FAILURES = (BackendError, MissingDependencyError)

logger = logging.getLogger("routeguard.api")


class ResourceNotFoundError(LookupError):
    """A requested public resource does not exist."""


class InvalidRequestError(ValueError):
    """A request is valid JSON but invalid for the selected configuration."""


class BackendUnavailableError(RuntimeError):
    """A configured model backend could not be reached or built.

    This is an operator-facing condition (model server down, missing API key,
    optional dependency not installed), not a bug, so it is reported with its
    own status code and message instead of a generic server error.
    """


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def configs(self) -> Path:
        return self.root / "configs"

    @property
    def runs(self) -> Path:
        return self.root / "results" / "runs"

    @property
    def published_results(self) -> Path:
        return self.root / "docs" / "results"


def clean_json(value: Any) -> Any:
    """Replace non-finite research metrics with null for standards-compliant JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


class RouteGuardService:
    def __init__(self, root: Path, trace_limit: int = 100):
        self.paths = Paths(root.resolve())
        self.trace_limit = trace_limit
        self._pipelines: dict[str, RouteGuardPipeline] = {}
        self._traces: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._fixture_cache: list[Item] | None = None
        self._lock = threading.RLock()

    def _config_files(self) -> dict[str, Path]:
        return {
            path.stem: path for path in sorted(self.paths.configs.glob("*.yaml")) if path.is_file()
        }

    def config(self, config_id: str) -> PipelineConfig:
        path = self._config_files().get(config_id)
        if path is None:
            raise ResourceNotFoundError(f"Unknown configuration '{config_id}'")
        return load_pipeline_config(path)

    def configurations(self) -> list[ConfigurationInfo]:
        output = []
        for config_id in self._config_files():
            config = self.config(config_id)
            ready = (
                config.analyzer.task_classifier != "learned"
                and config.difficulty.estimator not in {"learned", "neural"}
                and config.router.type not in {"learned", "cost_aware", "quality_cost", "oracle"}
            )
            output.append(
                ConfigurationInfo(
                    id=config_id,
                    name=config.name,
                    models=[model.name for model in config.models],
                    simulated=all(model.backend == "simulated" for model in config.models),
                    ready_for_inference=ready,
                )
            )
        return output

    def models(self, config_id: str) -> list[ModelInfo]:
        config = self.config(config_id)
        return [
            ModelInfo(
                name=model.name,
                backend=model.backend,
                model_id=model.model_id,
                params_b=model.params_b,
                simulated=model.backend == "simulated",
                max_new_tokens=model.max_new_tokens,
                priced=bool(model.price_input_per_1k or model.price_output_per_1k),
            )
            for model in config.models
        ]

    def _pipeline(self, request: InferenceRequest) -> RouteGuardPipeline:
        base = self.config(request.config)
        data = copy.deepcopy(base.model_dump())
        if request.routing == "manual":
            names = {model["name"] for model in data["models"]}
            if request.model not in names:
                raise InvalidRequestError(
                    f"Model '{request.model}' is not in configuration '{request.config}'"
                )
            data["router"] = {"type": "fixed", "options": {"model": request.model}}
        data["verification"]["enabled"] = request.verification
        data["verification"]["verifiers"] = [
            spec
            for spec in data["verification"]["verifiers"]
            if not (
                spec == "code_execution"
                or (isinstance(spec, dict) and spec.get("name") == "code_execution")
            )
        ]
        data["escalation"]["enabled"] = request.escalation
        config = PipelineConfig.model_validate(data)
        key = json.dumps(config.model_dump(mode="json"), sort_keys=True)
        with self._lock:
            if key not in self._pipelines:
                try:
                    pipeline = RouteGuardPipeline(config)
                except BACKEND_FAILURES as exc:
                    logger.warning("Cannot build pipeline for '%s': %s", request.config, exc)
                    raise BackendUnavailableError(str(exc)) from exc
                if pipeline.needs_training_data:
                    raise InvalidRequestError(
                        "This configuration contains unfitted learned components and cannot be "
                        "used for ad-hoc inference"
                    )
                self._pipelines[key] = pipeline
            return self._pipelines[key]

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        pipeline = self._pipeline(request)
        query = self._query(request, pipeline.pool.simulated)
        try:
            result = pipeline.run(query)
        except BACKEND_FAILURES as exc:
            logger.warning("Backend unavailable for config '%s': %s", request.config, exc)
            raise BackendUnavailableError(str(exc)) from exc
        trace_id = uuid4().hex
        raw_trace = clean_json(result.to_dict())
        with self._lock:
            self._traces[trace_id] = raw_trace
            self._traces.move_to_end(trace_id)
            while len(self._traces) > self.trace_limit:
                self._traces.popitem(last=False)
        return self._response(
            trace_id,
            result,
            pipeline.pool.simulated,
            language_requested=request.language != "auto",
        )

    def _fixtures(self) -> list[Item]:
        """Demo questions the simulated backend can answer, loaded once."""
        with self._lock:
            if self._fixture_cache is None:
                path = self.paths.root / "benchmarks" / "samples" / "smoke.jsonl"
                self._fixture_cache = (
                    load_jsonl(DatasetConfig(loader="jsonl", path=str(path)))
                    if path.exists()
                    else []
                )
            return self._fixture_cache

    def examples(self, config_id: str) -> list[ExampleQuery]:
        """Example queries for a configuration.

        Only the simulated demo has a fixed set of questions it can answer; a real
        model backend accepts anything, so it gets no example list.
        """
        config = self.config(config_id)
        if config_id != "demo" or not all(m.backend == "simulated" for m in config.models):
            return []
        return [
            ExampleQuery(
                query=item.question,
                answer_type=item.answer_type.value,
                language=item.language,
                category=item.category,
            )
            for item in self._fixtures()
        ]

    def _query(self, request: InferenceRequest, simulated: bool) -> Query:
        """Build an ad-hoc query, preserving gold only for exact demo-fixture matches."""
        text = request.query.strip()
        if simulated and request.config == "demo" and request.context is None:
            match = next(
                (
                    item
                    for item in self._fixtures()
                    if item.question == text and item.answer_type.value == request.answer_type
                ),
                None,
            )
            if match is not None:
                query = match.to_query()
                query.id = f"api-demo-{uuid4().hex[:12]}"
                if request.choices:
                    query.choices = request.choices
            else:
                query = Query(
                    id=f"api-{uuid4().hex[:12]}",
                    text=text,
                    answer_type=AnswerType(request.answer_type),
                    choices=request.choices,
                )
        else:
            query = Query(
                id=f"api-{uuid4().hex[:12]}",
                text=text,
                language=None if request.language == "auto" else request.language,
                answer_type=AnswerType(request.answer_type),
                choices=request.choices,
                context=request.context,
            )
        if request.language != "auto":
            query.metadata["language_override"] = request.language
        return query

    def trace(self, trace_id: str) -> dict[str, Any]:
        with self._lock:
            trace = self._traces.get(trace_id)
        if trace is None:
            raise ResourceNotFoundError(f"Trace '{trace_id}' is not available")
        return trace

    @staticmethod
    def _response(
        trace_id: str,
        result: PipelineResult,
        simulated: bool,
        language_requested: bool,
    ) -> InferenceResponse:
        attempts = []
        for attempt in result.attempts:
            confidence = attempt.confidence
            verification = attempt.verification
            attempts.append(
                AttemptView(
                    stage=attempt.stage,
                    model=attempt.model,
                    raw_text=attempt.raw_text,
                    answer=attempt.answer,
                    confidence=(
                        ConfidenceView(
                            raw=confidence.raw,
                            method=confidence.method,
                            calibrated=confidence.calibrated,
                            calibrated_label=(
                                "calibrated estimate of correctness"
                                if confidence.calibrated is not None
                                else "unavailable"
                            ),
                        )
                        if confidence
                        else None
                    ),
                    verification=(
                        VerificationView(
                            passed=verification.passed,
                            verifier=verification.verifier,
                            reason=verification.reason,
                        )
                        if verification
                        else None
                    ),
                    reliable=attempt.reliable,
                    triggers=list(attempt.trigger),
                )
            )
        totals = result.totals()
        return InferenceResponse(
            trace_id=trace_id,
            simulated=simulated,
            query=result.query,
            detected_language=result.analysis.language,
            language_source="requested" if language_requested else "detected",
            language_confidence=result.analysis.language_confidence,
            task_category=result.analysis.category,
            task_confidence=result.analysis.category_confidence,
            difficulty_score=result.difficulty.score,
            difficulty_label=result.difficulty.label.value,
            selected_model=result.routing.model,
            routing_strategy=result.routing.router,
            routing_reason=result.routing.reason,
            attempts=attempts,
            escalated=result.escalated,
            escalation_reasons=list(result.escalation_causes),
            final_answer=result.final_answer,
            final_model=result.final_model,
            totals=TotalsView(
                input_tokens=int(totals["input_tokens"]),
                output_tokens=int(totals["output_tokens"]),
                latency_s=totals["latency_s"],
                cost_usd=totals["cost_usd"] if totals["cost_usd"] > 0 else None,
                tflops=totals["tflops"] if totals["tflops"] > 0 else None,
                calls=int(totals["n_calls"]),
            ),
        )

    def _experiment_dir(self, run_id: str) -> tuple[Path, bool]:
        if not run_id or Path(run_id).name != run_id:
            raise ResourceNotFoundError("Invalid experiment identifier")
        path = (self.paths.runs / run_id).resolve()
        if path.parent == self.paths.runs and path.is_dir():
            return path, False
        if self.paths.published_results.exists():
            for published in self.paths.published_results.iterdir():
                provenance_path = published / "PROVENANCE.json"
                if not published.is_dir() or not provenance_path.exists():
                    continue
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                if provenance.get("run_id") == run_id:
                    return published.resolve(), True
        raise ResourceNotFoundError(f"Experiment '{run_id}' does not exist")

    def experiment_summary(self, run_id: str) -> ExperimentSummary:
        run, published = self._experiment_dir(run_id)
        metadata_path = run / ("PROVENANCE.json" if published else "manifest.json")
        manifest = json.loads(metadata_path.read_text(encoding="utf-8"))
        metrics_path = run / "metrics.json" if published else run / "processed" / "metrics.json"
        metrics = (
            json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
        )
        figures = list((run / "figures").glob("*")) if (run / "figures").exists() else []
        systems = manifest.get("systems") or metrics.get("systems", {})
        seeds = manifest.get("seeds") or []
        data = manifest.get("data") or {}
        return ExperimentSummary(
            id=run_id,
            name=str(manifest.get("name", run.name if published else run_id)),
            description=str(manifest.get("description", "")),
            started=manifest.get("started"),
            simulated=manifest.get("simulated"),
            systems=list(systems) if isinstance(systems, dict) else [],
            seeds=[int(seed) for seed in seeds],
            item_count=data.get("n_items"),
            has_metrics=metrics_path.exists(),
            figure_count=len([path for path in figures if path.suffix.lower() == ".png"]),
        )

    def experiments(self) -> list[ExperimentSummary]:
        run_ids = {
            path.name
            for path in self.paths.runs.glob("*")
            if path.is_dir() and (path / "manifest.json").exists()
        }
        for path in self.paths.published_results.glob("*/PROVENANCE.json"):
            provenance = json.loads(path.read_text(encoding="utf-8"))
            if provenance.get("run_id"):
                run_ids.add(str(provenance["run_id"]))
        return [self.experiment_summary(run_id) for run_id in sorted(run_ids, reverse=True)]

    def experiment(self, run_id: str) -> ExperimentDetail:
        run, published = self._experiment_dir(run_id)
        metadata_path = run / ("PROVENANCE.json" if published else "manifest.json")
        manifest = clean_json(json.loads(metadata_path.read_text(encoding="utf-8")))
        tables = sorted(path.name for path in (run / "tables").glob("*.csv"))
        figures = sorted(path.name for path in (run / "figures").glob("*.png"))
        return ExperimentDetail(
            summary=self.experiment_summary(run_id),
            manifest=manifest,
            available_tables=tables,
            available_figures=figures,
        )

    def metrics(self, run_id: str) -> dict[str, Any]:
        run, published = self._experiment_dir(run_id)
        path = run / "metrics.json" if published else run / "processed" / "metrics.json"
        if not path.exists():
            raise ResourceNotFoundError(f"Experiment '{run_id}' has no processed metrics")
        return clean_json(json.loads(path.read_text()))

    def artifact(self, run_id: str, kind: str, name: str) -> Path:
        if kind not in {"figures", "tables"} or Path(name).name != name:
            raise ResourceNotFoundError("Invalid artifact path")
        run, _ = self._experiment_dir(run_id)
        path = (run / kind / name).resolve()
        if path.parent != (run / kind).resolve() or not path.is_file():
            raise ResourceNotFoundError(f"Artifact '{name}' does not exist")
        return path


def version() -> str:
    return __version__
