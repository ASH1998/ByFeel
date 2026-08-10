# Teacher Demonstration Capture and Transcription Plan

## Current boundary

The local CLI now accepts a bounded teacher video, probes it locally, extracts
duration-aware representative frames (roughly 1 fps, bounded to 9–18), and conditionally extracts audio. One Lite-model
call produces a teacher-only factual draft when the command is run. Human
review and transcript approval remain mandatory before procedure extraction.

This is not yet a browser capture/review UI, live event-triggered sampling, or
a production-validated speech pipeline. Raw media and generated drafts remain
local, ignored artifacts.

## Capture routing

Every physical demonstration needs a visual account of actions and observable
checks. Speech adds another evidence channel; it does not replace the visual
channel.

- **Video with speech:** transcribe the audio verbatim and independently record
  visible actions, quantities that are actually observable, tool changes,
  checks, and results. Synchronize both into one chronological record.
- **Silent video:** record the visible events only and explicitly state
  `The teacher did not speak.` Do not create narration for the teacher.
- **Audio-only recording:** transcribe speech, but treat the recording as
  insufficient evidence of physical actions unless a human observer supplies
  and verifies factual action notes.
- **Still images:** use as supporting checkpoint evidence, not as proof of the
  complete action sequence.

The capture stage must not infer ratios, angles, pigment chemistry, causal
explanations, safety properties, or success guarantees that were not spoken,
measured, or visibly demonstrated. Uncertain observations stay uncertain.

## Gate A boundary

1. Keep raw demonstration media and its factual transcript in the teacher-only
   side of the experiment.
2. Require a human to confirm transcript fidelity and task safety.
3. Send the verified transcript to extraction.
4. Send only `Procedure.learner_view()` to every blinded probe.
5. Never give the probe raw video, audio, transcript, source metadata, or
   teacher-only observations.
6. Require a persisted human decision that the probe blocker is genuine before
   asking its teacher question or allowing repair.

Any Gemini call used for media transcription or visual event extraction counts
toward the Gate A call ceiling and requires a call-count statement before use.
Record actual billed cost only when available. Local human transcription
consumes no Gemini calls.

## Selected Gate A candidate

- Task: reproduce the obscure `Banana Panic` paint result using `Just White`,
  `Lavender Energy`, and `Vampire BBQ`.
- Available source: ignored local video
  `assets/videos/You NEED to See This Color Mixing Result!.mp4`.
- Audio state reported by the human reviewer: the teacher did not speak.
- Capture route: silent-video visual event transcription.
- Current source status: locally probed and sampled without a model call; the
  teacher-confirmed silent route successfully produced nine visual frames.
- Baseline evidence: a general model guessed the branded color meanings and
  produced an incorrect generic color-theory answer.

Before this candidate can count as a safe real demonstration, a human must
confirm the paint/material type and applicable handling precautions. Claims
such as a `60/35/5` ratio, hidden yellow pigment, a `45-degree` tool angle, or
repeatability must not enter the record unless directly evidenced.

Three independently performed demonstrations of the same mixture are still
required. A single source clip is only one candidate demonstration.

## Implementation status

- [x] Detect a local recording's video and audio streams.
- [x] Extract time-linked visual samples and optional audio.
- [x] Exclude audio and reject invented speech for human-declared silent video.
- [x] Preserve source hash, timestamps, model usage, and uncertainty.
- [x] Require a human-corrected transcript before creating `TeacherDemo`.
- [x] Keep raw media, samples, and drafts local and ignored.
- [x] Test silent routing, spoken routing, invented speech, and approval.
- [ ] Add browser capture, status, draft review, and approval UI.
- [ ] Validate voiced, noisy, multilingual, and uncertain-audio sources.
- [ ] Replace uniform samples with user/transition events where capture supports
  them.
- [ ] Upload only selected approved evidence when explicitly authorized.
