# Gate C readiness and checklist classification

Status: local engineering complete; genuine Gate C evidence pending, 2026-08-11.

The checklist contained 148 unchecked bullets at the start of this goal. They
are classified below before implementation. A checklist item that describes a
real learner, a held-out image, a human review, or a cloud mutation remains
unchecked even when the local mechanism that records it is now implemented.
That distinction is intentional: synthetic rehearsal and fake-model tests are
not Gate A, B, or C evidence.

## Classification key

1. Required local engineering for Gate A, B, or C.
2. External or human evidence required for a gate decision.
3. Cloud, Gemini, or paid-operation gated. No such mutation is authorized by
   this goal.
4. Post-hackathon or explicitly deferred until the core loop is reliable.
5. Already implemented, obsolete, or too broadly worded; reconcile the
   checklist to the narrower remaining work instead of claiming a new feature.

## 1. Required local engineering

These items are the agent-owned critical path or its direct safety/evidence
support. Gate C implementation adds the version-pinned two-arm runner,
append-only attempts and interventions, safe checkpoint advancement, report
generation, API routes, browser flow, and focused tests. The original checklist
items below are the gate-facing requirements that this work supports.

- **L318** — avoid unsafe instructions and stop on safety uncertainty; the
  runner requires an explicit low-risk/safety attestation and preserves
  abstention instead of advancing.
- **L471** — link procedure mutation and probe-run evidence; Gate C additionally
  links exact procedure versions, learner sessions, attempts, and interventions.
- **L481** — the existing API integration is extended with Gate C concurrency and
  arm-state invariants.
- **L523–L524** — run and record the static-procedure baseline versus ByFeel
  transfer; the software path is local, while the real observations remain
  category 2 evidence.

## 2. External or human evidence

### Gate A

- **L69** — supply two separately performed Banana Panic demonstrations (or
  explicitly revise the same-procedure protocol).
- **L71** — human-review each transcript and proposed blocker.
- **L72** — obtain two genuine blocker → clarification → repair → fresh
  unblocked cycles.
- **L74** — complete the final human reliability review and record Gate A
  pass/fail.
- **L139–L142** — capture the teacher clarification, verify its provenance, run a
  fresh blinded probe, and confirm the reason for the transition.
- **L144** — repeat across at least three genuine demonstrations.
- **L146** — Gate A pass decision.

### Gate B

- **L211–L218** — capture, vary, de-identify, split, label, and freeze the real
  calibration/held-out image dataset.
- **L226–L227** — capture independent incorrect/overshot and held-out examples.
- **L237–L242** — run the intended Gemini path, compute held-out metrics, test
  poor-quality behavior, verify no false advance, reconcile usage/cost, and
  make the Gate B decision.
- **L215** — human-confirmation-only handling for unavailable senses and
  uncertain cues is already stated in the Gate B protocol; the remaining
  evidence is the human-labeled application of that rule.
- **L498** — bad-angle and human-confirmation path on real evidence.
- **L517–L520** — fixed candidate-domain benchmark, novice-probe rubric, blocker
  outcomes, and checkpoint accuracy/abstention measurements.

### Gate C

- **L246** — recruit and pseudonymize a fresh learner who did not see the
  demonstration.
- **L247–L253** — provide only the repaired learner artifact, guide step by step,
  introduce the agreed incorrect state, detect or safely abstain, deliver the
  teacher-derived intervention, confirm correction, and observe advancement
  only after correction.
- **L254–L257** — run the static baseline, compare arms, record provenance and
  outcome, and conduct the Gate C pass review. The local runner now records
  these facts but cannot manufacture them.
- **L529–L532** — select and freeze the evidence-backed domain/scenario and
  rehearse the narrative that shows the real transfer loop.
- **L537** — final human privacy and safety review.

### Human-dependent release claims

- **L418–L420** — consent, retention, deletion, and evidence-handling language
  must be approved for the actual participants/media.
- **L535** — prepare a backup recording and static artifacts from the real run.
- **L540–L541** — reconcile Devpost/submission claims to collected evidence and
  remove unvalidated capability claims.

## 3. Cloud, Gemini, or paid-operation gated

No cloud mutation or paid experiment is part of this goal. The following remain
approval-gated, even if a later deployment or evaluation would be useful:

