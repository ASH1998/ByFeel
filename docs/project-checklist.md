# ByFeel project checklist

This is the canonical feature, test, cloud, evaluation, and release checklist.
Update it whenever work is completed or scope changes.

Legend:

- `[x]` complete and verified
- `[ ]` not complete
- Items marked **gate** block later phases
- Cloud checkboxes never constitute approval; `KEY_INSTRUCTIONS.md` still applies

## Current snapshot — 2026-08-10

### Local product loop

- [x] Ingest bounded silent or voiced teacher video.
- [x] Extract duration-aware visual frames and conditional audio.
- [x] Produce a teacher-only factual media draft.
- [x] Require human transcript approval before canonical procedure extraction.
- [x] Keep raw media and teacher-only context outside the blinded probe.
- [x] Extract a learner-facing procedure with application-owned lifecycle state.
- [x] Run a fresh learner-only blinded probe.
- [x] Separate execution blockers from optional precision improvements.
- [x] Require immutable human blocker review before clarification or repair.
- [x] Prevent false blockers from entering clarification, repair, or reprobe.
- [x] Preserve calls and token usage in ignored run artifacts and the ledger.
- [x] Add bounded teacher video upload and synchronized sampled-frame review to the browser.
- [ ] Add true event-triggered capture instead of bounded offline sampling.

### Judge-ready build checkpoints

- [x] Audit the existing implementation, tests, ignored run artifacts, and cloud ledger.
- [x] Document the proposed UI, API, ADK, isolation, persistence, and test architecture.
- [x] Decide to extend the existing FastAPI browser application instead of adding React.
- [x] Identify the browser/API blocker-review bypass as a required integrity fix.
- [x] Verify the current official hackathon rules from the supplied Devpost rules page.
- [x] Distinguish mandatory requirements, bonuses, judging, deliverables, deployment, and eligibility.
- [x] Record that final video proof requires a cloud-hosted backend beyond this goal's deployment boundary.
- [x] Begin ADK implementation with the rules checkpoint resolved.

### Google ADK foundation

- [x] Pin Google ADK 2.x through uv and the project lockfile.
- [x] Route production blinded probes through Google ADK without a live wiring call.
- [x] Create a new ADK agent, runner, user, and in-memory session for every probe/reprobe.
- [x] Restrict the probe to a frozen `LearnerProcedure` and one read-only application tool.
- [x] Add explicit Teaching Partner, Blinded Probe, and Learner Coach tool policies.
- [x] Persist safe ADK role/run/session/tool/token metadata without prompts or tool results.
- [x] Test fresh sessions, teacher-context sentinel exclusion, forbidden-tool calls, and canonical-input rejection.
- [x] Wrap approved teacher extraction and reviewed repair as Teaching Partner ADK operations.
- [x] Wrap learner checkpoint orchestration as a Learner Coach ADK operation.

### Evidence status

- Gate A: **incomplete; not passed or failed**.
- Same-procedure demonstrations completed: **1 of 3** (`Banana Panic`).
- Genuine blockers correctly repaired: **0 of required 2**.
- Demonstration 1 result: correctly `UNBLOCKED` after false-blocker calibration;
  no repair opportunity.
- Separate wood-selection use case: voiced ingest, human approval, extraction,
  and correctly unblocked probe complete; excluded from the same-procedure count.
- Tracked Gemini experiments: **12 of 18 calls**; actual later billed cost is
  unknown and is not estimated.
- Verification: **42 automated tests pass**; Ruff lint and formatting pass.

### Next human-dependent work

- [ ] Supply two separately performed demonstrations of the Banana Panic task,
  or explicitly revise the same-procedure Gate A protocol.
- [ ] Human-review each transcript and every proposed blocker.
- [ ] Obtain two genuine blocker → clarification → bounded repair → fresh
  unblocked cycles for Gate A to remain passable.
- [ ] Complete final human reliability review and record Gate A pass/fail.

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
- [x] Resumable human checkpoint without repeating extraction or initial probe.
- [x] Per-call model and token usage persisted without prompts or credentials.
- [x] Real-demonstration JSON template.
- [x] Gate A protocol and human-review criteria documented.
- [x] Voiced-video, silent-video, audio-only, and still-image capture policy documented.
- [x] Apply the original closed loop as a standing implementation-alignment filter.
- [x] Probe local video and extract representative frames plus conditional audio.
- [x] Produce a teacher-only media draft with one Lite-model call.
- [x] Require human transcript approval before emitting canonical `TeacherDemo`.
- [x] Dry-run the real silent source through local media extraction without a model call.
- [x] Add explicit non-blocking improvements to the probe contract.
- [x] Add immutable genuine/false-blocker human review artifacts.
- [x] Make procedure status and timestamps application-owned after extraction.

