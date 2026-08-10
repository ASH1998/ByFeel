from __future__ import annotations

from hashlib import sha256

import pytest
from byfeel.adk_runtime import (
    PROBE_ALLOWED_TOOLS,
    ROLE_TOOL_POLICIES,
    AdkLearnerCoachRuntime,
    AdkProbeRuntime,
    AdkTeachingPartnerRuntime,
    ScopedAdkAgentFactory,
)
from byfeel.models import (
    AgentRole,
    AgentRunStatus,
    ApprovedDemonstration,
    BlockerReview,
    BlockerReviewDecision,
    CheckpointDecision,
    CheckpointEvaluation,
    IssueType,
    KnowledgeGap,
    LearnerObservation,
    ProbeReport,
    ProbeRun,
    ProbeStatus,
    Procedure,
    ProcedureStatus,
    ProcedureStep,
    RepairResult,
    ReviewedRepairContext,
    TargetedClarification,
    TeacherDemo,
)
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


def learner_artifact():
    return Procedure(
        id="isolated-procedure",
        title="Fold paper",
        domain="paper craft",
        learner_goal="Make a stable fold",
        steps=[
            ProcedureStep(
                step_id="step-1",
                order=1,
                action="Press the fold until it is firm enough",
                confidence=0.5,
            )
        ],
    ).learner_view()


def blocked_report() -> ProbeReport:
    return ProbeReport(
        status=ProbeStatus.BLOCKED,
        summary="The learner has no observable stop condition.",
        blockers=[
            KnowledgeGap(
                gap_id="gap-1",
                step_id="step-1",
                issue_type=IssueType.MISSING_COMPLETION_CONDITION,
                description="Firm enough is not observable.",
                missing_information="A visible completion cue.",
                severity=0.9,
                blocks_execution=True,
            )
        ],
        teacher_question="What visible result shows that the crease is complete?",
    )


class ScriptedProbeModel(BaseLlm):
    calls: int = 0
    request_snapshots: list[str] = Field(default_factory=list)
    declared_tools: list[set[str]] = Field(default_factory=list)
    requested_tool: str = "read_learner_artifact"

    async def generate_content_async(self, llm_request, stream=False):
        del stream
        self.calls += 1
        self.request_snapshots.append(repr(llm_request.model_dump(mode="json")))
        self.declared_tools.append(
            {
                declaration.name
                for tool in (llm_request.config.tools or [])
                for declaration in (tool.function_declarations or [])
            }
        )
        usage = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10,
            candidates_token_count=5,
            total_token_count=15,
        )
        if self.calls % 2 == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_function_call(name=self.requested_tool, args={})],
                ),
                usage_metadata=usage,
                turn_complete=True,
            )
            return
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=blocked_report().model_dump_json())],
            ),
            usage_metadata=usage,
            turn_complete=True,
        )


class DirectResponseModel(ScriptedProbeModel):
    async def generate_content_async(self, llm_request, stream=False):
        del llm_request, stream
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=blocked_report().model_dump_json())],
            ),
            turn_complete=True,
        )


class ScriptedRoleModel(BaseLlm):
    tool_sequence: list[str]
    output_json: str
    call_index: int = 0
    request_snapshots: list[str] = Field(default_factory=list)
    declared_tools: list[set[str]] = Field(default_factory=list)

    async def generate_content_async(self, llm_request, stream=False):
        del stream
        self.request_snapshots.append(repr(llm_request.model_dump(mode="json")))
        self.declared_tools.append(
            {
                declaration.name
                for tool in (llm_request.config.tools or [])
                for declaration in (tool.function_declarations or [])
            }
        )
        if self.call_index < len(self.tool_sequence):
            tool_name = self.tool_sequence[self.call_index]
            self.call_index += 1
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_function_call(name=tool_name, args={})],
                ),
                turn_complete=True,
            )
            return
        self.call_index += 1
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text=self.output_json)],
            ),
            turn_complete=True,
        )


def canonical_procedure(*, action: str = "Fold the paper") -> Procedure:
    return Procedure(
        id="procedure-role-test",
        title="Fold paper",
        domain="paper craft",
        learner_goal="Make a stable fold",
        status=ProcedureStatus.LEARNER_READY,
        steps=[
            ProcedureStep(
                step_id="step-1",
                order=1,
                action=action,
                completion_conditions=["The edges align"],
                confidence=0.95,
            )
        ],
    )


