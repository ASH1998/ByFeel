# Implementation Alignment

The original ByFeel loop is the standing build filter:

```text
teacher demonstration
  -> human-approved factual record
  -> structured learner procedure
  -> blinded learner-only stress test
  -> one material clarification
  -> bounded repair
  -> real learner guidance
```

A feature is aligned only when it operates, strengthens, or measures one of
these links without weakening the blindness boundary. Evaluation fixtures,
frame labels, and metrics can measure reliability, but they are not the
learner-facing product and must not drive the product shape by themselves.

## Current implemented path

1. `byfeel ingest-demo` probes a bounded local video and extracts a
   duration-aware 9–18 frame sequence. Audio is included only for `spoken` or `unsure`
   routing; a human-declared silent demonstration does not send audio.
2. A Lite-model call creates a teacher-only, timestamped factual draft. The
   prompt prohibits inferred quantities, causes, criteria, safety claims, and
   invented narration.
3. `byfeel approve-demo` requires a human-reviewed transcript and emits the
   canonical `TeacherDemo` used by procedure extraction.
4. Only that approved record may enter Gate A. Raw video, audio, frames,
   source metadata, and the unapproved draft never enter the blinded probe.
5. A persisted human review must accept a probe blocker as genuine before the
   system may ask its teacher question or perform any repair. Rejected blockers
   close the run as honest negative results.

## Claims we do not make yet

- The browser UI does not yet expose video capture or transcript review.
- Sampling is bounded and time-based, not continuous live-video reasoning or
  true action-transition detection.
- Voiced, noisy, multilingual, and uncertain-audio demonstrations have not yet
  been validated with genuine sources.
- One source video is not three genuine demonstrations and is not a benchmark.
- Gate A remains deferred after one false-blocker result; it has neither passed
  nor failed.
