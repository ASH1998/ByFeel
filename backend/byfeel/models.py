"""Canonical ByFeel domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimestampedModel(StrictModel):
    schema_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProcedureStatus(StrEnum):
    DRAFT = "draft"
    TESTED = "tested"
    LEARNER_READY = "learner_ready"


class TeacherSessionStatus(StrEnum):
    AWAITING_MEDIA = "awaiting_media"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    FACTS_APPROVED = "facts_approved"
    PROCEDURE_EXTRACTED = "procedure_extracted"
    FAILED = "failed"


class IssueType(StrEnum):
    AMBIGUOUS_QUANTITY = "ambiguous_quantity"
    MISSING_COMPLETION_CONDITION = "missing_completion_condition"
    UNCLEAR_EXCEPTION = "unclear_exception"
    MISSING_STEP = "missing_step"
    CONFLICTING_INSTRUCTION = "conflicting_instruction"
    INSUFFICIENT_VISUAL_EVIDENCE = "insufficient_visual_evidence"
    AMBIGUOUS_ACTION = "ambiguous_action"
    MISSING_PREREQUISITE = "missing_prerequisite"


class CheckpointModality(StrEnum):
    VISUAL = "visual"
    TEMPORAL = "temporal"
    VERBAL = "verbal"
    MEASURABLE = "measurable"


class CheckpointDecision(StrEnum):
    ADVANCE = "advance"
    BLOCK = "block"
    RETRY_SNAPSHOT = "retry_snapshot"
    HUMAN_CONFIRMATION = "human_confirmation"


class AgentRole(StrEnum):
    TEACHING_PARTNER = "teaching_partner"
    BLINDED_PROBE = "blinded_probe"
    LEARNER_COACH = "learner_coach"


class AgentRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentToolStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VisualCheckpointState(StrEnum):
    NOT_READY = "not_ready"
    READY = "ready"
    INCORRECT_OR_OVERSHOT = "incorrect_or_overshot"


class GateCArm(StrEnum):
    STATIC_INSTRUCTIONS = "static_instructions"
    BYFEEL_TEACHER_REPAIRED = "byfeel_teacher_repaired"


class GateCExperimentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETE = "complete"


class GateCArmStatus(StrEnum):
    ACTIVE = "active"
    FINALIZED = "finalized"


class GateCDetectionOutcome(StrEnum):
    DETECTED = "detected"
    SAFE_ABSTENTION = "safe_abstention"
    MISSED_DETECTION = "missed_detection"


class GateCFinalOutcome(StrEnum):
    COMPLETED_AFTER_CORRECTION = "completed_after_correction"
    COMPLETED_WITHOUT_CORRECTION = "completed_without_correction"
    DETECTED_NOT_CORRECTED = "detected_not_corrected"
    SAFE_ABSTENTION = "safe_abstention"
    MISSED_DETECTION = "missed_detection"
    INCOMPLETE = "incomplete"


class EvidenceRef(StrictModel):
    evidence_id: str
    object_name: str
    content_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)
    source: Literal["teacher", "learner", "test"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentTokenUsage(StrictModel):
    prompt_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    thinking_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class AgentToolEvent(StrictModel):
    call_id: str
    tool_name: str
    status: AgentToolStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRunRecord(StrictModel):
    run_id: str
    role: AgentRole
    session_id: str
    context_ref: str
    procedure_id: str | None = None
    model: str
    allowed_tools: list[str]
    tool_events: list[AgentToolEvent] = Field(default_factory=list)
    token_usage: AgentTokenUsage = Field(default_factory=AgentTokenUsage)
    human_boundary_refs: list[str] = Field(default_factory=list)
    status: AgentRunStatus
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def run_metadata_is_safe_and_consistent(self) -> AgentRunRecord:
        if len(self.allowed_tools) != len(set(self.allowed_tools)):
            raise ValueError("allowed tool names must be unique")
        unexpected = {
            event.tool_name
            for event in self.tool_events
            if event.tool_name not in self.allowed_tools
        }
        if unexpected:
            raise ValueError(f"tool events contain non-allowed tools: {sorted(unexpected)}")
        if self.completed_at < self.started_at:
            raise ValueError("agent run completion cannot precede its start")
        return self


class Checkpoint(StrictModel):
    checkpoint_id: str
    modality: CheckpointModality
    description: str = Field(min_length=1)
    positive_examples: list[str] = Field(default_factory=list)
    negative_examples: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    teacher_notes: str | None = None
    confidence: float = Field(ge=0, le=1)
    human_confirmation_only: bool = False


class ProcedureStep(StrictModel):
    step_id: str = Field(description="Stable short identifier, such as step-1")
    order: int = Field(ge=1)
    action: str = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    completion_conditions: list[str] = Field(default_factory=list)
    learner_risks: list[str] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    open_questions: list[str] = Field(default_factory=list)


class Procedure(TimestampedModel):
    id: str = Field(description="Stable short identifier")
    title: str
    domain: str
    learner_goal: str
    status: ProcedureStatus = ProcedureStatus.DRAFT
    steps: list[ProcedureStep] = Field(min_length=1)

    @model_validator(mode="after")
    def steps_are_unique(self) -> Procedure:
        orders = [step.order for step in self.steps]
        step_ids = [step.step_id for step in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("step order values must be unique")
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step IDs must be unique")
        self.steps.sort(key=lambda step: step.order)
        return self

    def learner_view(self) -> LearnerProcedure:
        return LearnerProcedure(
            id=self.id,
            title=self.title,
            domain=self.domain,
            learner_goal=self.learner_goal,
            status=self.status,
            steps=[LearnerStep.model_validate(step.model_dump()) for step in self.steps],
        )


class LearnerStep(StrictModel):
    step_id: str
    order: int
    action: str
    prerequisites: list[str]
    completion_conditions: list[str]
    learner_risks: list[str]
    checkpoints: list[Checkpoint]
    exceptions: list[str]
    confidence: float
    open_questions: list[str]


class LearnerProcedure(StrictModel):
    id: str
    title: str
    domain: str
    learner_goal: str
    status: ProcedureStatus
    steps: list[LearnerStep]

    def content_hash(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()


class KnowledgeGap(StrictModel):
    gap_id: str
    step_id: str
    source: Literal["novice_probe"] = "novice_probe"
    issue_type: IssueType
    description: str
    missing_information: str
    severity: float = Field(ge=0, le=1)
    blocks_execution: bool

    @field_validator("source", mode="before")
    @classmethod
    def provenance_is_application_owned(cls, value: object) -> str:
        del value
        return "novice_probe"


class ProbeStatus(StrEnum):
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"


class BlockerReviewDecision(StrEnum):
    GENUINE = "genuine"
    FALSE_BLOCKER = "false_blocker"


class BlockerReview(StrictModel):
    run_id: str
    decision: BlockerReviewDecision
    reason: str = Field(min_length=10)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProbeReport(StrictModel):
    status: ProbeStatus
    summary: str
    blockers: list[KnowledgeGap] = Field(default_factory=list)
    non_blocking_improvements: list[KnowledgeGap] = Field(default_factory=list)
    assumptions_required: list[str] = Field(default_factory=list)
    teacher_question: str | None = None

    @model_validator(mode="after")
    def status_matches_blockers(self) -> ProbeReport:
        if any(not gap.blocks_execution for gap in self.blockers):
            raise ValueError("blockers must contain execution-blocking gaps only")
        if any(gap.blocks_execution for gap in self.non_blocking_improvements):
            raise ValueError("non-blocking improvements cannot block execution")
        blocking = [gap for gap in self.blockers if gap.blocks_execution]
        if self.status == ProbeStatus.BLOCKED and not blocking:
            raise ValueError("a blocked report must include an execution-blocking gap")
        if self.status == ProbeStatus.UNBLOCKED and blocking:
            raise ValueError("an unblocked report cannot include an execution-blocking gap")
        if self.status == ProbeStatus.BLOCKED and not self.teacher_question:
            raise ValueError("a blocked report must include one targeted teacher question")
        return self


class RepairResult(StrictModel):
    procedure: Procedure
    changed_step_ids: list[str]
    change_summary: str
    source_quotes: list[str] = Field(default_factory=list)


class Correction(TimestampedModel):
    correction_id: str = Field(default_factory=lambda: f"correction-{uuid4().hex[:12]}")
    procedure_id: str
    step_id: str
    previous_state: dict[str, object]
    new_state: dict[str, object]
    teacher_feedback: str = Field(min_length=1)
    evidence_ref: EvidenceRef | None = None
    supersedes: str | None = None


class ApprovedTeacherIntervention(StrictModel):
    """A service-validated pointer to one teacher-derived correction."""

    correction_id: str = Field(min_length=1)
    procedure_version_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    guidance: str = Field(min_length=1)


class ProcedureVersion(StrictModel):
    version_id: str = Field(default_factory=lambda: f"version-{uuid4().hex[:12]}")
    procedure_id: str
    learner_artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: Literal["extracted", "repaired", "learner_approved"]
    procedure: Procedure
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def version_matches_procedure(self) -> ProcedureVersion:
        if self.procedure.id != self.procedure_id:
            raise ValueError("procedure version identity does not match its procedure")
        return self

    def learner_artifact(self) -> LearnerProcedure:
        return self.procedure.model_copy(
            update={"status": ProcedureStatus.LEARNER_READY}
        ).learner_view()


class AuditEvent(StrictModel):
    event_id: str = Field(default_factory=lambda: f"audit-{uuid4().hex[:12]}")
    event_type: str
    entity_ref: str
    procedure_id: str | None = None
    actor: Literal["teacher", "human_reviewer", "learner", "system"]
    summary: str
    related_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProbeRun(TimestampedModel):
    probe_run_id: str = Field(default_factory=lambda: f"probe-{uuid4().hex[:12]}")
    procedure_id: str
    learner_artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    report: ProbeReport
    phase: Literal["before_repair", "after_repair"]
    linked_probe_run_id: str | None = None


class LearnerSession(TimestampedModel):
    session_id: str = Field(default_factory=lambda: f"learner-{uuid4().hex[:12]}")
    procedure_id: str
    procedure_version_id: str | None = None
    procedure_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_step_order: int = Field(default=1, ge=1)
    completed_step_ids: list[str] = Field(default_factory=list)
    attempts: int = Field(default=0, ge=0)
    status: Literal["active", "completed", "needs_human"] = "active"


class LearnerObservation(StrictModel):
    step_id: str
    description: str = Field(min_length=1)
    evidence: EvidenceRef | None = None
    is_deliberate_incorrect: bool = False
    is_correction: bool = False

    @model_validator(mode="after")
    def observation_state_flags_are_distinct(self) -> LearnerObservation:
        if self.is_deliberate_incorrect and self.is_correction:
            raise ValueError("an observation cannot be both incorrect and a correction")
        return self


class CheckpointEvaluation(StrictModel):
    decision: CheckpointDecision
    visual_state: VisualCheckpointState | None = None
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1)
    corrective_guidance: str | None = None
    checkpoint_id: str | None = None
    teacher_derived: bool = False

    @model_validator(mode="after")
    def decision_is_safe(self) -> CheckpointEvaluation:
        if self.decision == CheckpointDecision.ADVANCE and self.confidence < 0.8:
            raise ValueError("advance requires confidence of at least 0.8")
        if self.decision == CheckpointDecision.ADVANCE and self.visual_state in {
            VisualCheckpointState.NOT_READY,
            VisualCheckpointState.INCORRECT_OR_OVERSHOT,
        }:
            raise ValueError("advance requires a ready visual state")
        if self.decision == CheckpointDecision.BLOCK and not self.corrective_guidance:
            raise ValueError("block requires corrective guidance")
        return self


class LearnerEvent(TimestampedModel):
    event_id: str = Field(default_factory=lambda: f"event-{uuid4().hex[:12]}")
    session_id: str
    step_id: str
    observation: LearnerObservation
    evaluation: CheckpointEvaluation
    attempt_number: int = Field(default=1, ge=1)
    elapsed_ms: int = Field(default=0, ge=0)
    requested_decision: CheckpointDecision | None = None
    unsafe_advance_suppressed: bool = False


class GateCExperiment(StrictModel):
    experiment_id: str = Field(default_factory=lambda: f"gate-c-{uuid4().hex[:12]}")
    learner_pseudonym: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$",
    )
    procedure_id: str = Field(min_length=1)
    baseline_version_id: str = Field(min_length=1)
    byfeel_version_id: str = Field(min_length=1)
    checkpoint_step_id: str = Field(min_length=1)
    deliberate_incorrect_state: str = Field(min_length=10, max_length=2000)
    safety_confirmed: bool = False
    synthetic: bool = False
    synthetic_label: str | None = Field(default=None, max_length=200)
    status: GateCExperimentStatus = GateCExperimentStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def experiment_identity_is_safe(self) -> GateCExperiment:
        if "@" in self.learner_pseudonym or any(char.isspace() for char in self.learner_pseudonym):
            raise ValueError("learner_pseudonym must be a non-personal code")
        if self.baseline_version_id == self.byfeel_version_id:
            raise ValueError("Gate C arms must use different procedure versions")
        if not self.safety_confirmed:
            raise ValueError("Gate C requires explicit confirmation of a low-risk procedure")
        if self.synthetic and not self.synthetic_label:
            raise ValueError("synthetic Gate C experiments require a synthetic label")
        return self


class GateCArmRun(StrictModel):
    arm_run_id: str = Field(default_factory=lambda: f"gate-c-arm-{uuid4().hex[:12]}")
    experiment_id: str
    arm: GateCArm
    learner_session_id: str
    procedure_version_id: str
    procedure_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    deliberate_incorrect_state: str = Field(min_length=10)
    status: GateCArmStatus = GateCArmStatus.ACTIVE
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finalized_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    attempt_event_ids: list[str] = Field(default_factory=list)
    detection_outcome: GateCDetectionOutcome | None = None
    intervention_id: str | None = None
    learner_correction: str | None = None
    advancement_after_correction: bool = False
    unsafe_advance_suppressed: bool = False
    final_outcome: GateCFinalOutcome | None = None

    @model_validator(mode="after")
    def finalized_arm_is_complete(self) -> GateCArmRun:
        if self.status == GateCArmStatus.FINALIZED:
            if self.finalized_at is None or self.final_outcome is None:
                raise ValueError("a finalized Gate C arm requires outcome and finalized_at")
            if self.advancement_after_correction and self.final_outcome != (
                GateCFinalOutcome.COMPLETED_AFTER_CORRECTION
            ):
                raise ValueError("advancement_after_correction requires a completed outcome")
        elif self.finalized_at is not None or self.final_outcome is not None:
            raise ValueError("an active Gate C arm cannot contain finalization fields")
        return self


class GateCAttempt(StrictModel):
    attempt_id: str = Field(default_factory=lambda: f"gate-c-attempt-{uuid4().hex[:12]}")
    experiment_id: str
    arm_run_id: str
    attempt_number: int = Field(ge=1)
    step_id: str
    learner_event_id: str
    observed_at: datetime
    elapsed_ms: int = Field(ge=0)
    observation: LearnerObservation
    requested_decision: CheckpointDecision
    safe_decision: CheckpointDecision
    detection_outcome: GateCDetectionOutcome | None = None
    advancement_happened: bool = False
    unsafe_advance_suppressed: bool = False
    intervention_id: str | None = None

    @model_validator(mode="after")
    def unsafe_state_cannot_advance(self) -> GateCAttempt:
        if (
            self.observation.is_deliberate_incorrect
            and self.safe_decision == CheckpointDecision.ADVANCE
        ):
            raise ValueError("a deliberate incorrect state cannot be recorded as advanced")
        if self.advancement_happened and self.safe_decision != CheckpointDecision.ADVANCE:
            raise ValueError("advancement must match the safe checkpoint decision")
        if self.observation.is_deliberate_incorrect and self.detection_outcome is None:
            raise ValueError("the deliberate incorrect attempt requires a detection outcome")
        return self


class GateCIntervention(StrictModel):
    intervention_id: str = Field(default_factory=lambda: f"gate-c-intervention-{uuid4().hex[:12]}")
    experiment_id: str
    arm_run_id: str
    attempt_id: str
    procedure_id: str
    procedure_version_id: str
    correction_id: str
    step_id: str
    guidance: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    source_kind: Literal["approved_teacher_clarification"] = "approved_teacher_clarification"
    approved_teacher_derived: Literal[True] = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GateCAttestation(StrictModel):
    experiment_id: str
    fresh_learner_confirmed: bool = False
    teacher_procedure_confirmed: bool = False
    recorded_without_personal_data: bool = False
    reviewer_note: str = Field(min_length=10, max_length=4000)
    attested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GateCArmSummary(StrictModel):
    arm_run_id: str
    arm: GateCArm
    procedure_version_id: str
    procedure_hash: str
    final_outcome: GateCFinalOutcome | None
    detection_outcome: GateCDetectionOutcome | None
    attempt_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    intervention_count: int = Field(ge=0)
    learner_corrected: bool
    advancement_after_correction: bool
    unsafe_advance_suppressed: bool
    finalized: bool


class GateCComparison(StrictModel):
    baseline_completed_after_correction: bool | None
    byfeel_completed_after_correction: bool | None
    baseline_detection: GateCDetectionOutcome | None
    byfeel_detection: GateCDetectionOutcome | None
    completion_delta: int | None
    correction_delta: int | None
    teacher_derived_intervention_only: bool
    requires_human_review: bool
    transfer_improved: bool | None


class GateCComparisonReport(StrictModel):
    experiment_id: str
    synthetic: bool
    gate_c_decision: Literal[
        "pending",
        "synthetic_excluded",
        "pending_real_evidence",
        "pass_candidate",
        "not_improved",
        "not_evaluable",
    ]
    experiment_status: GateCExperimentStatus
    baseline: GateCArmSummary | None = None
    byfeel: GateCArmSummary | None = None
    comparison: GateCComparison
    attestation: GateCAttestation | None = None
    limitation: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GateCAttemptResult(StrictModel):
    attempt: GateCAttempt
    intervention: GateCIntervention | None = None
    arm_run: GateCArmRun
    learner: LearnerProgress


class TeachingOutcome(StrictModel):
    procedure: Procedure
    probe_run: ProbeRun


class RepairOutcome(StrictModel):
    procedure: Procedure
    correction: Correction
    probe_run: ProbeRun


class LearnerProgress(StrictModel):
    session: LearnerSession
    current_step: LearnerStep | None
    latest_event: LearnerEvent | None = None


class TeacherDemo(StrictModel):
    title: str
    domain: str
    learner_goal: str
    raw_demonstration: str = Field(min_length=20)
    constraints: list[str] = Field(default_factory=list)


class TeacherSession(TimestampedModel):
    session_id: str = Field(default_factory=lambda: f"teacher-{uuid4().hex[:12]}")
    title: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    learner_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    speech_mode: Literal["silent", "spoken", "unsure"]
    status: TeacherSessionStatus = TeacherSessionStatus.AWAITING_MEDIA
    media_run_id: str | None = None
    procedure_id: str | None = None
    failure_message: str | None = None


class ApprovedDemonstration(StrictModel):
    approval_id: str
    teacher_session_id: str
    approved_factual_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    demo: TeacherDemo

    @model_validator(mode="after")
    def approval_hash_matches_record(self) -> ApprovedDemonstration:
        actual = sha256(self.demo.raw_demonstration.encode()).hexdigest()
        if actual != self.approved_factual_hash:
            raise ValueError("approved factual hash does not match the demonstration")
        return self


class TargetedClarification(StrictModel):
    clarification_id: str = Field(default_factory=lambda: f"clarification-{uuid4().hex[:12]}")
    probe_run_id: str
    gap_id: str
    question: str = Field(min_length=1)
    verbatim_answer: str = Field(min_length=1)
    answered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewedRepairContext(StrictModel):
    procedure: Procedure
    probe_run: ProbeRun
    review: BlockerReview
    clarification: TargetedClarification

    @model_validator(mode="after")
    def context_is_human_approved_and_single_blocker(self) -> ReviewedRepairContext:
        if (
            self.probe_run.phase != "before_repair"
            or self.probe_run.report.status != ProbeStatus.BLOCKED
        ):
            raise ValueError("repair context requires an initial blocked probe")
        if self.review.run_id != self.probe_run.probe_run_id:
            raise ValueError("blocker review does not match the probe run")
        if self.review.decision != BlockerReviewDecision.GENUINE:
            raise ValueError("repair context requires a genuine human blocker review")
        if self.clarification.probe_run_id != self.probe_run.probe_run_id:
            raise ValueError("clarification does not match the probe run")
        blocker_ids = {gap.gap_id for gap in self.probe_run.report.blockers}
        if self.clarification.gap_id not in blocker_ids:
            raise ValueError("clarification does not identify a probe blocker")
        return self


class RunManifest(StrictModel):
    run_id: str
    model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    probe_before: ProbeStatus
    probe_after: ProbeStatus
    status_transition_succeeded: bool
    gate_decision: Literal["pending_human_review"] = "pending_human_review"
