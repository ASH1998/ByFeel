from __future__ import annotations

from typing import TypeVar

from byfeel.api import create_app
from byfeel.models import (
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

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
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


def test_api_teacher_repair_learner_checkpoint_flow() -> None:
    service = ByFeelService(
        repository=InMemoryRepository(),
        teaching_client=ApiFlowClient(),
        checkpoint_evaluator=ApiCheckpointEvaluator(),
    )
    client = TestClient(create_app(service))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/version").json()["version"]
    assert client.get("/").status_code == 200

    taught = client.post(
        "/api/teacher/sessions",
        json={
            "title": "Fold paper",
            "domain": "paper craft",
            "learner_goal": "Make a stable fold",
            "raw_demonstration": (
                "The teacher folds the paper and presses until it feels firm enough."
            ),
            "constraints": [],
        },
    )
    assert taught.status_code == 200
    assert taught.json()["probe_run"]["report"]["status"] == "blocked"

    repaired = client.post(
        "/api/procedures/api-fold/clarifications",
        json={"clarification": "It is ready when the crease stays flat after my hand is removed."},
    )
    assert repaired.status_code == 200
    assert repaired.json()["procedure"]["status"] == "learner_ready"

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
