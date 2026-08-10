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
        f"/api/teacher/sessions/{session_id}/media",
        json={
            "content_base64": b64encode(b"fake bounded video").decode(),
            "content_type": "video/mp4",
        },
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


def test_api_teacher_repair_learner_checkpoint_flow(tmp_path) -> None:
    service = api_service(tmp_path)
    client = TestClient(create_app(service))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/version").json()["version"]
    assert client.get("/").status_code == 200

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
    procedure_id = seeded.json()["procedure"]["id"]
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
    evidence = client.get(f"/api/judge/evidence/{procedure_id}").json()
    assert evidence["gate_a"]["status"] == "incomplete"
    assert evidence["agent_runs"] == []
    assert evidence["audit_events"][0]["event_type"] == "seeded_rehearsal_loaded"
