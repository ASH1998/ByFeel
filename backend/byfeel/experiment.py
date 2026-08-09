"""Decision Gate A orchestration and artifact persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from .models import (
    ProbeReport,
    ProbeStatus,
    Procedure,
    RepairResult,
    RunManifest,
    TeacherDemo,
)
from .prompts import (
    EXTRACTION_SYSTEM,
    PROBE_SYSTEM,
    REPAIR_SYSTEM,
    extraction_prompt,
    probe_prompt,
    repair_prompt,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class StructuredClient(Protocol):
    model: str

    def generate(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT: ...


class GateAExperiment:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def extract(self, demo: TeacherDemo) -> Procedure:
        return self.client.generate(
            system=EXTRACTION_SYSTEM,
            prompt=extraction_prompt(demo),
            schema=Procedure,
        )

    def probe(self, procedure: Procedure) -> ProbeReport:
        return self.client.generate(
            system=PROBE_SYSTEM,
            prompt=probe_prompt(procedure.learner_view()),
            schema=ProbeReport,
        )

    def repair(
        self, procedure: Procedure, report: ProbeReport, teacher_clarification: str
    ) -> RepairResult:
        blockers = [gap for gap in report.blockers if gap.blocks_execution]
        if not blockers:
            raise ValueError("the probe report has no execution-blocking gap to repair")
        if not teacher_clarification.strip():
            raise ValueError("teacher clarification cannot be empty")
        blocker = max(blockers, key=lambda gap: gap.severity)
        return self.client.generate(
            system=REPAIR_SYSTEM,
            prompt=repair_prompt(procedure, blocker, teacher_clarification),
            schema=RepairResult,
        )


def create_run_directory(root: Path) -> Path:
    run_id = uuid4().hex[:12]
    path = root / run_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def save_artifact(path: Path, artifact: BaseModel) -> None:
    path.write_text(artifact.model_dump_json(indent=2) + "\n", encoding="utf-8")


def save_text(path: Path, value: str) -> None:
    path.write_text(value.strip() + "\n", encoding="utf-8")


def load_demo(path: Path) -> TeacherDemo:
    return TeacherDemo.model_validate_json(path.read_text(encoding="utf-8"))


def build_manifest(
    *, run_dir: Path, model: str, before: ProbeReport, after: ProbeReport
) -> RunManifest:
    return RunManifest(
        run_id=run_dir.name,
        model=model,
        probe_before=before.status,
        probe_after=after.status,
        gate_passed=(
            before.status == ProbeStatus.BLOCKED and after.status == ProbeStatus.UNBLOCKED
        ),
    )


def read_json(path: Path) -> dict[str, object]:
    """Convenience helper for inspecting a saved artifact without a schema."""
    return json.loads(path.read_text(encoding="utf-8"))
