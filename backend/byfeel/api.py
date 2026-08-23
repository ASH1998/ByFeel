"""FastAPI application for the local ByFeel MVP."""

from __future__ import annotations

import os
from base64 import b64decode
from binascii import Error as Base64Error
from hmac import compare_digest
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .adk_runtime import AdkLearnerCoachRuntime, AdkProbeRuntime, AdkTeachingPartnerRuntime
from .evidence import EvidenceStore, InMemoryEvidenceStore
from .gate_c import GateCExperimentRunner
from .gemini import ByFeelModelRouter, GeminiStructuredClient
from .media_ingest import (
    BROWSER_EVIDENCE_MAX_FRAMES,
    BROWSER_EVIDENCE_MIN_FRAMES,
    BrowserEvidenceFrame,
    BrowserEvidencePackage,
    MediaDraft,
)
from .models import (
    ApprovedDemonstration,
    BlockerReview,
    BlockerReviewDecision,
    EvidenceRef,
    GateCArm,
    GateCArmRun,
    GateCAttemptResult,
    GateCAttestation,
    GateCComparisonReport,
    GateCExperiment,
    LearnerObservation,
    LearnerProgress,
    RepairOutcome,
    TeacherSession,
    TeachingOutcome,
)
from .repositories import ConflictError, InMemoryRepository, NotFoundError
from .service import STREAM_VIDEO_UPLOAD_LIMIT_BYTES, ByFeelService

APP_VERSION = "0.4.0"
MAX_EVIDENCE_PACKAGE_REQUEST_BYTES = 8 * 1024 * 1024


def media_review_payload(session_id: str, draft: MediaDraft) -> dict[str, object]:
    """Return review-safe teacher data without private server paths or raw media."""

    return {
        "session_id": session_id,
        "status": "review_required",
        "source_sha256": draft.source_sha256,
        "source_hash_strategy": draft.source_hash_strategy,
        "source_kind": draft.source_kind,
        "speech_mode": draft.speech_mode.value,
        "sampling_strategy": draft.sampling_strategy,
        "metadata": draft.metadata.model_dump(mode="json"),
        "model_media": {
            "strategy": draft.sampling_strategy,
            "source_media_sent_to_model": draft.source_media_sent_to_model,
            "low_bandwidth_proxy_used": draft.low_bandwidth_proxy_path is not None,
            "payload_bytes": draft.model_payload_bytes,
            "payload_limit_bytes": draft.model_payload_limit_bytes,
        },
        "frames": [
            {
                "sample_id": sample.sample_id,
                "timestamp_seconds": sample.timestamp_seconds,
                "url": f"/api/teacher/sessions/{session_id}/frames/{sample.sample_id}",
            }
            for sample in draft.frame_samples
        ],
        "analysis": draft.analysis.model_dump(mode="json"),
        "human_approval_required": True,
    }


class ClarificationRequest(BaseModel):
    clarification: str = Field(min_length=1, max_length=4000)
    evidence: EvidenceRef | None = None


class StartLearnerRequest(BaseModel):
    procedure_id: str = Field(min_length=1, max_length=200)


class BlockerReviewRequest(BaseModel):
    decision: BlockerReviewDecision
    reason: str = Field(min_length=10, max_length=4000)


class EvidenceUploadRequest(BaseModel):
    content_base64: str = Field(min_length=1)
    content_type: str
    source: Literal["teacher", "learner", "test"]


class CreateTeacherSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=200)
    learner_goal: str = Field(min_length=1, max_length=500)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    speech_mode: Literal["silent", "spoken", "unsure"]


class TeacherVideoRequest(BaseModel):
    content_base64: str = Field(min_length=1)
    content_type: Literal["video/mp4", "video/webm", "video/quicktime"]


class BrowserEvidenceFrameRequest(BaseModel):
    sample_id: str = Field(pattern=r"^frame-[0-9]{2}$")
    timestamp_seconds: float = Field(ge=0)
    width: int = Field(gt=0, le=768)
    height: int = Field(gt=0, le=768)
    content_type: Literal["image/jpeg", "image/webp"]
    content_base64: str = Field(min_length=44)
    brightness_score: float = Field(ge=0, le=1)
    sharpness_score: float = Field(ge=0, le=1)
    quality_status: Literal["usable", "review"]


class BrowserEvidencePackageRequest(BaseModel):
    policy_version: Literal["browser-evidence-v1"]
    capture_kind: Literal["file", "camera"]
    source_pseudonym: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fingerprint_strategy: Literal["sampled-sha256-v1"]
    source_size_bytes: int = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    source_width: int = Field(gt=0)
    source_height: int = Field(gt=0)
    evidence_sampling_fps: float = Field(gt=0)
    frames: list[BrowserEvidenceFrameRequest] = Field(
        min_length=BROWSER_EVIDENCE_MIN_FRAMES,
        max_length=BROWSER_EVIDENCE_MAX_FRAMES,
    )


