"""FastAPI application contracts for prediction, retrieval, grounding, and local operations."""

from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, ApplicationConfig, load_config
from .observability import MetricsRegistry, build_logger
from .persistence import PersistenceError, SQLiteStore
from .services import ApplicationDependencyError, ApplicationInputError, ApplicationServices

logger = build_logger()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PredictionRequest(StrictModel):
    features: dict[str, float]


class RetrievalRequest(StrictModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)


class GroundedAnswerRequest(StrictModel):
    query: str = Field(min_length=1)


class EvaluationRequest(StrictModel):
    operation: Literal["predict", "retrieve", "answer"]
    outcome: Literal["pass", "fail", "needs_review"]
    related_request_id: str | None = Field(default=None, min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)


class PredictionResponse(StrictModel):
    request_id: str
    status: Literal["scored"]
    candidate_id: str
    model_sha256: str
    feature_count: int
    feature_names_sha256: str
    unusualness_score: float
    threshold: float
    alarm: bool
    interpretation: str


class PredictionSchemaResponse(StrictModel):
    candidate_id: str
    feature_count: int
    feature_names: list[str]
    feature_names_sha256: str
    matrix_dtype: str
    threshold: float
    threshold_comparison: str
    interpretation: str


class RetrievalResponse(StrictModel):
    request_id: str
    status: Literal["retrieved"]
    query: str
    top_k: int
    result_count: int
    results: list[dict[str, Any]]


class GroundedAnswerResponse(StrictModel):
    request_id: str
    status: str
    reason_code: str
    intent: str
    answer: str
    citations: list[dict[str, Any]]
    evidence_chunk_count: int
    general_guidance_available: bool
    schema_version: int
    grounding_id: str
    grounding_config_sha256: str
    retrieval_candidate_count: int
    reranked_candidate_count: int
    top_reranked: list[dict[str, Any]]


class ErrorResponse(StrictModel):
    request_id: str | None = None
    error_code: str
    message: str


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else uuid.uuid4().hex


def _safe_persist_event(
    store: SQLiteStore,
    *,
    event_name: str,
    severity: str,
    details: dict[str, Any],
    request_id: str | None = None,
) -> None:
    try:
        store.record_event(
            event_name=event_name,
            severity=severity,
            details=details,
            request_id=request_id,
        )
    except PersistenceError:
        logger.exception("application event persistence failed", extra={"event_name": event_name, "request_id": request_id})


