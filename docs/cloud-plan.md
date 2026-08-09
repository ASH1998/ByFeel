# ByFeel cloud plan

This is a planning document, not authorization to create cloud resources. Every
mutation still requires the direct approval defined in `KEY_INSTRUCTIONS.md`.

## Current account boundary

- Google Cloud project: `project-7ca77fe6-7ea2-403d-92b`.
- Project number: `775995990601`.
- Billing account currency: INR.
- The Gemini Developer API key belongs to a separate Google account and is not
  assumed to be linked to this project.

The local Decision Gate A experiment needs only the Gemini key and model. It
does not require Google Cloud resources.

## Minimum eventual cloud stack

| Service | Purpose | Planned timing | Small-MVP planning allowance |
|---|---|---|---:|
| Cloud Billing budget | Cost alerts for the project | Before other resources | INR 0 |
| Firestore Standard, Native mode | Procedures, corrections, probe runs, learner state | Persistence phase | Usually INR 0 within free quota |
| Cloud Storage Standard | Teacher and learner checkpoint images | Visual checkpoint phase | INR 10-100/month |
| Secret Manager | Gemini key for deployed backend | Deployment phase | Usually INR 0 within free quota |
| IAM service account | Least-privilege runtime identity | Deployment phase | INR 0 |
| Artifact Registry | Container image storage | Deployment phase | INR 0-50/month |
| Cloud Build | Reproducible source-to-container build | Deployment phase | Usually INR 0 within free quota |
| Cloud Run | FastAPI backend and optionally the compiled frontend | Deployment phase | INR 0-300/month at demo scale |
| Cloud Logging | Runtime logs from Cloud Run | Automatic with deployment | Usually INR 0 within free allotment |

## Recommended resource design

### Firestore

- Edition: Standard.
- Mode: Native.
- Database ID: `(default)`.
- Region: `asia-south1` (Mumbai).
- Use for structured metadata and state, not image bytes.
- Proposed collections: `procedures`, `probe_runs`, `learner_sessions`, and
  `audit_events`, with correction history beneath each procedure.
- The location is immutable after provisioning, so it requires an explicit
  location decision before creation.

Pricing reference: https://cloud.google.com/firestore/pricing

### Cloud Storage

- Regional Standard bucket in `asia-south1`.
- Public access blocked and uniform bucket-level access enabled.
- Versioning off initially.
- Proposed 30-day lifecycle for temporary evidence.
- Firestore stores object metadata and references; the bucket stores bytes.

Pricing reference: https://cloud.google.com/storage/pricing

### Secret Manager and service identity

- One Gemini secret with minimal active versions.
- Moving the separate-account key into Google Cloud is a distinct approval.
- One user-managed runtime service account such as `byfeel-api`.
- Grant only Firestore data access, bucket-scoped object access, and access to
  the exact Gemini secret.

Pricing reference: https://cloud.google.com/secret-manager/pricing

### Cloud Build, Artifact Registry, and Cloud Run

Cloud Build turns a reviewed source revision into a repeatable container image.
Artifact Registry stores that image. Cloud Run executes it as the public or
authenticated web service. Keeping all three in `asia-south1` avoids unnecessary
cross-region transfers.

The intended deployment is one Cloud Run service named `byfeel-api` in the same
Google Cloud project. Initially it can serve FastAPI and, if we choose the
simplest topology, the compiled Vite frontend as static files. Proposed safety
limits are request-based billing, minimum instances `0`, maximum instances `1`,
1 vCPU, and 512 MiB memory.

We do not need Cloud Build or Cloud Run during mechanism validation. They enter
only when the local transfer loop is reliable and we are ready for a judge-usable
URL and visible runtime logs.

Pricing references:

- https://cloud.google.com/build/pricing
- https://cloud.google.com/artifact-registry/pricing
- https://cloud.google.com/run/pricing

## Deliberately excluded

No Vertex AI, Cloud SQL, GKE, Compute Engine VM, Pub/Sub, Cloud Functions, VPC
connector, load balancer, multiple Firestore databases, or separate Firebase
project is planned for the MVP.

