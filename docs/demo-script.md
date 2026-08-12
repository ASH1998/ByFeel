# ByFeel four-minute judge demo

This script is a product rehearsal, not proof that Gate A passed. Use the
seeded path when reliability matters; it makes zero model calls and is visibly
excluded from experimental evidence. Use a pre-approved real teacher video only
when the call budget and factual review are ready.

## 0:00–0:35 — the problem and boundary

Open Teacher mode. Say: “Experts demonstrate with cues they do not think to
name. ByFeel preserves the demonstration as facts, asks a truly blinded novice
what is missing, and repairs only from one teacher answer.” Point out the role
rail and the fresh-session boundary copy.

## 0:35–1:25 — teacher facts before instructions

Show silent/spoken selection, bounded upload, sampled timestamps, and the
teacher-only factual draft. Emphasize that vague language is not improved by the
model. Approve the exact factual record, then extract. For a no-call rehearsal,
click **Load seeded rehearsal · 0 model calls** and state that it is a fixture.

## 1:25–2:25 — blind probe and bounded repair

In Blind Probe mode, show the exact JSON projection and the explicit exclusion
list. Explain that a new ADK agent, runner, user, and session are created for
each probe. Show blocker versus optional improvement handling, immutable human
review, the one saved question, the verbatim answer, exact before/after diff,
and the fresh reprobe. Never imply every demonstration must produce a blocker.

## 2:25–3:15 — Gate C arms and learner recovery

Open **Gate C transfer** and show that the experiment pins two exact versions.
Run the static-instructions baseline first and submit the deliberate incorrect
state. Its safe abstention or miss remains in the report. Start the ByFeel arm
with a fresh session, submit the same incorrect state, show the approved
teacher-derived intervention and provenance, then submit the learner's
correction. The runner permits advancement only after that correction. For the
zero-call rehearsal, the baseline is synthetic and the ByFeel arm completes
deterministically; say explicitly that it is excluded from a real Gate C pass.

## 3:15–4:00 — evidence and honest limits

Open Evidence mode and the Gate C JSON report. Show immutable versions, linked
probes, learner attempts, intervention provenance, human approvals, safe
role/model/tool/token records, and the blindness exclusions. State:
“Gate A is incomplete. The ledger records 12 of 18 calls; actual billed Gemini
cost is unknown. Gate C software is runnable, but the seeded rehearsal is
synthetic and does not replace a fresh learner, genuine teacher-derived
procedure, or facilitator-reviewed transfer evidence.” Close with the three
roles: Teaching Partner, Blinded Probe, and Learner Coach.

## Submission blocker

Official rules require the final video to show the backend running on Google
Cloud. This repository has not been deployed during this goal. A later Cloud Run
deployment needs exact resource, region, cost, recurring-risk, and rollback
approval under `AGENTS.md`.
