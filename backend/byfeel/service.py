"""Application services for the complete local ByFeel loop."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from .experiment import GateAExperiment, StructuredClient
from .models import (
    Checkpoint,
    CheckpointDecision,
    CheckpointEvaluation,
    CheckpointModality,
    Correction,
    EvidenceRef,
    LearnerEvent,
    LearnerObservation,
    LearnerProcedure,
    LearnerProgress,
    LearnerSession,
    LearnerStep,
    ProbeReport,
    ProbeRun,
    ProbeStatus,
    Procedure,
    ProcedureStatus,
    RepairOutcome,
    TeacherDemo,
    TeachingOutcome,
)
from .prompts import PROBE_SYSTEM, probe_prompt
from .repositories import ByFeelRepository


class CheckpointEvaluator(Protocol):
    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> CheckpointEvaluation: ...


class BlindedProbeGateway:
    """Runtime information barrier: this interface accepts learner artifacts only."""

    def __init__(self, client: StructuredClient) -> None:
        self._client = client

    def probe(self, artifact: LearnerProcedure) -> ProbeReport:
        if not isinstance(artifact, LearnerProcedure):
            raise TypeError("the blinded probe accepts LearnerProcedure only")
        return self._client.generate(
            system=PROBE_SYSTEM,
            prompt=probe_prompt(artifact),
            schema=ProbeReport,
        )


class ByFeelService:
    def __init__(
        self,
        *,
        repository: ByFeelRepository,
        teaching_client: StructuredClient,
        checkpoint_evaluator: CheckpointEvaluator,
    ) -> None:
        self.repository = repository
        self._experiment = GateAExperiment(teaching_client)
        self._probe = BlindedProbeGateway(teaching_client)
        self._checkpoint_evaluator = checkpoint_evaluator

    def teach(self, demo: TeacherDemo) -> TeachingOutcome:
        procedure = self._experiment.extract(demo)
        artifact = procedure.learner_view()
        report = self._probe.probe(artifact)
        run = ProbeRun(
            procedure_id=procedure.id,
            learner_artifact_hash=artifact.content_hash(),
            report=report,
            phase="before_repair",
        )
        self.repository.save_procedure(procedure)
        self.repository.save_probe_run(run)
        return TeachingOutcome(procedure=procedure, probe_run=run)

    def clarify(
        self,
        procedure_id: str,
        teacher_clarification: str,
        evidence: EvidenceRef | None = None,
    ) -> RepairOutcome:
        if not teacher_clarification.strip():
            raise ValueError("teacher clarification cannot be empty")
        before_procedure = self.repository.get_procedure(procedure_id)
        before_run = self.repository.latest_probe_run(procedure_id, "before_repair")
        repair = self._experiment.repair(
            before_procedure,
            before_run.report,
            teacher_clarification,
        )
        self._validate_bounded_repair(before_procedure, repair.procedure, repair.changed_step_ids)
        repaired = repair.procedure.model_copy(
            update={"status": ProcedureStatus.TESTED, "updated_at": datetime.now(UTC)}
        )
        if evidence is not None:
            changed_step = self._step(repaired, repair.changed_step_ids[0])
            changed_step.checkpoints.append(
                Checkpoint(
                    checkpoint_id=f"checkpoint-{evidence.evidence_id}",
                    modality=CheckpointModality.VISUAL,
                    description=teacher_clarification.strip(),
                    evidence_refs=[evidence],
                    confidence=1,
                )
            )
        artifact = repaired.learner_view()
        report = self._probe.probe(artifact)
        if report.status == ProbeStatus.UNBLOCKED:
            repaired = repaired.model_copy(
                update={"status": ProcedureStatus.LEARNER_READY, "updated_at": datetime.now(UTC)}
            )

        step_id = repair.changed_step_ids[0]
        correction = Correction(
            procedure_id=procedure_id,
            step_id=step_id,
            previous_state=self._step(before_procedure, step_id).model_dump(mode="json"),
            new_state=self._step(repaired, step_id).model_dump(mode="json"),
            teacher_feedback=teacher_clarification.strip(),
            evidence_ref=evidence,
        )
        run = ProbeRun(
            procedure_id=procedure_id,
            learner_artifact_hash=artifact.content_hash(),
            report=report,
            phase="after_repair",
            linked_probe_run_id=before_run.probe_run_id,
        )
        self.repository.save_procedure(
            repaired, expected_updated_at=before_procedure.updated_at.isoformat()
        )
        self.repository.append_correction(correction)
        self.repository.save_probe_run(run)
        return RepairOutcome(procedure=repaired, correction=correction, probe_run=run)

    def start_learner(self, procedure_id: str) -> LearnerProgress:
        procedure = self.repository.get_procedure(procedure_id)
        if procedure.status != ProcedureStatus.LEARNER_READY:
            raise ValueError("a learner session requires a learner-ready procedure")
        artifact = procedure.learner_view()
        session = LearnerSession(
            procedure_id=procedure_id,
            procedure_hash=artifact.content_hash(),
        )
        self.repository.save_learner_session(session)
        return LearnerProgress(session=session, current_step=artifact.steps[0])

    def checkpoint(self, session_id: str, observation: LearnerObservation) -> LearnerProgress:
        session = self.repository.get_learner_session(session_id)
        if session.status != "active":
            raise ValueError("learner session is not active")
        procedure = self.repository.get_procedure(session.procedure_id).learner_view()
        if procedure.content_hash() != session.procedure_hash:
            raise ValueError("procedure changed after this learner session started")
        step = procedure.steps[session.current_step_order - 1]
        if observation.step_id != step.step_id:
            raise ValueError("observation does not match the current learner step")

        evaluation = self._checkpoint_evaluator.evaluate(
            procedure=procedure,
            step=step,
            observation=observation,
        )
        event = LearnerEvent(
            session_id=session_id,
            step_id=step.step_id,
            observation=observation,
            evaluation=evaluation,
        )
        session.attempts += 1
        if evaluation.decision == CheckpointDecision.ADVANCE:
            session.completed_step_ids.append(step.step_id)
            if session.current_step_order == len(procedure.steps):
                session.status = "completed"
            else:
                session.current_step_order += 1
        elif evaluation.decision == CheckpointDecision.HUMAN_CONFIRMATION:
            session.status = "needs_human"
        session.updated_at = datetime.now(UTC)
        self.repository.append_learner_event(event)
        self.repository.save_learner_session(session)
        current = (
            None
            if session.status == "completed"
            else procedure.steps[session.current_step_order - 1]
        )
        return LearnerProgress(session=session, current_step=current, latest_event=event)

    @staticmethod
    def _step(procedure: Procedure, step_id: str):
        try:
            return next(step for step in procedure.steps if step.step_id == step_id)
        except StopIteration as exc:
            raise ValueError(f"unknown changed step {step_id!r}") from exc

    @classmethod
    def _validate_bounded_repair(
        cls, before: Procedure, after: Procedure, changed_step_ids: list[str]
    ) -> None:
        if not changed_step_ids:
            raise ValueError("repair must identify at least one changed step")
        if before.id != after.id or len(before.steps) != len(after.steps):
            raise ValueError("repair cannot replace the procedure or add/remove steps")
        declared = set(changed_step_ids)
        actual = {
            old.step_id
            for old, new in zip(before.steps, after.steps, strict=True)
            if old.model_dump() != new.model_dump()
        }
        if actual != declared:
            raise ValueError("repair changed steps do not match changed_step_ids")