def test_adk_probe_creates_fresh_sessions_and_records_safe_observability() -> None:
    model = ScriptedProbeModel(model="fake-adk-probe")
    runtime = AdkProbeRuntime(model=model)

    first = runtime.probe(learner_artifact())
    second = runtime.probe(learner_artifact())

    assert first.report.status == ProbeStatus.BLOCKED
    assert second.report.status == ProbeStatus.BLOCKED
    assert first.agent_run is not None
    assert second.agent_run is not None
    assert first.agent_run.run_id != second.agent_run.run_id
    assert first.agent_run.session_id != second.agent_run.session_id
    assert first.agent_run.role == AgentRole.BLINDED_PROBE
    assert first.agent_run.status == AgentRunStatus.SUCCEEDED
    assert first.agent_run.allowed_tools == list(PROBE_ALLOWED_TOOLS)
    assert [(event.tool_name, event.status.value) for event in first.agent_run.tool_events] == [
        ("read_learner_artifact", "started"),
        ("read_learner_artifact", "succeeded"),
    ]
    assert first.agent_run.token_usage.total_tokens == 30
    assert all(tools <= set(PROBE_ALLOWED_TOOLS) for tools in model.declared_tools)


def test_probe_request_cannot_contain_teacher_context_or_repository_tools() -> None:
    private_teacher_sentinel = "PRIVATE_TEACHER_CONTEXT_MUST_NOT_LEAK_4815"
    model = ScriptedProbeModel(model="fake-adk-probe")

    execution = AdkProbeRuntime(model=model).probe(learner_artifact())

    assert private_teacher_sentinel not in "".join(model.request_snapshots)
    assert all("get_teacher_session" not in tools for tools in model.declared_tools)
    assert all("save_procedure" not in tools for tools in model.declared_tools)
    assert execution.agent_run is not None
    safe_record = execution.agent_run.model_dump_json()
    assert "Press the fold" not in safe_record
    assert "observable stop condition" not in safe_record
    assert private_teacher_sentinel not in safe_record


def test_probe_rejects_an_attempt_to_call_a_non_allowlisted_teacher_tool() -> None:
    model = ScriptedProbeModel(
        model="fake-adk-probe",
        requested_tool="get_teacher_session",
    )

    with pytest.raises(ValueError, match="Tool 'get_teacher_session' not found"):
        AdkProbeRuntime(model=model).probe(learner_artifact())

    assert "get_teacher_session" not in model.declared_tools[0]


def test_probe_requires_the_learner_artifact_tool_even_for_structured_output() -> None:
    with pytest.raises(RuntimeError, match="read its learner artifact exactly once"):
        AdkProbeRuntime(model=DirectResponseModel(model="fake-adk-probe")).probe(learner_artifact())


def test_adk_probe_rejects_canonical_procedure_input() -> None:
    canonical = Procedure(
        id="canonical",
        title="Canonical",
        domain="test",
        learner_goal="Reject canonical input",
        steps=[ProcedureStep(step_id="step-1", order=1, action="Test", confidence=1)],
    )
    with pytest.raises(TypeError, match="LearnerProcedure"):
        AdkProbeRuntime(model=ScriptedProbeModel(model="fake-adk-probe")).probe(canonical)  # type: ignore[arg-type]


def test_teaching_partner_extracts_only_a_human_approved_record() -> None:
    demo = TeacherDemo(
        title="Fold paper",
        domain="paper craft",
        learner_goal="Make a stable fold",
        raw_demonstration="Fold the paper and align both visible edges.",
    )
    approved = ApprovedDemonstration(
        approval_id="approval-teacher-1",
        teacher_session_id="teacher-session-1",
        approved_factual_hash=sha256(demo.raw_demonstration.encode()).hexdigest(),
        demo=demo,
    )
    model = ScriptedRoleModel(
        model="fake-teaching-partner",
        tool_sequence=["read_approved_demonstration"],
        output_json=canonical_procedure().model_dump_json(),
    )

    execution = AdkTeachingPartnerRuntime(model=model).extract(approved)

    assert execution.output.status == ProcedureStatus.DRAFT
    assert execution.agent_run.role == AgentRole.TEACHING_PARTNER
    assert execution.agent_run.context_ref == approved.teacher_session_id
    assert execution.agent_run.human_boundary_refs == [approved.approval_id]
    assert all(
        tools <= {"read_approved_demonstration", "set_model_response"}
        for tools in model.declared_tools
    )
    assert demo.raw_demonstration not in execution.agent_run.model_dump_json()


