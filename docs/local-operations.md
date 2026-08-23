# Local operations and runbooks

This document contains the detailed instructions moved out of the root
README. The root README is intentionally short so a judge can understand the
product before reading implementation notes.

## Prerequisites and setup

- Python 3.12 managed by `uv`
- Git
- Node.js 22 or newer for the video tooling under `videos/`
- Google Cloud CLI only when using the already-approved, namespaced cloud test
  adapters

Create the local environment:

```powershell
uv sync
Copy-Item .env.example .env
```

Fill in local values in `.env`. It is ignored by Git and must never be
committed. The default web app uses in-memory persistence and does not deploy
or mutate cloud configuration.

## Local web app

Start the app:

```powershell
uv run byfeel serve
```

Open <http://127.0.0.1:8000>. The role-separated browser covers:

1. bounded silent or spoken teacher video, sampled-frame review, and immutable
   factual-record approval;
2. Teaching Partner extraction from the approved record only;
3. a fresh learner-only blinded probe with its exact projection and exclusions;
4. blocker review, one verbatim clarification, provenance-checked repair, an
   exact diff, and a fresh reprobe;
5. learner-artifact approval and Learner Coach checkpoints; and
6. the facilitator Gate C transfer flow and read-only evidence view.

Choose **Load seeded rehearsal · 0 model calls** for a deterministic browser
walkthrough. It includes a deliberate learner error and teacher-derived
recovery, is visibly synthetic, produces no ADK/model evidence, and is excluded
from Gate A and Gate C claims.

### Media boundary

The hosted browser never uploads source video. It derives 6–18 ordered JPEG
frames on-device, limits each frame to 768 pixels, rejects a predominantly
unusable package, and sends at most 5 MiB of decoded image evidence. The
package retains timestamps, dimensions, a sampled source fingerprint,
extraction-policy version, and a pseudonymous source ID. Live camera uses the
same frame-only contract. No raw video or audio reaches FastAPI, Cloud Storage,
or Gemini; spoken facts are added during mandatory teacher review.

Optional PNG, JPEG, and WebP learner snapshots are limited to 5 MiB. The API
validates the media signature, records a SHA-256 checksum and provenance, and
sends a snapshot to Gemini only at an explicit learner checkpoint.

The old raw-video endpoints are disabled unless a local operator explicitly
sets `BYFEEL_ALLOW_LOCAL_RAW_VIDEO=1`.

## Decision Gate A CLI

Gate A tests whether a learner-only view exposes a real blocker and whether one
teacher clarification repairs it.

1. Copy `experiments/gate_a/demo.template.json` to
   `experiments/gate_a/demo.json` and replace every placeholder with notes from
   a real three-step demonstration.
2. Ensure `.env` contains `GOOGLE_API_KEY`, `GOOGLE_MODEL`, and
   `GOOGLE_MODEL_LITE`.
3. Run the initial extraction and blinded probe:

```powershell
uv run byfeel gate-a --demo experiments/gate_a/demo.json
```

The CLI stops after the blinded probe. A human must classify the result before
any repair:

```powershell
uv run byfeel review-blocker `
  --run runs/gate-a/<run-id> `
  --decision genuine `
  --reason "Why this omission prevents execution"
```

Use `--decision false_blocker` to close a negative run. For a genuine blocker,
put the teacher’s answer alone in a text file and resume without repeating
extraction or the first probe:

```powershell
uv run byfeel gate-a --resume-run runs/gate-a/<run-id> --clarification-file answer.txt
```

Artifacts, including per-call model and token usage, are written below
`runs/`, which is intentionally ignored because it can contain raw
demonstrations. See [decision-gate-a.md](decision-gate-a.md) for the contract
and success criteria.

### Teacher video ingestion

Create a teacher-only draft from a bounded demonstration:

```powershell
uv run byfeel ingest-demo `
  --video "assets/videos/teacher-demo.mp4" `
  --title "Demonstrated task" `
  --domain "task domain" `
  --learner-goal "observable learner result" `
  --constraint "real safety constraint" `
  --speech-mode silent
