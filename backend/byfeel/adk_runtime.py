"""Google ADK runtimes with application-enforced role and context boundaries."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from google.adk import Agent, Runner
from google.adk.models.base_llm import BaseLlm
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .models import (
    AgentRole,
    AgentRunRecord,
    AgentRunStatus,
    AgentTokenUsage,
    AgentToolEvent,
    AgentToolStatus,
    ApprovedDemonstration,
    CheckpointEvaluation,
    LearnerObservation,
    LearnerProcedure,
    LearnerStep,
    ProbeReport,
    Procedure,
    ProcedureStatus,
    RepairResult,
    ReviewedRepairContext,
)
from .prompts import CHECKPOINT_SYSTEM, EXTRACTION_SYSTEM, PROBE_SYSTEM, REPAIR_SYSTEM

PROBE_APP_NAME = "byfeel_blinded_probe"
PROBE_USER_MESSAGE = (
    "Call read_learner_artifact exactly once. Attempt that artifact from a cold start, then "
    "return the required structured probe report. You have no other context or tools."
)
PROBE_ALLOWED_TOOLS = ("read_learner_artifact", "set_model_response")
ROLE_TOOL_POLICIES: dict[AgentRole, frozenset[str]] = {
    AgentRole.TEACHING_PARTNER: frozenset(
        {
            "read_approved_demonstration",
            "read_current_procedure",
            "read_reviewed_blocker",
            "read_verbatim_clarification",
            "extract_learner_procedure",
            "handle_candidate_blocker",
            "request_targeted_clarification",
            "repair_selected_blocker",
            "save_procedure_version",
            "record_evidence_event",
        }
    ),
    AgentRole.BLINDED_PROBE: frozenset({"read_learner_artifact"}),
    AgentRole.LEARNER_COACH: frozenset(
        {
            "read_approved_step",
            "read_current_learner_state",
            "evaluate_checkpoint",
            "record_learner_event",
        }
    ),
}


class ScopedAdkAgentFactory:
    """Builds role agents only after checking their exact application tool policy."""

    @staticmethod
    def tool_name(tool: Callable) -> str:
        name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
        if not name:
            raise TypeError("ADK tools must expose a stable name")
        return str(name)

    @classmethod
    def validate_tools(cls, role: AgentRole, tools: Sequence[Callable]) -> list[str]:
        names = [cls.tool_name(tool) for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("ADK tool names must be unique")
        unexpected = set(names) - ROLE_TOOL_POLICIES[role]
        if unexpected:
            raise ValueError(f"{role.value} tools are not allowed: {sorted(unexpected)}")
        return names

    @classmethod
    def build(
        cls,
        *,
        role: AgentRole,
        name: str,
        description: str,
        model: str | BaseLlm,
        instruction: str,
        tools: Sequence[Callable],
        output_schema: type,
        output_key: str,
    ) -> Agent:
        cls.validate_tools(role, tools)
        return Agent(
            name=name,
            description=description,
            model=model,
            instruction=instruction,
            tools=list(tools),
            output_schema=output_schema,
            output_key=output_key,
            mode="chat",
            include_contents="none",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )


@dataclass(frozen=True)
class ProbeExecution:
    report: ProbeReport
    agent_run: AgentRunRecord | None = None


class ProbeRuntime(Protocol):
    def probe(self, artifact: LearnerProcedure) -> ProbeExecution: ...


@dataclass(frozen=True)
class TeachingExecution:
    output: Procedure | RepairResult
    agent_run: AgentRunRecord


class TeachingPartnerRuntime(Protocol):
    def extract(self, approved: ApprovedDemonstration) -> TeachingExecution: ...

    def repair(self, context: ReviewedRepairContext) -> TeachingExecution: ...


@dataclass(frozen=True)
class LearnerCoachExecution:
    evaluation: CheckpointEvaluation
    agent_run: AgentRunRecord


def _sync(coroutine, *, operation: str):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    raise RuntimeError(f"synchronous ADK {operation} cannot run inside an active event loop")


def _add_usage(current: AgentTokenUsage, metadata) -> AgentTokenUsage:
    if metadata is None:
        return current
    return AgentTokenUsage(
        prompt_tokens=current.prompt_tokens + int(getattr(metadata, "prompt_token_count", 0) or 0),
        output_tokens=current.output_tokens
        + int(getattr(metadata, "candidates_token_count", 0) or 0),
        thinking_tokens=current.thinking_tokens
        + int(getattr(metadata, "thoughts_token_count", 0) or 0),
        total_tokens=current.total_tokens + int(getattr(metadata, "total_token_count", 0) or 0),
    )


async def _run_scoped_agent(
    *,
    role: AgentRole,
    name: str,
    description: str,
    model: str | BaseLlm,
    instruction: str,
    tools: Sequence[Callable],
    output_schema: type,
    output_key: str,
    message_parts: list[types.Part],
    required_tool_counts: dict[str, int],
    context_ref: str,
    human_boundary_refs: list[str] | None = None,
) -> tuple[object, AgentRunRecord]:
    run_id = f"adk-run-{uuid4().hex}"
    session_id = f"adk-session-{uuid4().hex}"
    user_id = f"{role.value}-user-{uuid4().hex}"
    app_name = f"byfeel_{role.value}"
    started_at = datetime.now(UTC)
    tool_events: list[AgentToolEvent] = []
    usage = AgentTokenUsage()
    observed_calls: dict[str, int] = {}
    explicit_tool_names = ScopedAdkAgentFactory.validate_tools(role, tools)
    allowed_tools = [*explicit_tool_names, "set_model_response"]
    agent = ScopedAdkAgentFactory.build(
        role=role,
        name=name,
        description=description,
        model=model,
        instruction=instruction,
        tools=tools,
        output_schema=output_schema,
        output_key=output_key,
    )
    sessions = InMemorySessionService()
    await sessions.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    runner = Runner(app_name=app_name, agent=agent, session_service=sessions)
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=message_parts),
    ):
        for call in event.get_function_calls():
            tool_name = call.name or "unknown"
            observed_calls[tool_name] = observed_calls.get(tool_name, 0) + 1
            tool_events.append(
                AgentToolEvent(
                    call_id=call.id or f"call-{uuid4().hex}",
                    tool_name=tool_name,
                    status=AgentToolStatus.STARTED,
                )
            )
        for response in event.get_function_responses():
            tool_events.append(
                AgentToolEvent(
                    call_id=response.id or f"response-{uuid4().hex}",
                    tool_name=response.name or "unknown",
                    status=AgentToolStatus.SUCCEEDED,
                )
            )
        usage = _add_usage(usage, event.usage_metadata)

    for tool_name, required_count in required_tool_counts.items():
        if observed_calls.get(tool_name, 0) != required_count:
            if role == AgentRole.BLINDED_PROBE and tool_name == "read_learner_artifact":
                raise RuntimeError("blinded probe must read its learner artifact exactly once")
            raise RuntimeError(
                f"{role.value} must call {tool_name} exactly {required_count} time(s)"
            )
    session = await sessions.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None or output_key not in session.state:
        raise RuntimeError(f"{role.value} returned no structured {output_key}")
    completed_at = datetime.now(UTC)
    model_name = model if isinstance(model, str) else model.model
    record = AgentRunRecord(
        run_id=run_id,
        role=role,
        session_id=session_id,
        context_ref=context_ref,
        model=model_name,
        allowed_tools=allowed_tools,
        tool_events=tool_events,
        token_usage=usage,
        human_boundary_refs=human_boundary_refs or [],
        status=AgentRunStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=completed_at,
    )
    return session.state[output_key], record


class AdkProbeRuntime:
    """Creates a new read-only ADK agent, runner, and session for every probe."""

    def __init__(self, *, model: str | BaseLlm) -> None:
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model if isinstance(self._model, str) else self._model.model

    def probe(self, artifact: LearnerProcedure) -> ProbeExecution:
        if not isinstance(artifact, LearnerProcedure):
            raise TypeError("the ADK blinded probe accepts LearnerProcedure only")
        return _sync(self._probe_async(artifact), operation="probe")

    async def _probe_async(self, artifact: LearnerProcedure) -> ProbeExecution:
        def read_learner_artifact() -> dict[str, object]:
            """Return the frozen learner-facing procedure supplied to this isolated run."""

            return artifact.model_dump(mode="json")

        output, record = await _run_scoped_agent(
            role=AgentRole.BLINDED_PROBE,
            name="blinded_probe",
            description="Tests one learner-facing procedure without teacher context.",
            model=self._model,
            instruction=PROBE_SYSTEM,
            tools=[read_learner_artifact],
            output_schema=ProbeReport,
            output_key="probe_report",
            message_parts=[types.Part(text=PROBE_USER_MESSAGE)],
            required_tool_counts={"read_learner_artifact": 1},
            context_ref=artifact.id,
        )
        return ProbeExecution(report=ProbeReport.model_validate(output), agent_run=record)


class AdkTeachingPartnerRuntime:
    """Teaching operations accept only application-proven human-approved contexts."""

    def __init__(self, *, model: str | BaseLlm) -> None:
        self._model = model

    def extract(self, approved: ApprovedDemonstration) -> TeachingExecution:
        if not isinstance(approved, ApprovedDemonstration):
            raise TypeError("Teaching Partner extraction requires ApprovedDemonstration")
        return _sync(self._extract_async(approved), operation="teaching extraction")

    async def _extract_async(self, approved: ApprovedDemonstration) -> TeachingExecution:
        def read_approved_demonstration() -> dict[str, object]:
            """Return the exact human-approved factual demonstration, without raw media."""

            return approved.demo.model_dump(mode="json")

        output, record = await _run_scoped_agent(
            role=AgentRole.TEACHING_PARTNER,
            name="teaching_partner",
            description="Extracts learner knowledge from one approved factual record.",
            model=self._model,
            instruction=EXTRACTION_SYSTEM,
            tools=[read_approved_demonstration],
            output_schema=Procedure,
            output_key="procedure",
            message_parts=[
                types.Part(
                    text=(
                        "Call read_approved_demonstration exactly once. Extract only that "
                        "approved record into the required learner-facing procedure."
                    )
                )
            ],
            required_tool_counts={"read_approved_demonstration": 1},
            context_ref=approved.teacher_session_id,
            human_boundary_refs=[approved.approval_id],
        )
        now = datetime.now(UTC)
        procedure = Procedure.model_validate(output).model_copy(
            update={
                "status": ProcedureStatus.DRAFT,
                "created_at": now,
                "updated_at": now,
            }
        )
        return TeachingExecution(output=procedure, agent_run=record)

    def repair(self, context: ReviewedRepairContext) -> TeachingExecution:
        if not isinstance(context, ReviewedRepairContext):
            raise TypeError("Teaching Partner repair requires ReviewedRepairContext")
        return _sync(self._repair_async(context), operation="teaching repair")

    async def _repair_async(self, context: ReviewedRepairContext) -> TeachingExecution:
        selected_gap = next(
            gap
            for gap in context.probe_run.report.blockers
            if gap.gap_id == context.clarification.gap_id
        )

        def read_current_procedure() -> dict[str, object]:
            """Return the canonical procedure version being repaired."""

            return context.procedure.model_dump(mode="json")

        def read_reviewed_blocker() -> dict[str, object]:
            """Return only the blocker accepted as genuine by the human reviewer."""

            return selected_gap.model_dump(mode="json")

        def read_verbatim_clarification() -> dict[str, str]:
            """Return the teacher's single verbatim answer and its exact question."""

            return {
                "question": context.clarification.question,
                "verbatim_answer": context.clarification.verbatim_answer,
            }

        output, record = await _run_scoped_agent(
            role=AgentRole.TEACHING_PARTNER,
            name="teaching_partner",
            description="Repairs exactly one human-approved blocker from one teacher answer.",
            model=self._model,
            instruction=REPAIR_SYSTEM,
            tools=[
                read_current_procedure,
                read_reviewed_blocker,
                read_verbatim_clarification,
            ],
            output_schema=RepairResult,
            output_key="repair",
            message_parts=[
                types.Part(
                    text=(
                        "Call each allowed read tool exactly once. Repair only the reviewed "
                        "blocker using only the verbatim teacher answer, then return the required "
                        "structured repair."
                    )
                )
            ],
            required_tool_counts={
                "read_current_procedure": 1,
                "read_reviewed_blocker": 1,
                "read_verbatim_clarification": 1,
            },
            context_ref=context.procedure.id,
            human_boundary_refs=[
                context.review.run_id,
                context.clarification.clarification_id,
            ],
        )
        return TeachingExecution(output=RepairResult.model_validate(output), agent_run=record)


