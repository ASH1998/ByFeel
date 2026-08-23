# ByFeel

ByFeel finds what an expert forgot to explain. The local MVP extracts a
learner-facing procedure from a teacher demonstration, tests it through a
learner-only blinded probe, repairs one blocker from a teacher clarification,
and applies the repaired criterion at a learner checkpoint.

## Prerequisites

- Python 3.12 managed by `uv`
- Node.js 22 or newer
- Google Cloud CLI
- Git

## Local setup

```powershell
uv sync
Copy-Item .env.example .env
```

Fill in the local values in `.env`. That file is ignored by Git and must not be
committed.

Google Cloud CLI authentication is already configured for this project. Do not
change its account, project, authentication, or any cloud resource without the
user's direct approval. See [KEY_INSTRUCTIONS.md](KEY_INSTRUCTIONS.md) and the
local cloud ledger at `cloud-ledger/README.md` (intentionally ignored by Git).

Project execution status is tracked in the
[feature and test checklist](docs/project-checklist.md).
The [implementation alignment note](docs/implementation-alignment.md) keeps
product work tied to the original closed loop and distinguishes product
capabilities from evaluation tooling.
The [judge-ready architecture](docs/judge-ready-architecture.md) records the
implemented UI, API, ADK, isolation, persistence, and test boundaries.
[Hackathon compliance](docs/hackathon-compliance.md) distinguishes official
rules from internal strategy, and the [four-minute demo script](docs/demo-script.md)
provides a reproducible judge narrative.

## Decision Gate A

The first experiment tests whether a model that sees only learner-facing
instructions can expose a real blocker, and whether a teacher clarification
repairs it.

1. Copy `experiments/gate_a/demo.template.json` and replace every placeholder
   with notes from a real three-step demonstration.
2. Ensure `.env` contains `GOOGLE_API_KEY`, `GOOGLE_MODEL`, and
   `GOOGLE_MODEL_LITE`.
3. Run:

```powershell
uv run byfeel gate-a --demo experiments/gate_a/demo.json
```

The CLI stops after the blinded probe. A human must first accept or reject the
reported blocker:

```powershell
uv run byfeel review-blocker `
  --run runs/gate-a/<run-id> `
  --decision genuine `
  --reason "Why this omission prevents execution"
```

Use `--decision false_blocker` to close a negative run without clarification or
repair. Only after a genuine review, put the teacher's answer alone in a text
file and resume without repeating extraction or the initial probe:

```powershell
uv run byfeel gate-a --resume-run runs/gate-a/<run-id> --clarification-file answer.txt
```

The resumed stage repairs the procedure and runs a fresh blinded probe. All
artifacts, including per-call model and token usage, are written beneath
`runs/`, which is intentionally ignored because it can contain raw
demonstrations.

See `docs/decision-gate-a.md` for the experiment contract and success criteria.

Current validation status: Gate A remains incomplete. Its ignored ledger records
12 of the 18 allowed calls, actual billed Gemini cost is unknown, and final real-
demonstration reliability review remains required. UI or ADK functionality is
not counted as Gate A evidence. Local Gate B preparation is described in
`docs/decision-gate-b.md`; no held-out Gate B evaluation has been completed.
The supplied towel-video workaround is recorded factually in
`docs/towel-folding-pilot.md`: it is useful pilot evidence, but the purported
teacher/student pair is byte-identical and therefore not an independent learner
comparison.

### Teacher video ingestion

The local CLI can create a teacher-only draft from a bounded demonstration:

```powershell
uv run byfeel ingest-demo `
  --video "assets/videos/teacher-demo.mp4" `
  --title "Demonstrated task" `
  --domain "task domain" `
  --learner-goal "observable learner result" `
  --constraint "real safety constraint" `
  --speech-mode silent
```

Offline sampling defaults to roughly one frame per second, bounded to 9–18
frames. `--frame-count` can override that within the local safety bound when a
rapid or unusually slow demonstration needs different coverage.

Review the resulting draft against the real source, put the corrected factual
transcript in a text file, and approve it:

```powershell
uv run byfeel approve-demo `
  --run runs/media-ingest/<run-id> `
  --approved-transcript-file reviewed-transcript.txt