### Real validation — **gate**

Current status: **active but waiting for human demonstrations; incomplete**.
Demonstration 1 was a valid negative result. Gate A has neither passed nor
failed, and two separately performed demonstrations of the same task remain.

- [x] Select one real, safe, 3–5 step physical task.
- [x] Select `Banana Panic` branded-paint mixing as the candidate task.
- [x] Confirm acrylic paint with a simple protective-glove setup.
- [x] Verify, locally inspect, and sample the ignored silent source-video file.
- [x] Save the human-approved factual transcript for candidate demonstration 1.
- [x] Exclude unobserved ratio, pigment chemistry, angle, and repeatability claims.
- [x] Resolve demonstration 1 material safety before any model experiment.
- [x] Record or directly observe real expert demonstration 1.
- [x] Human-verify demonstration 1 actions, silence, checks, and constraints without improving vague language.
- [x] Run procedure extraction with `gemini-3.5-flash-lite` for demonstration 1.
- [x] Run the blinded probe using only the learner artifact for demonstration 1.
- [x] Human-assess the proposed blocker and reject it when it is not execution-relevant.
- [ ] Capture exactly one targeted teacher clarification.
- [ ] Confirm the repair contains only teacher-supplied information.
- [ ] Run a fresh blinded probe against the repaired artifact.
- [ ] Confirm blocked → unblocked for the correct reason.
- [x] Record model, calls, tokens, and actual billed cost when available.
- [ ] Repeat across at least three demonstrations.
- [x] Record failures, false blockers, and cases where no blocker is found.
- [ ] **Gate A pass:** mechanism succeeds reliably enough to justify Gate B.

#### Demonstration 1 — `Banana Panic` acrylic mixing

- [x] Human-confirm the silent visual transcript and acrylic/glove safety boundary.
- [x] Extract the three-step learner procedure with `gemini-3.5-flash-lite`.
- [x] Run a `gemini-3.6-flash` probe using only the learner artifact.
- [x] Preserve the blindness boundary in saved run `27ec5619ec7c`.
- [x] Record 2 calls and 2,757 tokens; actual billed cost remains unreconciled.
- [x] Human-reject the missing-quantity complaint as a false blocker.
- [x] Record that exact ratios are a useful precision improvement, not required for execution.
- [x] End the run without asking the proposed clarification or forcing a repair.
- [x] Record the run as a non-success with no invented criteria or residual repair claims.
- [x] Run the approved media-derived artifact through extraction and a fresh blinded probe.
- [x] Preserve the blindness boundary in saved run `9058f5b2938c`.
- [x] Human-reject the repeated exact-quantity complaint as a false blocker.
- [x] Close the run through immutable blocker review without clarification or repair.
- [x] Separate non-blocking improvements from execution blockers in the probe schema.
- [x] Require a genuine human blocker review before clarification, repair, or reprobe.
- [x] Re-run the calibrated probe and classify missing ratios as non-blocking.
- [x] Record the unblocked result honestly as no genuine blocker/no repair opportunity.
- [x] Force newly extracted procedure status and timestamps to application-owned values.

#### Teacher-media ingestion validation

- [x] Send exactly nine approved sampled frames to `gemini-3.5-flash-lite` with no audio.
- [x] Preserve the teacher-silence boundary in the generated draft.
- [x] Record 1 call and 11,116 tokens; actual billed cost remains unreconciled.
- [x] Human-review the draft and identify missed white-base and maroon-addition events.
- [x] Replace summary-first analysis with a frame-complete two-pass observation contract.
- [x] Reject model output that omits or reorders a supplied frame observation.
- [x] Rerun the approved source with the stricter observer after fresh call approval.
- [x] Recover the white transfer and preserve the unexplained transition as uncertainty.
- [x] Record the residual lavender/maroon miss as a sampling limitation, not a model fact.
- [x] Add duration-aware bounded sampling for rapid offline demonstrations.
- [x] Validate the strict observer with 18 frames from the genuine silent source.
- [x] Capture white, lavender, maroon, mixing, and final-swatch events without invented speech.
- [x] Record the 18-frame call and 23,351 tokens; actual billed cost remains unreconciled.
- [ ] Add true event-triggered capture in the teacher browser experience.
- [x] Obtain teacher approval or correction of the factual transcript.
- [x] Emit `approved-demo.json`; do not pass the unapproved media draft downstream.

