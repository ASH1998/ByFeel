"""FastAPI application for the local ByFeel MVP."""

from __future__ import annotations

import os
from base64 import b64decode
from binascii import Error as Base64Error
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .checkpoint import GeminiCheckpointEvaluator
from .evidence import EvidenceStore, InMemoryEvidenceStore
from .gemini import ByFeelModelRouter, GeminiStructuredClient
from .models import (
    EvidenceRef,
    LearnerObservation,
    LearnerProgress,
    RepairOutcome,
    TeacherDemo,
    TeachingOutcome,
)
from .repositories import InMemoryRepository, NotFoundError
from .service import ByFeelService

APP_VERSION = "0.2.0"


class ClarificationRequest(BaseModel):
    clarification: str = Field(min_length=1, max_length=4000)
    evidence: EvidenceRef | None = None


class StartLearnerRequest(BaseModel):
    procedure_id: str = Field(min_length=1, max_length=200)


class EvidenceUploadRequest(BaseModel):
    content_base64: str = Field(min_length=1)
    content_type: str
    source: Literal["teacher", "learner", "test"]


def build_local_components() -> tuple[ByFeelService, EvidenceStore]:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    model = os.getenv("GOOGLE_MODEL", "").strip()
    lite_model = os.getenv("GOOGLE_MODEL_LITE", "").strip()
    if not api_key or not model or not lite_model:
        raise RuntimeError(
            "GOOGLE_API_KEY, GOOGLE_MODEL, and GOOGLE_MODEL_LITE must be set in .env"
        )
    main_client = GeminiStructuredClient(api_key=api_key, model=model)
    lite_client = GeminiStructuredClient(api_key=api_key, model=lite_model)
    client = ByFeelModelRouter(main=main_client, lite=lite_client)
    repository_name = os.getenv("BYFEEL_REPOSITORY", "memory").strip().lower()
    if repository_name == "firestore":
        from .evidence import CloudStorageEvidenceStore
        from .firestore_repository import FirestoreRepository

        namespace = os.getenv("BYFEEL_TEST_NAMESPACE", "local-mvp").strip()
        repository = FirestoreRepository(
            namespace=namespace,
            database=os.getenv("FIRESTORE_DATABASE", "(default)"),
        )
        evidence_store: EvidenceStore = CloudStorageEvidenceStore(
            bucket_name=os.getenv("EVIDENCE_BUCKET", ""),
            namespace=namespace,
        )
    elif repository_name == "memory":
        repository = InMemoryRepository()
        evidence_store = InMemoryEvidenceStore()
    else:
        raise RuntimeError("BYFEEL_REPOSITORY must be memory or firestore")
    service = ByFeelService(
        repository=repository,
        teaching_client=client,
        checkpoint_evaluator=GeminiCheckpointEvaluator(lite_client, evidence_store),
    )
    return service, evidence_store


def create_app(
    service: ByFeelService | None = None, evidence_store: EvidenceStore | None = None
) -> FastAPI:
    app = FastAPI(title="ByFeel local MVP", version=APP_VERSION)
    app.state.byfeel_service = service
    app.state.evidence_store = evidence_store or InMemoryEvidenceStore()

    def get_service() -> ByFeelService:
        if app.state.byfeel_service is None:
            app.state.byfeel_service, app.state.evidence_store = build_local_components()
        return app.state.byfeel_service

    def get_evidence_store() -> EvidenceStore:
        get_service()
        return app.state.evidence_store

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except NotFoundError as exc:
            response = JSONResponse(
                status_code=404,
                content={
                    "error": {"code": "not_found", "message": str(exc), "request_id": request_id}
                },
            )
        except ValueError as exc:
            response = JSONResponse(
                status_code=409,
                content={
                    "error": {
                        "code": "invalid_state",
                        "message": str(exc),
                        "request_id": request_id,
                    }
                },
            )
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_failed",
                    "message": "Request validation failed",
                    "request_id": request.state.request_id,
                    "details": exc.errors(),
                }
            },
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        get_service()
        return {"status": "ready"}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"version": APP_VERSION}

    @app.post("/api/teacher/sessions", response_model=TeachingOutcome)
    def teach(demo: TeacherDemo) -> TeachingOutcome:
        return get_service().teach(demo)

    @app.post("/api/procedures/{procedure_id}/clarifications", response_model=RepairOutcome)
    def clarify(procedure_id: str, request: ClarificationRequest) -> RepairOutcome:
        return get_service().clarify(procedure_id, request.clarification, request.evidence)

    @app.post("/api/evidence", response_model=EvidenceRef)
    def upload_evidence(request: EvidenceUploadRequest) -> EvidenceRef:
        try:
            data = b64decode(request.content_base64, validate=True)
        except (Base64Error, ValueError) as exc:
            raise ValueError("content_base64 is not valid base64") from exc
        return get_evidence_store().put(
            data,
            content_type=request.content_type,
            source=request.source,
        )

    @app.get("/api/procedures/{procedure_id}")
    def procedure(procedure_id: str):
        return get_service().repository.get_procedure(procedure_id)

    @app.post("/api/learner/sessions", response_model=LearnerProgress)
    def start_learner(request: StartLearnerRequest) -> LearnerProgress:
        return get_service().start_learner(request.procedure_id)

    @app.post("/api/learner/sessions/{session_id}/checkpoints", response_model=LearnerProgress)
    def checkpoint(session_id: str, observation: LearnerObservation) -> LearnerProgress:
        return get_service().checkpoint(session_id, observation)

    @app.get("/api/learner/sessions/{session_id}/events")
    def events(session_id: str):
        return get_service().repository.list_learner_events(session_id)

    return app


app = create_app()
