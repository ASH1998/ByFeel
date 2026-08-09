# ByFeel

This repository is the workspace for the ByFeel experiments. It currently
contains the local Decision Gate A mechanism test; the application and UI have
not been implemented.

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
[cloud ledger](cloud-ledger/README.md).

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

## Repository layout

- `backend/` — Python experiment code; no API yet
- `frontend/` — web client (not yet implemented)
- `docs/` — project documentation
- `scripts/` — development and operational scripts
