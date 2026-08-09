# ByFeel project checklist

This is the canonical feature, test, cloud, evaluation, and release checklist.
Update it whenever work is completed or scope changes.

Legend:

- `[x]` complete and verified
- `[ ]` not complete
- Items marked **gate** block later phases
- Cloud checkboxes never constitute approval; `KEY_INSTRUCTIONS.md` still applies

## 0. Governance and workspace

- [x] Git repository initialized.
- [x] Python 3.12 managed by uv.
- [x] `pyproject.toml`, lockfile, `.python-version`, and virtual environment established.
- [x] Python, uv, Git, Node, and gcloud availability verified.
- [x] `.env` ignored and `.env.example` contains no secrets.
- [x] Python, Node/Vite, editor, OS, credential, run-artifact, and ledger ignore rules added.
- [x] Root `AGENTS.md` encodes cloud approval and budget policy.
- [x] `KEY_INSTRUCTIONS.md` records account boundaries and the INR 10k/15k limits.
- [x] Local `cloud-ledger/` organized by service and date.
- [x] Entire `cloud-ledger/` verified as Git-ignored.
- [x] Current GCP project and billing currency verified read-only.
- [x] Cloud architecture and cost plan documented.
- [x] Cloud Billing alert budget created and verified.
- [ ] Decide whether to add an eligible service-specific spend cap later.
- [ ] Define who may approve production/cloud changes besides the user, if anyone.

## 1. Decision Gate A — blinded procedure stress test

### Experiment harness

- [x] Typed teacher-demo schema.
- [x] Typed procedure and procedure-step schemas.
- [x] Typed knowledge-gap and probe-report schemas.
- [x] Typed repair result and run manifest.
- [x] Gemini structured-output client.
- [x] Strict learner-facing projection for the probe.
- [x] Raw teacher context excluded from probe prompt by construction.
- [x] Extraction → probe → clarification → repair → reprobe orchestration.
- [x] CLI entry point and ignored per-run artifacts.
- [x] Real-demonstration JSON template.
- [x] Gate A protocol and human-review criteria documented.

### Real validation — **gate**

- [ ] Select one real, safe, three-step physical task.
- [ ] Record or directly observe a real expert demonstration.
- [ ] Transcribe actions, narration, checks, and constraints without improving vague language.
- [ ] Run procedure extraction with `gemini-3.5-flash`.
- [ ] Run the blinded probe using only the learner artifact.
- [ ] Confirm the initial blocker is non-trivial and execution-relevant.
- [ ] Capture exactly one targeted teacher clarification.
- [ ] Confirm the repair contains only teacher-supplied information.
- [ ] Run a fresh blinded probe against the repaired artifact.
- [ ] Confirm blocked → unblocked for the correct reason.
- [ ] Record model, calls, tokens, and estimated cost in the local ledger.
- [ ] Repeat across at least three demonstrations.
- [ ] Record failures, false blockers, and cases where no blocker is found.
- [ ] **Gate A pass:** mechanism succeeds reliably enough to justify Gate B.

## 2. Decision Gate B — visual checkpoint

### Dataset and protocol

- [ ] Select one demo-critical visual checkpoint from a Gate A procedure.
- [ ] Define observable `not_ready`, `ready`, and `incorrect_or_overshot` states.
- [ ] Capture multiple real images for every state.
- [ ] Include modest lighting, angle, distance, and background variation.
- [ ] Separate calibration examples from held-out evaluation examples.
- [ ] Remove faces, personal information, and unnecessary background details.
- [ ] Define human-confirmation-only handling for touch, smell, taste, or uncertain cues.

### Evaluation — **gate**

- [ ] Implement typed checkpoint-classification output.
- [ ] Include confidence and `needs_human_confirmation` state.
- [ ] Prevent auto-advance below the agreed confidence threshold.
- [ ] Run all held-out images through the intended Gemini path.
- [ ] Compute per-class precision, recall, confusion matrix, and abstention rate.
- [ ] Test bad-angle and poor-light recovery behavior.
- [ ] Confirm no demo-critical false-positive advance.
- [ ] Record image calls/tokens/cost in the local ledger.
- [ ] **Gate B pass:** critical states remain reliably distinguishable.

## 3. Decision Gate C — real learner transfer

