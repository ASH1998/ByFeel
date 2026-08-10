from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import TypeVar

from byfeel.cli import _UsageRecorder, build_parser, run_review_blocker
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
from byfeel.prompts import EXTRACTION_SYSTEM, PROBE_SYSTEM
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


def test_extraction_cannot_self_grant_learner_ready_status() -> None:
    original = procedure().model_copy(
        update={"status": "learner_ready", "created_at": "2020-01-01T00:00:00Z"}
    )

    class ReadyClient(FakeClient):
        def generate(self, *, system, prompt, schema):
            if schema is Procedure:
                return original
            return super().generate(system=system, prompt=prompt, schema=schema)

    extracted = GateAExperiment(ReadyClient()).extract(
        TeacherDemo(
            title="Test",
            domain="test",
            learner_goal="Test application-owned status",
            raw_demonstration="The teacher performs a sufficiently detailed bounded demonstration.",
        )
    )

    assert extracted.status.value == "draft"
    assert extracted.created_at != original.created_at


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
    assert manifest.status_transition_succeeded is True
    assert manifest.gate_decision == "pending_human_review"

    output = tmp_path / "manifest.json"
    save_artifact(output, manifest)
    assert output.exists()


def test_usage_recorder_persists_each_routed_call_once(tmp_path: Path) -> None:
    main = SimpleNamespace(model="main-model", usage=[])
    lite = SimpleNamespace(model="lite-model", usage=[])
    router = SimpleNamespace(main=main, lite=lite)
    recorder = _UsageRecorder(tmp_path, router)

    recorder.call(
        "extraction",
        lambda: lite.usage.append(
            {
                "prompt_tokens": 10,
                "output_tokens": 5,
                "thinking_tokens": 0,
                "total_tokens": 15,
            }
        ),
    )
    recorder.call(
        "probe_before",
        lambda: main.usage.append(
            {
                "prompt_tokens": 20,
                "output_tokens": 8,
                "thinking_tokens": 2,
                "total_tokens": 30,
            }
        ),
    )

    payload = json.loads((tmp_path / "usage.json").read_text())
    assert [call["phase"] for call in payload["calls"]] == [
        "extraction",
        "probe_before",
    ]
    assert [call["model"] for call in payload["calls"]] == [
        "lite-model",
        "main-model",
    ]


def test_gate_a_parser_accepts_saved_run_resume() -> None:
    args = build_parser().parse_args(
        ["gate-a", "--resume-run", "runs/gate-a/example", "--clarification", "Ready"]
    )

    assert args.demo is None
    assert args.resume_run == Path("runs/gate-a/example")


def test_probe_does_not_treat_optional_precision_as_blocking() -> None:
    assert "ordinary bounded judgment" in PROBE_SYSTEM
    assert "precision suggestions in non_blocking_improvements" in PROBE_SYSTEM
    assert "Do not create open questions merely because" in EXTRACTION_SYSTEM


def test_false_blocker_review_closes_run_without_clarification(tmp_path: Path) -> None:
    run = tmp_path / "run-false"
    run.mkdir()
    save_artifact(run / "02_probe_before.json", blocked_report())
    args = build_parser().parse_args(
        [
            "review-blocker",
            "--run",
            str(run),
            "--decision",
            "false_blocker",
            "--reason",
            "The missing detail improves precision but does not prevent execution.",
        ]
    )

    assert run_review_blocker(args) == 0
    review = json.loads((run / "03_blocker_review.json").read_text())
    assert review["decision"] == "false_blocker"
    assert not (run / "03_teacher_clarification.txt").exists()
