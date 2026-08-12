# ByFeel competition checklist

This is the canonical execution board for delivering a complete, defensible,
and competitive hackathon product. Each checkbox represents a demonstrable
outcome, not an implementation detail.

The historical 148-item Gate A/B/C classification remains in
[gate-c-readiness.md](gate-c-readiness.md). Completed mechanism and architecture
details remain in the linked design documents and automated tests.

Legend:

- `[x]` complete and locally verified
- `[ ]` required or deliberately selected work
- **P0** blocks deployment, eligibility, or a safe judge demo
- **P1** materially improves evidence or competitiveness
- **P2** is optional only after P0 and P1 are secure
- Cloud checkboxes never authorize a mutation. `KEY_INSTRUCTIONS.md` still
  requires exact, single-scope user approval.

## Snapshot — 2026-08-12

- Deadline: **2026-08-31 17:00 Pacific**, approximately
  **2026-09-01 05:30 IST**. Internal target: **2026-08-30 IST**.
- Practical completion: **60–65% competition-ready**.
- Core mechanism: **85–90%**.
- Deployment and reliability: **40–45%**.
- Real Gate A/B/C evidence: **incomplete**.
- Demo and submission package: **30–35%**.
- Primary category: **Collaborative Partner**.

## Winning definition of done

A judge can open a stable hosted URL and see a real teacher-to-learner transfer
loop. The backend visibly uses Gemini 3.5+, Google ADK, and Google Cloud. Teacher
truth, blinded probing, learner guidance, and evidence review remain separated.
High-resolution source video never reaches Gemini. Missing, uncertain,
synthetic, or unreviewed evidence never becomes success. The four-minute demo,
README, architecture, tests, costs, limitations, and Devpost claims all match
the deployed product and collected evidence.

## Completed foundation

- [x] FastAPI application with a responsive plain HTML/CSS/JS interface; no
  React rebuild.
- [x] Teacher media review, factual approval, procedure extraction, blinded
  probe, reviewed repair, procedure diff, learner coaching, and evidence view.
- [x] Google ADK role/tool boundaries and Gemini 3.5 Lite / 3.6 routing.
- [x] In-memory and Firestore repositories plus private Storage evidence adapter.
- [x] Learner sessions, checkpoint evaluation, provenance-backed intervention,
  safe abstention, and append-only corrections.
- [x] Formal two-arm Gate C runner, structured report, facilitator browser flow,
  unsafe-advance prevention, and synthetic exclusion.
- [x] Local low-bandwidth proxy/frame extraction and a 5 MiB model-media cap.
- [x] Gate C implementation passed the full local test suite, Ruff checks, and
  browser smoke test.

## P0 — hosted media boundary

- [ ] Downsample video on the browser/device into a bounded 6–18 frame,
  640–768 px JPEG/WebP package before hosted upload; apply the same boundary to
  live camera.
- [ ] Add blur, darkness, occlusion, and missing-checkpoint feedback before a
  media package can be accepted.
- [ ] Preserve timestamps, dimensions, hashes, extraction-policy version, and
  pseudonymous provenance while retaining no high-resolution hosted source.
- [ ] Reject raw/high-resolution video and oversized model payloads on the
  hosted backend, with a test proving a 200+ MB source becomes only a few-MB
  derived package before network/model use.

## P0 — durable and failure-safe product

- [ ] Persist only approved low-resolution evidence in private Storage and
  replace durable references to local `runs/...` paths.
- [ ] Prove procedures, learner sessions, interventions, and Gate C evidence
  survive a Cloud Run restart through Firestore-backed repositories.
- [ ] Add idempotency, concurrency/version protection, and atomic evidence
  linkage for model-backed and evidence-producing mutations.
- [ ] Add bounded invalid-output retry and request timeout handling that ends in
  abstention, never invented success or unsafe background mutation.
- [ ] Pass focused restart, duplicate-request, concurrent-update, timeout,
  missing-object, and recovery tests; any facilitator override must be an
  explicit append-only audit event.

## P0 — security, privacy, and access

- [ ] Choose and implement judge access, exact-origin CORS, request/media limits,
  and rate limiting.
- [ ] Add participant consent plus media/evidence retention and deletion rules;
  strip unnecessary EXIF/location metadata.
- [ ] Redact secrets, authorization, personal data, prompts, and raw media from
  logs and error responses.
- [ ] Threat-model teacher-input prompt injection and unsafe tasks; verify model
  output cannot bypass application validation, provenance, role boundaries, or
  required human escalation.
- [ ] Pass secret, dependency, Git-history, and container-artifact scans with no
  `.env`, credential, personal data, raw media, ignored run, or ledger leakage.

## P0 — deployment and operations

- [ ] Add and locally verify the production container: Dockerfile,
  `.dockerignore`, `$PORT`, health/readiness, graceful shutdown, non-root where
  practical, and a complete clean-checkout browser smoke test.
- [ ] Produce the exact cloud proposal covering project/account, APIs,
  resources, names, region, IAM, commands, INR cost, recurring risk, budget
  impact, and rollback; obtain separate approval for every mutation.
- [ ] Configure only approved runtime identity, build/artifact path, secret
  reference, Firestore, Storage, and Cloud Run resources with least privilege.
- [ ] Deploy an immutable revision using request-based billing, min instances
  `0`, tightly bounded maximum instances, and conservative resources/concurrency.
- [ ] Verify hosted health and full browser flow, durable restart recovery,
  least-privilege allow/deny behavior, secret non-disclosure, scale-to-zero,
  maximum-instance protection, and rollback.
