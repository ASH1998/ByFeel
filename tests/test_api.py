from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime
from hashlib import sha256
from typing import TypeVar

from byfeel.adk_runtime import TeachingExecution
from byfeel.api import create_app
from byfeel.media_ingest import (
    DemonstrationEvent,
    FrameObservation,
    MediaAnalysis,
    MediaDraft,
    MediaMetadata,
    SpeechMode,
)
from byfeel.models import (
    AgentRole,
    AgentRunRecord,
    AgentRunStatus,
    CheckpointDecision,
    CheckpointEvaluation,
    IssueType,
    KnowledgeGap,
    LearnerObservation,
    LearnerProcedure,
    LearnerStep,
    ProbeReport,
    ProbeStatus,
    Procedure,
    ProcedureStep,
    RepairResult,
)
from byfeel.repositories import InMemoryRepository
from byfeel.service import ByFeelService
from fastapi.testclient import TestClient
from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def procedure(*, repaired: bool = False) -> Procedure:
    conditions = ["The crease stays flat after the hand is removed"] if repaired else []
    return Procedure(
        id="api-fold",
        title="Fold paper",
        domain="paper craft",
        learner_goal="Make a stable fold",
        steps=[
            ProcedureStep(
                step_id="step-1",
                order=1,
                action="Press the fold until it is firm enough",
                completion_conditions=conditions,
                confidence=0.5,
            )
        ],
    )


class ApiFlowClient:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        self.calls += 1
        if schema is Procedure:
            value: BaseModel = procedure()
        elif schema is RepairResult:
            value = RepairResult(
                procedure=procedure(repaired=True),
                changed_step_ids=["step-1"],
                change_summary="Added an observable completion condition.",
            )
        elif "crease stays flat" in prompt:
            value = ProbeReport(status=ProbeStatus.UNBLOCKED, summary="Ready for a learner.")
        else:
            value = ProbeReport(
                status=ProbeStatus.BLOCKED,
                summary="No observable stop condition.",
                blockers=[
                    KnowledgeGap(
                        gap_id="gap-1",
                        step_id="step-1",
                        issue_type=IssueType.MISSING_COMPLETION_CONDITION,
                        description="Firm enough is ambiguous.",
                        missing_information="An observable completion cue.",
                        severity=0.9,
                        blocks_execution=True,
                    )
                ],
                teacher_question="What shows that the crease is complete?",
            )
        return value  # type: ignore[return-value]


class ApiCheckpointEvaluator:
    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> CheckpointEvaluation:
        del procedure, step, observation
        return CheckpointEvaluation(
            decision=CheckpointDecision.ADVANCE,
            confidence=0.95,
            explanation="The teacher-derived cue is satisfied.",
            teacher_derived=True,
        )


class ApiTeachingRuntime:
    @staticmethod
    def run_record(run_id: str) -> AgentRunRecord:
        now = datetime.now(UTC)
        return AgentRunRecord(
            run_id=run_id,
            role=AgentRole.TEACHING_PARTNER,
            session_id=f"{run_id}-session",
            context_ref="api-fold",
            model="fake-adk-teaching",
            allowed_tools=[],
            status=AgentRunStatus.SUCCEEDED,
            started_at=now,
            completed_at=now,
        )

    def extract(self, approved) -> TeachingExecution:
        del approved
        return TeachingExecution(
            output=procedure(),
            agent_run=self.run_record("teaching-api-extract-run"),
        )

    def repair(self, context) -> TeachingExecution:
        del context
        return TeachingExecution(
            output=RepairResult(
                procedure=procedure(repaired=True),
                changed_step_ids=["step-1"],
                change_summary="Added an approved observable completion condition.",
                source_quotes=["crease stays flat"],
            ),
            agent_run=self.run_record("teaching-api-repair-run"),
        )