def create_app(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
    config: ApplicationConfig | None = None,
    services: ApplicationServices | Any | None = None,
    store: SQLiteStore | None = None,
    metrics: MetricsRegistry | None = None,
) -> FastAPI:
    """Create the bounded local application without rebuilding governed artifacts."""
    application_config = config or load_config(config_path, project_root=project_root)
    service_container = services or ApplicationServices(application_config)
    persistence = store or SQLiteStore(
        application_config.resolve_path(application_config.persistence["database_path"]),
        max_records=application_config.persistence["max_records"],
        max_evaluations=application_config.persistence["max_evaluations"],
        max_events=application_config.persistence["max_events"],
    )
    persistence.initialize()
    registry = metrics or MetricsRegistry()

    app = FastAPI(
        title=application_config.api["title"],
        version=application_config.api["version"],
        description=(
            "Bounded local API over frozen predictive-maintenance and governed technical-knowledge artifacts. "
            "This interface does not refit models, retune retrieval, or claim production deployment."
        ),
    )
    app.state.application_config = application_config
    app.state.services = service_container
    app.state.store = persistence
    app.state.metrics = registry

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        registry.increment("http_requests_total")
        try:
            response = await call_next(request)
        except Exception:
            registry.increment("http_unhandled_errors_total")
            _safe_persist_event(
                persistence,
                event_name="http_unhandled_exception",
                severity="error",
                details={"method": request.method, "path": request.url.path},
                request_id=request_id,
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        response.headers["X-Request-ID"] = request_id
        registry.increment(f"http_status_{response.status_code}_total")
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "event_name": "http_request_completed",
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        _safe_persist_event(
            persistence,
            event_name="http_request_completed",
            severity="info" if response.status_code < 500 else "error",
            details={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
            request_id=request_id,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        registry.increment("validation_errors_total")
        request_id = _request_id(request)
        _safe_persist_event(
            persistence,
            event_name="request_validation_failed",
            severity="warning",
            details={"error_count": len(exc.errors())},
            request_id=request_id,
        )
        return JSONResponse(
            status_code=422,
            content={"request_id": request_id, "error_code": "invalid_request", "message": "Request validation failed."},
        )

    @app.exception_handler(ApplicationInputError)
    async def application_input_error(request: Request, exc: ApplicationInputError):
        registry.increment("application_input_errors_total")
        request_id = _request_id(request)
        return JSONResponse(
            status_code=422,
            content={"request_id": request_id, "error_code": "invalid_application_input", "message": str(exc)},
        )

    @app.exception_handler(ApplicationDependencyError)
    async def dependency_error(request: Request, exc: ApplicationDependencyError):
        registry.increment("dependency_errors_total")
        request_id = _request_id(request)
        _safe_persist_event(
            persistence,
            event_name="governed_dependency_unavailable",
            severity="error",
            details={"dependency_error": str(exc)},
            request_id=request_id,
        )
        return JSONResponse(
            status_code=503,
            content={
                "request_id": request_id,
                "error_code": "governed_dependency_unavailable",
                "message": "A required governed local artifact or capability is unavailable or invalid.",
            },
        )

    @app.exception_handler(PersistenceError)
    async def persistence_error(request: Request, exc: PersistenceError):
        registry.increment("persistence_errors_total")
        request_id = _request_id(request)
        logger.error("persistence failure", extra={"request_id": request_id, "event_name": "persistence_failure"})
        return JSONResponse(
            status_code=503,
            content={
                "request_id": request_id,
                "error_code": "persistence_unavailable",
                "message": "Local demonstration persistence is unavailable.",
            },
        )

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "alive", "application_id": application_config.raw["application_id"]}

    @app.get("/health/ready")
    def health_ready():
        result = service_container.readiness()
        try:
            result["persistence"] = {"available": True, **persistence.counts()}
        except PersistenceError:
            result["status"] = "not_ready"
            result["persistence"] = {"available": False}
        code = 200 if result["status"] == "ready" else 503
        return JSONResponse(status_code=code, content=result)

    prefix = application_config.api["prefix"]
    query_limit = int(application_config.api["query_max_characters"])
    default_top_k = int(application_config.api["retrieval_default_top_k"])
    max_top_k = int(application_config.api["retrieval_max_top_k"])
    history_default = int(application_config.api["history_default_limit"])
    history_max = int(application_config.api["history_max_limit"])

    @app.get(f"{prefix}/prediction/schema", response_model=PredictionSchemaResponse)
    def prediction_schema():
        return service_container.prediction.schema()

    @app.post(
        f"{prefix}/predict",
        response_model=PredictionResponse,
        responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def predict(payload: PredictionRequest, request: Request):
        request_id = _request_id(request)
        result = service_container.prediction.predict(payload.features)
        response = {"request_id": request_id, **result}
        request_record: dict[str, Any]
        if application_config.security["persist_raw_feature_values"]:
            request_record = {"features": payload.features}
        else:
            schema = service_container.prediction.schema()
            request_record = {
                "feature_count": len(payload.features),
                "feature_names_sha256": schema["feature_names_sha256"],
                "raw_feature_values_persisted": False,
            }
        persistence.record_interaction(
            request_id=request_id,
            operation="predict",
            status=result["status"],
            request_payload=request_record,
            response_payload=result,
        )
        registry.increment("prediction_requests_total")
        registry.increment("prediction_alarms_total" if result["alarm"] else "prediction_non_alarms_total")
        return response

    @app.post(
        f"{prefix}/retrieve",
        response_model=RetrievalResponse,
        responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def retrieve_endpoint(payload: RetrievalRequest, request: Request):
        query = payload.query.strip()
        if len(query) > query_limit:
            raise ApplicationInputError(f"query exceeds configured maximum of {query_limit} characters")
        top_k = default_top_k if payload.top_k is None else payload.top_k
        if top_k > max_top_k:
            raise ApplicationInputError(f"top_k exceeds configured maximum of {max_top_k}")
        request_id = _request_id(request)
        results = service_container.knowledge.retrieve(query, top_k)
        result = {
            "status": "retrieved",
            "query": query,
            "top_k": top_k,
            "result_count": len(results),
            "results": results,
        }
        persistence.record_interaction(
            request_id=request_id,
            operation="retrieve",
            status="retrieved",
            request_payload={"query": query, "top_k": top_k},
            response_payload={"result_count": len(results)},
        )
        registry.increment("retrieval_requests_total")
        registry.increment("retrieval_empty_results_total" if not results else "retrieval_nonempty_results_total")
        return {"request_id": request_id, **result}

    @app.post(
        f"{prefix}/answer",
        response_model=GroundedAnswerResponse,
        responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def grounded_answer(payload: GroundedAnswerRequest, request: Request):
        query = payload.query.strip()
        if len(query) > query_limit:
            raise ApplicationInputError(f"query exceeds configured maximum of {query_limit} characters")
        request_id = _request_id(request)
        result = service_container.knowledge.answer(query)
        persistence.record_interaction(
            request_id=request_id,
            operation="answer",
            status=str(result["status"]),
            request_payload={"query": query},
            response_payload={
                "status": result["status"],
                "reason_code": result["reason_code"],
                "intent": result["intent"],
                "citation_count": len(result["citations"]),
            },
        )
        registry.increment("grounded_answer_requests_total")
        registry.increment(f"grounded_answer_status_{result['status']}_total")
        return {"request_id": request_id, **result}

    @app.post(f"{prefix}/evaluations")
    def record_evaluation(payload: EvaluationRequest, request: Request) -> dict[str, Any]:
        request_id = _request_id(request)
        evaluation_id = uuid.uuid4().hex
        persistence.record_evaluation(
            evaluation_id=evaluation_id,
            related_request_id=payload.related_request_id,
            operation=payload.operation,
            outcome=payload.outcome,
            note=payload.note,
        )
        registry.increment("application_evaluations_total")
        registry.increment(f"application_evaluation_outcome_{payload.outcome}_total")
        return {
            "status": "recorded",
            "request_id": request_id,
            "evaluation_id": evaluation_id,
            "scope": "local_demonstration_review_not_model_or_rag_benchmark_evidence",
        }

    @app.get(f"{prefix}/evaluations")
    def evaluations(limit: int = Query(default=history_default, ge=1, le=history_max)) -> dict[str, Any]:
        records = persistence.recent_evaluations(limit=limit)
        return {"status": "ok", "evaluation_count": len(records), "evaluations": records}

    @app.get(f"{prefix}/history")
    def history(
        limit: int = Query(default=history_default, ge=1, le=history_max),
        operation: str | None = Query(default=None),
    ) -> dict[str, Any]:
        records = persistence.recent_records(limit=limit, operation=operation)
        return {"status": "ok", "record_count": len(records), "records": records}

    @app.get(f"{prefix}/metrics")
    def metrics_endpoint() -> dict[str, Any]:
        return {"status": "ok", "counters": registry.snapshot(), "persistence": persistence.counts()}

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)
    config = load_config(args.config, project_root=PROJECT_ROOT)
    if config.server["require_loopback_bind"] and config.server["host"] not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing non-loopback bind for bounded local demonstration release")
    import uvicorn

    app = create_app(config=config)
    uvicorn.run(
        app,
        host=config.server["host"],
        port=int(config.server["port"]),
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