- [ ] Recruit a fresh learner who did not see the teacher demonstration.
- [ ] Provide only the repaired learner-facing procedure.
- [ ] Guide the learner step by step.
- [ ] Deliberately introduce one agreed incorrect state.
- [ ] Detect or safely abstain on the mismatch.
- [ ] Deliver guidance derived from the teacher clarification.
- [ ] Confirm the learner corrects the state.
- [ ] Advance only after the checkpoint is satisfied.
- [ ] Capture a baseline attempt using static instructions.
- [ ] Compare baseline and ByFeel outcomes.
- [ ] Record intervention provenance and learner outcome.
- [ ] **Gate C pass:** teacher-derived information visibly improves transfer.

## 4. Canonical domain models

- [x] Procedure, step, gap, probe, repair, and manifest models exist for Gate A.
- [ ] Add stable IDs and UTC timestamps to all persistent entities.
- [ ] Add checkpoint model with visual/temporal/verbal/measurable modality.
- [ ] Add positive and negative checkpoint examples.
- [ ] Add evidence-reference model with provenance and media metadata.
- [ ] Add append-only correction model with `supersedes` relationship.
- [ ] Add learner-session and learner-step-state models.
- [ ] Add intervention, abstention, and human-confirmation events.
- [ ] Add audit-event envelope with schema version.
- [ ] Define forward-compatible schema migration policy.
- [ ] Define canonical state invariants and validation errors.
- [ ] Define deletion/retention semantics for procedures and evidence.

## 5. Teaching Partner

- [ ] Accept teacher transcript and approved snapshots.
- [ ] Extract ordered learner-facing actions.
- [ ] Preserve uncertainty instead of inventing criteria.
- [ ] Generate candidate gaps from missing quantities, cues, prerequisites, and exceptions.
- [ ] Rank gaps by execution impact and confidence.
- [ ] Ask at most one high-value clarification at a time.
- [ ] Explain why the clarification is needed.
- [ ] Attach approved evidence to the relevant checkpoint.
- [ ] Mutate canonical procedure state only through validated operations.
- [ ] Preserve append-only correction history.
- [ ] Detect contradictions with prior teacher rules.
- [ ] Require teacher confirmation for destructive or broad procedure changes.

## 6. Blinded Novice Probe

- [x] Probe receives a learner-only projection in Gate A code.
- [x] Probe cannot mutate canonical state.
- [ ] Enforce permission boundary outside prompt text as an application interface.
- [ ] Version and hash the exact learner artifact sent to each probe.
- [ ] Report blocker type, severity, step, missing information, and assumptions.
- [ ] Prefer the highest-value execution blocker over stylistic criticism.
- [ ] Detect unusable exceptions and missing prerequisites.
- [ ] Distinguish blocker, warning, and optional improvement.
- [ ] Reject blockers that rely on hidden teacher context.
- [ ] Add bounded retry for invalid structured output.
- [ ] Add low-value blocker rejection/human review path.
- [ ] Store probe run provenance and before/after linkage.

## 7. Learner Coach

- [ ] Start a fresh learner session from an approved procedure version.
- [ ] Present one step and its completion conditions at a time.
- [ ] Request snapshots only at decision-relevant moments.
- [ ] Track current step, attempts, checkpoint state, and interventions.
- [ ] Decide `advance`, `block`, `retry_snapshot`, or `human_confirmation`.
- [ ] Explain interventions in learner-friendly language.
- [ ] Cite the teacher-derived checkpoint or correction used.
- [ ] Avoid claiming unavailable touch, smell, or taste sensing.
- [ ] Avoid unsafe instructions and stop on safety uncertainty.
- [ ] Persist learner progress and recovery history.
- [ ] Allow learner or facilitator override with an audit event.

## 8. Backend and API

- [ ] Establish FastAPI application factory.
- [ ] Add health, readiness, and version endpoints.
- [ ] Add structured error envelope and request IDs.
- [ ] Add teacher-session endpoints.
- [ ] Add procedure read/update endpoints with optimistic concurrency.
- [ ] Add probe-run and repair endpoints.
- [ ] Add evidence upload URL or server-upload endpoint.
- [ ] Add learner-session and checkpoint-evaluation endpoints.
- [ ] Add audit/event query endpoint for demo visibility.
- [ ] Add request validation limits and media size/type checks.
- [ ] Add CORS policy for the exact frontend origin.
- [ ] Add API authentication/authorization decision.
- [ ] Add idempotency for retried mutations.
- [ ] Generate OpenAPI schema and keep client types synchronized.

## 9. Frontend

### Foundation

- [ ] Initialize React, Vite, and TypeScript.
- [ ] Add Tailwind and a small documented design system.
- [ ] Add routing, API client, loading/error states, and accessible primitives.
- [ ] Define responsive desktop/tablet layout for the demo.

