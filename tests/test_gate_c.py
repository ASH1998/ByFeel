from __future__ import annotations

from datetime import UTC, datetime

import pytest
from byfeel.api import create_app
from byfeel.gate_c import GateCExperimentRunner
from byfeel.models import (
    CheckpointDecision,
    CheckpointEvaluation,
    Correction,
    GateCArm,
    GateCAttempt,
    GateCDetectionOutcome,
    GateCFinalOutcome,
    LearnerObservation,
    LearnerProcedure,
    LearnerStep,
    Procedure,
    ProcedureStep,
    ProcedureVersion,
)
from byfeel.repositories import ConflictError, InMemoryRepository
from byfeel.service import ByFeelService
from fastapi.testclient import TestClient


def procedure(*, repaired: bool) -> Procedure:
    return Procedure(
        id="gate-c-fold",
        title="Fold a stable paper marker",
        domain="paper craft",
        learner_goal="Make a stable folded marker",
        status="learner_ready" if repaired else "tested",
        steps=[
            ProcedureStep(
                step_id="step-1",
                order=1,
                action="Press the fold until it is firm enough",
                completion_conditions=(
                    ["The crease stays flat after the hand is removed"] if repaired else []
                ),
                confidence=0.9 if repaired else 0.5,
            )
        ],
    )


class GateCCheckpointEvaluator:
    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> CheckpointEvaluation:
        del procedure
        if not step.completion_conditions:
            return CheckpointEvaluation(
                decision=CheckpointDecision.HUMAN_CONFIRMATION,
                confidence=0.4,
                explanation="The static procedure has no observable completion cue.",
            )
        if "flat" in observation.description.casefold():
            return CheckpointEvaluation(
                decision=CheckpointDecision.ADVANCE,
                confidence=0.96,
                explanation="The repaired cue is satisfied.",
            )
        return CheckpointEvaluation(
            decision=CheckpointDecision.BLOCK,
            confidence=0.94,
            explanation="The crease is not yet stable.",
            corrective_guidance="A model must not supply the teacher correction directly.",
        )


class AlwaysAdvanceEvaluator:
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
            confidence=0.99,
            explanation="Unsafe fake model response for a negative-path test.",
        )


def seeded_repository(*, with_correction: bool = True) -> tuple[InMemoryRepository, ByFeelService]:
    repository = InMemoryRepository()
    baseline = procedure(repaired=False)
    byfeel = procedure(repaired=True)
    baseline_version = ProcedureVersion(
        procedure_id=baseline.id,
        learner_artifact_hash=baseline.model_copy(update={"status": "learner_ready"})
        .learner_view()
        .content_hash(),
        reason="extracted",
        procedure=baseline,
    )
    byfeel_version = ProcedureVersion(
        procedure_id=byfeel.id,
        learner_artifact_hash=byfeel.learner_view().content_hash(),
        reason="learner_approved",
        procedure=byfeel,
    )
    repository.append_procedure_version(baseline_version)
    repository.append_procedure_version(byfeel_version)
    repository.save_procedure(byfeel)
    if with_correction:
        repository.append_correction(
            Correction(
                procedure_id=byfeel.id,
                step_id="step-1",
                previous_state=baseline.steps[0].model_dump(mode="json"),
                new_state=byfeel.steps[0].model_dump(mode="json"),
                teacher_feedback="The crease stays flat after the hand is removed.",
            )
        )
    service = ByFeelService(
        repository=repository,
        teaching_client=object(),  # The runner never calls the Gate A client.
        checkpoint_evaluator=GateCCheckpointEvaluator(),
    )
    return repository, service


def make_runner(
    *, with_correction: bool = True
) -> tuple[InMemoryRepository, GateCExperimentRunner]:
    repository, service = seeded_repository(with_correction=with_correction)
    return repository, GateCExperimentRunner(repository=repository, learner_service=service)


def create_experiment(runner: GateCExperimentRunner):
    return runner.create_experiment(
        learner_pseudonym="learner-001",
        procedure_id="gate-c-fold",
        baseline_version_id=runner.repository.list_procedure_versions("gate-c-fold")[0].version_id,
        byfeel_version_id=runner.repository.list_procedure_versions("gate-c-fold")[1].version_id,
        checkpoint_step_id="step-1",
        deliberate_incorrect_state="The crease springs open when the hand is removed.",
        safety_confirmed=True,
    )


