# ByFeel repository instructions

These instructions apply to every task in this repository. Read
`KEY_INSTRUCTIONS.md` before planning or performing work involving Google,
Gemini, deployment, infrastructure, data persistence, or paid services.

## Non-negotiable cloud boundary

- Google Cloud CLI is already installed, authenticated, and connected to the
  user's ByFeel project. Do not run `gcloud init`, change the active account or
  project, log in/out, or alter local Google authentication unless the user
  directly approves that exact change.
- The Gemini Developer API key in `.env` belongs to a separate Google account.
  Never assume it belongs to, bills through, or has access to the active Google
  Cloud project. Never copy it into Google Cloud, Vertex AI, Secret Manager, a
  committed file, logs, or command output.
- Do not create, delete, deploy, enable, disable, update, upload to, write to, or
  otherwise mutate any cloud resource without the user's direct approval in the
  current conversation for the exact proposed operation and resource.
- Before requesting approval, state the exact project, service, resource,
  region, mutation, expected cost, recurring-cost risk, and rollback/deletion
  plan. Approval for one mutation does not authorize later mutations.
- Read-only cloud inspection is permitted when needed. Use explicit read-only
  commands and do not accept prompts that would enable APIs or alter state.
- Never treat a general goal such as "deploy the app" or a previous approval as
  standing permission for cloud mutations. Pause at the mutation boundary.

## Budget control

- Total project budget: INR 10,000-15,000.
- Use INR 10,000 as the planning target and INR 15,000 as the hard ceiling unless
  the user explicitly changes these limits.
- Prefer local experiments and free-tier/scale-to-zero designs. Before any paid
  operation, estimate one-time and monthly cost in INR and explain uncertainty.
- Do not start or scale a service if the conservative estimate could cross the
  remaining hard-ceiling budget.
- Gemini API usage is part of this budget even though its key belongs to a
  separate account. State planned call counts before substantial experiments.

## Resource and spend tracking

- `cloud-ledger/` is the canonical cloud inventory, approval log, cost ledger,
  and chronological audit trail. Its `README.md` is the entry point. The entire
  folder is intentionally Git-ignored; never stage or force-add it.
- After every approved cloud mutation, update the register in the same change
  with the exact resource ID, project/account boundary, region, purpose, status,
  approval reference, creation/update date, cost estimate, and cleanup plan.
- Create one dated immutable event under `cloud-ledger/events/YYYY-MM-DD/` for
  each cloud mutation or material billing/API event, and link it from the
  relevant page under `cloud-ledger/services/`.
- Record Gemini/API experiments with date, model, purpose, call count, and cost
  estimate; never record API keys, tokens, credential paths, or secret values.
- Distinguish pre-existing user-managed resources from resources created for
  ByFeel. Never claim ownership of a resource merely because it is visible.
- If inventory or cost is uncertain, mark it `unknown` and resolve it with a
  read-only check before proposing further cloud work.
- If `cloud-ledger/` is absent in a fresh clone, recreate the local ledger before
  performing cloud work; do not remove its ignore rule.

## Current build boundary

- The current milestone is local mechanism validation. Do not add UI,
  persistence, ADK orchestration, or deployment unless the user asks for the
  next phase.
- Keep secrets in ignored local environment files only. Never commit `.env`,
  Google credentials, raw tokens, or generated run artifacts.