class FactualApprovalRequest(BaseModel):
    approved_factual_record: str = Field(min_length=20, max_length=20000)


class CreateGateCExperimentRequest(BaseModel):
    learner_pseudonym: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$",
    )
    procedure_id: str = Field(min_length=1, max_length=200)
    baseline_version_id: str = Field(min_length=1, max_length=200)
    byfeel_version_id: str = Field(min_length=1, max_length=200)
    checkpoint_step_id: str = Field(min_length=1, max_length=200)
    deliberate_incorrect_state: str = Field(min_length=10, max_length=2000)
    safety_confirmed: bool = False


class GateCAttemptRequest(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    is_deliberate_incorrect: bool = False
    is_correction: bool = False
    evidence: EvidenceRef | None = None


class GateCAttestationRequest(BaseModel):
    fresh_learner_confirmed: bool = False
    teacher_procedure_confirmed: bool = False
    recorded_without_personal_data: bool = False
    reviewer_note: str = Field(min_length=10, max_length=4000)


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
        checkpoint_evaluator=AdkLearnerCoachRuntime(
            model=lite_model,
            evidence_store=evidence_store,
        ),
        probe_runtime=AdkProbeRuntime(model=model),
        teaching_runtime=AdkTeachingPartnerRuntime(model=lite_model),
        media_client=lite_client,
        evidence_store=evidence_store,
    )
    return service, evidence_store