### Additional use-case validation — beginner wood selection

- [x] Classify as a separate decision-guide use case, not Banana Panic demonstration 2.
- [x] Probe 35.97-second vertical video and confirm its audio stream locally.
- [x] Extract 18 representative frames, a labeled contact sheet, and WAV locally.
- [x] Obtain a verbatim transcript through consented spoken-media handling.
- [x] Merge spoken guidance with 18 visible wood/carving observations for human review.
- [x] Record 1 call and 23,857 tokens; leave actual monetary cost unknown.
- [x] Require voiced decision drafts to preserve comparisons, recommendations, and counterexamples.
- [x] Human-approve or correct the full spoken factual record.
- [x] Emit a canonical wood-selection `TeacherDemo` without raw-media provenance.
- [x] Validate wood selection as an executable one-step decision guide with an unblocked probe.
- [x] Exclude it from the original Gate A count because it is not the same 3–5-step procedure.
- [x] Record 2 calls and 1,847 tokens; leave actual monetary cost unknown.

## 2. Decision Gate B — visual checkpoint

Current status: local preparation only; Gate A evidence remains incomplete.

### Dataset and protocol

- [x] Select uniform mixed paint before the final swatch as the candidate checkpoint.
- [x] Define observable `not_ready`, `ready`, and `incorrect_or_overshot` states.
- [ ] Capture multiple real images for every state.
- [ ] Include modest lighting, angle, distance, and background variation.
- [ ] Separate calibration examples from held-out evaluation examples.
- [ ] Remove faces, personal information, and unnecessary background details.
- [ ] Define human-confirmation-only handling for touch, smell, taste, or uncertain cues.
- [x] Define retry for poor image quality and human confirmation for uncertain visual match.
- [ ] Capture and human-label the real image dataset.
- [ ] Freeze teacher references and calibration/held-out manifests.
- [x] Inspect source-video metadata locally and preserve its SHA-256 provenance.
- [x] Extract an 18-frame 1-fps sequence and labeled early/middle/late contact sheet.
- [x] Extract and inspect the audio stream without running unnecessary ASR.
- [x] Record teacher speech as absent while preserving non-speech audio separately.
- [x] Identify candidate `not_ready` and `ready` calibration frames.
- [x] Human-approve four `not_ready` and three `ready` candidate frame labels.
- [x] Freeze three initial ready references in a calibration-only manifest.
- [ ] Capture independent `incorrect_or_overshot` examples; none exist in this clip.
- [ ] Capture independent held-out examples; sequential frames from one clip do not qualify.

### Evaluation — **gate**

- [x] Implement typed checkpoint-classification output.
- [x] Include confidence and `needs_human_confirmation` state.
- [x] Prevent auto-advance below the agreed confidence threshold.
- [x] Add an explicit predicted visual-state label to checkpoint evaluation.
- [x] Compare the learner image with up to three actual teacher reference images.
- [x] Add a local Gate B metrics runner with deterministic confusion, precision, recall, abstention, and false-advance calculations.
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
- [x] Add stable IDs and UTC timestamps to all persistent entities.
- [x] Add checkpoint model with visual/temporal/verbal/measurable modality.
- [x] Add positive and negative checkpoint examples.
- [x] Add evidence-reference model with provenance and media metadata.
- [x] Add append-only correction model with `supersedes` relationship.
- [x] Add learner-session and learner-step-state models.
- [x] Add intervention, abstention, and human-confirmation events.
- [x] Add application-safe audit-event and ADK run envelopes.
- [ ] Define forward-compatible schema migration policy.
- [x] Define canonical state invariants and validation errors.
- [ ] Define deletion/retention semantics for procedures and evidence.

## 5. Teaching Partner

