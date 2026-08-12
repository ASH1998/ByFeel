# Decision Gate C — real learner transfer

Status: local runner, API, persistence, browser flow, and tests are complete.
Gate C itself is not passed. A real run still needs a fresh learner, genuine
teacher-derived procedure evidence, and human review.

## What the local harness guarantees

- The experiment pins one exact `extracted` procedure version for the
  `static_instructions` arm and one exact `learner_approved` version for the
  `byfeel_teacher_repaired` arm.
- Each arm gets a fresh version-pinned learner session and the same named
  checkpoint and deliberate incorrect state.
- Learner events, Gate C attempts, and interventions are append-only. Attempts
  retain requested decision, safe decision, detection outcome, correction flag,
  advancement, suppression, and elapsed time.
- A ByFeel intervention is accepted only when its correction, version, step,
  guidance, and source quote resolve to an approved teacher correction. The
  browser displays that provenance.
- A deliberate incorrect observation cannot be recorded as a safe advance. A
  model request to advance is preserved as a missed detection and converted to
  safe human confirmation.
- Missing, uncertain, abstained, incomplete, or unreviewed evidence is never
  converted into a Gate C pass. `pass_candidate` means “eligible for human
  review,” not “passed.”
- The seeded rehearsal is deterministic, labelled synthetic, and reported as
  `synthetic_excluded`.

## Real facilitator protocol

1. Select a low-risk task and obtain the teacher’s normal bounded demonstration.
   Complete the existing factual approval, blocker review, targeted
   clarification, repaired procedure, fresh reprobe, and learner approval.
2. Confirm the learner has not seen the demonstration. Assign a random-looking
   pseudonymous code; do not enter a name, email, raw media, or hidden note.
3. In **04 · Gate C transfer**, pin the exact extracted version and exact
   learner-approved repaired version for the same procedure. Choose one
   observable checkpoint and write the deliberate incorrect state before either
   arm starts. Confirm the task is low risk and does not require an unavailable
   sense.
4. Start the static arm with a fresh learner session. Use only the static
   instructions. Have the learner reach the agreed incorrect state, record what
   was observed, and record detection, safe abstention, or missed detection.
   Do not provide the ByFeel repaired guidance. Finalize the arm.
5. Start the ByFeel arm with a different fresh learner session. Use the same
   incorrect state. If the checkpoint blocks, show the intervention and its
   provenance. Record the learner’s correction as a new attempt. Advance only
   after the evaluator advances on the corrected state. Finalize the arm.
6. Record the three human attestations: fresh learner, genuine teacher-derived
   procedure, and no personal learner information. Review the JSON comparison,
   arm attempts, elapsed times, learner events, intervention provenance, and
   any uncertainty. Keep the result pending or not evaluable when evidence is
   missing.

## Evidence required before a Gate C decision

- Two arm records for the same procedure, exact version hashes, checkpoint, and
  agreed incorrect state.
- Fresh learner confirmation and a short facilitator record that the learner
  did not see the demonstration.
- The teacher-approved repair and its correction provenance, including the
  exact teacher-derived guidance used in the ByFeel arm.
- The baseline observation and outcome, including safe abstention or missed
  detection when applicable.
- The ByFeel detection, intervention, learner correction, and advancement after
  correction, with attempts and timing.
- Facilitator review of the structured comparison and a privacy/safety review.

The seeded browser rehearsal, local fake-model tests, and any unapproved
Gemini calls are not Gate C evidence.
