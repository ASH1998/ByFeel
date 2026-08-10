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

## Decision Gate A

The first experiment tests whether a model that sees only learner-facing
instructions can expose a real blocker, and whether a teacher clarification
repairs it.

1. Copy `experiments/gate_a/demo.template.json` and replace every placeholder
   with notes from a real three-step demonstration.
2. Ensure `.env` contains `GOOGLE_API_KEY` and `GOOGLE_MODEL`.
3. Run:

```powershell
uv run byfeel gate-a --demo experiments/gate_a/demo.json
```

The CLI pauses after the blinded probe, shows its blocker, asks for the
teacher's clarification, repairs the procedure, and runs a fresh blinded probe.
All artifacts are written beneath `runs/`, which is intentionally ignored
because it can contain raw demonstrations.

See `docs/decision-gate-a.md` for the experiment contract and success criteria.

## Local MVP web app

The default app uses in-memory persistence while calling the configured Gemini
model. It does not deploy or mutate cloud configuration.

```powershell
uv run byfeel serve
```

Open <http://127.0.0.1:8000>. The page walks through:

1. teacher demonstration and extraction;
2. learner-only blinded probe;
3. one targeted teacher clarification and exact before/after diff;
4. fresh reprobe;
5. learner checkpoint and teacher-derived guidance.

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
- `POST /api/evidence`
- `POST /api/procedures/{id}/clarifications`
- `POST /api/learner/sessions`
- `POST /api/learner/sessions/{id}/checkpoints`
- `GET /api/learner/sessions/{id}/events`

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

## Repository layout

- `backend/` — domain models, services, persistence adapters, FastAPI, and UI
- `docs/` — project documentation
- `scripts/` — development and operational scripts
