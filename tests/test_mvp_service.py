from __future__ import annotations

from typing import TypeVar

import pytest
from byfeel.models import (
    BlockerReviewDecision,
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
    TeacherDemo,
    VisualCheckpointState,
)
from byfeel.repositories import ConflictError, InMemoryRepository
from byfeel.service import BlindedProbeGateway, ByFeelService
from pydantic import BaseModel, ValidationError

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def initial_procedure() -> Procedure:
    return Procedure(
        id="paper-fold",
        title="Fold a paper marker",
        domain="paper craft",
        learner_goal="Make a stable folded marker",
        steps=[
            ProcedureStep(
                step_id="step-1",
                order=1,
                action="Press the fold until it is firm enough",
                confidence=0.5,
            )
        ],
    )


def blocked_report() -> ProbeReport:
    return ProbeReport(
        status=ProbeStatus.BLOCKED,
        summary="The stop condition is missing.",
        blockers=[
            KnowledgeGap(
                gap_id="gap-1",
                step_id="step-1",
                issue_type=IssueType.MISSING_COMPLETION_CONDITION,
                description="Firm enough is not observable.",
                missing_information="An observable sign that the fold is complete.",
                severity=0.95,
                blocks_execution=True,
            )
        ],
        teacher_question="What should the learner observe when the fold is firm enough?",
    )


class FlowClient:
    model = "fake-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        self.prompts.append(prompt)
        if schema is Procedure:
            value: BaseModel = initial_procedure()
        elif schema is RepairResult:
            repaired = initial_procedure()
            repaired.steps[0].completion_conditions = [
                "Advance when the crease stays flat after the hand is removed"
            ]
            value = RepairResult(
                procedure=repaired,
                changed_step_ids=["step-1"],
                change_summary="Added the teacher's visible completion condition.",
            )
        elif "crease stays flat" in prompt:
            value = ProbeReport(
                status=ProbeStatus.UNBLOCKED,
                summary="The learner now has an observable stop condition.",
            )
        else:
            value = blocked_report()
        return value  # type: ignore[return-value]


class FlowCheckpointEvaluator:
    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> CheckpointEvaluation:
        del procedure, step
        if "springs open" in observation.description:
            return CheckpointEvaluation(
                decision=CheckpointDecision.BLOCK,
                confidence=0.94,
                explanation="The crease does not yet hold.",
                corrective_guidance="Press the crease again, then remove your hand and recheck.",
                teacher_derived=True,
            )
        return CheckpointEvaluation(
            decision=CheckpointDecision.ADVANCE,
            confidence=0.96,
            explanation="The crease remains flat after the hand is removed.",
            teacher_derived=True,
        )


def test_complete_teacher_to_learner_recovery_flow() -> None:
    repository = InMemoryRepository()
    client = FlowClient()
    service = ByFeelService(
        repository=repository,
        teaching_client=client,
        checkpoint_evaluator=FlowCheckpointEvaluator(),
    )
    sentinel = "PRIVATE_TEACHER_SENTINEL_6221"
    taught = service.teach(
        TeacherDemo(
            title="Fold a paper marker",
            domain="paper craft",
            learner_goal="Make a stable folded marker",
            raw_demonstration=(
                f"The teacher folds the paper and says press it until firm enough. {sentinel}"
            ),
        )
    )
    assert taught.probe_run.report.status == ProbeStatus.BLOCKED
    assert sentinel in client.prompts[0]
    assert sentinel not in client.prompts[1]

    service.review_blocker(
        taught.probe_run.probe_run_id,
        BlockerReviewDecision.GENUINE,
        "The learner cannot decide when to stop pressing without an observable cue.",
    )

    repaired = service.clarify(
        taught.procedure.id,
        "It is ready when the crease stays flat after I remove my hand.",
    )
    assert repaired.probe_run.report.status == ProbeStatus.UNBLOCKED
    assert len(repository.list_corrections(taught.procedure.id)) == 1

    service.approve_procedure_for_learner(taught.procedure.id)
    learner = service.start_learner(taught.procedure.id)
    blocked = service.checkpoint(
        learner.session.session_id,
        LearnerObservation(step_id="step-1", description="The paper springs open."),
    )
    assert blocked.latest_event.evaluation.decision == CheckpointDecision.BLOCK
    assert blocked.session.status == "active"

    completed = service.checkpoint(
        learner.session.session_id,
        LearnerObservation(step_id="step-1", description="The crease stays flat."),
    )
    assert completed.session.status == "completed"
    assert completed.latest_event.evaluation.teacher_derived is True
    assert len(repository.list_learner_events(learner.session.session_id)) == 2


def test_adk_repair_provenance_rejects_invented_or_non_verbatim_claims() -> None:
    before = initial_procedure()
    invented = initial_procedure().model_copy(deep=True)
    invented.steps[0].completion_conditions = ["Wait exactly five minutes"]

    with pytest.raises(ValueError, match="exact teacher-answer substrings"):
        ByFeelService._validate_repair_provenance(
            before,
            invented,
            ["step-1"],
            "Stop when the crease stays flat.",
            ["five minutes"],
        )

    with pytest.raises(ValueError, match="every new learner-facing repair claim"):
        ByFeelService._validate_repair_provenance(
            before,
            invented,
            ["step-1"],
            "Stop when the crease stays flat.",
            ["crease stays flat"],
        )


def test_probe_gateway_rejects_canonical_procedure() -> None:
    with pytest.raises(TypeError, match="LearnerProcedure"):
        BlindedProbeGateway(FlowClient()).probe(initial_procedure())  # type: ignore[arg-type]


def test_model_invariants_reject_duplicates_and_unsafe_advance() -> None:
    with pytest.raises(ValidationError, match="step IDs must be unique"):
        Procedure(
            id="duplicate",
            title="Duplicate",
            domain="test",
            learner_goal="Reject duplicate IDs",
            steps=[
                ProcedureStep(step_id="same", order=1, action="One", confidence=1),
                ProcedureStep(step_id="same", order=2, action="Two", confidence=1),
            ],
        )
    with pytest.raises(ValidationError, match="advance requires confidence"):
        CheckpointEvaluation(
            decision=CheckpointDecision.ADVANCE,
            confidence=0.79,
            explanation="Not confident enough.",
        )
    with pytest.raises(ValidationError, match="advance requires a ready visual state"):
        CheckpointEvaluation(
            decision=CheckpointDecision.ADVANCE,
            visual_state=VisualCheckpointState.INCORRECT_OR_OVERSHOT,
            confidence=0.95,
            explanation="The mixture is uniform but does not match the target.",
        )
    gap = KnowledgeGap.model_validate(
        {
            "gap_id": "gap-provenance",
            "step_id": "step-1",
            "source": "model-controlled-wrong-value",
            "issue_type": "missing_step",
            "description": "A step is missing.",
            "missing_information": "The missing action.",
            "severity": 0.8,
            "blocks_execution": True,
        }
    )
    assert gap.source == "novice_probe"


def test_in_memory_repository_enforces_optimistic_concurrency_and_append_only() -> None:
    repository = InMemoryRepository()
    procedure = initial_procedure()
    repository.save_procedure(procedure)
    with pytest.raises(ConflictError):
        repository.save_procedure(procedure, expected_updated_at="stale")

    report = blocked_report()
    from byfeel.models import ProbeRun

    run = ProbeRun(
        procedure_id=procedure.id,
        learner_artifact_hash=procedure.learner_view().content_hash(),
        report=report,
        phase="before_repair",
    )
    repository.save_probe_run(run)
    assert repository.latest_probe_run(procedure.id, "before_repair") == run