class ApiMediaClient:
    model = "fake-media"
    usage: list[dict[str, int]] = []

    def generate_with_media(self, *, system, prompt, media, schema):
        del system, prompt, schema
        return MediaAnalysis(
            teacher_spoke=False,
            frame_observations=[
                FrameObservation(
                    sample_id=f"frame-{index:02d}",
                    timestamp_seconds=float(index),
                    visible_tool_and_contact="Hands contact the paper.",
                    visible_state="The paper is progressively folded.",
                )
                for index in range(1, len(media) + 1)
            ],
            events=[
                DemonstrationEvent(
                    event_id="event-1",
                    start_seconds=0,
                    end_seconds=6,
                    visible_action="The teacher folds the paper.",
                )
            ],
            factual_demonstration_draft=(
                "The teacher folds the paper and presses until it appears firm enough."
            ),
        )


def fake_media_analyzer(**kwargs) -> MediaDraft:
    source = kwargs["source"]
    run_dir = kwargs["run_dir"]
    return MediaDraft(
        run_id=run_dir.name,
        source_path=str(source),
        source_sha256=sha256(source.read_bytes()).hexdigest(),
        title=kwargs["title"],
        domain=kwargs["domain"],
        learner_goal=kwargs["learner_goal"],
        constraints=kwargs["constraints"],
        speech_mode=SpeechMode(kwargs["speech_mode"]),
        metadata=MediaMetadata(
            duration_seconds=8,
            width=1280,
            height=720,
            frames_per_second=30,
            audio_stream_present=False,
        ),
        frame_samples=[],
        analysis_model="fake-media",
        analysis=MediaAnalysis(
            teacher_spoke=False,
            frame_observations=[
                FrameObservation(
                    sample_id="frame-1",
                    timestamp_seconds=1,
                    visible_tool_and_contact="Hands contact the paper.",
                    visible_state="The paper is folded.",
                )
            ],
            events=[
                DemonstrationEvent(
                    event_id="event-1",
                    start_seconds=0,
                    end_seconds=2,
                    visible_action="The teacher folds the paper.",
                )
            ],
            factual_demonstration_draft=(
                "The teacher folds the paper and presses until it appears firm enough."
            ),
        ),
    )


def api_service(tmp_path) -> ByFeelService:
    return ByFeelService(
        repository=InMemoryRepository(),
        teaching_client=ApiFlowClient(),
        checkpoint_evaluator=ApiCheckpointEvaluator(),
        teaching_runtime=ApiTeachingRuntime(),
        media_client=ApiMediaClient(),
        media_analyzer=fake_media_analyzer,
        run_root=tmp_path,
    )


def minimal_jpeg(width: int = 2, height: int = 2) -> bytes:
    return (
        b"\xff\xd8\xff\xe0\x00\x10"
        + b"0" * 14
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9"
    )


def browser_evidence_payload() -> dict:
    image = b64encode(minimal_jpeg()).decode()
    return {
        "policy_version": "browser-evidence-v1",
        "capture_kind": "file",
        "source_pseudonym": "src-api-test",
        "source_fingerprint": "a" * 64,
        "source_fingerprint_strategy": "sampled-sha256-v1",
        "source_size_bytes": 225_000_000,
        "duration_seconds": 8,
        "source_width": 1920,
        "source_height": 1080,
        "evidence_sampling_fps": 0.75,
        "frames": [
            {
                "sample_id": f"frame-{index:02d}",
                "timestamp_seconds": float(index),
                "width": 2,
                "height": 2,
                "content_type": "image/jpeg",
                "content_base64": image,
                "brightness_score": 0.5,
                "sharpness_score": 0.5,
                "quality_status": "usable",
            }
            for index in range(1, 7)
        ],
    }


