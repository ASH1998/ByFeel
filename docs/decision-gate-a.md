# Decision Gate A — Blinded Procedure Stress Test

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

## Run protocol

1. Record or observe one real three-step physical demonstration.
2. Transcribe what happened and what the teacher said into a demo JSON file.
3. Run `uv run byfeel gate-a --demo <path>`.
4. Answer the probe's one targeted question as the teacher.
5. Inspect the before/after artifacts under `runs/gate-a/<run-id>/`.

Do not coach the initial probe, add a known ambiguity solely to make it fail, or
edit generated artifacts between calls.

## Pass condition

The manifest reports `blocked -> unblocked`, and a human reviewer agrees that:

- the original blocker was non-trivial and execution-relevant;
- the question was answerable by the teacher;
- the repair added only teacher-supplied information; and
- the second probe cleared the original blocker for the right reason.

The status transition alone is not sufficient evidence. Repeat the test across
several real demonstrations before accepting the mechanism.

