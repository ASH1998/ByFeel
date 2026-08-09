# Key instructions for ByFeel

This document records the user's durable operating constraints for the project.
The root `AGENTS.md` repeats the actionable rules so Codex and Codex CLI load
them automatically at the start of work in this repository.

## Account boundaries

1. The Gemini Developer API key comes from a Google account that is separate
   from the account authenticated in Google Cloud CLI.
2. Google Cloud CLI setup is complete and connected to the user's account and
   ByFeel project.
3. Do not merge these identities conceptually or operationally. In particular,
   do not assume the Gemini key is associated with the Google Cloud project or
   migrate/store that key in Google Cloud without direct approval.

## Mandatory approval boundary

Codex must not create, delete, deploy, enable, disable, modify, upload to, or
write to any cloud resource without direct user approval for the exact action.
This includes, but is not limited to:

- enabling or disabling Google APIs;
- creating or changing Cloud Run services or jobs;
- creating or changing Firestore databases, documents, or indexes;
- creating buckets or uploading/deleting Cloud Storage objects;
- creating or changing Secret Manager secrets or versions;
- changing IAM roles, service accounts, billing, quotas, budgets, or alerts;
- creating Artifact Registry repositories or pushing images;
- deploying from source or triggering Cloud Build;
- changing the active `gcloud` account, project, region, or authentication.

Read-only inspection is allowed. If a command might prompt to enable an API or
otherwise mutate state, stop instead of accepting the prompt.

Before asking for approval, Codex must provide:

- exact project/account boundary;
- exact service and resource name;
- region;
- command or API operation;
- purpose;
- conservative cost estimate in INR;
- recurring-cost and budget impact;
- rollback or cleanup plan.

Approval is single-scope and single-use. A changed command, resource, region, or
purpose requires fresh approval.

## Budget

- Planning target: INR 10,000 total.
- Hard ceiling: INR 15,000 total.
- The ceiling includes Google Cloud and Gemini Developer API usage across both
  Google accounts.
- Prefer local execution, emulators, free tiers, request limits, and
  scale-to-zero services.
- Do not incur a paid charge or create an open-ended recurring cost without a
  conservative estimate and direct approval.

## Recordkeeping

The canonical ledger is the `cloud-ledger/` folder. It must be updated after
every approved resource mutation and meaningful paid API experiment. Each event
must be traceable by both date and service. The folder is intentionally ignored
by Git and must never be staged or force-added. Never put credentials or secret
values in the ledger.

Last confirmed by the user: 2026-08-10.
