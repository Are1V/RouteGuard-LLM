"""Versioned HTTP API for RouteGuard inference and read-only experiment inspection."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from apps.api.schemas import (
    ConfigurationInfo,
    ErrorBody,
    ErrorResponse,
    ExampleQuery,
    ExperimentDetail,
    ExperimentList,
    HealthResponse,
    InferenceRequest,
    InferenceResponse,
    ModelInfo,
)
from apps.api.service import (
    BackendUnavailableError,
    InvalidRequestError,
    ResourceNotFoundError,
    RouteGuardService,
    version,
)

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger("routeguard.api")


def _error(
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def create_app(root: Path = ROOT) -> FastAPI:
    service = RouteGuardService(root)
    api = FastAPI(
        title="RouteGuard-LLM API",
        version=version(),
        description=(
            "Local inference and read-only access to stored RouteGuard research runs. "
            "Experiment execution is intentionally not exposed."
        ),
    )
    origins = [
        origin.strip()
        for origin in os.getenv(
            "ROUTEGUARD_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @api.middleware("http")
    async def warn_on_blocked_origin(request: Request, call_next: Any) -> Any:
        # A browser drops the response of a disallowed origin silently, and the server
        # otherwise records a plain 200 — so say it here, where an operator will see it.
        origin = request.headers.get("origin")
        if origin and "*" not in origins and origin not in origins:
            logger.warning(
                "Request from origin %s will be blocked by the browser; "
                "ROUTEGUARD_CORS_ORIGINS currently allows %s",
                origin,
                ", ".join(origins) or "(nothing)",
            )
        return await call_next(request)

    @api.exception_handler(ResourceNotFoundError)
    async def not_found(_: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return _error(404, "not_found", str(exc))

    @api.exception_handler(InvalidRequestError)
    async def invalid_request(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return _error(400, "invalid_request", str(exc))

    @api.exception_handler(BackendUnavailableError)
    async def backend_unavailable(_: Request, exc: BackendUnavailableError) -> JSONResponse:
        return _error(503, "backend_unavailable", str(exc))

    @api.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Keep the documented error envelope for unexpected failures, but send the
        # client only a reference; the traceback stays in the server log.
        incident = uuid4().hex[:12]
        logger.exception("Unhandled error [%s] on %s", incident, request.url.path)
        return _error(
            500,
            "internal_error",
            "The server failed to handle this request. See the server log for details.",
            {"incident": incident},
        )

    @api.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "type": item.get("type"),
                "loc": list(item.get("loc", ())),
                "msg": item.get("msg"),
                "input": item.get("input"),
            }
            for item in exc.errors()
        ]
        return _error(
            422,
            "validation_error",
            "Request validation failed",
            {"errors": errors},
        )

    router = APIRouter(prefix="/api/v1")

    @router.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=version())

    @router.get("/ready", response_model=HealthResponse, tags=["system"])
    def ready() -> HealthResponse:
        configurations = service.configurations()
        demo = next((item for item in configurations if item.id == "demo"), None)
        return HealthResponse(
            status="ok" if demo and demo.ready_for_inference else "not_ready",
            version=version(),
            simulated=demo.simulated if demo else None,
        )

    @router.get("/configurations", response_model=list[ConfigurationInfo], tags=["configuration"])
    def configurations() -> list[ConfigurationInfo]:
        return service.configurations()

    @router.get("/models", response_model=list[ModelInfo], tags=["configuration"])
    def models(config: str = Query("demo")) -> list[ModelInfo]:
        return service.models(config)

    @router.get("/examples", response_model=list[ExampleQuery], tags=["configuration"])
    def examples(config: str = Query("demo")) -> list[ExampleQuery]:
        return service.examples(config)

    @router.post("/inference", response_model=InferenceResponse, tags=["inference"])
    def inference(body: InferenceRequest) -> InferenceResponse:
        return service.infer(body)

    @router.get("/traces/{trace_id}", response_model=dict[str, Any], tags=["inference"])
    def trace(trace_id: str) -> dict[str, Any]:
        return service.trace(trace_id)

    @router.get("/experiments", response_model=ExperimentList, tags=["experiments"])
    def experiments() -> ExperimentList:
        return ExperimentList(experiments=service.experiments())

    @router.get("/experiments/{run_id}", response_model=ExperimentDetail, tags=["experiments"])
    def experiment(run_id: str) -> ExperimentDetail:
        return service.experiment(run_id)

    @router.get(
        "/experiments/{run_id}/metrics",
        response_model=dict[str, Any],
        tags=["experiments"],
    )
    def metrics(run_id: str) -> dict[str, Any]:
        return service.metrics(run_id)

    @router.get("/experiments/{run_id}/artifacts/{kind}/{name}", tags=["experiments"])
    def artifact(run_id: str, kind: str, name: str) -> FileResponse:
        return FileResponse(service.artifact(run_id, kind, name))

    api.include_router(router)

    @api.get("/", include_in_schema=False)
    def index() -> dict[str, str]:
        return {"name": "RouteGuard-LLM API", "docs": "/docs", "health": "/api/v1/health"}

    return api


app = create_app()