class AdkLearnerCoachRuntime:
    """Evaluates one approved learner checkpoint through a scoped ADK execution."""

    def __init__(self, *, model: str | BaseLlm, evidence_store=None) -> None:
        self._model = model
        self._evidence_store = evidence_store

    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> LearnerCoachExecution:
        return _sync(
            self._evaluate_async(
                procedure=procedure,
                step=step,
                observation=observation,
            ),
            operation="learner checkpoint",
        )

    async def _evaluate_async(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> LearnerCoachExecution:
        if observation.step_id != step.step_id:
            raise ValueError("learner observation does not match the approved step")

        def read_approved_step() -> dict[str, object]:
            """Return only the current approved learner-facing step and checkpoints."""

            return step.model_dump(mode="json")

        def read_current_learner_state() -> dict[str, object]:
            """Return the frozen procedure identity and learner-submitted observation."""

            return {
                "procedure_id": procedure.id,
                "procedure_hash": procedure.content_hash(),
                "procedure_status": procedure.status.value,
                "observation": observation.model_dump(mode="json"),
            }

        message = (
            "Call read_approved_step and read_current_learner_state exactly once. Evaluate only "
            "that approved checkpoint and the learner submission. Return the required decision."
        )
        parts = [types.Part(text=message)]
        if observation.evidence is not None:
            if self._evidence_store is None:
                raise ValueError("learner checkpoint evidence store is not configured")
            references = [
                evidence
                for checkpoint in step.checkpoints
                for evidence in checkpoint.evidence_refs
                if evidence.source == "teacher"
            ][:3]
            for reference in references:
                parts.append(
                    types.Part.from_bytes(
                        data=self._evidence_store.get(reference),
                        mime_type=reference.content_type,
                    )
                )
            parts.append(
                types.Part.from_bytes(
                    data=self._evidence_store.get(observation.evidence),
                    mime_type=observation.evidence.content_type,
                )
            )
            parts[0] = types.Part(
                text=(
                    f"{message} IMAGE ORDER: the first {len(references)} image(s) are "
                    "teacher-approved references and the final image is the learner snapshot."
                )
            )

        output, record = await _run_scoped_agent(
            role=AgentRole.LEARNER_COACH,
            name="learner_coach",
            description="Evaluates one learner checkpoint from approved procedure knowledge.",
            model=self._model,
            instruction=CHECKPOINT_SYSTEM,
            tools=[read_approved_step, read_current_learner_state],
            output_schema=CheckpointEvaluation,
            output_key="checkpoint_evaluation",
            message_parts=parts,
            required_tool_counts={
                "read_approved_step": 1,
                "read_current_learner_state": 1,
            },
            context_ref=procedure.id,
            human_boundary_refs=[procedure.content_hash()],
        )
        return LearnerCoachExecution(
            evaluation=CheckpointEvaluation.model_validate(output),
            agent_run=record,
        )