def test_gate_c_runner_records_comparable_arms_and_pass_candidate() -> None:
    repository, experiment_runner = make_runner()
    experiment = create_experiment(experiment_runner)

    baseline = experiment_runner.start_arm(experiment.experiment_id, GateCArm.STATIC_INSTRUCTIONS)
    baseline_attempt = experiment_runner.record_attempt(
        baseline.arm_run_id,
        description="The crease springs open.",
        is_deliberate_incorrect=True,
    )
    assert baseline_attempt.attempt.detection_outcome == GateCDetectionOutcome.SAFE_ABSTENTION
    assert baseline_attempt.attempt.advancement_happened is False
    baseline_final = experiment_runner.finalize_arm(baseline.arm_run_id)
    assert baseline_final.final_outcome == GateCFinalOutcome.SAFE_ABSTENTION

    byfeel = experiment_runner.start_arm(experiment.experiment_id, GateCArm.BYFEEL_TEACHER_REPAIRED)
    blocked = experiment_runner.record_attempt(
        byfeel.arm_run_id,
        description="The crease springs open.",
        is_deliberate_incorrect=True,
    )
    assert blocked.attempt.detection_outcome == GateCDetectionOutcome.DETECTED
    assert blocked.intervention is not None
    assert blocked.intervention.approved_teacher_derived is True
    assert blocked.intervention.source_quote == ("The crease stays flat after the hand is removed.")
    assert blocked.learner.latest_event.evaluation.corrective_guidance == (
        "The crease stays flat after the hand is removed."
    )
    completed = experiment_runner.record_attempt(
        byfeel.arm_run_id,
        description="The crease stays flat after the hand is removed.",
        is_correction=True,
    )
    assert completed.attempt.safe_decision == CheckpointDecision.ADVANCE
    byfeel_final = experiment_runner.finalize_arm(byfeel.arm_run_id)
    assert byfeel_final.final_outcome == GateCFinalOutcome.COMPLETED_AFTER_CORRECTION
    assert byfeel_final.advancement_after_correction is True

    pending = experiment_runner.report(experiment.experiment_id)
    assert pending.gate_c_decision == "pending_real_evidence"
    assert pending.comparison.transfer_improved is True
    assert pending.baseline.procedure_version_id != pending.byfeel.procedure_version_id

    experiment_runner.attest(
        experiment.experiment_id,
        fresh_learner_confirmed=True,
        teacher_procedure_confirmed=True,
        recorded_without_personal_data=True,
        reviewer_note="Fresh learner and approved teacher repair were confirmed locally.",
    )
    report = experiment_runner.report(experiment.experiment_id)
    assert report.gate_c_decision == "pass_candidate"
    assert report.comparison.teacher_derived_intervention_only is True
    assert report.experiment_status.value == "complete"
    assert len(repository.list_gate_c_interventions(byfeel.arm_run_id)) == 1


def test_gate_c_suppresses_unsafe_advance_and_records_missed_detection() -> None:
    repository, service = seeded_repository()
    service = ByFeelService(
        repository=repository,
        teaching_client=object(),
        checkpoint_evaluator=AlwaysAdvanceEvaluator(),
    )
    experiment_runner = GateCExperimentRunner(repository=repository, learner_service=service)
    experiment = create_experiment(experiment_runner)
    arm = experiment_runner.start_arm(experiment.experiment_id, GateCArm.STATIC_INSTRUCTIONS)

    attempt = experiment_runner.record_attempt(
        arm.arm_run_id,
        description="The crease springs open.",
        is_deliberate_incorrect=True,
    ).attempt
    assert attempt.requested_decision == CheckpointDecision.ADVANCE
    assert attempt.safe_decision == CheckpointDecision.HUMAN_CONFIRMATION
    assert attempt.detection_outcome == GateCDetectionOutcome.MISSED_DETECTION
    assert attempt.unsafe_advance_suppressed is True
    assert attempt.advancement_happened is False
    assert (
        experiment_runner.finalize_arm(arm.arm_run_id).final_outcome
        == GateCFinalOutcome.MISSED_DETECTION
    )