```

Review the draft against the source, put the corrected factual transcript in a
text file, and approve it:

```powershell
uv run byfeel approve-demo `
  --run runs/media-ingest/<run-id> `
  --approved-transcript-file reviewed-transcript.txt
```

Only `approved-demo.json` may enter Gate A. Raw video, extracted frames/audio,
source metadata, and the unapproved draft remain teacher-side and ignored.
Sampling defaults to roughly one frame per second, bounded to 9–18 frames;
`--frame-count` may change coverage within that bound.

## Gate C transfer experiment

Open **04 · Gate C transfer** after a learner-ready procedure exists. Pin the
exact extracted procedure for the `static_instructions` arm and the exact
`learner_approved` version for the `byfeel_teacher_repaired` arm. Give both
fresh learner sessions the same pseudonymous learner code, checkpoint, and
deliberate incorrect state.

Run the static arm first, record detection/abstention/missed detection, then
run the ByFeel arm, show the approved intervention and its provenance, submit
the learner’s correction, and finalize both arms. The structured report
distinguishes `pending`, `pending_real_evidence`, `synthetic_excluded`,
`not_evaluable`, and `pass_candidate`. `pass_candidate` is not a Gate C pass.

The seeded button creates a deterministic zero-model-call pair and is always
labelled synthetic and excluded.

See [decision-gate-c.md](decision-gate-c.md) for the formal invariants and
[gate-c-readiness.md](gate-c-readiness.md) for the checklist classification.

## API quick reference

Useful local endpoints:

```text
GET  /health, /ready, /version
POST /api/teacher/sessions
POST /api/teacher/sessions/{id}/media
POST /api/teacher/sessions/{id}/media-stream
POST /api/teacher/sessions/{id}/evidence-package
POST /api/teacher/sessions/{id}/factual-approval
POST /api/teacher/sessions/{id}/extract
GET  /api/teacher/sessions/{id}/frames/{sample-id}
POST /api/probe-runs/{id}/review
POST /api/evidence
POST /api/procedures/{id}/clarifications
POST /api/procedures/{id}/learner-approval
POST /api/learner/sessions
GET  /api/learner/sessions/{id}
POST /api/learner/sessions/{id}/checkpoints
GET  /api/learner/sessions/{id}/events
GET  /api/judge/evidence/{procedure-id}
POST /api/demo/seeded-rehearsal
```

Gate C routes are documented in [decision-gate-c.md](decision-gate-c.md):
experiment creation/reporting, arm start, attempt recording, finalization, and
human attestation.

## Verification

The automated suite uses fake-model and in-memory/cloud doubles, so it makes
no Gemini or Google Cloud calls:

```powershell
uv run pytest -q --basetemp=.pytest-tmp-final
uv run ruff check .
uv run ruff format --check .
```

The bounded live smoke script is separate because it writes authorized,
namespaced test data and incurs model usage:

```powershell
uv run python scripts/live_smoke.py --namespace your-unique-test-namespace
```

## Cloud test mode

Only already-approved test resources may be used, and only after the exact
operation has been approved under `AGENTS.md` and `KEY_INSTRUCTIONS.md`:

```powershell
uv run byfeel serve --cloud --test-namespace local-mvp
```

Cloud mode is hard-scoped to Firestore
`byfeel_test_runs/{test-namespace}/...` and
`gs://byfeel-evidence-775995990601/test-data/{test-namespace}/...`. The adapters
do not manage databases, buckets, APIs, IAM, indexes, policies, deployment, or
deletion. Use a new namespace for independent runs and record material
experiments in the ignored `cloud-ledger/`.

## Current limitations

- Gate A remains incomplete: the ignored ledger records 12 of 18 allowed calls,
  actual billed Gemini cost is unknown, and a final real-demonstration review is
  still required.
- The seeded rehearsal is synthetic and cannot establish Gate A or Gate C
  success.
- In-memory state does not survive a server restart.
- General request idempotency, authentication, and asynchronous media
  processing are not yet implemented.
- No deployed Cloud Run backend is part of this local milestone; a later
  deployment requires a separately approved, costed operation.

For the product invariant and role boundaries, read
[judge-ready-architecture.md](judge-ready-architecture.md). For the submission
narrative, read [demo-script.md](demo-script.md).
