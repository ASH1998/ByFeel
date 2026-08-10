"""CLI for local ByFeel mechanism experiments."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv

from .experiment import (
    GateAExperiment,
    build_manifest,
    create_run_directory,
    load_demo,
    save_artifact,
    save_text,
)
from .gate_b import GateBEvaluationSet, calculate_gate_b_metrics
from .gemini import ByFeelModelRouter, GeminiStructuredClient
from .media_ingest import MediaDraft, analyze_teacher_media, approve_media_draft
from .models import (
    BlockerReview,
    BlockerReviewDecision,
    ProbeReport,
    ProbeStatus,
    Procedure,
)

ResultT = TypeVar("ResultT")


def _print_report(label: str, report: ProbeReport) -> None:
    print(f"\n{label}: {report.status.value.upper()}")
    print(report.summary)
    for gap in report.blockers:
        print(f"- [BLOCKER] {gap.step_id}: {gap.description}")
        print(f"  Missing: {gap.missing_information}")
    for gap in report.non_blocking_improvements:
        print(f"- [improvement] {gap.step_id}: {gap.description}")
    if report.teacher_question:
        print(f"\nTeacher question: {report.teacher_question}")


class _UsageRecorder:
    """Append per-call token usage without exposing prompts or credentials."""

    def __init__(self, run_dir: Path, client: ByFeelModelRouter) -> None:
        self.path = run_dir / "usage.json"
        self.client = client
        self.seen = {"main": 0, "lite": 0}

    def call(self, phase: str, operation: Callable[[], ResultT]) -> ResultT:
        try:
            return operation()
        finally:
            self._append_new(phase)

    def _append_new(self, phase: str) -> None:
        payload = {"calls": []}
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        calls = payload.setdefault("calls", [])
        for role, routed_client in (
            ("main", self.client.main),
            ("lite", self.client.lite),
        ):
            for usage in routed_client.usage[self.seen[role] :]:
                calls.append(
                    {
                        "phase": phase,
                        "role": role,
                        "model": routed_client.model,
                        **usage,
                    }
                )
            self.seen[role] = len(routed_client.usage)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_saved[LoadedT](path: Path, schema: type[LoadedT]) -> LoadedT:
    return schema.model_validate_json(path.read_text(encoding="utf-8"))


def _teacher_clarification(args: argparse.Namespace) -> str:
    clarification = args.clarification
    if args.clarification_file:
        clarification = args.clarification_file.read_text(encoding="utf-8")
    return (clarification or "").strip()


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

    client = ByFeelModelRouter(
        main=GeminiStructuredClient(api_key=api_key, model=model),
        lite=GeminiStructuredClient(api_key=api_key, model=lite_model),
    )
    experiment = GateAExperiment(client)

    if args.resume_run:
        run_dir = args.resume_run
        if not run_dir.is_dir():
            print(f"Saved run does not exist: {run_dir}", file=sys.stderr)
            return 2
        procedure = _load_saved(run_dir / "01_procedure.json", Procedure)
        before = _load_saved(run_dir / "02_probe_before.json", ProbeReport)
        review_path = run_dir / "03_blocker_review.json"
        if not review_path.exists():
            print("Human blocker review is required before clarification or repair.")
            return 2
        review = _load_saved(review_path, BlockerReview)
        if review.decision != BlockerReviewDecision.GENUINE:
            print("The human review rejected this blocker; this run cannot be repaired.")
            return 2
        if (run_dir / "03_teacher_clarification.txt").exists():
            print("This run already contains a teacher clarification; refusing a second one.")
            return 2
        usage = _UsageRecorder(run_dir, client)
        print(f"Resuming run: {run_dir}")
    else:
        demo = load_demo(args.demo)
        run_dir = create_run_directory(args.output)
        save_artifact(run_dir / "00_teacher_demo.json", demo)
        usage = _UsageRecorder(run_dir, client)
        print(f"Run: {run_dir}")
        print("Extracting learner-facing procedure...")
        procedure = usage.call("extraction", lambda: experiment.extract(demo))
        save_artifact(run_dir / "01_procedure.json", procedure)

        print("Running blinded novice probe...")
        before = usage.call("probe_before", lambda: experiment.probe(procedure))
        save_artifact(run_dir / "02_probe_before.json", before)
        _print_report("Probe before repair", before)

    if before.status != ProbeStatus.BLOCKED:
        print("\nGate inconclusive: the initial procedure did not produce a blocker.")
        return 1

    clarification = _teacher_clarification(args)
    if not clarification:
        print("\nHuman blocker-review checkpoint reached; do not answer the question yet.")
        print(
            f"Review with: uv run byfeel review-blocker --run {run_dir} "
            '--decision genuine|false_blocker --reason "<human reason>"'
        )
        return 1
    save_text(run_dir / "03_teacher_clarification.txt", clarification)

    print("Repairing canonical procedure...")
    repair = usage.call("repair", lambda: experiment.repair(procedure, before, clarification))
    save_artifact(run_dir / "04_repair.json", repair)

    print("Rerunning a fresh blinded novice probe...")
    after = usage.call("probe_after", lambda: experiment.probe(repair.procedure))
    save_artifact(run_dir / "05_probe_after.json", after)
    _print_report("Probe after repair", after)

    manifest = build_manifest(run_dir=run_dir, model=client.model, before=before, after=after)
    save_artifact(run_dir / "manifest.json", manifest)
    result = "SUCCEEDED" if manifest.status_transition_succeeded else "DID NOT SUCCEED"
    print(f"\nAutomated per-run status transition: {result}")
    print("Decision Gate A remains pending three demonstrations and human review.")
    print(f"Artifacts: {run_dir}")
    return 0 if manifest.status_transition_succeeded else 1


def run_review_blocker(args: argparse.Namespace) -> int:
    report = _load_saved(args.run / "02_probe_before.json", ProbeReport)
    if report.status != ProbeStatus.BLOCKED:
        print("Only a blocked probe report can receive a blocker review.", file=sys.stderr)
        return 2
    target = args.run / "03_blocker_review.json"
    if target.exists():
        print("This run already has an immutable blocker review.", file=sys.stderr)
        return 2
    review = BlockerReview(
        run_id=args.run.name,
        decision=BlockerReviewDecision(args.decision),
        reason=args.reason,
    )
    save_artifact(target, review)
    if review.decision == BlockerReviewDecision.FALSE_BLOCKER:
        print("False blocker recorded. Run closed without clarification or repair.")
    else:
        print(f"Genuine blocker recorded. Ask exactly one question: {report.teacher_question}")
    return 0


def run_gate_b_metrics(args: argparse.Namespace) -> int:
    evaluation = GateBEvaluationSet.model_validate_json(args.results.read_text(encoding="utf-8"))
    metrics = calculate_gate_b_metrics(evaluation)
    if args.output:
        save_artifact(args.output, metrics)
        print(f"Gate B metrics: {args.output}")
    else:
        print(metrics.model_dump_json(indent=2))
    return 0


def run_ingest_demo(args: argparse.Namespace) -> int:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    lite_model = os.getenv("GOOGLE_MODEL_LITE", "").strip()
    if not api_key or not lite_model:
        print("Set GOOGLE_API_KEY and GOOGLE_MODEL_LITE before media ingestion.", file=sys.stderr)
        return 2
    run_dir = create_run_directory(args.output)
    client = GeminiStructuredClient(api_key=api_key, model=lite_model)
    draft = analyze_teacher_media(
        client=client,
        source=args.video,
        run_dir=run_dir,
        title=args.title,
        domain=args.domain,
        learner_goal=args.learner_goal,
        constraints=args.constraint,
        speech_mode=args.speech_mode,
        frame_count=args.frame_count,
    )
    save_artifact(run_dir / "media-draft.json", draft)
    (run_dir / "usage.json").write_text(
        json.dumps({"model": client.model, "calls": client.usage}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Teacher media draft: {run_dir / 'media-draft.json'}")
    print("Human approval required; this draft cannot enter Gate A yet.")
    return 0


def run_approve_demo(args: argparse.Namespace) -> int:
    draft = MediaDraft.model_validate_json(
        (args.run / "media-draft.json").read_text(encoding="utf-8")
    )
    transcript = args.approved_transcript_file.read_text(encoding="utf-8")
    approval = approve_media_draft(draft, transcript)
    save_artifact(args.run / "approval.json", approval)
    save_artifact(args.run / "approved-demo.json", approval.demo)
    print(f"Approved Gate A input: {args.run / 'approved-demo.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="byfeel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    gate = subparsers.add_parser("gate-a", help="Run the blinded-procedure stress test")
    source = gate.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", type=Path, help="Teacher demo JSON file")
    source.add_argument(
        "--resume-run",
        type=Path,
        help="Resume a saved run at its one-teacher-clarification checkpoint",
    )
    gate.add_argument("--output", type=Path, default=Path("runs/gate-a"))
    gate.add_argument("--clarification", help="Teacher clarification text")
    gate.add_argument("--clarification-file", type=Path)
    gate.set_defaults(handler=run_gate_a)
    review = subparsers.add_parser(
        "review-blocker", help="Accept or reject a blinded-probe blocker before clarification"
    )
    review.add_argument("--run", type=Path, required=True)
    review.add_argument("--decision", choices=["genuine", "false_blocker"], required=True)
    review.add_argument("--reason", required=True)
    review.set_defaults(handler=run_review_blocker)
    gate_b = subparsers.add_parser(
        "gate-b-metrics", help="Calculate deterministic metrics from Gate B results"
    )
    gate_b.add_argument("--results", type=Path, required=True)
    gate_b.add_argument("--output", type=Path)
    gate_b.set_defaults(handler=run_gate_b_metrics)
    ingest = subparsers.add_parser(
        "ingest-demo", help="Create a human-reviewable draft from teacher video"
    )
    ingest.add_argument("--video", type=Path, required=True)
    ingest.add_argument("--title", required=True)
    ingest.add_argument("--domain", required=True)
    ingest.add_argument("--learner-goal", required=True)
    ingest.add_argument("--constraint", action="append", default=[])
    ingest.add_argument("--speech-mode", choices=["silent", "spoken", "unsure"], required=True)
    ingest.add_argument(
        "--frame-count",
        type=int,
        default=None,
        help="Override duration-aware sampling (default about 1 fps, bounded to 9-18 frames)",
    )
    ingest.add_argument("--output", type=Path, default=Path("runs/media-ingest"))
    ingest.set_defaults(handler=run_ingest_demo)
    approve = subparsers.add_parser(
        "approve-demo", help="Approve a reviewed media transcript for Gate A"
    )
    approve.add_argument("--run", type=Path, required=True)
    approve.add_argument("--approved-transcript-file", type=Path, required=True)
    approve.set_defaults(handler=run_approve_demo)
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
