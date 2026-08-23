"""Application services for the complete local ByFeel loop."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .adk_runtime import (
    LearnerCoachExecution,
    ProbeExecution,
    ProbeRuntime,
    TeachingPartnerRuntime,
)
from .evidence import EvidenceStore
from .experiment import GateAExperiment, StructuredClient
from .media_ingest import (
    BrowserEvidencePackage,
    MediaDraft,
    MultimodalClient,
    SpeechMode,
    analyze_teacher_evidence_package,
    analyze_teacher_media,
)
from .models import (
    ApprovedDemonstration,
    ApprovedTeacherIntervention,
    AuditEvent,
    BlockerReview,
    BlockerReviewDecision,
    Checkpoint,
    CheckpointDecision,
    CheckpointEvaluation,
    CheckpointModality,
    Correction,
    EvidenceRef,
    IssueType,
    KnowledgeGap,
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
    ProcedureStep,
    ProcedureVersion,
    RepairOutcome,
    RepairResult,
    ReviewedRepairContext,
    TargetedClarification,
    TeacherDemo,
    TeacherSession,
    TeacherSessionStatus,
    TeachingOutcome,
)
from .prompts import PROBE_SYSTEM, probe_prompt
from .repositories import ByFeelRepository, NotFoundError

LEGACY_VIDEO_UPLOAD_LIMIT_BYTES = 50 * 1024 * 1024
STREAM_VIDEO_UPLOAD_LIMIT_BYTES = 512 * 1024 * 1024
TEACHER_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
}


class CheckpointEvaluator(Protocol):
    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> CheckpointEvaluation | LearnerCoachExecution: ...


class BlindedProbeGateway:
    """Runtime information barrier: this interface accepts learner artifacts only."""

    def __init__(self, client: StructuredClient) -> None:
        self._client = client

    def probe(self, artifact: LearnerProcedure) -> ProbeExecution:
        if not isinstance(artifact, LearnerProcedure):
            raise TypeError("the blinded probe accepts LearnerProcedure only")
        return ProbeExecution(
            report=self._client.generate(
                system=PROBE_SYSTEM,
                prompt=probe_prompt(artifact),
                schema=ProbeReport,
            )
        )


class ByFeelService:
    def __init__(
        self,
        *,
        repository: ByFeelRepository,
        teaching_client: StructuredClient,
        checkpoint_evaluator: CheckpointEvaluator,
        probe_runtime: ProbeRuntime | None = None,
        teaching_runtime: TeachingPartnerRuntime | None = None,
        media_client: MultimodalClient | None = None,
        media_analyzer: Callable[..., MediaDraft] = analyze_teacher_media,
        media_evidence_analyzer: Callable[..., MediaDraft] = analyze_teacher_evidence_package,
        evidence_store: EvidenceStore | None = None,
        run_root: Path | None = None,
    ) -> None:
        self.repository = repository
        self._experiment = GateAExperiment(teaching_client)
        self._probe = probe_runtime or BlindedProbeGateway(teaching_client)
        self._checkpoint_evaluator = checkpoint_evaluator
        self._teaching_runtime = teaching_runtime
        self._media_client = media_client
        self._media_analyzer = media_analyzer
        self._media_evidence_analyzer = media_evidence_analyzer
        self.evidence_store = evidence_store
        self._run_root = run_root or Path(os.getenv("BYFEEL_RUN_ROOT", "runs/web"))

    def create_teacher_session(
        self,
        *,
        title: str,
        domain: str,
        learner_goal: str,
        constraints: list[str],
        speech_mode: str,
    ) -> TeacherSession:
        session = TeacherSession(
            title=title,
            domain=domain,
            learner_goal=learner_goal,
            constraints=constraints,
            speech_mode=SpeechMode(speech_mode).value,
        )
        self.repository.save_teacher_session(session)
        self._audit(
            event_type="teacher_session_created",
            entity_ref=session.session_id,
            actor="teacher",
            summary="Teacher created a private bounded-demonstration session.",
        )
        return session

    def process_teacher_video(
        self,
        session_id: str,
        *,
        video: bytes,
        content_type: str,
    ) -> MediaDraft:
        if not video:
            raise ValueError("teacher video cannot be empty")
        if len(video) > LEGACY_VIDEO_UPLOAD_LIMIT_BYTES:
            raise ValueError("teacher video exceeds the 50 MiB limit")
        source = self.begin_teacher_video_upload(session_id, content_type=content_type)
        try:
            source.write_bytes(video)
        except Exception as exc:
            self.fail_teacher_video_upload(session_id, exc)
            raise
        return self.finish_teacher_video_upload(
            session_id,
            source=source,
            content_type=content_type,
        )

    def begin_teacher_video_upload(self, session_id: str, *, content_type: str) -> Path:
        if self._media_client is None:
            raise RuntimeError("teacher media processing is not configured")
        try:
            extension = TEACHER_VIDEO_TYPES[content_type]
        except KeyError as exc:
            raise ValueError("teacher video must be MP4, WebM, QuickTime, or Matroska") from exc
        session = self.repository.get_teacher_session(session_id)
        if session.status != TeacherSessionStatus.AWAITING_MEDIA:
            raise ValueError("this teacher session already received media")
        session.status = TeacherSessionStatus.PROCESSING
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)
        run_dir = self._run_root / session.session_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir / f"teacher-source{extension}"

    def process_teacher_evidence_package(
        self,
        session_id: str,
        *,
        package: BrowserEvidencePackage,
    ) -> MediaDraft:
        if self._media_client is None:
            raise RuntimeError("teacher media processing is not configured")
        session = self.repository.get_teacher_session(session_id)
        if session.status != TeacherSessionStatus.AWAITING_MEDIA:
            raise ValueError("this teacher session already received media")
        session.status = TeacherSessionStatus.PROCESSING
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)
        run_dir = self._run_root / session.session_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            draft = self._media_evidence_analyzer(
                client=self._media_client,
                package=package,
                run_dir=run_dir,
                title=session.title,
                domain=session.domain,
                learner_goal=session.learner_goal,
                constraints=session.constraints,
                speech_mode=session.speech_mode,
            )
            if self.evidence_store is not None:
                content_by_id = {frame.sample_id: frame.content for frame in package.frames}
                type_by_id = {frame.sample_id: frame.content_type for frame in package.frames}
                draft.frame_samples = [
                    sample.model_copy(
                        update={
                            "evidence": self.evidence_store.put(
                                content_by_id[sample.sample_id],
                                content_type=type_by_id[sample.sample_id],
                                source="teacher",
                            )
                        }
                    )
                    for sample in draft.frame_samples
                ]
        except Exception as exc:
            self.fail_teacher_video_upload(session_id, exc)
            raise
        self.repository.save_media_draft(draft)
        session.status = TeacherSessionStatus.REVIEW_REQUIRED
        session.media_run_id = draft.run_id
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)
        self._audit(
            event_type="browser_evidence_package_ingested",
            entity_ref=session_id,
            actor="teacher",
            summary=(
                f"Accepted {len(package.frames)} bounded browser-derived frames; "
                "source video and audio were not uploaded."
            ),
            related_refs=[package.policy_version, package.source_fingerprint],
        )
        return draft

    def finish_teacher_video_upload(
        self,
        session_id: str,
        *,
        source: Path,
        content_type: str,
    ) -> MediaDraft:
        try:
            extension = TEACHER_VIDEO_TYPES[content_type]
        except KeyError as exc:
            raise ValueError("teacher video must be MP4, WebM, QuickTime, or Matroska") from exc
        session = self.repository.get_teacher_session(session_id)
        if session.status != TeacherSessionStatus.PROCESSING:
            raise ValueError("teacher media upload was not reserved for processing")
        expected_source = self._run_root / session.session_id / f"teacher-source{extension}"
        if source.resolve() != expected_source.resolve():
            raise ValueError("teacher media source is outside its reserved local session path")
        if not source.exists() or source.stat().st_size == 0:
            raise ValueError("teacher video cannot be empty")
        if source.stat().st_size > STREAM_VIDEO_UPLOAD_LIMIT_BYTES:
            raise ValueError("teacher video exceeds the 512 MiB streaming limit")
        try:
            draft = self._media_analyzer(
                client=self._media_client,
                source=source,
                run_dir=source.parent,
                title=session.title,
                domain=session.domain,
                learner_goal=session.learner_goal,
                constraints=session.constraints,
                speech_mode=session.speech_mode,
            )
        except Exception as exc:
            self.fail_teacher_video_upload(session_id, exc)
            raise
        self.repository.save_media_draft(draft)
        session.status = TeacherSessionStatus.REVIEW_REQUIRED
        session.media_run_id = draft.run_id
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)
        return draft

    def fail_teacher_video_upload(self, session_id: str, error: Exception) -> None:
        session = self.repository.get_teacher_session(session_id)
        session.status = TeacherSessionStatus.FAILED
        session.failure_message = str(error)[:500]
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)

    def approve_factual_record(
        self, session_id: str, approved_factual_record: str
    ) -> ApprovedDemonstration:
        session = self.repository.get_teacher_session(session_id)
        if session.status != TeacherSessionStatus.REVIEW_REQUIRED:
            raise ValueError("teacher facts can be approved only after media review")
        draft = self.repository.get_media_draft(session_id)
        factual_record = approved_factual_record.strip()
        if len(factual_record) < 20:
            raise ValueError("approved factual record must contain at least 20 characters")
        demo = TeacherDemo(
            title=draft.title,
            domain=draft.domain,
            learner_goal=draft.learner_goal,
            raw_demonstration=factual_record,
            constraints=draft.constraints,
        )
        approval = ApprovedDemonstration(
            approval_id=f"factual-approval-{session_id}",
            teacher_session_id=session_id,
            approved_factual_hash=sha256(factual_record.encode()).hexdigest(),
            demo=demo,
        )
        self.repository.save_demonstration_approval(approval)
        session.status = TeacherSessionStatus.FACTS_APPROVED
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)
        self._audit(
            event_type="factual_record_approved",
            entity_ref=approval.approval_id,
            actor="teacher",
            summary="Teacher approved the exact factual record for extraction.",
            related_refs=[session_id, approval.approved_factual_hash],
        )
        return approval

    def extract_approved_demonstration(self, session_id: str) -> TeachingOutcome:
        if self._teaching_runtime is None:
            raise RuntimeError("ADK Teaching Partner is not configured")
        session = self.repository.get_teacher_session(session_id)
        if session.status != TeacherSessionStatus.FACTS_APPROVED:
            raise ValueError("procedure extraction requires immutable factual-record approval")
        approval = self.repository.get_demonstration_approval(session_id)
        teaching_execution = self._teaching_runtime.extract(approval)
        if not isinstance(teaching_execution.output, Procedure):
            raise RuntimeError("Teaching Partner extraction returned an invalid output type")
        procedure = teaching_execution.output
        artifact = procedure.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()
        probe_execution = self._probe.probe(artifact)
        run = ProbeRun(
            procedure_id=procedure.id,
            learner_artifact_hash=artifact.content_hash(),
            report=probe_execution.report,
            phase="before_repair",
        )
        procedure = procedure.model_copy(
            update={"status": ProcedureStatus.TESTED, "updated_at": datetime.now(UTC)}
        )
        self.repository.save_procedure(procedure)
        self.repository.save_probe_run(run)
        self._version(procedure, "extracted")
        self.repository.append_agent_run(
            teaching_execution.agent_run.model_copy(update={"procedure_id": procedure.id})
        )
        if probe_execution.agent_run is not None:
            self.repository.append_agent_run(
                probe_execution.agent_run.model_copy(update={"procedure_id": procedure.id})
            )
        session.status = TeacherSessionStatus.PROCEDURE_EXTRACTED
        session.procedure_id = procedure.id
        session.updated_at = datetime.now(UTC)
        self.repository.save_teacher_session(session)
        self._audit(
            event_type="procedure_extracted_and_probed",
            entity_ref=procedure.id,
            procedure_id=procedure.id,
            actor="system",
            summary=(
                "Teaching Partner extracted approved facts and a fresh blinded probe tested "
                "the learner artifact."
            ),
            related_refs=[approval.approval_id, run.probe_run_id],
        )
        return TeachingOutcome(procedure=procedure, probe_run=run)

    def teach(self, demo: TeacherDemo) -> TeachingOutcome:
        procedure = self._experiment.extract(demo)
        artifact = procedure.learner_view()
        execution = self._probe.probe(artifact)
        report = execution.report
        run = ProbeRun(
            procedure_id=procedure.id,
            learner_artifact_hash=artifact.content_hash(),
            report=report,
            phase="before_repair",
        )
        self.repository.save_procedure(procedure)
        self.repository.save_probe_run(run)
        if execution.agent_run is not None:
            self.repository.append_agent_run(execution.agent_run)
        return TeachingOutcome(procedure=procedure, probe_run=run)

    def seed_rehearsal(self) -> TeachingOutcome:
        """Create a clearly labeled local fixture; this is not model or Gate A evidence."""

        procedure_id = f"seeded-rehearsal-{uuid4().hex[:8]}"
        initial = Procedure(
            id=procedure_id,
            title="Seeded paper-fold rehearsal",
            domain="local deterministic fixture",
            learner_goal="Practice the full ByFeel browser loop without model calls",
            status=ProcedureStatus.TESTED,
            steps=[
                ProcedureStep(
                    step_id="step-1",
                    order=1,
                    action="Press the fold until it is firm enough",
                    prerequisites=[],
                    completion_conditions=[],
                    learner_risks=[],
                    checkpoints=[],
                    exceptions=[],
                    confidence=0.5,
                    open_questions=[],
                )
            ],
        )
        initial_artifact = initial.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()
        blocker = KnowledgeGap(
            gap_id="seed-gap-1",
            step_id="step-1",
            issue_type=IssueType.MISSING_COMPLETION_CONDITION,
            description="The learner cannot observe what firm enough means.",
            missing_information="A visible stopping cue.",
            severity=0.95,
            blocks_execution=True,
        )
        before = ProbeRun(
            procedure_id=procedure_id,
            learner_artifact_hash=initial_artifact.content_hash(),
            report=ProbeReport(
                status=ProbeStatus.BLOCKED,
                summary="Seeded novice cannot identify the stopping point.",
                blockers=[blocker],
                teacher_question="What visible result shows the crease is complete?",
            ),
            phase="before_repair",
        )
        repaired = Procedure(
            id=procedure_id,
            title=initial.title,
            domain=initial.domain,
            learner_goal=initial.learner_goal,
            status=ProcedureStatus.TESTED,
            steps=[
                initial.steps[0].model_copy(
                    update={
                        "action": (
                            "Press the fold until the crease stays flat after your hand is removed"
                        ),
                        "completion_conditions": [
                            "The crease stays flat after your hand is removed"
                        ],
                        "confidence": 1,
                    }
                )
            ],
        )
        repaired_artifact = repaired.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()
        after = ProbeRun(
            procedure_id=procedure_id,
            learner_artifact_hash=repaired_artifact.content_hash(),
            report=ProbeReport(
                status=ProbeStatus.UNBLOCKED,
                summary="Seeded fresh novice can act and observe when to advance.",
            ),
            phase="after_repair",
            linked_probe_run_id=before.probe_run_id,
        )
        review = BlockerReview(
            run_id=before.probe_run_id,
            decision=BlockerReviewDecision.GENUINE,
            reason="Seed fixture: the missing observable cue prevents a stopping decision.",
        )
        correction = Correction(
            procedure_id=procedure_id,
            step_id="step-1",
            previous_state=initial.steps[0].model_dump(mode="json"),
            new_state=repaired.steps[0].model_dump(mode="json"),
            teacher_feedback="The crease stays flat after your hand is removed.",
        )
        approved = repaired.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY, "updated_at": datetime.now(UTC)}
        )
        self.repository.save_procedure(approved)
        self.repository.save_probe_run(before)
        self.repository.append_blocker_review(review)
        self.repository.append_correction(correction)
        self.repository.save_probe_run(after)
        self._version(initial, "extracted")
        self._version(repaired, "repaired")
        self._version(approved, "learner_approved")
        self._audit(
            event_type="seeded_rehearsal_loaded",
            entity_ref=procedure_id,
            procedure_id=procedure_id,
            actor="system",
            summary=(
                "Deterministic local fixture loaded with zero model calls; excluded from Gate A."
            ),
            related_refs=[before.probe_run_id, after.probe_run_id],
        )
        return TeachingOutcome(procedure=approved, probe_run=after)

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
        review = self.repository.get_blocker_review(before_run.probe_run_id)
        if review.decision != BlockerReviewDecision.GENUINE:
            raise ValueError("a human reviewer rejected this blocker; repair is not allowed")
        try:
            self.repository.latest_probe_run(procedure_id, "after_repair")
        except NotFoundError:
            pass
        else:
            raise ValueError("this blocker already received its one clarification and repair")
        teaching_agent_run = None
        if self._teaching_runtime is not None:
            selected_gap = max(before_run.report.blockers, key=lambda gap: gap.severity)
            clarification = TargetedClarification(
                probe_run_id=before_run.probe_run_id,
                gap_id=selected_gap.gap_id,
                question=before_run.report.teacher_question or selected_gap.missing_information,
                verbatim_answer=teacher_clarification.strip(),
            )
            context = ReviewedRepairContext(
                procedure=before_procedure,
                probe_run=before_run,
                review=review,
                clarification=clarification,
            )
            teaching_execution = self._teaching_runtime.repair(context)
            if not isinstance(teaching_execution.output, RepairResult):
                raise RuntimeError("Teaching Partner repair returned an invalid output type")
            repair = teaching_execution.output
            teaching_agent_run = teaching_execution.agent_run
            self._validate_repair_provenance(
                before_procedure,
                repair.procedure,
                repair.changed_step_ids,
                teacher_clarification.strip(),
                repair.source_quotes,
            )
        else:
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
        artifact = repaired.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()
        execution = self._probe.probe(artifact)
        report = execution.report
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
        self._version(repaired, "repaired")
        if teaching_agent_run is not None:
            self.repository.append_agent_run(
                teaching_agent_run.model_copy(update={"procedure_id": procedure_id})
            )
        if execution.agent_run is not None:
            self.repository.append_agent_run(
                execution.agent_run.model_copy(update={"procedure_id": procedure_id})
            )
        self._audit(
            event_type="bounded_repair_reprobed",
            entity_ref=correction.correction_id,
            procedure_id=procedure_id,
            actor="system",
            summary=(
                "One reviewed blocker was repaired from one verbatim answer and tested in a "
                "fresh probe session."
            ),
            related_refs=[before_run.probe_run_id, run.probe_run_id],
        )
        return RepairOutcome(procedure=repaired, correction=correction, probe_run=run)

    def approve_procedure_for_learner(self, procedure_id: str) -> Procedure:
        procedure = self.repository.get_procedure(procedure_id)
        try:
            probe = self.repository.latest_probe_run(procedure_id, "after_repair")
        except NotFoundError:
            probe = self.repository.latest_probe_run(procedure_id, "before_repair")
        approved_artifact = procedure.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()
        if probe.learner_artifact_hash != approved_artifact.content_hash():
            raise ValueError("the latest probe did not test this exact learner artifact")
        if probe.report.status != ProbeStatus.UNBLOCKED:
            raise ValueError("only an unblocked learner artifact can be approved")
        if procedure.status != ProcedureStatus.TESTED:
            raise ValueError("only a probe-tested procedure can be approved")
        approved = procedure.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY, "updated_at": datetime.now(UTC)}
        )
        self.repository.save_procedure(
            approved,
            expected_updated_at=procedure.updated_at.isoformat(),
        )
        self._version(approved, "learner_approved")
        self._audit(
            event_type="learner_artifact_approved",
            entity_ref=approved.id,
            procedure_id=approved.id,
            actor="teacher",
            summary="Human approved the exact unblocked artifact for learner sessions.",
            related_refs=[probe.probe_run_id, probe.learner_artifact_hash],
        )
        return approved

    def review_blocker(
        self,
        probe_run_id: str,
        decision: BlockerReviewDecision,
        reason: str,
    ) -> BlockerReview:
        run = self.repository.get_probe_run(probe_run_id)
        if run.phase != "before_repair" or run.report.status != ProbeStatus.BLOCKED:
            raise ValueError("only an initial blocked probe can receive blocker review")
        review = BlockerReview(
            run_id=probe_run_id,
            decision=decision,
            reason=reason,
        )
        self.repository.append_blocker_review(review)
        self._audit(
            event_type="blocker_reviewed",
            entity_ref=review.run_id,
            procedure_id=run.procedure_id,
            actor="human_reviewer",
            summary=f"Human classified the candidate as {review.decision.value}.",
            related_refs=[run.probe_run_id],
        )
        return review

    def start_learner(self, procedure_id: str) -> LearnerProgress:
        procedure = self.repository.get_procedure(procedure_id)
        if procedure.status != ProcedureStatus.LEARNER_READY:
            raise ValueError("a learner session requires a learner-ready procedure")
        artifact = procedure.learner_view()
        version_id = None
        for version in reversed(self.repository.list_procedure_versions(procedure_id)):
            if version.learner_artifact_hash == artifact.content_hash():
                version_id = version.version_id
                break
        session = LearnerSession(
            procedure_id=procedure_id,
            procedure_version_id=version_id,
            procedure_hash=artifact.content_hash(),
        )
        self.repository.save_learner_session(session)
        return LearnerProgress(session=session, current_step=artifact.steps[0])

    def start_learner_for_version(self, procedure_version_id: str) -> LearnerProgress:
        version = self.repository.get_procedure_version(procedure_version_id)
        artifact = version.learner_artifact()
        session = LearnerSession(
            procedure_id=version.procedure_id,
            procedure_version_id=version.version_id,
            procedure_hash=artifact.content_hash(),
        )
        self.repository.save_learner_session(session)
        return LearnerProgress(session=session, current_step=artifact.steps[0])

    def checkpoint(
        self,
        session_id: str,
        observation: LearnerObservation,
        *,
        approved_intervention: ApprovedTeacherIntervention | None = None,
    ) -> LearnerProgress:
        session = self.repository.get_learner_session(session_id)
        if session.status != "active":
            raise ValueError("learner session is not active")
        if session.procedure_version_id is not None:
            version = self.repository.get_procedure_version(session.procedure_version_id)
            procedure = version.learner_artifact()
        else:
            procedure = self.repository.get_procedure(session.procedure_id).learner_view()
        if procedure.content_hash() != session.procedure_hash:
            raise ValueError("procedure changed after this learner session started")
        step = procedure.steps[session.current_step_order - 1]
        if observation.step_id != step.step_id:
            raise ValueError("observation does not match the current learner step")

        if approved_intervention is not None:
            self._validate_approved_intervention(
                session=session,
                procedure=procedure,
                step=step,
                intervention=approved_intervention,
            )

        if procedure.id.startswith("seeded-rehearsal-"):
            incorrect = any(
                marker in observation.description.casefold()
                for marker in ("springs", "opens", "misaligned", "not flat", "uneven")
            )
            has_approved_cue = bool(step.completion_conditions)
            checkpoint_execution = CheckpointEvaluation(
                decision=(
                    CheckpointDecision.BLOCK
                    if incorrect and has_approved_cue
                    else CheckpointDecision.HUMAN_CONFIRMATION
                    if incorrect
                    else CheckpointDecision.ADVANCE
                ),
                confidence=1,
                explanation=(
                    "The seeded learner state misses the teacher-approved visible cue."
                    if incorrect and has_approved_cue
                    else "The static seeded instructions do not provide a safe visible cue."
                    if incorrect
                    else "The seeded learner state satisfies the approved visible cue."
                ),
                corrective_guidance=(
                    "Press again until the crease stays flat after your hand is removed."
                    if incorrect and has_approved_cue
                    else None
                ),
                teacher_derived=has_approved_cue,
            )
        else:
            checkpoint_execution = self._checkpoint_evaluator.evaluate(
                procedure=procedure,
                step=step,
                observation=observation,
            )
        if isinstance(checkpoint_execution, LearnerCoachExecution):
            evaluation = checkpoint_execution.evaluation
            self.repository.append_agent_run(
                checkpoint_execution.agent_run.model_copy(update={"procedure_id": procedure.id})
            )
        else:
            evaluation = checkpoint_execution
        requested_decision = evaluation.decision
        if approved_intervention is not None and evaluation.decision == CheckpointDecision.BLOCK:
            evaluation = evaluation.model_copy(
                update={
                    "corrective_guidance": approved_intervention.guidance,
                    "teacher_derived": True,
                }
            )
        unsafe_advance_suppressed = (
            observation.is_deliberate_incorrect and requested_decision == CheckpointDecision.ADVANCE
        )
        if unsafe_advance_suppressed:
            evaluation = CheckpointEvaluation(
                decision=CheckpointDecision.HUMAN_CONFIRMATION,
                visual_state=evaluation.visual_state,
                confidence=evaluation.confidence,
                explanation=(
                    "Advance was suppressed because the facilitator marked this as the "
                    "deliberate incorrect state."
                ),
                checkpoint_id=evaluation.checkpoint_id,
                teacher_derived=False,
            )
        event_time = datetime.now(UTC)
        event = LearnerEvent(
            session_id=session_id,
            step_id=step.step_id,
            observation=observation,
            evaluation=evaluation,
            attempt_number=session.attempts + 1,
            elapsed_ms=max(0, int((event_time - session.created_at).total_seconds() * 1000)),
            requested_decision=requested_decision,
            unsafe_advance_suppressed=unsafe_advance_suppressed,
            created_at=event_time,
            updated_at=event_time,
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
        session.updated_at = event_time
        self.repository.append_learner_event(event)
        self.repository.save_learner_session(session)
        self._audit(
            event_type="learner_checkpoint_evaluated",
            entity_ref=event.event_id,
            procedure_id=procedure.id,
            actor="learner",
            summary=f"Learner Coach returned {evaluation.decision.value} for the current step.",
            related_refs=[session_id, step.step_id],
        )
        current = (
            None
            if session.status == "completed"
            else procedure.steps[session.current_step_order - 1]
        )
        return LearnerProgress(session=session, current_step=current, latest_event=event)

    def resume_learner(self, session_id: str) -> LearnerProgress:
        session = self.repository.get_learner_session(session_id)
        if session.procedure_version_id is not None:
            procedure = self.repository.get_procedure_version(
                session.procedure_version_id
            ).learner_artifact()
        else:
            procedure = self.repository.get_procedure(session.procedure_id).learner_view()
        if procedure.content_hash() != session.procedure_hash:
            raise ValueError("procedure changed after this learner session started")
        current = (
            None
            if session.status == "completed"
            else procedure.steps[session.current_step_order - 1]
        )
        events = self.repository.list_learner_events(session_id)
        return LearnerProgress(
            session=session,
            current_step=current,
            latest_event=events[-1] if events else None,
        )

    @staticmethod
    def _step(procedure: Procedure, step_id: str):
        try:
            return next(step for step in procedure.steps if step.step_id == step_id)
        except StopIteration as exc:
            raise ValueError(f"unknown changed step {step_id!r}") from exc

    def _validate_approved_intervention(
        self,
        *,
        session: LearnerSession,
        procedure: LearnerProcedure,
        step: LearnerStep,
        intervention: ApprovedTeacherIntervention,
    ) -> None:
        if session.procedure_version_id != intervention.procedure_version_id:
            raise ValueError("intervention provenance does not match the learner procedure version")
        version = self.repository.get_procedure_version(intervention.procedure_version_id)
        if version.reason != "learner_approved":
            raise ValueError("only a learner-approved procedure version may guide a learner")
        if version.procedure_id != session.procedure_id:
            raise ValueError("intervention provenance does not match the learner procedure")
        if intervention.step_id != step.step_id:
            raise ValueError("intervention provenance does not match the current learner step")
        if version.learner_artifact().content_hash() != session.procedure_hash:
            raise ValueError("intervention provenance does not match the frozen learner artifact")
        correction = self.repository.get_correction(intervention.correction_id)
        if correction.procedure_id != session.procedure_id or correction.step_id != step.step_id:
            raise ValueError("intervention correction provenance does not match the learner step")
        version_step = self._step(version.procedure, step.step_id)
        if correction.new_state != version_step.model_dump(mode="json"):
            raise ValueError(
                "intervention correction does not match the approved procedure version"
            )
        if intervention.guidance != correction.teacher_feedback:
            raise ValueError("intervention guidance must be the approved teacher feedback verbatim")

    def _version(
        self,
        procedure: Procedure,
        reason: str,
    ) -> ProcedureVersion:
        learner_artifact = procedure.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()
        version = ProcedureVersion(
            procedure_id=procedure.id,
            learner_artifact_hash=learner_artifact.content_hash(),
            reason=reason,
            procedure=procedure,
        )
        self.repository.append_procedure_version(version)
        return version

    def _audit(
        self,
        *,
        event_type: str,
        entity_ref: str,
        actor: str,
        summary: str,
        procedure_id: str | None = None,
        related_refs: list[str] | None = None,
    ) -> None:
        self.repository.append_audit_event(
            AuditEvent(
                event_type=event_type,
                entity_ref=entity_ref,
                procedure_id=procedure_id,
                actor=actor,
                summary=summary,
                related_refs=related_refs or [],
            )
        )

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

    @classmethod
    def _validate_repair_provenance(
        cls,
        before: Procedure,
        after: Procedure,
        changed_step_ids: list[str],
        verbatim_answer: str,
        source_quotes: list[str],
    ) -> None:
        if not source_quotes:
            raise ValueError("ADK repair must cite the verbatim teacher answer")
        if any(len(quote.strip()) < 5 or quote not in verbatim_answer for quote in source_quotes):
            raise ValueError("repair source quotes must be exact teacher-answer substrings")
        for step_id in changed_step_ids:
            old = cls._step(before, step_id)
            new = cls._step(after, step_id)
            old_claims = {
                old.action,
                *old.prerequisites,
                *old.completion_conditions,
                *old.learner_risks,
                *old.exceptions,
                *old.open_questions,
            }
            new_claims = {
                new.action,
                *new.prerequisites,
                *new.completion_conditions,
                *new.learner_risks,
                *new.exceptions,
                *new.open_questions,
            }
            for claim in new_claims - old_claims:
                if not any(quote.casefold() in claim.casefold() for quote in source_quotes):
                    raise ValueError(
                        "every new learner-facing repair claim must contain an exact source quote"
                    )