def test_gate_c_missing_teacher_provenance_is_rejected_before_checkpoint() -> None:
    repository, experiment_runner = make_runner(with_correction=False)
    experiment = create_experiment(experiment_runner)
    arm = experiment_runner.start_arm(experiment.experiment_id, GateCArm.BYFEEL_TEACHER_REPAIRED)

    with pytest.raises(ValueError, match="no approved teacher correction provenance"):
        experiment_runner.record_attempt(
            arm.arm_run_id,
            description="The crease springs open.",
            is_deliberate_incorrect=True,
        )
    assert repository.list_gate_c_attempts(arm.arm_run_id) == []
    assert repository.list_learner_events(arm.learner_session_id) == []


def test_gate_c_attempt_and_intervention_history_is_append_only() -> None:
    repository, experiment_runner = make_runner()
    experiment = create_experiment(experiment_runner)
    arm = experiment_runner.start_arm(experiment.experiment_id, GateCArm.BYFEEL_TEACHER_REPAIRED)
    result = experiment_runner.record_attempt(
        arm.arm_run_id,
        description="The crease springs open.",
        is_deliberate_incorrect=True,
    )
    with pytest.raises(ConflictError):
        repository.append_gate_c_attempt(result.attempt)
    assert len(repository.list_gate_c_interventions(arm.arm_run_id)) == 1


def test_gate_c_model_rejects_direct_unsafe_attempt_record() -> None:
    with pytest.raises(ValueError, match="cannot be recorded as advanced"):
        GateCAttempt(
            experiment_id="gate-c-test",
            arm_run_id="arm-1",
            attempt_number=1,
            step_id="step-1",
            learner_event_id="event-1",
            observed_at=datetime.now(UTC),
            elapsed_ms=1,
            observation=LearnerObservation(
                step_id="step-1",
                description="incorrect",
                is_deliberate_incorrect=True,
            ),
            requested_decision=CheckpointDecision.ADVANCE,
            safe_decision=CheckpointDecision.ADVANCE,
            detection_outcome=GateCDetectionOutcome.MISSED_DETECTION,
            advancement_happened=True,
        )


def test_gate_c_model_rejects_conflicting_observation_flags() -> None:
    with pytest.raises(ValueError, match="both incorrect and a correction"):
        LearnerObservation(
            step_id="step-1",
            description="incorrect and corrected",
            is_deliberate_incorrect=True,
            is_correction=True,
        )


def test_gate_c_api_and_browser_surface_expose_experiment_states() -> None:
    repository, service = seeded_repository()
    client = TestClient(create_app(service))
    versions = repository.list_procedure_versions("gate-c-fold")
    created = client.post(
        "/api/gate-c/experiments",
        json={
            "learner_pseudonym": "learner-api-001",
            "procedure_id": "gate-c-fold",
            "baseline_version_id": versions[0].version_id,
            "byfeel_version_id": versions[1].version_id,
            "checkpoint_step_id": "step-1",
            "deliberate_incorrect_state": "The crease springs open.",
            "safety_confirmed": True,
        },
    )
    assert created.status_code == 200
    experiment_id = created.json()["experiment_id"]
    started = client.post(f"/api/gate-c/experiments/{experiment_id}/arms/static_instructions/start")
    assert started.status_code == 200
    arm_run_id = started.json()["arm_run_id"]
    attempt = client.post(
        f"/api/gate-c/arms/{arm_run_id}/attempts",
        json={"description": "The crease springs open.", "is_deliberate_incorrect": True},
    )
    assert attempt.status_code == 200
    assert attempt.json()["attempt"]["detection_outcome"] == "safe_abstention"
    assert client.post(f"/api/gate-c/arms/{arm_run_id}/finalize").status_code == 200
    report = client.get(f"/api/gate-c/experiments/{experiment_id}/report")
    assert report.status_code == 200
    assert report.json()["gate_c_decision"] == "pending"

    html = client.get("/").text
    assert "Gate C" in html
    assert "static_instructions" in html
    assert "byfeel_teacher_repaired" in html
    assert "Synthetic rehearsal" in html