def test_teaching_partner_repair_requires_reviewed_blocker_and_verbatim_answer() -> None:
    procedure = canonical_procedure(action="Press until it feels firm")
    report = blocked_report()
    probe_run = ProbeRun(
        probe_run_id="probe-reviewed-1",
        procedure_id=procedure.id,
        learner_artifact_hash=procedure.learner_view().content_hash(),
        report=report,
        phase="before_repair",
    )
    context = ReviewedRepairContext(
        procedure=procedure,
        probe_run=probe_run,
        review=BlockerReview(
            run_id=probe_run.probe_run_id,
            decision=BlockerReviewDecision.GENUINE,
            reason="The learner genuinely cannot identify the stopping point.",
        ),
        clarification=TargetedClarification(
            probe_run_id=probe_run.probe_run_id,
            gap_id="gap-1",
            question=report.teacher_question or "What is the cue?",
            verbatim_answer="Stop when the full crease is visibly sharp.",
        ),
    )
    repaired = canonical_procedure(action="Press until the full crease is visibly sharp")
    result = RepairResult(
        procedure=repaired,
        changed_step_ids=["step-1"],
        change_summary="Added the teacher's visible completion cue.",
        source_quotes=["full crease is visibly sharp"],
    )
    model = ScriptedRoleModel(
        model="fake-teaching-partner",
        tool_sequence=[
            "read_current_procedure",
            "read_reviewed_blocker",
            "read_verbatim_clarification",
        ],
        output_json=result.model_dump_json(),
    )

    execution = AdkTeachingPartnerRuntime(model=model).repair(context)

    assert isinstance(execution.output, RepairResult)
    assert execution.agent_run.human_boundary_refs == [
        probe_run.probe_run_id,
        context.clarification.clarification_id,
    ]
    assert all(
        tools
        <= {
            "read_current_procedure",
            "read_reviewed_blocker",
            "read_verbatim_clarification",
            "set_model_response",
        }
        for tools in model.declared_tools
    )
    assert context.clarification.verbatim_answer not in execution.agent_run.model_dump_json()


def test_learner_coach_reads_only_the_approved_step_and_current_observation() -> None:
    procedure = canonical_procedure().learner_view()
    observation = LearnerObservation(
        step_id="step-1",
        description="The paper edges are aligned.",
    )
    evaluation = CheckpointEvaluation(
        decision=CheckpointDecision.ADVANCE,
        confidence=0.95,
        explanation="The approved visible endpoint is satisfied.",
        checkpoint_id="checkpoint-1",
        teacher_derived=True,
    )
    model = ScriptedRoleModel(
        model="fake-learner-coach",
        tool_sequence=["read_approved_step", "read_current_learner_state"],
        output_json=evaluation.model_dump_json(),
    )

    execution = AdkLearnerCoachRuntime(model=model).evaluate(
        procedure=procedure,
        step=procedure.steps[0],
        observation=observation,
    )

    assert execution.evaluation.decision == CheckpointDecision.ADVANCE
    assert execution.agent_run.role == AgentRole.LEARNER_COACH
    assert execution.agent_run.context_ref == procedure.id
    assert all(
        tools <= {"read_approved_step", "read_current_learner_state", "set_model_response"}
        for tools in model.declared_tools
    )
    safe_record = execution.agent_run.model_dump_json()
    assert observation.description not in safe_record
    assert "PRIVATE_TEACHER_CONTEXT" not in "".join(model.request_snapshots)


def test_scoped_roles_reject_unapproved_input_types() -> None:
    model = ScriptedRoleModel(
        model="fake-role",
        tool_sequence=[],
        output_json="{}",
    )
    with pytest.raises(TypeError, match="ApprovedDemonstration"):
        AdkTeachingPartnerRuntime(model=model).extract(
            TeacherDemo(  # type: ignore[arg-type]
                title="Unsafe",
                domain="test",
                learner_goal="Reject raw input",
                raw_demonstration="This raw demonstration is not approved.",
            )
        )
    with pytest.raises(TypeError, match="ReviewedRepairContext"):
        AdkTeachingPartnerRuntime(model=model).repair(canonical_procedure())  # type: ignore[arg-type]


def test_role_policies_reject_cross_context_tools_before_agent_execution() -> None:
    def read_approved_demonstration() -> dict:
        return {}

    def read_learner_artifact() -> dict:
        return {}

    def read_approved_step() -> dict:
        return {}

    assert ScopedAdkAgentFactory.validate_tools(
        AgentRole.TEACHING_PARTNER, [read_approved_demonstration]
    ) == ["read_approved_demonstration"]
    assert ScopedAdkAgentFactory.validate_tools(
        AgentRole.BLINDED_PROBE, [read_learner_artifact]
    ) == ["read_learner_artifact"]
    assert ScopedAdkAgentFactory.validate_tools(AgentRole.LEARNER_COACH, [read_approved_step]) == [
        "read_approved_step"
    ]

    with pytest.raises(ValueError, match="blinded_probe tools are not allowed"):
        ScopedAdkAgentFactory.validate_tools(AgentRole.BLINDED_PROBE, [read_approved_demonstration])
    with pytest.raises(ValueError, match="learner_coach tools are not allowed"):
        ScopedAdkAgentFactory.validate_tools(AgentRole.LEARNER_COACH, [read_learner_artifact])

    assert "save_procedure_version" in ROLE_TOOL_POLICIES[AgentRole.TEACHING_PARTNER]
    assert "save_procedure_version" not in ROLE_TOOL_POLICIES[AgentRole.BLINDED_PROBE]
    assert "record_learner_event" not in ROLE_TOOL_POLICIES[AgentRole.BLINDED_PROBE]
