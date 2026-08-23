# Decision Gate B — Banana Panic Visual Checkpoint

## Current decision state

Gate A is deferred, not passed or failed. One genuine demonstration preserved
the blindness boundary but produced a human-rejected false blocker. No
clarification or repair was performed. Additional Gate A demonstrations remain
required before any later claim that Gate A passed.

Gate B preparation may continue locally, but it does not erase or waive that
missing evidence.

## Claim under test

Given a learner snapshot and teacher-approved visual references, ByFeel can
distinguish an unfinished mixture, the intended ready mixture, and a uniform but
incorrect result. It must abstain when image quality or visual similarity is too
uncertain and must never auto-advance an incorrect result.

## Selected checkpoint

Task: mix `Just White`, `Lavender Energy`, and a smaller amount of `Vampire BBQ`
acrylic paint to produce the result called `Banana Panic`.

Checkpoint: after chopping, stirring, folding, and flattening, inspect the mixed
paint before making the final display swatch.

The checkpoint is deliberately based on teacher-approved reference images, not
on a model's prior beliefs about the branded color names or generic color
theory.

## Human-labeled states

### `not_ready`

- Separate white, lavender, or maroon streaks or patches remain visible.
- The mixture is visibly non-uniform.
- Further folding or mixing is still appropriate.

### `ready`

- The paint is visually uniform across the inspected area.
- No separate source-color streaks remain.
- The color and opacity fall within the human-approved range represented by the
  teacher's ready references.

### `incorrect_or_overshot`

- The mixture may be uniform, but it falls outside the teacher-approved target
  range.
- A clearly muted, pink, purple, brown, excessively pale, or excessively dark
  result belongs here only when the human labels it against the same physical
  reference and capture conditions.
- More mixing alone would not be expected to correct the state.

### Evidence-quality outcome

- Blur, glare, clipping, shadows, severe white-balance shift, poor framing, or
  insufficient visible paint should produce `retry_snapshot`.
- A clear image whose target match remains genuinely uncertain should produce
  `human_confirmation`, never `advance`.

## Dataset requirements

- Capture multiple real examples of all three states using the same acrylic
  materials and protected workspace.
- Include modest variation in angle, distance, lighting, and background without
  making the task adversarial or unrealistic.
- Preserve one or more teacher-approved ready references.
- Label every image by human review before any Gemini evaluation.
- Separate calibration/reference images from held-out evaluation images.
- Include dedicated poor-quality images for retry/abstention behavior; do not
  silently mix them into the three state classes.
- Keep faces, personal data, and unnecessary surroundings out of frame.
- Store media locally and ignored by default. Any use of the approved bucket
  requires a unique test namespace and an exact mutation/cost/cleanup proposal.

No human-approved evaluation dataset exists yet. The existing YouTube video has
now been inspected locally. Eighteen 1-fps frames, an early/middle/late
contact sheet, the audio stream, and a spectrogram are stored under ignored
`runs/gate-b/source-inspection/banana-panic-video-01/`.

The source supplies candidate `not_ready` and `ready` calibration frames. It
does not supply an evident `incorrect_or_overshot` example, poor-quality test
case, or independent held-out sample. Sequential frames from one edited clip
must not be split across calibration and held-out sets because that would leak
near-duplicate visual information.

Human review approved four `not_ready` frames (`004`, `006`, `008`, `010`) and
three `ready` frames (`012`, `014`, `016`). The three ready frames are frozen as
initial teacher-reference candidates in `calibration-manifest.json`. They remain
calibration-only and cannot contribute to held-out metrics.

An AAC stereo audio track exists, but the human reviewer confirmed the teacher
did not speak. The track is preserved as non-instructional audio; ASR was not
run because it could hallucinate speech from sparse effects or handling sounds.

## Existing implementation audit

Implemented locally:

- one learner JPEG, PNG, or WebP image plus up to three teacher references per
  checkpoint request;
- checksum and provenance metadata;
- `advance`, `block`, `retry_snapshot`, and `human_confirmation` decisions;
- explicit `not_ready`, `ready`, and `incorrect_or_overshot` visual states;
- teacher-reference images loaded before the learner image for comparison;
- confidence in `[0, 1]`;
- schema rejection of `advance` below `0.8`;
- learner-step-only prompt boundary.

Missing before Gate B evaluation:

- a frozen dataset manifest with human ground truth and calibration/held-out
  split;
- a model-evaluation runner that records image calls, tokens, cost,
  predictions, and provenance (the deterministic metrics stage now exists);
- per-class precision and recall, confusion matrix, abstention rate, and
  demo-critical false-positive count;
- tests for wrong-color-but-uniform paint, bad angle, glare, poor lighting,
  reference mismatch, and uncertain target similarity.

## Pass condition

Gate B passes only when held-out evidence shows:

- no demo-critical `incorrect_or_overshot -> advance` result;
- useful discrimination among all three human-labeled states;
- poor-quality and genuinely uncertain images cause retry or human confirmation;
- every prediction is traceable to the exact learner image, reference set,
  model, tokens, and cost;
- human review agrees the behavior is reliable enough to start Gate C; and
- the complete automated test, Ruff lint, and formatting suites pass.

A few plausible model responses or a successful ready image are not sufficient.
