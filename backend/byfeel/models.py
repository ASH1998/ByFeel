"""Typed artifacts for the Decision Gate A experiment."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProcedureStatus(StrEnum):
    DRAFT = "draft"
    TESTED = "tested"
    LEARNER_READY = "learner_ready"


class IssueType(StrEnum):
    AMBIGUOUS_QUANTITY = "ambiguous_quantity"
    MISSING_COMPLETION_CONDITION = "missing_completion_condition"
    UNCLEAR_EXCEPTION = "unclear_exception"
    MISSING_STEP = "missing_step"
    CONFLICTING_INSTRUCTION = "conflicting_instruction"
    INSUFFICIENT_VISUAL_EVIDENCE = "insufficient_visual_evidence"
    AMBIGUOUS_ACTION = "ambiguous_action"
    MISSING_PREREQUISITE = "missing_prerequisite"


class ProcedureStep(StrictModel):
    step_id: str = Field(description="Stable short identifier, such as step-1")
    order: int = Field(ge=1)
    action: str = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    completion_conditions: list[str] = Field(default_factory=list)
    learner_risks: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    open_questions: list[str] = Field(default_factory=list)


class Procedure(StrictModel):
    id: str = Field(description="Stable short identifier")
    title: str
    domain: str
    learner_goal: str
    status: ProcedureStatus = ProcedureStatus.DRAFT
    steps: list[ProcedureStep] = Field(min_length=1)

    @model_validator(mode="after")
    def orders_are_unique(self) -> Procedure:
        orders = [step.order for step in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("step order values must be unique")
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
    checkpoints: list[str]
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


class KnowledgeGap(StrictModel):
    gap_id: str
    step_id: str
    source: Literal["novice_probe"] = "novice_probe"
    issue_type: IssueType
    description: str
    missing_information: str
    severity: float = Field(ge=0, le=1)
    blocks_execution: bool


class ProbeStatus(StrEnum):
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"


class ProbeReport(StrictModel):
    status: ProbeStatus
    summary: str
    blockers: list[KnowledgeGap] = Field(default_factory=list)
    assumptions_required: list[str] = Field(default_factory=list)
    teacher_question: str | None = None

    @model_validator(mode="after")
    def status_matches_blockers(self) -> ProbeReport:
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


class TeacherDemo(StrictModel):
    title: str
    domain: str
    learner_goal: str
    raw_demonstration: str = Field(min_length=20)
    constraints: list[str] = Field(default_factory=list)


class RunManifest(StrictModel):
    run_id: str
    model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    probe_before: ProbeStatus
    probe_after: ProbeStatus
    gate_passed: bool