```

Only the resulting `approved-demo.json` may enter `gate-a`. Raw video, extracted
frames/audio, source metadata, and the unapproved draft remain ignored and on
the teacher side. Voiced/uncertain demonstrations include audio for verbatim
speech extraction; silent demonstrations use visual evidence only. See
`docs/demonstration-capture-plan.md` for the exact boundary and current limits.

## Local MVP web app

The default app uses in-memory persistence while calling the configured Gemini
model. It does not deploy or mutate cloud configuration.

```powershell
uv run byfeel serve
```

Open <http://127.0.0.1:8000>. The role-separated page walks through:

1. bounded silent or spoken teacher video, sampled-frame review, and immutable
   factual-record approval;
2. Google ADK Teaching Partner extraction from that approved record only;
3. a fresh Google ADK blinded probe with the exact learner projection and
   excluded contexts shown;
4. immutable blocker review, one verbatim clarification, provenance-checked
   bounded repair, exact diff, and fresh reprobe;
5. explicit learner-artifact approval and Google ADK Learner Coach checkpoints;
6. a facilitator Gate C flow that pins a static baseline and a ByFeel repaired
   version, runs separate learner sessions, and records attempts, detection,
   abstention, intervention provenance, correction, timing, and final outcome;
7. a read-only evidence view with versions, approvals, tool/model records,
   token usage when available, and honest limitations.

Use **Load seeded rehearsal · 0 model calls** for a deterministic browser
rehearsal. It includes a deliberate learner error and teacher-derived recovery,
is visibly labeled, produces no ADK/model evidence, and is excluded from Gate A.
Teacher and learner session IDs can be resumed after a page refresh while the
configured repository remains available.

The hosted browser never uploads source video. It derives 6–18 ordered JPEG
frames on-device, limits each frame to 768 pixels, rejects a predominantly
unusable package, and sends at most 5 MiB of decoded image evidence. The package
retains timestamps, dimensions, a sampled source fingerprint, extraction-policy
version, and a pseudonymous source ID. Live camera uses the same frame-only
contract. No raw video or audio reaches FastAPI, Cloud Storage, or Gemini;
spoken facts must be added during mandatory teacher review. The old raw-video
endpoints are disabled unless a local operator explicitly sets
`BYFEEL_ALLOW_LOCAL_RAW_VIDEO=1`.

### Decision Gate C transfer experiment

Open **04 · Gate C transfer** after a learner-ready procedure exists. The
facilitator selects the exact extracted procedure version for the
static_instructions baseline and the exact learner_approved version for the
byfeel_teacher_repaired arm. Each arm receives a new version-pinned learner
session. The first target-checkpoint attempt must be marked as the same agreed
deliberate incorrect state; the runner records whether the system detected it,
abstained safely, or missed it. A ByFeel intervention is accepted only when it
resolves to an existing append-only teacher correction and the exact approved
procedure version.

The report is structured JSON and intentionally distinguishes pending,
pending_real_evidence, synthetic_excluded, not_evaluable, and pass_candidate.
pass_candidate is not a claim that Gate C passed: a real facilitator must
review the fresh learner observations and genuine teacher provenance. The
seeded button creates a deterministic pair with zero model calls and is always
labelled synthetic and excluded.

The formal invariants, remaining evidence, and facilitator protocol are in
[docs/decision-gate-c.md](docs/decision-gate-c.md); the 148-item checklist
classification is in [docs/gate-c-readiness.md](docs/gate-c-readiness.md).

For a real run, do not enter names, email addresses, raw media, or hidden notes.
Use the concise facilitator protocol below. Only separately approved Gemini
usage may be used for a real run.

Optional PNG, JPEG, and WebP snapshots are limited to 5 MiB. The API validates
the media signature, records a SHA-256 checksum and provenance, and sends a
learner snapshot to Gemini only at an explicit checkpoint.

The configured models have explicit roles:

- `GOOGLE_MODEL` (`gemini-3.6-flash`) runs the reasoning-critical blinded probe.
- `GOOGLE_MODEL_LITE` (`gemini-3.5-flash-lite`) runs extraction, bounded repair,
  and learner checkpoint evaluation to reduce latency and cost.

### Existing Firestore and evidence bucket

To use only the already approved cloud resources for local test application
data, run:

```powershell
uv run byfeel serve --cloud --test-namespace local-mvp
```

Cloud mode is hard-scoped to:

- Firestore `(default)`: `byfeel_test_runs/{test-namespace}/...`
- `gs://byfeel-evidence-775995990601`:
  `test-data/{test-namespace}/...`