def create_app(
    service: ByFeelService | None = None, evidence_store: EvidenceStore | None = None
) -> FastAPI:
    app = FastAPI(title="ByFeel local MVP", version=APP_VERSION)
    app.state.byfeel_service = service
    app.state.evidence_store = (
        evidence_store or getattr(service, "evidence_store", None) or InMemoryEvidenceStore()
    )
    app.state.gate_c_runner = None

    def get_service() -> ByFeelService:
        if app.state.byfeel_service is None:
            app.state.byfeel_service, app.state.evidence_store = build_local_components()
        return app.state.byfeel_service

    def get_evidence_store() -> EvidenceStore:
        get_service()
        return app.state.evidence_store

    def get_gate_c_runner() -> GateCExperimentRunner:
        if app.state.gate_c_runner is None:
            service = get_service()
            app.state.gate_c_runner = GateCExperimentRunner(
                repository=service.repository,
                learner_service=service,
            )
        return app.state.gate_c_runner

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        request.state.request_id = request_id
        access_code = os.getenv("BYFEEL_ACCESS_CODE", "").strip()
        if request.url.path.startswith("/api/") and access_code:
            supplied_code = request.headers.get("x-byfeel-access-code", "")
            if not compare_digest(supplied_code, access_code):
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "access_denied",
                            "message": "A valid ByFeel judge access code is required",
                            "request_id": request_id,
                        }
                    },
                )
                response.headers["x-request-id"] = request_id
                return response
        try:
            response = await call_next(request)
        except NotFoundError as exc:
            response = JSONResponse(
                status_code=404,
                content={
                    "error": {"code": "not_found", "message": str(exc), "request_id": request_id}
                },
            )
        except (ConflictError, ValueError) as exc:
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

    @app.post("/api/teacher/sessions", response_model=TeacherSession)
    def create_teacher_session(request: CreateTeacherSessionRequest) -> TeacherSession:
        return get_service().create_teacher_session(**request.model_dump())

    @app.post("/api/demo/seeded-rehearsal")
    def seeded_rehearsal() -> dict[str, object]:
        outcome = get_service().seed_rehearsal()
        report = get_gate_c_runner().seed_rehearsal(outcome.procedure.id)
        payload = outcome.model_dump(mode="json")
        payload["gate_c"] = report.model_dump(mode="json")
        return payload

    @app.get("/api/teacher/sessions/{session_id}")
    def teacher_session(session_id: str):
        service = get_service()
        session = service.repository.get_teacher_session(session_id)
        response: dict[str, object] = {"session": session.model_dump(mode="json")}
        if session.media_run_id:
            response["media_review"] = media_review_payload(
                session_id,
                service.repository.get_media_draft(session_id),
            )
        if session.procedure_id:
            response["procedure"] = service.repository.get_procedure(
                session.procedure_id
            ).model_dump(mode="json")
            try:
                probe = service.repository.latest_probe_run(session.procedure_id, "after_repair")
            except NotFoundError:
                probe = service.repository.latest_probe_run(session.procedure_id, "before_repair")
            response["probe_run"] = probe.model_dump(mode="json")
        return response

    @app.post("/api/teacher/sessions/{session_id}/media")
    def process_teacher_media(session_id: str, request: TeacherVideoRequest):
        if os.getenv("BYFEEL_ALLOW_LOCAL_RAW_VIDEO", "0") != "1":
            raise ValueError(
                "raw video upload is disabled; submit a browser evidence package instead"
            )
        try:
            video = b64decode(request.content_base64, validate=True)
        except (Base64Error, ValueError) as exc:
            raise ValueError("content_base64 is not valid base64") from exc
        draft = get_service().process_teacher_video(
            session_id,
            video=video,
            content_type=request.content_type,
        )
        return media_review_payload(session_id, draft)

    @app.post("/api/teacher/sessions/{session_id}/media-stream")
    async def stream_teacher_media(session_id: str, request: Request):
        if os.getenv("BYFEEL_ALLOW_LOCAL_RAW_VIDEO", "0") != "1":
            raise ValueError(
                "raw video streaming is disabled; submit a browser evidence package instead"
            )
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > STREAM_VIDEO_UPLOAD_LIMIT_BYTES:
            raise ValueError("teacher video exceeds the 512 MiB streaming limit")
        service = get_service()
        source = service.begin_teacher_video_upload(session_id, content_type=content_type)
        received = 0
        stream_complete = False
        try:
            with source.open("xb") as destination:
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > STREAM_VIDEO_UPLOAD_LIMIT_BYTES:
                        raise ValueError("teacher video exceeds the 512 MiB streaming limit")
                    destination.write(chunk)
            stream_complete = True
            draft = service.finish_teacher_video_upload(
                session_id,
                source=source,
                content_type=content_type,
            )
        except Exception as exc:
            service.fail_teacher_video_upload(session_id, exc)
            if not stream_complete and source.exists():
                source.unlink()
            raise
        return media_review_payload(session_id, draft)

    @app.post("/api/teacher/sessions/{session_id}/evidence-package")
    async def process_teacher_evidence_package(
        session_id: str,
        request: Request,
    ):
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > MAX_EVIDENCE_PACKAGE_REQUEST_BYTES:
            raise ValueError("browser evidence request exceeds the 8 MiB transport limit")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_EVIDENCE_PACKAGE_REQUEST_BYTES:
                raise ValueError("browser evidence request exceeds the 8 MiB transport limit")
        try:
            incoming = BrowserEvidencePackageRequest.model_validate_json(bytes(body))
            frames = []
            for frame in incoming.frames:
                try:
                    content = b64decode(frame.content_base64, validate=True)
                except (Base64Error, ValueError) as exc:
                    raise ValueError(
                        f"{frame.sample_id} content_base64 is not valid base64"
                    ) from exc
                frames.append(
                    BrowserEvidenceFrame(
                        **frame.model_dump(exclude={"content_base64"}),
                        content=content,
                    )
                )
            package = BrowserEvidencePackage(
                **incoming.model_dump(exclude={"frames"}),
                frames=frames,
            )
        except RequestValidationError:
            raise
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError("browser evidence package is invalid") from exc
        draft = get_service().process_teacher_evidence_package(
            session_id,
            package=package,
        )
        return media_review_payload(session_id, draft)

    @app.get("/api/teacher/sessions/{session_id}/frames/{sample_id}")
    def teacher_frame(session_id: str, sample_id: str):
        draft = get_service().repository.get_media_draft(session_id)
        try:
            sample = next(item for item in draft.frame_samples if item.sample_id == sample_id)
        except StopIteration as exc:
            raise NotFoundError(f"frame sample {sample_id!r} was not found") from exc
        if sample.evidence is not None:
            from fastapi.responses import Response

            try:
                content = get_evidence_store().get(sample.evidence)
            except LookupError as exc:
                raise NotFoundError(
                    f"frame evidence {sample.evidence.evidence_id!r} was not found"
                ) from exc
            return Response(content=content, media_type=sample.evidence.content_type)
        return FileResponse(sample.path, media_type="image/jpeg")

    @app.post(
        "/api/teacher/sessions/{session_id}/factual-approval",
        response_model=ApprovedDemonstration,
    )
    def approve_factual_record(
        session_id: str, request: FactualApprovalRequest
    ) -> ApprovedDemonstration:
        return get_service().approve_factual_record(
            session_id,
            request.approved_factual_record,
        )

    @app.post(
        "/api/teacher/sessions/{session_id}/extract",
        response_model=TeachingOutcome,
    )
    def extract_approved_demonstration(session_id: str) -> TeachingOutcome:
        return get_service().extract_approved_demonstration(session_id)

    @app.post("/api/procedures/{procedure_id}/clarifications", response_model=RepairOutcome)
    def clarify(procedure_id: str, request: ClarificationRequest) -> RepairOutcome:
        return get_service().clarify(procedure_id, request.clarification, request.evidence)

    @app.post("/api/probe-runs/{probe_run_id}/review", response_model=BlockerReview)
    def review_blocker(probe_run_id: str, request: BlockerReviewRequest) -> BlockerReview:
        return get_service().review_blocker(probe_run_id, request.decision, request.reason)

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

    @app.post("/api/procedures/{procedure_id}/learner-approval")
    def approve_procedure_for_learner(procedure_id: str):
        return get_service().approve_procedure_for_learner(procedure_id)

    @app.post("/api/learner/sessions", response_model=LearnerProgress)
    def start_learner(request: StartLearnerRequest) -> LearnerProgress:
        return get_service().start_learner(request.procedure_id)

    @app.post("/api/learner/sessions/{session_id}/checkpoints", response_model=LearnerProgress)
    def checkpoint(session_id: str, observation: LearnerObservation) -> LearnerProgress:
        return get_service().checkpoint(session_id, observation)

    @app.get("/api/learner/sessions/{session_id}", response_model=LearnerProgress)
    def resume_learner(session_id: str) -> LearnerProgress:
        return get_service().resume_learner(session_id)

    @app.get("/api/learner/sessions/{session_id}/events")
    def events(session_id: str):
        return get_service().repository.list_learner_events(session_id)

    @app.post("/api/gate-c/experiments", response_model=GateCExperiment)
    def create_gate_c_experiment(request: CreateGateCExperimentRequest) -> GateCExperiment:
        return get_gate_c_runner().create_experiment(**request.model_dump())

    @app.get("/api/gate-c/experiments/{experiment_id}")
    def gate_c_experiment(experiment_id: str) -> dict[str, object]:
        return get_gate_c_runner().snapshot(experiment_id)

    @app.get("/api/gate-c/experiments/{experiment_id}/report", response_model=GateCComparisonReport)
    def gate_c_report(experiment_id: str) -> GateCComparisonReport:
        return get_gate_c_runner().report(experiment_id)

    @app.post(
        "/api/gate-c/experiments/{experiment_id}/arms/{arm}/start",
        response_model=GateCArmRun,
    )
    def start_gate_c_arm(experiment_id: str, arm: GateCArm) -> GateCArmRun:
        return get_gate_c_runner().start_arm(experiment_id, arm)

    @app.post("/api/gate-c/arms/{arm_run_id}/attempts", response_model=GateCAttemptResult)
    def record_gate_c_attempt(arm_run_id: str, request: GateCAttemptRequest) -> GateCAttemptResult:
        return get_gate_c_runner().record_attempt(
            arm_run_id,
            description=request.description,
            evidence=request.evidence,
            is_deliberate_incorrect=request.is_deliberate_incorrect,
            is_correction=request.is_correction,
        )

    @app.post("/api/gate-c/arms/{arm_run_id}/finalize", response_model=GateCArmRun)
    def finalize_gate_c_arm(arm_run_id: str) -> GateCArmRun:
        return get_gate_c_runner().finalize_arm(arm_run_id)

    @app.post(
        "/api/gate-c/experiments/{experiment_id}/attestation",
        response_model=GateCAttestation,
    )
    def attest_gate_c(experiment_id: str, request: GateCAttestationRequest) -> GateCAttestation:
        return get_gate_c_runner().attest(experiment_id, **request.model_dump())

    @app.get("/api/judge/evidence/{procedure_id}")
    def judge_evidence(procedure_id: str):
        repository = get_service().repository
        repository.get_procedure(procedure_id)
        gate_c_experiments = repository.list_gate_c_experiments(procedure_id)
        return {
            "gate_a": {
                "status": "incomplete",
                "recorded_calls_used": 12,
                "call_ceiling": 18,
                "actual_billed_cost": "unknown",
                "limitation": (
                    "UI and ADK integration do not pass Gate A; real-demonstration evidence and "
                    "final human reliability review remain required."
                ),
            },
            "procedure_versions": repository.list_procedure_versions(procedure_id),
            "probe_runs": repository.list_probe_runs(procedure_id),
            "blocker_reviews": repository.list_blocker_reviews(procedure_id),
            "corrections": repository.list_corrections(procedure_id),
            "agent_runs": repository.list_agent_runs(procedure_id),
            "audit_events": repository.list_audit_events(procedure_id),
            "gate_c": [
                get_gate_c_runner().report(item.experiment_id) for item in gate_c_experiments
            ],
            "blindness_boundary": {
                "probe_input": "frozen LearnerProcedure projection",
                "excluded": [
                    "raw teacher video and audio",
                    "teacher-only factual draft",
                    "hidden notes and evidence",
                    "canonical repository access",
                    "correction history",
                    "previous probe session or reasoning",
                ],
                "tool_policy": ["read_learner_artifact", "set_model_response"],
            },
        }

    return app


app = create_app()
