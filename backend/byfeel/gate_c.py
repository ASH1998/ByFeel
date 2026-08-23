"""Decision Gate C transfer experiment runner.

The runner deliberately keeps the experiment evidence separate from the normal
learner history while reusing the same version-pinned learner session and
checkpoint service. It is local-first: no model or cloud call is required by
the runner itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from .models import (
    ApprovedTeacherIntervention,
    AuditEvent,
    CheckpointDecision,
    Correction,
    GateCArm,
    GateCArmRun,
    GateCArmStatus,
    GateCArmSummary,
    GateCAttempt,
    GateCAttemptResult,
    GateCAttestation,
    GateCComparison,
    GateCComparisonReport,
    GateCDetectionOutcome,
    GateCExperiment,
    GateCExperimentStatus,
    GateCFinalOutcome,
    GateCIntervention,
    LearnerObservation,
    LearnerProgress,
)
from .repositories import ByFeelRepository, NotFoundError


class GateCLearnerService(Protocol):
    def start_learner_for_version(self, procedure_version_id: str) -> LearnerProgress: ...

    def resume_learner(self, session_id: str) -> LearnerProgress: ...

    def checkpoint(
        self,
        session_id: str,
        observation: LearnerObservation,
        *,
        approved_intervention: ApprovedTeacherIntervention | None = None,
    ) -> LearnerProgress: ...


class GateCExperimentRunner:
    """Create, run, and compare static-versus-repaired learner arms."""

    def __init__(self, *, repository: ByFeelRepository, learner_service: GateCLearnerService):
        self.repository = repository
        self.learner_service = learner_service

    def create_experiment(
        self,
        *,
        learner_pseudonym: str,
        procedure_id: str,
        baseline_version_id: str,
        byfeel_version_id: str,
        checkpoint_step_id: str,
        deliberate_incorrect_state: str,
        safety_confirmed: bool,
        synthetic: bool = False,
        synthetic_label: str | None = None,
    ) -> GateCExperiment:
        if procedure_id.startswith("seeded-rehearsal-") and not synthetic:
            raise ValueError("seeded rehearsal procedures cannot create real Gate C experiments")
        baseline = self._version(baseline_version_id, procedure_id)
        byfeel = self._version(byfeel_version_id, procedure_id)
        if baseline.reason != "extracted":
            raise ValueError("the baseline arm must use the extracted static procedure version")
        if byfeel.reason != "learner_approved":
            raise ValueError("the ByFeel arm must use a learner-approved repaired version")
        baseline_steps = [(step.step_id, step.order) for step in baseline.procedure.steps]
        byfeel_steps = [(step.step_id, step.order) for step in byfeel.procedure.steps]
        if baseline_steps != byfeel_steps:
            raise ValueError("Gate C arms must contain the same ordered steps")
        if checkpoint_step_id not in {step_id for step_id, _ in baseline_steps}:
            raise ValueError("checkpoint_step_id is not present in both procedure versions")
        if (
            baseline.procedure.title != byfeel.procedure.title
            or baseline.procedure.domain != byfeel.procedure.domain
            or baseline.procedure.learner_goal != byfeel.procedure.learner_goal
        ):
            raise ValueError("Gate C arms must describe the same task and learner goal")
        experiment = GateCExperiment(
            learner_pseudonym=learner_pseudonym,
            procedure_id=procedure_id,
            baseline_version_id=baseline_version_id,
            byfeel_version_id=byfeel_version_id,
            checkpoint_step_id=checkpoint_step_id,
            deliberate_incorrect_state=deliberate_incorrect_state.strip(),
            safety_confirmed=safety_confirmed,
            synthetic=synthetic,
            synthetic_label=synthetic_label,
        )
        self.repository.save_gate_c_experiment(experiment)
        self._audit(
            event_type="gate_c_experiment_created",
            entity_ref=experiment.experiment_id,
            procedure_id=procedure_id,
            summary=(
                "Created a version-pinned static baseline and ByFeel repaired transfer "
                f"experiment{' (synthetic)' if synthetic else ''}."
            ),
            related_refs=[baseline_version_id, byfeel_version_id],
        )
        return experiment

    def start_arm(self, experiment_id: str, arm: GateCArm) -> GateCArmRun:
        experiment = self.repository.get_gate_c_experiment(experiment_id)
        if experiment.status != GateCExperimentStatus.ACTIVE:
            raise ValueError("a completed Gate C experiment cannot start another arm")
        if self._arm_for(experiment_id, arm) is not None:
            raise ValueError(f"the {arm.value} arm has already started")
        version_id = (
            experiment.baseline_version_id
            if arm == GateCArm.STATIC_INSTRUCTIONS
            else experiment.byfeel_version_id
        )
        learner = self.learner_service.start_learner_for_version(version_id)
        arm_run = GateCArmRun(
            experiment_id=experiment_id,
            arm=arm,
            learner_session_id=learner.session.session_id,
            procedure_version_id=version_id,
            procedure_hash=learner.session.procedure_hash,
            deliberate_incorrect_state=experiment.deliberate_incorrect_state,
        )
        self.repository.save_gate_c_arm_run(arm_run)
        self._audit(
            event_type="gate_c_arm_started",
            entity_ref=arm_run.arm_run_id,
            procedure_id=experiment.procedure_id,
            summary=f"Started the {arm.value} Gate C arm with an isolated learner session.",
            related_refs=[experiment_id, version_id, arm_run.learner_session_id],
        )
        return arm_run

    def record_attempt(
        self,
        arm_run_id: str,
        *,
        description: str,
        evidence=None,
        is_deliberate_incorrect: bool = False,
        is_correction: bool = False,
    ) -> GateCAttemptResult:
        arm_run = self.repository.get_gate_c_arm_run(arm_run_id)
        if arm_run.status != GateCArmStatus.ACTIVE:
            raise ValueError("a finalized Gate C arm cannot receive another attempt")
        experiment = self.repository.get_gate_c_experiment(arm_run.experiment_id)
        progress = self.learner_service.resume_learner(arm_run.learner_session_id)
        if progress.current_step is None:
            raise ValueError("the learner session has no active step")
        target = progress.current_step.step_id == experiment.checkpoint_step_id
        prior_attempts = self.repository.list_gate_c_attempts(arm_run_id)
        target_attempts = [
            item for item in prior_attempts if item.step_id == experiment.checkpoint_step_id
        ]
        if target and not target_attempts and not is_deliberate_incorrect:
            raise ValueError("the first target-checkpoint attempt must be deliberately incorrect")
        if target and target_attempts and is_deliberate_incorrect:
            raise ValueError(
                "only the first target-checkpoint attempt may be deliberately incorrect"
            )
        if not target and (is_deliberate_incorrect or is_correction):
            raise ValueError("incorrect-state and correction flags belong to the target checkpoint")
        if (
            is_correction
            and arm_run.arm == GateCArm.BYFEEL_TEACHER_REPAIRED
            and not arm_run.intervention_id
        ):
            raise ValueError("a ByFeel learner correction requires a recorded intervention")

        observation = LearnerObservation(
            step_id=progress.current_step.step_id,
            description=description.strip(),
            evidence=evidence,
            is_deliberate_incorrect=is_deliberate_incorrect,
            is_correction=is_correction,
        )
        approved_intervention = None
        if target and arm_run.arm == GateCArm.BYFEEL_TEACHER_REPAIRED:
            approved_intervention = self._approved_intervention(
                experiment=experiment,
                arm_run=arm_run,
            )
        learner = self.learner_service.checkpoint(
            arm_run.learner_session_id,
            observation,
            approved_intervention=approved_intervention,
        )
        if learner.latest_event is None:
            raise RuntimeError("learner checkpoint returned no append-only event")
        event = learner.latest_event
        requested_decision = event.requested_decision or event.evaluation.decision
        detection_outcome = None
        if target and not target_attempts:
            detection_outcome = self._detection_outcome(requested_decision)

        attempt = GateCAttempt(
            experiment_id=experiment.experiment_id,
            arm_run_id=arm_run_id,
            attempt_number=len(prior_attempts) + 1,
            step_id=event.step_id,
            learner_event_id=event.event_id,
            observed_at=event.created_at,
            elapsed_ms=max(0, int((event.created_at - arm_run.started_at).total_seconds() * 1000)),
            observation=observation,
            requested_decision=requested_decision,
            safe_decision=event.evaluation.decision,
            detection_outcome=detection_outcome,
            advancement_happened=event.evaluation.decision == CheckpointDecision.ADVANCE,
            unsafe_advance_suppressed=event.unsafe_advance_suppressed,
        )
        intervention = None
        if (
            target
            and not target_attempts
            and arm_run.arm == GateCArm.BYFEEL_TEACHER_REPAIRED
            and event.evaluation.decision == CheckpointDecision.BLOCK
        ):
            if approved_intervention is None:
                raise RuntimeError("ByFeel blocked without an approved intervention context")
            if not event.evaluation.teacher_derived:
                raise RuntimeError("ByFeel intervention was not marked teacher-derived")
            if event.evaluation.corrective_guidance != approved_intervention.guidance:
                raise RuntimeError("learner guidance did not come from the approved correction")
            correction = self.repository.get_correction(approved_intervention.correction_id)
            intervention = GateCIntervention(
                experiment_id=experiment.experiment_id,
                arm_run_id=arm_run_id,
                attempt_id=attempt.attempt_id,
                procedure_id=experiment.procedure_id,
                procedure_version_id=approved_intervention.procedure_version_id,
                correction_id=approved_intervention.correction_id,
                step_id=approved_intervention.step_id,
                guidance=approved_intervention.guidance,
                source_quote=correction.teacher_feedback,
                evidence_ids=(
                    [correction.evidence_ref.evidence_id] if correction.evidence_ref else []
                ),
            )
            attempt = attempt.model_copy(update={"intervention_id": intervention.intervention_id})
            self.repository.append_gate_c_intervention(intervention)
        self.repository.append_gate_c_attempt(attempt)
        updated = arm_run.model_copy(
            update={
                "updated_at": event.created_at,
                "attempt_count": attempt.attempt_number,
                "attempt_event_ids": [*arm_run.attempt_event_ids, event.event_id],
                "detection_outcome": arm_run.detection_outcome or detection_outcome,
                "intervention_id": intervention.intervention_id
                if intervention is not None
                else arm_run.intervention_id,
                "learner_correction": description.strip()
                if is_correction
                else arm_run.learner_correction,
                "unsafe_advance_suppressed": (
                    arm_run.unsafe_advance_suppressed or event.unsafe_advance_suppressed
                ),
            }
        )
        self.repository.save_gate_c_arm_run(updated)
        self._audit(
            event_type="gate_c_attempt_recorded",
            entity_ref=attempt.attempt_id,
            procedure_id=experiment.procedure_id,
            summary=(
                f"Recorded attempt {attempt.attempt_number} for {arm_run.arm.value}; "
                f"safe decision was {attempt.safe_decision.value}."
            ),
            related_refs=[
                arm_run_id,
                event.event_id,
                *([intervention.intervention_id] if intervention else []),
            ],
        )
        return GateCAttemptResult(
            attempt=attempt,
            intervention=intervention,
            arm_run=updated,
            learner=learner,
        )

    def finalize_arm(self, arm_run_id: str) -> GateCArmRun:
        arm_run = self.repository.get_gate_c_arm_run(arm_run_id)
        if arm_run.status != GateCArmStatus.ACTIVE:
            raise ValueError("the Gate C arm is already finalized")
        experiment = self.repository.get_gate_c_experiment(arm_run.experiment_id)
        attempts = self.repository.list_gate_c_attempts(arm_run_id)
        target_attempts = [
            item for item in attempts if item.step_id == experiment.checkpoint_step_id
        ]
        final_outcome = self._final_outcome(arm_run, target_attempts)
        corrected = any(item.observation.is_correction for item in target_attempts[1:])
        advanced_after_correction = final_outcome == GateCFinalOutcome.COMPLETED_AFTER_CORRECTION
        if (
            arm_run.arm == GateCArm.BYFEEL_TEACHER_REPAIRED
            and advanced_after_correction
            and not arm_run.intervention_id
        ):
            raise ValueError("ByFeel cannot claim transfer without a recorded intervention")
        now = datetime.now(UTC)
        finalized = arm_run.model_copy(
            update={
                "status": GateCArmStatus.FINALIZED,
                "updated_at": now,
                "finalized_at": now,
                "attempt_count": len(attempts),
                "duration_ms": max(0, int((now - arm_run.started_at).total_seconds() * 1000)),
                "final_outcome": final_outcome,
                "advancement_after_correction": advanced_after_correction,
                "learner_correction": arm_run.learner_correction if corrected else None,
            }
        )
        self.repository.save_gate_c_arm_run(finalized)
        self._update_experiment_status(experiment)
        self._audit(
            event_type="gate_c_arm_finalized",
            entity_ref=arm_run_id,
            procedure_id=experiment.procedure_id,
            summary=f"Finalized {arm_run.arm.value} with outcome {final_outcome.value}.",
            related_refs=[experiment.experiment_id],
        )
        return finalized

    def attest(
        self,
        experiment_id: str,
        *,
        fresh_learner_confirmed: bool,
        teacher_procedure_confirmed: bool,
        recorded_without_personal_data: bool,
        reviewer_note: str,
    ) -> GateCAttestation:
        experiment = self.repository.get_gate_c_experiment(experiment_id)
        if not experiment.synthetic and not fresh_learner_confirmed:
            raise ValueError("a real Gate C experiment requires fresh-learner confirmation")
        if not experiment.synthetic and not teacher_procedure_confirmed:
            raise ValueError("a real Gate C experiment requires teacher-procedure confirmation")
        if not recorded_without_personal_data:
            raise ValueError("Gate C evidence must be recorded without personal data")
        attestation = GateCAttestation(
            experiment_id=experiment_id,
            fresh_learner_confirmed=fresh_learner_confirmed,
            teacher_procedure_confirmed=teacher_procedure_confirmed,
            recorded_without_personal_data=recorded_without_personal_data,
            reviewer_note=reviewer_note.strip(),
        )
        self.repository.append_gate_c_attestation(attestation)
        self._audit(
            event_type="gate_c_attested",
            entity_ref=experiment_id,
            procedure_id=experiment.procedure_id,
            summary="Facilitator recorded the Gate C human-evidence attestation.",
            related_refs=[experiment_id],
        )
        return attestation

    def report(self, experiment_id: str) -> GateCComparisonReport:
        experiment = self.repository.get_gate_c_experiment(experiment_id)
        baseline = self._summary(experiment_id, GateCArm.STATIC_INSTRUCTIONS)
        byfeel = self._summary(experiment_id, GateCArm.BYFEEL_TEACHER_REPAIRED)
        attestation = self._optional_attestation(experiment_id)
        baseline_complete = self._completed(baseline)
        byfeel_complete = self._completed(byfeel)
        transfer_improved = None
        if baseline and byfeel and baseline.finalized and byfeel.finalized:
            if any(
                summary.final_outcome == GateCFinalOutcome.INCOMPLETE
                for summary in (baseline, byfeel)
            ):
                transfer_improved = None
            else:
                transfer_improved = bool(byfeel_complete and not baseline_complete)
        comparison = GateCComparison(
            baseline_completed_after_correction=baseline_complete,
            byfeel_completed_after_correction=byfeel_complete,
            baseline_detection=baseline.detection_outcome if baseline else None,
            byfeel_detection=byfeel.detection_outcome if byfeel else None,
            completion_delta=(
                int(bool(byfeel_complete)) - int(bool(baseline_complete))
                if transfer_improved is not None
                else None
            ),
            correction_delta=(
                int(bool(byfeel and byfeel.learner_corrected))
                - int(bool(baseline and baseline.learner_corrected))
                if baseline and byfeel and baseline.finalized and byfeel.finalized
                else None
            ),
            teacher_derived_intervention_only=self._interventions_are_approved(experiment_id),
            requires_human_review=True,
            transfer_improved=transfer_improved,
        )
        both_finalized = bool(baseline and byfeel and baseline.finalized and byfeel.finalized)
        if experiment.synthetic:
            decision = "synthetic_excluded"
            limitation = "Synthetic deterministic rehearsal; excluded from any real Gate C pass."
        elif not both_finalized:
            decision = "pending"
            limitation = "Both comparable arms must be finalized before transfer is evaluable."
        elif (
            attestation is None
            or not attestation.fresh_learner_confirmed
            or not attestation.teacher_procedure_confirmed
            or not attestation.recorded_without_personal_data
        ):
            decision = "pending_real_evidence"
            limitation = (
                "Fresh-learner, teacher-procedure, and privacy attestations remain required."
            )
        elif transfer_improved is None:
            decision = "not_evaluable"
            limitation = "Missing or incomplete observations prevent a defensible transfer result."
        elif transfer_improved is True and comparison.teacher_derived_intervention_only:
            decision = "pass_candidate"
            limitation = (
                "Candidate only; facilitator must review the real observations and outcome."
            )
        elif transfer_improved is False:
            decision = "not_improved"
            limitation = "The repaired arm did not visibly improve the recorded transfer outcome."
        else:
            decision = "not_evaluable"
            limitation = "Missing or uncertain observations prevent a defensible transfer result."
        if experiment.status != GateCExperimentStatus.COMPLETE and both_finalized:
            experiment = experiment.model_copy(
                update={"status": GateCExperimentStatus.COMPLETE, "updated_at": datetime.now(UTC)}
            )
            self.repository.save_gate_c_experiment(experiment)
        return GateCComparisonReport(
            experiment_id=experiment_id,
            synthetic=experiment.synthetic,
            gate_c_decision=decision,
            experiment_status=experiment.status,
            baseline=baseline,
            byfeel=byfeel,
            comparison=comparison,
            attestation=attestation,
            limitation=limitation,
        )

    def snapshot(self, experiment_id: str) -> dict[str, object]:
        experiment = self.repository.get_gate_c_experiment(experiment_id)
        arms = self.repository.list_gate_c_arm_runs(experiment_id)
        return {
            "experiment": experiment,
            "arms": [
                {
                    "arm_run": arm,
                    "attempts": self.repository.list_gate_c_attempts(arm.arm_run_id),
                    "interventions": self.repository.list_gate_c_interventions(arm.arm_run_id),
                }
                for arm in arms
            ],
            "attestation": self._optional_attestation(experiment_id),
            "report": self.report(experiment_id),
        }

    def seed_rehearsal(self, procedure_id: str) -> GateCComparisonReport:
        versions = self.repository.list_procedure_versions(procedure_id)
        try:
            baseline = next(item for item in versions if item.reason == "extracted")
            byfeel = next(item for item in reversed(versions) if item.reason == "learner_approved")
        except StopIteration as exc:
            raise ValueError(
                "seeded procedure has no comparable extracted and approved versions"
            ) from exc
        experiment = self.create_experiment(
            learner_pseudonym="synthetic-learner",
            procedure_id=procedure_id,
            baseline_version_id=baseline.version_id,
            byfeel_version_id=byfeel.version_id,
            checkpoint_step_id=byfeel.procedure.steps[0].step_id,
            deliberate_incorrect_state="The crease springs open when the learner removes a hand.",
            safety_confirmed=True,
            synthetic=True,
            synthetic_label="seeded deterministic browser rehearsal",
        )
        self.attest(
            experiment.experiment_id,
            fresh_learner_confirmed=False,
            teacher_procedure_confirmed=False,
            recorded_without_personal_data=True,
            reviewer_note=(
                "Synthetic fixture only; no person or real Gate C evidence is represented."
            ),
        )
        baseline_run = self.start_arm(experiment.experiment_id, GateCArm.STATIC_INSTRUCTIONS)
        self.record_attempt(
            baseline_run.arm_run_id,
            description="The paper springs open.",
            is_deliberate_incorrect=True,
        )
        self.finalize_arm(baseline_run.arm_run_id)
        byfeel_run = self.start_arm(experiment.experiment_id, GateCArm.BYFEEL_TEACHER_REPAIRED)
        self.record_attempt(
            byfeel_run.arm_run_id,
            description="The paper springs open.",
            is_deliberate_incorrect=True,
        )
        self.record_attempt(
            byfeel_run.arm_run_id,
            description="The crease stays flat after the hand is removed.",
            is_correction=True,
        )
        self.finalize_arm(byfeel_run.arm_run_id)
        return self.report(experiment.experiment_id)

    def _version(self, version_id: str, procedure_id: str):
        version = self.repository.get_procedure_version(version_id)
        if version.procedure_id != procedure_id:
            raise ValueError("procedure version does not belong to the requested procedure")
        if version.learner_artifact_hash != version.learner_artifact().content_hash():
            raise ValueError("procedure version learner hash is not internally consistent")
        return version

    def _arm_for(self, experiment_id: str, arm: GateCArm) -> GateCArmRun | None:
        return next(
            (
                item
                for item in self.repository.list_gate_c_arm_runs(experiment_id)
                if item.arm == arm
            ),
            None,
        )

    def _approved_intervention(
        self, *, experiment: GateCExperiment, arm_run: GateCArmRun
    ) -> ApprovedTeacherIntervention:
        version = self.repository.get_procedure_version(arm_run.procedure_version_id)
        target_step = next(
            step
            for step in version.procedure.steps
            if step.step_id == experiment.checkpoint_step_id
        )
        matches: list[Correction] = [
            correction
            for correction in self.repository.list_corrections(experiment.procedure_id)
            if correction.step_id == experiment.checkpoint_step_id
            and correction.new_state == target_step.model_dump(mode="json")
        ]
        if not matches:
            raise ValueError("the ByFeel version has no approved teacher correction provenance")
        correction = max(matches, key=lambda item: item.created_at)
        return ApprovedTeacherIntervention(
            correction_id=correction.correction_id,
            procedure_version_id=arm_run.procedure_version_id,
            step_id=experiment.checkpoint_step_id,
            guidance=correction.teacher_feedback,
        )

    @staticmethod
    def _detection_outcome(decision: CheckpointDecision) -> GateCDetectionOutcome:
        if decision == CheckpointDecision.BLOCK:
            return GateCDetectionOutcome.DETECTED
        if decision == CheckpointDecision.ADVANCE:
            return GateCDetectionOutcome.MISSED_DETECTION
        return GateCDetectionOutcome.SAFE_ABSTENTION

    @staticmethod
    def _completed(summary: GateCArmSummary | None) -> bool | None:
        if summary is None or not summary.finalized:
            return None
        return summary.final_outcome == GateCFinalOutcome.COMPLETED_AFTER_CORRECTION

    def _final_outcome(
        self, arm_run: GateCArmRun, target_attempts: list[GateCAttempt]
    ) -> GateCFinalOutcome:
        if not target_attempts:
            return GateCFinalOutcome.INCOMPLETE
        first = target_attempts[0]
        if first.detection_outcome == GateCDetectionOutcome.SAFE_ABSTENTION:
            return GateCFinalOutcome.SAFE_ABSTENTION
        if first.detection_outcome == GateCDetectionOutcome.MISSED_DETECTION:
            return GateCFinalOutcome.MISSED_DETECTION
        correction_advanced = any(
            attempt.observation.is_correction
            and attempt.safe_decision == CheckpointDecision.ADVANCE
            for attempt in target_attempts[1:]
        )
        if correction_advanced and (
            arm_run.arm == GateCArm.STATIC_INSTRUCTIONS or arm_run.intervention_id is not None
        ):
            return GateCFinalOutcome.COMPLETED_AFTER_CORRECTION
        if any(
            attempt.safe_decision == CheckpointDecision.ADVANCE for attempt in target_attempts[1:]
        ):
            return GateCFinalOutcome.COMPLETED_WITHOUT_CORRECTION
        return GateCFinalOutcome.DETECTED_NOT_CORRECTED

    def _summary(self, experiment_id: str, arm: GateCArm) -> GateCArmSummary | None:
        arm_run = self._arm_for(experiment_id, arm)
        if arm_run is None:
            return None
        interventions = self.repository.list_gate_c_interventions(arm_run.arm_run_id)
        attempts = self.repository.list_gate_c_attempts(arm_run.arm_run_id)
        return GateCArmSummary(
            arm_run_id=arm_run.arm_run_id,
            arm=arm,
            procedure_version_id=arm_run.procedure_version_id,
            procedure_hash=arm_run.procedure_hash,
            final_outcome=arm_run.final_outcome,
            detection_outcome=arm_run.detection_outcome,
            attempt_count=arm_run.attempt_count,
            duration_ms=arm_run.duration_ms,
            intervention_count=len(interventions),
            learner_corrected=any(item.observation.is_correction for item in attempts),
            advancement_after_correction=arm_run.advancement_after_correction,
            unsafe_advance_suppressed=arm_run.unsafe_advance_suppressed,
            finalized=arm_run.status == GateCArmStatus.FINALIZED,
        )

    def _interventions_are_approved(self, experiment_id: str) -> bool:
        experiment = self.repository.get_gate_c_experiment(experiment_id)
        arm_runs = self.repository.list_gate_c_arm_runs(experiment_id)
        baseline = next(
            (item for item in arm_runs if item.arm == GateCArm.STATIC_INSTRUCTIONS), None
        )
        byfeel = next(
            (item for item in arm_runs if item.arm == GateCArm.BYFEEL_TEACHER_REPAIRED), None
        )
        if baseline is not None and self.repository.list_gate_c_interventions(baseline.arm_run_id):
            return False
        if byfeel is None:
            return False
        interventions = self.repository.list_gate_c_interventions(byfeel.arm_run_id)
        if not interventions:
            return False
        version = self.repository.get_procedure_version(experiment.byfeel_version_id)
        for item in interventions:
            if not item.approved_teacher_derived:
                return False
            if (
                item.procedure_id != experiment.procedure_id
                or item.procedure_version_id != experiment.byfeel_version_id
                or item.step_id != experiment.checkpoint_step_id
            ):
                return False
            correction = self.repository.get_correction(item.correction_id)
            if (
                correction.procedure_id != experiment.procedure_id
                or correction.step_id != experiment.checkpoint_step_id
                or correction.teacher_feedback != item.guidance
                or correction.teacher_feedback != item.source_quote
            ):
                return False
            version_step = next(
                step for step in version.procedure.steps if step.step_id == item.step_id
            )
            if correction.new_state != version_step.model_dump(mode="json"):
                return False
        return True

    def _optional_attestation(self, experiment_id: str) -> GateCAttestation | None:
        try:
            return self.repository.get_gate_c_attestation(experiment_id)
        except NotFoundError:
            return None

    def _update_experiment_status(self, experiment: GateCExperiment) -> None:
        arms = self.repository.list_gate_c_arm_runs(experiment.experiment_id)
        if len(arms) == 2 and all(item.status == GateCArmStatus.FINALIZED for item in arms):
            updated = experiment.model_copy(
                update={"status": GateCExperimentStatus.COMPLETE, "updated_at": datetime.now(UTC)}
            )
            self.repository.save_gate_c_experiment(updated)

    def _audit(
        self,
        *,
        event_type: str,
        entity_ref: str,
        procedure_id: str,
        summary: str,
        related_refs: list[str],
    ) -> None:
        self.repository.append_audit_event(
            AuditEvent(
                event_type=event_type,
                entity_ref=entity_ref,
                procedure_id=procedure_id,
                actor="system",
                summary=summary,
                related_refs=related_refs,
            )
        )