def create_and_extract(client: TestClient) -> dict:
    session = client.post(
        "/api/teacher/sessions",
        json={
            "title": "Fold paper",
            "domain": "paper craft",
            "learner_goal": "Make a stable fold",
            "constraints": [],
            "speech_mode": "silent",
        },
    )
    assert session.status_code == 200
    session_id = session.json()["session_id"]
    media = client.post(
        f"/api/teacher/sessions/{session_id}/evidence-package",
        json=browser_evidence_payload(),
    )
    assert media.status_code == 200
    assert media.json()["human_approval_required"] is True
    approved = client.post(
        f"/api/teacher/sessions/{session_id}/factual-approval",
        json={
            "approved_factual_record": (
                "The teacher folds the paper and presses until it feels firm enough."
            )
        },
    )
    assert approved.status_code == 200
    extracted = client.post(f"/api/teacher/sessions/{session_id}/extract").json()
    resumed = client.get(f"/api/teacher/sessions/{session_id}")
    assert resumed.status_code == 200
    assert resumed.json()["procedure"]["id"] == "api-fold"
    return extracted


def test_api_raw_video_is_disabled_by_default(tmp_path) -> None:
    client = TestClient(create_app(api_service(tmp_path)))
    session = client.post(
        "/api/teacher/sessions",
        json={
            "title": "Fold a towel",
            "domain": "towel folding",
            "learner_goal": "Produce the demonstrated folded end state",
            "constraints": [],
            "speech_mode": "silent",
        },
    )
    response = client.post(
        f"/api/teacher/sessions/{session.json()['session_id']}/media-stream",
        content=b"raw video must not be accepted",
        headers={"content-type": "video/x-matroska"},
    )

    assert response.status_code == 409
    assert "raw video streaming is disabled" in response.json()["error"]["message"]


