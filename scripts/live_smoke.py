"""Bounded live smoke run against approved ByFeel test-data paths."""

from __future__ import annotations

import argparse
import os
import sys
from base64 import b64decode
from datetime import UTC, datetime

from byfeel.checkpoint import GeminiCheckpointEvaluator
from byfeel.evidence import CloudStorageEvidenceStore
from byfeel.firestore_repository import FirestoreRepository
from byfeel.gemini import ByFeelModelRouter, GeminiStructuredClient
from byfeel.models import LearnerObservation, ProbeStatus, TeacherDemo
from byfeel.service import ByFeelService
from dotenv import load_dotenv

ONE_PIXEL_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
ACTIVE_CLIENT: ByFeelModelRouter | None = None


def print_usage(client: ByFeelModelRouter) -> None:
    print(f"calls={len(client.usage)}")
    print(f"prompt_tokens={sum(item['prompt_tokens'] for item in client.usage)}")
    print(f"output_tokens={sum(item['output_tokens'] for item in client.usage)}")
    print(f"thinking_tokens={sum(item['thinking_tokens'] for item in client.usage)}")
    print(f"total_tokens={sum(item['total_tokens'] for item in client.usage)}")


def main() -> int:
    global ACTIVE_CLIENT
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--namespace",
        default=f"smoke-{datetime.now(UTC):%Y%m%d-%H%M%S}",
    )
    args = parser.parse_args()
    load_dotenv()
    api_key = os.environ["GOOGLE_API_KEY"]
    model = os.environ["GOOGLE_MODEL"]
    lite_model = os.environ["GOOGLE_MODEL_LITE"]
    bucket = os.environ["EVIDENCE_BUCKET"]
    database = os.getenv("FIRESTORE_DATABASE", "(default)")

    repository = FirestoreRepository(namespace=args.namespace, database=database)
    evidence_store = CloudStorageEvidenceStore(
        bucket_name=bucket,
        namespace=args.namespace,
    )
    main_client = GeminiStructuredClient(api_key=api_key, model=model)
    lite_client = GeminiStructuredClient(api_key=api_key, model=lite_model)
    client = ByFeelModelRouter(main=main_client, lite=lite_client)
    ACTIVE_CLIENT = client
    service = ByFeelService(
        repository=repository,
        teaching_client=client,
        checkpoint_evaluator=GeminiCheckpointEvaluator(lite_client, evidence_store),
    )

    taught = service.teach(
        TeacherDemo(
            title="Make a stable paper tent",
            domain="paper craft",
            learner_goal="Fold paper into a small tent that stays upright",
            raw_demonstration=(
                "Use one dry rectangular A4 or US Letter sheet of ordinary 75 to 90 gsm printer "
                "paper on a flat table. Step 1: Lift one long edge, bring it to meet the opposite "
                "long edge without "
                "pressing a crease, and slide it until neither edge extends past the other. "
                "Step 2: While holding those matched edges in place, press the fold from the "
                "center outward until the crease is firm enough. "
                "Step 3: Open the folded sheet, place both outer long edges flat on the table, "
                "and adjust it until the ridge is centered between those edges and the paper "
                "stands for three seconds without hands. "
                "Keep fingers away from paper edges and stop if the paper tears."
            ),
            constraints=["Safe paper craft only", "No hidden measurements"],
        )
    )
    if taught.probe_run.report.status != ProbeStatus.BLOCKED:
        print(f"namespace={args.namespace}")
        print("result=inconclusive_initial_probe")
        print_usage(client)
        return 1

    evidence = evidence_store.put(ONE_PIXEL_PNG, content_type="image/png", source="test")
    repaired = service.clarify(
        taught.procedure.id,
        (
            "The crease is firm enough when a sharp, continuous crease line is visible from one "
            "short edge to the other and the two folded long edges remain directly aligned after "
            "the learner removes both hands. Natural springback at the open side is acceptable."
        ),
        evidence,
    )
    if repaired.probe_run.report.status != ProbeStatus.UNBLOCKED:
        print(f"namespace={args.namespace}")
        print("result=repair_still_blocked")
        print_usage(client)
        return 1

    learner = service.start_learner(taught.procedure.id)
    current_step = learner.current_step
    if current_step is None:
        raise RuntimeError("learner session started without a current step")
    checkpoint = service.checkpoint(
        learner.session.session_id,
        LearnerObservation(
            step_id=current_step.step_id,
            description="The two long edges are aligned exactly with no visible offset.",
        ),
    )

    print(f"namespace={args.namespace}")
    print(f"procedure_id={taught.procedure.id}")
    print(f"evidence_object={evidence.object_name}")
    print(f"probe_before={taught.probe_run.report.status.value}")
    print(f"probe_after={repaired.probe_run.report.status.value}")
    print(f"checkpoint={checkpoint.latest_event.evaluation.decision.value}")
    print_usage(client)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error={type(exc).__name__}")
        print(str(exc))
        if ACTIVE_CLIENT is not None:
            print(f"calls={len(ACTIVE_CLIENT.usage)}")
            print(f"total_tokens={sum(item['total_tokens'] for item in ACTIVE_CLIENT.usage)}")
        sys.exit(1)
