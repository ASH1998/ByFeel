from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from byfeel.experiment import GateAExperiment, build_manifest, save_artifact
from byfeel.models import (
    IssueType,
    KnowledgeGap,
    ProbeReport,
    ProbeStatus,
    Procedure,
    ProcedureStep,
    RepairResult,
    TeacherDemo,
)
from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def procedure(*, repaired: bool = False) -> Procedure:
    conditions = ["Stop when the surface holds a visible ridge for two seconds"] if repaired else []
    return Procedure(
        id="mixing-test",
        title="Mixing test",
        domain="test",
        learner_goal="Finish the mixture",
        steps=[
            ProcedureStep(
                step_id="step-1",
                order=1,
                action="Mix until it is ready",
                completion_conditions=conditions,
                confidence=0.5,
            )
        ],
    )


def blocked_report() -> ProbeReport:
    return ProbeReport(
        status=ProbeStatus.BLOCKED,
        summary="The learner cannot determine when to stop.",
        blockers=[
            KnowledgeGap(
                gap_id="gap-1",
                step_id="step-1",
                issue_type=IssueType.MISSING_COMPLETION_CONDITION,
                description="No observable stop condition is provided.",
                missing_information="A visible cue that distinguishes ready from not ready.",
                severity=0.9,
                blocks_execution=True,
            )
        ],
        teacher_question="What should the learner see when the mixture is ready?",
    )


class FakeClient:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        self.calls.append((system, prompt, schema))
        if schema is Procedure:
            value: BaseModel = procedure()
        elif schema is RepairResult:
            value = RepairResult(
                procedure=procedure(repaired=True),
                changed_step_ids=["step-1"],
                change_summary="Added the teacher's observable stop condition.",
            )
        elif "visible ridge" in prompt:
            value = ProbeReport(
                status=ProbeStatus.UNBLOCKED,
                summary="The step now has an observable stop condition.",
            )
        else:
            value = blocked_report()
        return value  # type: ignore[return-value]


def test_raw_demonstration_never_reaches_probe() -> None:
    sentinel = "PRIVATE_RAW_TEACHER_CONTEXT_8472"
    demo = TeacherDemo(
        title="Test",
        domain="test",
        learner_goal="Test the boundary",
        raw_demonstration=f"A sufficiently long demonstration containing {sentinel}.",
    )
    client = FakeClient()
    experiment = GateAExperiment(client)

    extracted = experiment.extract(demo)
    experiment.probe(extracted)

    extraction_call, probe_call = client.calls
    assert sentinel in extraction_call[1]
    assert sentinel not in probe_call[1]


def test_blocked_to_unblocked_repair_loop(tmp_path: Path) -> None:
    client = FakeClient()
    experiment = GateAExperiment(client)
    before = experiment.probe(procedure())
    repair = experiment.repair(
        procedure(),
        before,
        "Stop when the surface holds a visible ridge for two seconds.",
    )
    after = experiment.probe(repair.procedure)
    manifest = build_manifest(
        run_dir=tmp_path / "run-1", model=client.model, before=before, after=after
    )

    assert before.status == ProbeStatus.BLOCKED
    assert after.status == ProbeStatus.UNBLOCKED
    assert manifest.gate_passed is True

    output = tmp_path / "manifest.json"
    save_artifact(output, manifest)
    assert output.exists()