def test_api_access_code_protects_mutations_but_not_health(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BYFEEL_ACCESS_CODE", "judge-code-test")
    client = TestClient(create_app(api_service(tmp_path)))

    assert client.get("/health").status_code == 200
    denied = client.post(
        "/api/teacher/sessions",
        json={
            "title": "Fold a towel",
            "domain": "towel folding",
            "learner_goal": "Produce the demonstrated folded end state",
            "constraints": [],
            "speech_mode": "silent",
        },
    )
    allowed = client.post(
        "/api/teacher/sessions",
        headers={"x-byfeel-access-code": "judge-code-test"},
        json={
            "title": "Fold a towel",
            "domain": "towel folding",
            "learner_goal": "Produce the demonstrated folded end state",
            "constraints": [],
            "speech_mode": "silent",
        },
    )

    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "access_denied"
    assert allowed.status_code == 200


def test_api_streams_large_video_only_with_explicit_local_opt_in(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BYFEEL_ALLOW_LOCAL_RAW_VIDEO", "1")
    client = TestClient(create_app(api_service(tmp_path)))
    session = client.post(
        "/api/teacher/sessions",
        json={
            "title": "Fold a towel",
            "domain": "towel folding",
            "learner_goal": "Produce the demonstrated folded end state",
            "constraints": [],
            "speech_mode": "silent",
        },
    )
    session_id = session.json()["session_id"]

    media = client.post(
        f"/api/teacher/sessions/{session_id}/media-stream",
        content=b"fake matroska video",
        headers={"content-type": "video/x-matroska"},
    )

    assert media.status_code == 200
    assert media.json()["human_approval_required"] is True
    assert media.json()["model_media"]["source_media_sent_to_model"] is False
    assert (tmp_path / session_id / "teacher-source.mkv").read_bytes() == (b"fake matroska video")


def test_api_accepts_only_bounded_browser_evidence_from_large_source(tmp_path) -> None:
    client = TestClient(create_app(api_service(tmp_path)))
    session = client.post(
        "/api/teacher/sessions",
        json={
            "title": "Fold a towel",
            "domain": "towel folding",
            "learner_goal": "Produce the demonstrated folded end state",
            "constraints": [],
            "speech_mode": "silent",
        },
    ).json()

    media = client.post(
        f"/api/teacher/sessions/{session['session_id']}/evidence-package",
        json=browser_evidence_payload(),
    )

    assert media.status_code == 200
    assert media.json()["source_kind"] == "browser_evidence"
    assert media.json()["source_hash_strategy"] == "sampled-sha256-v1"
    assert media.json()["metadata"]["source_size_bytes"] == 225_000_000
    assert media.json()["model_media"]["payload_bytes"] < 5 * 1024 * 1024
    assert not list((tmp_path / session["session_id"]).glob("teacher-source*"))


def test_api_teacher_repair_learner_checkpoint_flow(tmp_path) -> None:
    service = api_service(tmp_path)
    client = TestClient(create_app(service))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/version").json()["version"]
    html = client.get("/")
    assert html.status_code == 200
    assert "evidence-package" in html.text
    assert "getUserMedia" in html.text
    assert "source video stays on this device" in html.text

    taught = create_and_extract(client)
    assert taught["probe_run"]["report"]["status"] == "blocked"
    probe_run_id = taught["probe_run"]["probe_run_id"]

    review = client.post(
        f"/api/probe-runs/{probe_run_id}/review",
        json={
            "decision": "genuine",
            "reason": (
                "The missing stop condition prevents the learner from deciding when to advance."
            ),
        },
    )
    assert review.status_code == 200
    assert review.json()["decision"] == "genuine"

    repaired = client.post(
        "/api/procedures/api-fold/clarifications",
        json={"clarification": "It is ready when the crease stays flat after my hand is removed."},
    )
    assert repaired.status_code == 200
    assert repaired.json()["procedure"]["status"] == "tested"

    approval = client.post("/api/procedures/api-fold/learner-approval")
    assert approval.status_code == 200
    assert approval.json()["status"] == "learner_ready"

    learner = client.post("/api/learner/sessions", json={"procedure_id": "api-fold"})
    session_id = learner.json()["session"]["session_id"]
    checked = client.post(
        f"/api/learner/sessions/{session_id}/checkpoints",
        json={"step_id": "step-1", "description": "The crease remains flat."},
    )
    assert checked.status_code == 200
    assert checked.json()["session"]["status"] == "completed"
    assert checked.json()["latest_event"]["evaluation"]["teacher_derived"] is True
    assert len(client.get(f"/api/learner/sessions/{session_id}/events").json()) == 1
    resumed_learner = client.get(f"/api/learner/sessions/{session_id}")
    assert resumed_learner.status_code == 200
    assert resumed_learner.json()["session"]["status"] == "completed"
    assert resumed_learner.json()["current_step"] is None

    evidence = client.get("/api/judge/evidence/api-fold")
    assert evidence.status_code == 200
    payload = evidence.json()
    assert payload["gate_a"]["status"] == "incomplete"
    assert payload["gate_a"]["actual_billed_cost"] == "unknown"
    assert [version["reason"] for version in payload["procedure_versions"]] == [
        "extracted",
        "repaired",
        "learner_approved",
    ]
    assert {run["role"] for run in payload["agent_runs"]} == {"teaching_partner"}
    assert len(payload["probe_runs"]) == 2
    assert len(payload["blocker_reviews"]) == 1
    assert payload["blindness_boundary"]["probe_input"] == ("frozen LearnerProcedure projection")


def test_api_repair_requires_immutable_genuine_blocker_review(tmp_path) -> None:
    service = api_service(tmp_path)
    client = TestClient(create_app(service))
    taught = create_and_extract(client)
    probe_run_id = taught["probe_run"]["probe_run_id"]

    bypass = client.post(
        "/api/procedures/api-fold/clarifications",
        json={"clarification": "The crease stays flat when released."},
    )
    assert bypass.status_code == 404
    assert "blocker review" in bypass.json()["error"]["message"]

    rejected = client.post(
        f"/api/probe-runs/{probe_run_id}/review",
        json={
            "decision": "false_blocker",
            "reason": "The complaint is optional precision and does not prevent execution.",
        },
    )
    assert rejected.status_code == 200
    duplicate = client.post(
        f"/api/probe-runs/{probe_run_id}/review",
        json={
            "decision": "genuine",
            "reason": "A second decision must never replace the immutable first review.",
        },
    )
    assert duplicate.status_code == 409
    blocked = client.post(
        "/api/procedures/api-fold/clarifications",
        json={"clarification": "The crease stays flat when released."},
    )
    assert blocked.status_code == 409
    assert "rejected this blocker" in blocked.json()["error"]["message"]


def test_api_returns_structured_not_found_error_and_request_id() -> None:
    service = ByFeelService(
        repository=InMemoryRepository(),
        teaching_client=ApiFlowClient(),
        checkpoint_evaluator=ApiCheckpointEvaluator(),
    )
    client = TestClient(create_app(service))
    response = client.get("/api/procedures/missing", headers={"x-request-id": "test-request"})
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "test-request"
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "procedure 'missing' was not found",
        "request_id": "test-request",
    }

    invalid = client.post(
        "/api/teacher/sessions",
        headers={"x-request-id": "invalid-request"},
        json={
            "title": "Too short",
            "domain": "test",
            "learner_goal": "Validate input",
            "raw_demonstration": "short",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"
    assert invalid.json()["error"]["request_id"] == "invalid-request"


def test_seeded_rehearsal_is_deterministic_and_explicitly_excluded_from_gate_a() -> None:
    model = ApiFlowClient()
    service = ByFeelService(
        repository=InMemoryRepository(),
        teaching_client=model,
        checkpoint_evaluator=ApiCheckpointEvaluator(),
    )
    client = TestClient(create_app(service))

    seeded = client.post("/api/demo/seeded-rehearsal")
    assert seeded.status_code == 200
    assert seeded.json()["gate_c"]["gate_c_decision"] == "synthetic_excluded"
    assert seeded.json()["gate_c"]["synthetic"] is True
    procedure_id = seeded.json()["procedure"]["id"]
    evidence = client.get(f"/api/judge/evidence/{procedure_id}").json()
    baseline = next(
        item for item in evidence["procedure_versions"] if item["reason"] == "extracted"
    )
    approved = next(
        item for item in evidence["procedure_versions"] if item["reason"] == "learner_approved"
    )
    real_from_seeded = client.post(
        "/api/gate-c/experiments",
        json={
            "learner_pseudonym": "learner-002",
            "procedure_id": procedure_id,
            "baseline_version_id": baseline["version_id"],
            "byfeel_version_id": approved["version_id"],
            "checkpoint_step_id": "step-1",
            "deliberate_incorrect_state": "The crease springs open after release.",
            "safety_confirmed": True,
        },
    )
    assert real_from_seeded.status_code == 409
    assert "cannot create real Gate C experiments" in real_from_seeded.json()["error"]["message"]
    learner = client.post("/api/learner/sessions", json={"procedure_id": procedure_id}).json()
    session_id = learner["session"]["session_id"]

    blocked = client.post(
        f"/api/learner/sessions/{session_id}/checkpoints",
        json={"step_id": "step-1", "description": "The paper springs open."},
    )
    assert blocked.json()["latest_event"]["evaluation"]["decision"] == "block"
    assert (
        "crease stays flat" in blocked.json()["latest_event"]["evaluation"]["corrective_guidance"]
    )

    completed = client.post(
        f"/api/learner/sessions/{session_id}/checkpoints",
        json={"step_id": "step-1", "description": "The crease stays flat."},
    )
    assert completed.json()["session"]["status"] == "completed"
    assert model.calls == 0
    assert evidence["gate_a"]["status"] == "incomplete"
    assert evidence["agent_runs"] == []
    assert evidence["audit_events"][0]["event_type"] == "seeded_rehearsal_loaded"