### Teacher experience

- [ ] Start/continue teacher session.
- [ ] Capture narration/transcript and event-driven snapshots.
- [ ] Review extracted procedure steps.
- [ ] Display ranked candidate gaps.
- [ ] Show blinded-probe status and blocker evidence.
- [ ] Capture one teacher clarification.
- [ ] Show exact before/after procedure diff.
- [ ] Approve the repaired learner artifact.

### Learner experience

- [ ] Start fresh learner session.
- [ ] Display current action and observable completion conditions.
- [ ] Capture checkpoint image.
- [ ] Show advance/block/retry/human-confirmation result.
- [ ] Display teacher-derived corrective guidance.
- [ ] Show progress without exposing hidden teacher context.

## 10. Persistence and evidence

- [x] Obtain direct approval for Firestore creation.
- [x] Create Firestore Standard Native `(default)` in the approved region.
- [x] Record creation event in ledger by date and Firestore service.
- [ ] Implement Firestore repositories behind interfaces.
- [ ] Implement local/in-memory repositories for tests.
- [x] Define initial document paths; finalize transaction boundaries during repository implementation.
- [ ] Add required Firestore indexes only after explicit approval.
- [x] Obtain direct approval for Cloud Storage bucket creation.
- [x] Create private regional Standard bucket with uniform access and public access prevention.
- [ ] Configure approved retention/lifecycle policy.
- [x] Record bucket event in ledger by date and Storage service.
- [ ] Validate content type, extension, dimensions, and object size.
- [ ] Store checksums and provenance for every evidence object.
- [ ] Ensure deleted procedures do not silently orphan sensitive evidence.

## 11. Cloud deployment

- [ ] Maintain an exact proposal and cost estimate before every mutation.
- [x] Cloud Billing alert budget exists and is verified.
- [ ] Obtain approval to enable each required API.
- [ ] Create dedicated runtime service account.
- [ ] Grant least-privilege Firestore, bucket, and exact-secret access.
- [ ] Obtain separate approval to store the Gemini key in Secret Manager.
- [ ] Create and record the Secret Manager secret/version.
- [ ] Create Artifact Registry repository in the approved region.
- [ ] Configure artifact cleanup to avoid stale-image storage.
- [ ] Decide Cloud Build versus approved local container build.
- [ ] Build, scan, and record the deployable image digest.
- [ ] Create Cloud Run service only after explicit approval.
- [ ] Configure request-based billing, min `0`, max `1`, 1 vCPU, 512 MiB initially.
- [ ] Configure exact service account and secret reference.
- [ ] Decide public versus authenticated invocation.
- [ ] Deploy one immutable revision and record its URL/digest.
- [ ] Verify scale-to-zero and maximum-instance safeguards.
- [ ] Document rollback to the previous revision.
- [ ] Record every cloud resource and deployment event in the local ledger.

## 12. Security, privacy, and safety

- [x] API key and raw run artifacts are ignored.
- [x] Gemini and GCP account boundaries documented.
- [ ] Add automated secret scanning to local checks/CI.
- [ ] Ensure logs redact authorization headers, keys, tokens, and raw secrets.
- [ ] Define image/transcript consent language.
- [ ] Define evidence retention and user deletion workflow.
- [ ] Strip EXIF/location metadata where appropriate.
- [x] Block public bucket access.
- [ ] Threat-model prompt injection through teacher text and images.
- [ ] Treat model output as untrusted and validate every mutation.
- [ ] Add rate, media-size, and request-duration limits.
- [ ] Define unsafe-task refusal and human-escalation rules.
- [ ] Review IAM with least privilege before deployment.
- [ ] Verify no secrets exist in Git history or build artifacts.

## 13. Observability and cost control

- [ ] Structured JSON logs with request/run/session IDs.
- [ ] Log model name, latency, token usage, and status without sensitive prompts.
- [ ] Record Gemini call counts and estimated cost per experiment.
- [ ] Record Cloud Run revision, image digest, and deployment time.
- [ ] Add error-rate, latency, and model-failure dashboards or saved queries.
- [ ] Add alerts for repeated model failures and Cloud Run instance saturation.
- [ ] Verify project budget email recipients.
- [ ] Review actual GCP and Gemini spend after every demo rehearsal.
- [ ] Keep infrastructure allowance below INR 1,000 unless re-approved.
- [ ] Stop work before the INR 15,000 hard ceiling could be crossed.

## 14. Automated test matrix

### Unit tests