- [x] Accept teacher transcript and approved snapshots.
- [x] Ingest bounded silent, spoken, or uncertain teacher video locally.
- [x] Produce timestamped visual and verbatim-speech event drafts.
- [x] Reject invented teacher speech for human-declared silent video.
- [x] Require human draft approval before learner-procedure extraction.
- [x] Extract ordered learner-facing actions.
- [x] Preserve uncertainty instead of inventing criteria.
- [ ] Generate candidate gaps from missing quantities, cues, prerequisites, and exceptions.
- [ ] Rank gaps by execution impact and confidence.
- [x] Ask at most one high-value clarification at a time.
- [ ] Explain why the clarification is needed.
- [x] Attach approved evidence to the relevant checkpoint.
- [x] Mutate canonical procedure state only through validated operations.
- [x] Preserve append-only correction history.
- [ ] Detect contradictions with prior teacher rules.
- [ ] Require teacher confirmation for destructive or broad procedure changes.

## 6. Blinded Novice Probe

- [x] Probe receives a learner-only projection in Gate A code.
- [x] Probe cannot mutate canonical state.
- [x] Enforce permission boundary outside prompt text as an application interface.
- [x] Version and hash the exact learner artifact sent to each probe.
- [x] Report blocker type, severity, step, missing information, and assumptions.
- [x] Prefer the highest-value execution blocker over stylistic criticism.
- [x] Detect unusable exceptions and missing prerequisites.
- [x] Distinguish execution blockers from non-blocking optional improvements.
- [x] Reject blockers that rely on hidden teacher context.
- [ ] Add bounded retry for invalid structured output.
- [x] Add low-value blocker rejection/human review path across CLI, service, API, and browser.
- [x] Store probe run provenance and before/after linkage.

## 7. Learner Coach

- [x] Start a fresh learner session from an approved procedure version.
- [x] Present one step and its completion conditions at a time.
- [x] Request snapshots only at decision-relevant moments.
- [x] Track current step, attempts, checkpoint state, and interventions.
- [x] Decide `advance`, `block`, `retry_snapshot`, or `human_confirmation`.
- [x] Explain interventions in learner-friendly language.
- [x] Cite the teacher-derived checkpoint or correction used.
- [x] Avoid claiming unavailable touch, smell, or taste sensing.
- [ ] Avoid unsafe instructions and stop on safety uncertainty.
- [x] Persist learner progress and recovery history.
- [ ] Allow learner or facilitator override with an audit event.

## 8. Backend and API

- [x] Establish FastAPI application factory.
- [x] Add health, readiness, and version endpoints.
- [x] Add structured error envelope and request IDs.
- [x] Add teacher-session endpoints.
- [x] Add procedure read/update endpoints with optimistic concurrency.
- [x] Add probe-run and repair endpoints.
- [x] Add evidence upload URL or server-upload endpoint.
- [x] Add learner-session and checkpoint-evaluation endpoints.
- [x] Add read-only audit/evidence query endpoint for demo visibility.
- [x] Add request validation limits and media size/type checks.
- [ ] Add CORS policy for the exact frontend origin.
- [ ] Add API authentication/authorization decision.
- [ ] Add idempotency for retried mutations.
- [ ] Generate OpenAPI schema and keep client types synchronized.

## 9. Frontend

### Foundation

- [x] Deliberately extend the FastAPI HTML/CSS/JS client instead of adding React/Vite.
- [x] Add a cohesive responsive visual system, role navigation, status regions, and focus styles.
- [x] Add shared API/error handling and loading/disabled operation states.
- [x] Define responsive desktop/tablet/mobile layout for the demo.

### Teacher experience

- [x] Start/continue teacher session.
- [x] Accept teacher-entered narration/transcript and event-driven snapshots.
- [x] Ingest local teacher video and route voiced versus silent demonstrations.
- [x] Produce human-reviewable, time-linked speech and visual event tracks.
- [x] Require factual-record approval before procedure extraction.
- [x] Review extracted procedure steps.
- [x] Display blocker severity and optional improvements from the blind probe.
- [x] Show blinded-probe status and blocker evidence.
- [x] Require immutable genuine/false-blocker review before enabling clarification.
- [x] Capture one teacher clarification.
- [x] Show exact before/after procedure diff.
- [x] Approve the exact tested learner artifact before learner sessions.

### Learner experience

- [x] Start fresh learner session.
- [x] Display current action and observable completion conditions.
- [x] Capture checkpoint image.
- [x] Show advance/block/retry/human-confirmation result.
- [x] Display teacher-derived corrective guidance.
- [x] Show progress without exposing hidden teacher context.
- [x] Resume an interrupted learner session from its saved ID.

