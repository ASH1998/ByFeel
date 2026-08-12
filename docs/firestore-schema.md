# Firestore schema plan

The active database is `(default)`, Firestore Native mode, in `asia-south1`.
This document defines the initial logical paths without creating dummy cloud
documents. Firestore collections will be created by the first validated real
application writes.

## Initial paths

- `procedures/{procedure_id}` — canonical procedure metadata and active version.
- `procedures/{procedure_id}/versions/{version_id}` — immutable learner-facing
  versions and hashes.
- `procedures/{procedure_id}/corrections/{correction_id}` — append-only teacher
  corrections with `supersedes` linkage.
- `probe_runs/{probe_run_id}` — blinded-probe input hash, result, and provenance.
- `learner_sessions/{session_id}` — learner progress and current procedure version.
- `learner_sessions/{session_id}/events/{event_id}` — append-only checkpoint,
  intervention, abstention, and human-confirmation events.
- `evidence/{evidence_id}` — metadata, checksum, provenance, consent, and the
  Cloud Storage object reference; image bytes remain in Cloud Storage.
- `audit_events/{event_id}` — append-only administrative and mutation audit events.

## Gate C collections

The local/test adapter adds namespaced collections for the transfer evidence:

- gate_c_experiments — immutable arm/version identity plus experiment status.
- gate_c_arm_runs — mutable facilitator-facing arm summary; once finalized it
  is immutable.
- gate_c_attempts — append-only learner attempts with requested versus safe
  decisions, detection outcome, timing, and correction flags.
- gate_c_interventions — append-only approved teacher-derived interventions
  linked to a correction and exact procedure version.
- gate_c_attestations — one append-only human evidence attestation per
  experiment.

These logical collections remain under the existing namespaced test root. No
new cloud resource, index, or production path is created by the Gate C code.

## Boundaries

- Store UTC timestamps, stable IDs, and `schema_version` on every document.
- Never store Gemini or Google Cloud credentials in Firestore.
- Treat model output as untrusted until Pydantic validation succeeds.
- Keep corrections and audit/session events append-only.
- Use transactions when changing a procedure's active version and writing the
  corresponding correction/audit record; exact repository mechanics remain an
  implementation task.
- Add indexes only when an implemented query requires them and after direct cloud
  approval.

## Local MVP test-data boundary

The implemented cloud adapter intentionally does not write the eventual
production paths above. Local smoke/application data is hard-scoped beneath:

```text
byfeel_test_runs/{namespace}/procedures/{procedure_id}
byfeel_test_runs/{namespace}/probe_runs/{probe_run_id}
byfeel_test_runs/{namespace}/corrections/{correction_id}
byfeel_test_runs/{namespace}/learner_sessions/{session_id}
byfeel_test_runs/{namespace}/learner_events/{event_id}
```

The adapter reads the small namespace locally instead of issuing compound
queries, so it requires no new Firestore indexes. It exposes no database,
collection, document, or index deletion operation. Canonical production paths
and transaction boundaries remain a later-phase decision.