- [ ] Record every resource, approval, image digest, revision URL, cost estimate,
  and cleanup plan in the ignored cloud ledger; add redacted structured logs for
  request/session/run IDs, latency, failures, abstention, and revision identity.
- [ ] Reconcile actual Cloud and Gemini spend after deployment and rehearsals;
  remain below the INR 10,000 target and stop before INR 15,000.

## P1 — honest Gate A, B, and C evidence

### Gate A — knowledge repair

- [ ] Freeze one safe towel-fold target and intended final shape; confirm which
  supplied recordings are genuinely independent.
- [ ] Collect or observe enough independent demonstrations for the final stated
  protocol, with human-approved factual transcripts and blocker reviews.
- [ ] Record genuine blocker → targeted teacher clarification → provenance-
  bounded repair → fresh blinded reprobe cycles, while retaining false blockers
  and naturally unblocked runs without forcing repair.
- [ ] Human-review the evidence and record Gate A passed, failed, or
  inconclusive; duplicates and harness runs cannot establish a pass.

### Gate B — checkpoint reliability

- [x] Define ready/not-ready/incorrect states, safe abstention, a deterministic
  metrics runner, and a low-bandwidth towel-folding pilot labelled non-gating.
- [ ] Capture and human-label independent ready, not-ready, incorrect, and
  poor-view examples with modest lighting/angle variation.
- [ ] Freeze calibration references separately from held-out data, run the
  separately approved intended-model evaluation, and record calls/tokens/cost.
- [ ] Report confusion matrix, per-class precision/recall, abstention, poor-view
  recovery, and false advances; require no demo-critical false advance before a
  human Gate B decision.

### Gate C — real learner transfer

- [x] Provide comparable static and ByFeel arms, exact version pinning,
  append-only evidence, safe advancement, and JSON/browser comparison.
- [ ] Recruit and pseudonymize a fresh learner who did not see the demonstration;
  predeclare the same incorrect state and checkpoint for both arms.
- [ ] Record baseline detection/abstention/miss, attempts, timing, and outcome
  without exposing repaired guidance.
- [ ] Record ByFeel detection/abstention/miss, exact teacher-derived intervention
  provenance, learner correction, advancement timing, and outcome; retain unsafe
  or incomplete runs as not evaluable.
- [ ] Obtain facilitator freshness, provenance, safety, privacy, and completeness
  attestations; review the comparison and record passed, failed, or inconclusive.
  Seeded and fake-model runs remain excluded.

## P1 — competitive autonomous review loop

Build one **Procedure Steward** using the existing roles and scoped tools. Do
not add agents merely to increase the agent count.

- [ ] Trigger a bounded review after an approved procedure mutation or completed
  learner session; make triggers idempotent and visible.
- [ ] Detect contradictions against approved teacher rules and re-run a fresh
  blinded sufficiency check, with exact provenance and “why this is needed.”
- [ ] Self-audit checkpoint discriminability and request better references when
  ready/not-ready evidence is too similar, poor quality, or unsupported.
- [ ] Aggregate repeated pseudonymous learner failures by procedure version,
  step, and checkpoint and create a teacher-facing repair proposal.
- [ ] Never auto-publish new facts: preserve approve/reject decisions,
  supersession, evidence, abstention, and no-auto-publish invariants in tests and
  one concise judge-facing review screen.

## P1 — judge demo and submission

- [ ] Create a reliable 60–90 second judge path while retaining the full
  teacher, learner, Gate C, and evidence views.
- [ ] Freeze the final towel procedure, checkpoints, incorrect state, model
  versions, real evidence, and demo data.
- [ ] Demonstrate teacher example → missing knowledge → targeted question →
  procedure diff → learner error → provenance-backed correction → safe advance,
  plus the bounded Procedure Steward review.
- [ ] Rehearse the unedited flow, call budget, timeouts, camera denial, poor
  image, model failure, refresh/recovery, and backup path; visibly prove the
  Google Cloud-hosted backend.
- [ ] Record a public English or English-subtitled video no longer than four
  minutes and prepare backup recording/static evidence.
- [ ] Finalize README, hosted access, architecture, test commands, Google
  services/models, privacy, costs, limitations, repository visibility, and
  Devpost claims from a clean checkout.
- [ ] Pass final test/lint/format, security, privacy, accessibility, responsive
  browser, cloud smoke, cost, secret, and evidence audits; submit by the internal
  target and preserve the final evidence manifest.

## P2 — optional only after P0/P1

- Publish one eligible build article/video and one eligible social post for the
  available competition bonuses.
- Add another Google AI model only if it has a distinct measured role and does
  not weaken reliability, cost control, or the demo.
- Improve event-triggered capture beyond the bounded browser sampler.

## Explicitly deferred

- Multi-teacher merging, large libraries, marketplaces, generic RAG, or vector
  databases.
- Quizzes, gamification, social/community features, and a full mobile app.
- Five-agent orchestration, agent theatre, or “AI clone of an expert” framing.
- Pub/Sub, schedulers, or always-running infrastructure without a proven need.
- Autonomous publication of procedural facts without teacher approval.

## Current user and approval dependencies

- [ ] Choose the official towel target: narrow rectangle or triangle.
- [ ] Facilitate remaining independent teacher/learner observations and final
  human gate reviews.
- [ ] Approve the exact Gemini call plan before paid experiments and each exact
  cloud mutation after reviewing resource, region, IAM, cost, and rollback.
- [ ] Choose deployed judge access and provide Devpost/video-publishing access
  when submission work begins.
