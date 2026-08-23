# Decision Gate A — Blinded Procedure Stress Test

## Current status

Deferred by user decision after demonstration 1. The run preserved blindness
but its quantity complaint was rejected as a false blocker, so it did not
receive a clarification or repair and does not count as a success. Two further
genuine demonstrations and a final human pass/fail decision are still missing.
Gate B preparation may proceed, but Gate A must not be represented as passed.

## Claim under test

A model that receives only the generated learner-facing artifact can expose a
real missing execution criterion, and a bounded teacher clarification can repair
that criterion without leaking the original demonstration to the probe.

## Information boundary

The extraction call may receive the raw teacher demonstration. The probe call
is built exclusively from `Procedure.learner_view()` and cannot accept the raw
demonstration. The repair call receives the current procedure, the highest
severity blocking gap, and the teacher clarification. A fresh probe sees only
the repaired learner view.

## Three-demonstration validation protocol

Use three genuine demonstrations of the same safe, bounded 3–5 step physical
task. Each demonstration is an independent observation; do not reuse or tune a
transcript to force a blocker.

The selected candidate is the silent-video mixing of `Just White`, `Lavender
Energy`, and `Vampire BBQ` into the result called `Banana Panic`. The recording
is one candidate demonstration, not three. Its factual visual transcript and
material safety still require human confirmation before the first model call.
See `demonstration-capture-plan.md` for the audio/video routing policy.

For each demonstration:

1. Record or directly observe the expert and transcribe only actual actions,
   words, visible checks, and real constraints into a demo JSON file. For silent
   video, state that the teacher did not speak. For voiced video, preserve exact
   speech and separately capture visible actions; audio alone is not a physical
   demonstration transcript.
2. Run `uv run byfeel gate-a --demo <path>`. This makes two calls, saves the
   learner artifact and blinded probe, and stops at the human checkpoint.
3. Human-review the proposed blocker before answering. Reject and record it if
   it is stylistic, trivial, unsafe, depends on hidden teacher context, or would
   not prevent correct execution.
   A rejected blocker ends that demonstration as an honest negative result: do
   not ask its proposed clarification, repair it, rerun it, or tune the same
   demonstration until it appears successful.
4. If the blocker is accepted, obtain the teacher's answer to exactly the one
   saved question. Do not coach the teacher or add unrelated information.
5. Save that answer alone in a text file and run
   `uv run byfeel gate-a --resume-run <run-dir> --clarification-file <path>`.
   This reuses the saved learner artifact and makes only the repair and fresh
   blinded-probe calls.
6. Inspect the before/after artifacts and `usage.json` under the run directory.
7. Copy `experiments/gate_a/review.template.json` into the run directory and
   record false blockers, missed gaps, invented criteria, residual blockers,
   call/token usage, actual billed cost when available, and the human judgment about why the
   original blocker did or did not change.

Do not coach the initial probe, add a known ambiguity solely to make it fail, or
edit generated artifacts between calls.

## Pass condition

At least two of three demonstrations must report `blocked -> unblocked`, and a
human reviewer must agree for each counted success that:

- the original blocker was non-trivial and execution-relevant;
- the question was answerable by the teacher;
- the repair added only teacher-supplied information; and
- the second probe cleared the original blocker for the right reason.

All three demonstrations must preserve the blindness boundary, no counted
repair may invent information, and failures or negative results remain part of
the evidence. The status transition alone is not sufficient. Gate A passes only
after a human explicitly judges the full three-run record reliable enough to
begin Gate B and the automated tests, Ruff lint, and formatting checks pass.