The adapters contain no database/bucket/API/IAM/index/policy/deployment
management operations and no delete methods. The current restricted identity
can create/read/update test documents and create/read unique evidence objects,
but cannot delete or overwrite them. Use a new namespace for independent runs
and record material experiments in the ignored `cloud-ledger/`.

## API

Useful local endpoints:

- `GET /health`, `GET /ready`, `GET /version`
- `POST /api/teacher/sessions`
- `GET /api/teacher/sessions/{id}`
- `POST /api/teacher/sessions/{id}/media`
- `POST /api/teacher/sessions/{id}/media-stream`
- `POST /api/teacher/sessions/{id}/evidence-package` (hosted/default path)
- `POST /api/teacher/sessions/{id}/factual-approval`
- `POST /api/teacher/sessions/{id}/extract`
- `GET /api/teacher/sessions/{id}/frames/{sample-id}`
- `POST /api/probe-runs/{id}/review`
- `POST /api/evidence`
- `POST /api/procedures/{id}/clarifications`
- `POST /api/procedures/{id}/learner-approval`
- `POST /api/learner/sessions`
- `GET /api/learner/sessions/{id}`
- `POST /api/learner/sessions/{id}/checkpoints`
- `GET /api/learner/sessions/{id}/events`
- `GET /api/judge/evidence/{procedure-id}`
- `POST /api/demo/seeded-rehearsal`

Gate C API routes:

- POST /api/gate-c/experiments
- GET /api/gate-c/experiments/{id}
- GET /api/gate-c/experiments/{id}/report
- POST /api/gate-c/experiments/{id}/arms/{arm}/start
- POST /api/gate-c/arms/{arm-run-id}/attempts
- POST /api/gate-c/arms/{arm-run-id}/finalize
- POST /api/gate-c/experiments/{id}/attestation

## Verification

```powershell
uv run pytest -q --basetemp=.pytest-tmp-final
uv run ruff check .
uv run ruff format --check .
```

Automated tests use fake model and in-memory/cloud doubles, so they make no
Gemini or Google Cloud calls. The bounded live smoke script is intentionally
separate because it writes authorized namespaced test data and incurs model
usage:

```powershell
uv run python scripts/live_smoke.py --namespace your-unique-test-namespace
```

## Real Gate C facilitator protocol

1. Confirm the task is low-risk, the teacher-approved repair is genuine, and
   the learner has not seen the demonstration. Assign a pseudonymous learner
   code and keep the same code for both arms.
2. Pin the extracted static version and the learner-approved repaired version
   for the same procedure and checkpoint. Write one observable deliberate
   incorrect state before the learner starts.
3. Run the static arm with only its static instructions. Submit the incorrect
   observation, record detection/abstention/missed detection, and do not provide
   ByFeel teacher-repaired guidance. Finalize the arm.
4. Run the ByFeel arm with a fresh session. Submit the same incorrect state.
   Show the intervention and its correction provenance, then let the learner
   correct the state and submit a correction observation. Advance only when
   the checkpoint evaluator advances after that correction. Finalize the arm.
5. Record the human attestation without personal information. Review the JSON
   comparison, attempts, elapsed times, learner events, intervention source,
   and any uncertainty. Treat missing or abstained evidence as not evaluable.

The only remaining Gate C claim is real evidence: fresh learner behavior,
genuine teacher-derived procedure and observations, and a facilitator-reviewed
comparison. Local fake-model tests and the synthetic rehearsal do not satisfy
that claim.

## Repository layout

- `backend/` — domain models, services, persistence adapters, FastAPI, and UI
- `docs/` — project documentation
- `scripts/` — development and operational scripts