- **L91–L92** — service-specific spend cap and production/cloud approver policy.
- **L237, L241** — intended Gemini held-out evaluation and cost reconciliation.
- **L381, L384, L392, L394–L410** — Firestore indexes, Storage lifecycle,
  mutation proposals/approvals, APIs, IAM/service account, Secret Manager,
  Artifact Registry, Cloud Build/image, Cloud Run configuration/deployment,
  safeguards, rollback, and ledger events.
- **L395–L399, L402–L407** — runtime identity, exact secret handling, image
  digest, and immutable deployment resources.
- **L427** — IAM least-privilege review before deployment.
- **L435–L441** — Cloud Run telemetry, alerts, billing recipients, spend review,
  infrastructure allowance, and hard-ceiling stop condition.
- **L454** — billing/token-accounting reconciliation where provider billing data
  is required.
- **L469** — Firestore emulator/live-adapter validation before cloud use.
- **L499–L503** — deployed health, permissions, secret injection, scale-to-zero,
  and rollback rehearsal.
- **L533, L536** — showing cloud resources and checking current spend before a
  submission demo.

## 4. Post-hackathon or explicitly deferred

These do not belong in the minimal local Gate C path and are retained as
backlog, security/release hardening, or future product scope:

- **L29, L184** — true event-triggered teacher capture; the current bounded
  offline sampling boundary is explicit and sufficient for local validation.
- **L270, L272** — schema migration and deletion/retention semantics beyond the
  current namespaced local/test persistence contract.
- **L283–L286** — broader candidate-gap generation/ranking/explanation beyond
  the existing reviewed-blocker path.
- **L290–L291** — contradiction detection and broad/destructive procedure
  changes.
- **L304** — bounded invalid-model-output retry.
- **L320** — learner/facilitator override; an override would need a separate
  audit and safety design and is not needed for Gate C success.
- **L334–L337** — CORS, authentication/authorization, general mutation
  idempotency, and generated client-type synchronization.
- **L388** — deletion/orphan policy for sensitive evidence.
- **L400–L401** — artifact cleanup and Cloud Build/local build strategy.
- **L416–L428** — automated secret scanning, generalized log redaction,
  consent/deletion workflows, EXIF stripping, prompt-injection threat model,
  generic rate limits, broader unsafe-task refusal rules, and a clean history/
  build-artifact secret audit.
- **L432, L435–L441** — production structured logs, dashboards, alerts, billing
  review, infrastructure allowance, and spend stop controls.
- **L459–L464** — invalid-response retry, prompt snapshots, prompt-injection
  cases, invented-completion-condition benchmark, and low-value-blocker
  benchmark.
- **L473** — full retention/deletion audit workflows.
- **L487–L491** — a framework component-test suite, automated accessibility and
  responsive checks, and camera permission matrix; the app remains plain
  HTML/JS and receives a local browser smoke test in this goal.
- **L510–L513** — type checker, frontend build/lint framework, vulnerability
  scan, and clean-checkout setup hardening.
- **L529–L533, L535–L541** — final release rehearsal, cloud proof, backup, budget
  check, privacy review, README reproduction, and submission materials after
  real evidence exists.
- **L545–L552** — multi-teacher merge, marketplace/library, generic RAG,
  quizzes/gamification/social, mobile, five-agent orchestration, unnecessary
  background infrastructure, and “AI clone of expert” framing.

## 5. Already implemented, obsolete, or not reconciled

These entries should not be silently treated as new work:

- **L215** — the unavailable-sense/human-confirmation rule is already present
  in the checkpoint contract and Gate B documentation; only real application
  evidence remains.
- **L386** — content type, extension/signature, and object-size validation are
  already implemented. Dimensions remain a separate residual requirement if
  real media needs them.
- **L424** — Pydantic domain validation, bounded repair validation, checkpoint
  safety validation, and provenance tests already treat model output as
  untrusted; the broad checklist wording needs narrowing.
- **L472** — evidence references already carry checksums, namespaces, and
  missing/mismatch validation in the local evidence store; retention is the
  separate deferred item.
- **L489** — the plain HTML/JS client already has loading, disabled, status,
  error, empty, and resume states; an automated component test is not implied
  by that fact.

## Remaining Gate C evidence after local implementation

The software can conduct and record both arms locally. A genuine Gate C result
still requires a fresh learner, a genuinely teacher-derived repaired procedure,
the same agreed incorrect state across arms, actual learner observations,
human-confirmed detection/abstention, a learner correction, and a facilitator
review of the comparison. Any separate Gemini usage must be explicitly approved
and recorded; the seeded rehearsal and fake-model tests remain synthetic and
excluded from a Gate C pass.
