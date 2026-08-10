"""CLI for local ByFeel mechanism experiments."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .experiment import (
    GateAExperiment,
    build_manifest,
    create_run_directory,
    load_demo,
    save_artifact,
    save_text,
)
from .gemini import ByFeelModelRouter, GeminiStructuredClient
from .models import ProbeReport, ProbeStatus


def _print_report(label: str, report: ProbeReport) -> None:
    print(f"\n{label}: {report.status.value.upper()}")
    print(report.summary)
    for gap in report.blockers:
        marker = "BLOCKER" if gap.blocks_execution else "warning"
        print(f"- [{marker}] {gap.step_id}: {gap.description}")
        print(f"  Missing: {gap.missing_information}")
    if report.teacher_question:
        print(f"\nTeacher question: {report.teacher_question}")


def run_gate_a(args: argparse.Namespace) -> int:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    model = os.getenv("GOOGLE_MODEL", "").strip()
    lite_model = os.getenv("GOOGLE_MODEL_LITE", "").strip()
    if not api_key or not model or not lite_model:
        print(
            "Set GOOGLE_API_KEY, GOOGLE_MODEL, and GOOGLE_MODEL_LITE in .env "
            "before running Gate A.",
            file=sys.stderr,
        )
        return 2

    demo = load_demo(args.demo)
    run_dir = create_run_directory(args.output)
    save_artifact(run_dir / "00_teacher_demo.json", demo)

    client = ByFeelModelRouter(
        main=GeminiStructuredClient(api_key=api_key, model=model),
        lite=GeminiStructuredClient(api_key=api_key, model=lite_model),
    )
    experiment = GateAExperiment(client)
    print(f"Run: {run_dir}")
    print("Extracting learner-facing procedure...")
    procedure = experiment.extract(demo)
    save_artifact(run_dir / "01_procedure.json", procedure)

    print("Running blinded novice probe...")
    before = experiment.probe(procedure)
    save_artifact(run_dir / "02_probe_before.json", before)
    _print_report("Probe before repair", before)

    if before.status != ProbeStatus.BLOCKED:
        print("\nGate inconclusive: the initial procedure did not produce a blocker.")
        return 1

    clarification = args.clarification
    if args.clarification_file:
        clarification = args.clarification_file.read_text(encoding="utf-8")
    if not clarification:
        clarification = input("\nTeacher clarification: ").strip()
    if not clarification:
        print("No clarification supplied; saved the initial probe and stopped.")
        return 1
    save_text(run_dir / "03_teacher_clarification.txt", clarification)

    print("Repairing canonical procedure...")
    repair = experiment.repair(procedure, before, clarification)
    save_artifact(run_dir / "04_repair.json", repair)

    print("Rerunning a fresh blinded novice probe...")
    after = experiment.probe(repair.procedure)
    save_artifact(run_dir / "05_probe_after.json", after)
    _print_report("Probe after repair", after)

    manifest = build_manifest(run_dir=run_dir, model=client.model, before=before, after=after)
    save_artifact(run_dir / "manifest.json", manifest)
    result = "PASSED" if manifest.gate_passed else "FAILED"
    print(f"\nDecision Gate A: {result}")
    print(f"Artifacts: {run_dir}")
    return 0 if manifest.gate_passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="byfeel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    gate = subparsers.add_parser("gate-a", help="Run the blinded-procedure stress test")
    gate.add_argument("--demo", type=Path, required=True, help="Teacher demo JSON file")
    gate.add_argument("--output", type=Path, default=Path("runs/gate-a"))
    gate.add_argument("--clarification", help="Teacher clarification text")
    gate.add_argument("--clarification-file", type=Path)
    gate.set_defaults(handler=run_gate_a)
    serve = subparsers.add_parser("serve", help="Run the local ByFeel MVP web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--cloud",
        action="store_true",
        help="Use the existing default Firestore database and approved evidence bucket",
    )
    serve.add_argument("--test-namespace", default="local-mvp")
    serve.set_defaults(handler=run_server)
    return parser


def run_server(args: argparse.Namespace) -> int:
    import uvicorn

    if args.cloud:
        os.environ["BYFEEL_REPOSITORY"] = "firestore"
        os.environ["BYFEEL_TEST_NAMESPACE"] = args.test_namespace
    uvicorn.run("byfeel.api:app", host=args.host, port=args.port, reload=False)
    return 0


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