## 10. Persistence and evidence

- [x] Obtain direct approval for Firestore creation.
- [x] Create Firestore Standard Native `(default)` in the approved region.
- [x] Record creation event in ledger by date and Firestore service.
- [x] Implement Firestore repositories behind interfaces.
- [x] Implement local/in-memory repositories for tests.
- [x] Define initial document paths; finalize transaction boundaries during repository implementation.
- [ ] Add required Firestore indexes only after explicit approval.
- [x] Obtain direct approval for Cloud Storage bucket creation.
- [x] Create private regional Standard bucket with uniform access and public access prevention.
- [ ] Configure approved retention/lifecycle policy.
- [x] Record bucket event in ledger by date and Storage service.
- [ ] Validate content type, extension, dimensions, and object size.
- [x] Store checksums and provenance for every evidence object.
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
- [ ] Define raw audio/video consent, retention, and deletion language.
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
- [x] Record model name, token usage when available, role, tool status, and run/session IDs without prompts.
- [x] Record Gemini call counts and tokens per experiment; reconcile actual cost when available.
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
- [x] Schema validation rejects duplicate step order/IDs and invalid confidence.
- [x] Probe status/blocker invariants cover all edge cases.
- [x] Repair selects the intended highest-severity blocker.
- [x] Empty/unsafe clarification is rejected.
- [x] Learner projection excludes every private field.
- [ ] Actual-billing reconciliation and token-accounting tests.

### Model contract and prompt tests

- [x] Structured-output parsing against representative Gemini responses.
- [ ] Invalid JSON/partial response retry and terminal failure tests.
- [ ] Prompt snapshot tests for extraction, probe, repair, and checkpoint evaluation.
- [x] Blindness sentinel tests across direct and ADK probe entry points.
- [ ] Prompt-injection resistance cases.
- [ ] No invented completion-condition evaluation set.
- [ ] Low-value/false blocker benchmark.

### Repository and persistence tests

- [x] In-memory repository CRUD and concurrency tests.
- [ ] Firestore emulator integration tests before live Firestore use.
- [x] Correction history is append-only.
- [ ] Procedure mutation and probe run are linked atomically.
- [ ] Evidence references reject missing or mismatched objects.
- [ ] Retention and deletion workflows preserve audit requirements.

### API tests

- [x] Health/readiness/version endpoint tests.
- [x] Request validation and structured error-envelope tests.
- [x] Teacher → probe → repair API integration test.
- [x] Learner checkpoint and intervention API integration test.
- [ ] Idempotency and concurrent update tests.
- [x] Media upload type/size/security tests.
- [x] Factual-approval, resume, learner-release, and judge-evidence API tests.

### Frontend tests

- [ ] Component tests for procedure, blocker, diff, checkpoint, and intervention states.
- [ ] Accessibility checks for keyboard, labels, focus, contrast, and live status.
- [ ] API loading, timeout, retry, empty, and error-state tests.
- [ ] Responsive layout checks at demo device sizes.
- [ ] Camera permission denied/unavailable recovery.

### End-to-end and cloud tests

- [x] Local unedited teacher → learner happy path.
- [x] Deliberate learner-error recovery path.
- [x] Seeded zero-model-call browser rehearsal and evidence-view smoke test.
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
- [x] Measure correction persistence across fresh sessions.
- [x] Run blindness test with planted private-context sentinel.
- [ ] Run static-procedure baseline versus ByFeel transfer.
- [ ] Record learner completion, correction, and intervention outcomes.
- [x] Document negative results and kill/pivot evidence honestly.

## 16. Demo and release readiness

- [ ] Select final domain based on evidence, not convenience.
- [ ] Freeze procedure, checkpoint examples, and learner scenario.
- [ ] Rehearse four-minute narrative and call budget.
- [ ] Show expert demo, blocker, targeted question, diff, learner error, and recovery.
- [ ] Show architecture, cloud resources, and visible logs without exposing secrets.
- [x] Run one reliable unedited end-to-end demo.
- [ ] Prepare backup recording and static artifacts.
- [ ] Verify demo project budget and current spend immediately beforehand.
- [ ] Final privacy/safety review.
- [ ] Final README reproduction test.
- [x] Architecture diagram complete.
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