- [x] Raw teacher context does not reach the probe prompt.
- [x] Fake blocked → repair → unblocked loop passes.
- [ ] Schema validation rejects duplicate step order/IDs and invalid confidence.
- [ ] Probe status/blocker invariants cover all edge cases.
- [ ] Repair selects the intended highest-severity blocker.
- [ ] Empty/unsafe clarification is rejected.
- [ ] Learner projection excludes every private field.
- [ ] Cost calculation and token accounting tests.

### Model contract and prompt tests

- [ ] Structured-output parsing against representative Gemini responses.
- [ ] Invalid JSON/partial response retry and terminal failure tests.
- [ ] Prompt snapshot tests for extraction, probe, repair, and checkpoint evaluation.
- [ ] Blindness sentinel tests across every probe entry point.
- [ ] Prompt-injection resistance cases.
- [ ] No invented completion-condition evaluation set.
- [ ] Low-value/false blocker benchmark.

### Repository and persistence tests

- [ ] In-memory repository CRUD and concurrency tests.
- [ ] Firestore emulator integration tests before live Firestore use.
- [ ] Correction history is append-only.
- [ ] Procedure mutation and probe run are linked atomically.
- [ ] Evidence references reject missing or mismatched objects.
- [ ] Retention and deletion workflows preserve audit requirements.

### API tests

- [ ] Health/readiness endpoint tests.
- [ ] Request validation, auth, CORS, and error-envelope tests.
- [ ] Teacher → probe → repair API integration test.
- [ ] Learner checkpoint and intervention API integration test.
- [ ] Idempotency and concurrent update tests.
- [ ] Media upload type/size/security tests.

### Frontend tests

- [ ] Component tests for procedure, blocker, diff, checkpoint, and intervention states.
- [ ] Accessibility checks for keyboard, labels, focus, contrast, and live status.
- [ ] API loading, timeout, retry, empty, and error-state tests.
- [ ] Responsive layout checks at demo device sizes.
- [ ] Camera permission denied/unavailable recovery.

### End-to-end and cloud tests

- [ ] Local unedited teacher → learner happy path.
- [ ] Deliberate learner-error recovery path.
- [ ] Bad camera angle and human-confirmation path.
- [ ] Deployed Cloud Run health and full smoke test.
- [ ] Service-account permissions allow required actions and deny unrelated ones.
- [ ] Secret is injected without appearing in environment/log output.
- [ ] Scale-to-zero and maximum-instance configuration verified.
- [ ] Rollback rehearsal.

### Quality gates

- [x] Ruff lint passes.
- [x] Ruff formatting check passes.
- [x] Current unit test suite passes.
- [ ] Type checker selected and passing.
- [ ] Frontend lint/typecheck/tests passing.
- [ ] Dependency and vulnerability scan passing.
- [ ] Reproducible clean checkout setup test.

## 15. Evaluation

- [ ] Define a fixed candidate-domain benchmark.
- [ ] Define novice-probe precision/utility rubric.
- [ ] Measure blockers accepted, rejected, and missed.
- [ ] Measure checkpoint accuracy and abstention.
- [ ] Measure correction persistence across fresh sessions.
- [ ] Run blindness test with planted private-context sentinel.
- [ ] Run static-procedure baseline versus ByFeel transfer.
- [ ] Record learner completion, correction, and intervention outcomes.
- [ ] Document negative results and kill/pivot evidence honestly.

## 16. Demo and release readiness

- [ ] Select final domain based on evidence, not convenience.
- [ ] Freeze procedure, checkpoint examples, and learner scenario.
- [ ] Rehearse four-minute narrative and call budget.
- [ ] Show expert demo, blocker, targeted question, diff, learner error, and recovery.
- [ ] Show architecture, cloud resources, and visible logs without exposing secrets.
- [ ] Run one reliable unedited end-to-end demo.
- [ ] Prepare backup recording and static artifacts.
- [ ] Verify demo project budget and current spend immediately beforehand.
- [ ] Final privacy/safety review.
- [ ] Final README reproduction test.
- [ ] Architecture diagram complete.
- [ ] Devpost description, claims, and limitations match actual evidence.
- [ ] No unvalidated capability claim in presentation or submission.

## 17. Explicitly deferred unless core gates pass

- [ ] Multi-teacher merge.
- [ ] Large knowledge library or marketplace.
- [ ] Generic RAG/vector architecture.
- [ ] Quizzes, gamification, or social layer.
- [ ] Full mobile application.
- [ ] Five-agent orchestration.
- [ ] Pub/Sub or background infrastructure without demonstrated need.
- [ ] Broad “AI clone of expert” framing.
