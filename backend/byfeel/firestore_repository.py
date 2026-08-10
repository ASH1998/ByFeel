"""Firestore repository restricted to an existing database and test namespace."""

from __future__ import annotations

from .evidence import NAMESPACE_PATTERN
from .media_ingest import MediaDraft
from .models import (
    AgentRunRecord,
    ApprovedDemonstration,
    AuditEvent,
    BlockerReview,
    Correction,
    LearnerEvent,
    LearnerSession,
    ProbeRun,
    Procedure,
    ProcedureVersion,
    TeacherSession,
)
from .repositories import ConflictError, NotFoundError


class FirestoreRepository:
    """Uses only document data operations beneath byfeel_test_runs/{namespace}."""

    def __init__(self, *, namespace: str, database: str = "(default)", client=None) -> None:
        if not NAMESPACE_PATTERN.fullmatch(namespace):
            raise ValueError("invalid test-data namespace")
        if database != "(default)":
            raise ValueError("only the existing (default) Firestore database is allowed")
        if client is None:
            from google.cloud import firestore

            client = firestore.Client(database=database)
        self._root = client.collection("byfeel_test_runs").document(namespace)

    def _collection(self, name: str):
        return self._root.collection(name)

    def save_procedure(
        self, procedure: Procedure, *, expected_updated_at: str | None = None
    ) -> None:
        reference = self._collection("procedures").document(procedure.id)
        if expected_updated_at is not None:
            snapshot = reference.get()
            current = Procedure.model_validate(snapshot.to_dict()) if snapshot.exists else None
            if current is None or current.updated_at.isoformat() != expected_updated_at:
                raise ConflictError("procedure was modified by another request")
        reference.set(procedure.model_dump(mode="json"))

    def get_procedure(self, procedure_id: str) -> Procedure:
        snapshot = self._collection("procedures").document(procedure_id).get()
        if not snapshot.exists:
            raise NotFoundError(f"procedure {procedure_id!r} was not found")
        return Procedure.model_validate(snapshot.to_dict())

    def save_probe_run(self, run: ProbeRun) -> None:
        self._collection("probe_runs").document(run.probe_run_id).create(
            run.model_dump(mode="json")
        )

    def get_probe_run(self, probe_run_id: str) -> ProbeRun:
        snapshot = self._collection("probe_runs").document(probe_run_id).get()
        if not snapshot.exists:
            raise NotFoundError(f"probe run {probe_run_id!r} was not found")
        return ProbeRun.model_validate(snapshot.to_dict())

    def append_blocker_review(self, review: BlockerReview) -> None:
        self._collection("blocker_reviews").document(review.run_id).create(
            review.model_dump(mode="json")
        )

    def get_blocker_review(self, probe_run_id: str) -> BlockerReview:
        snapshot = self._collection("blocker_reviews").document(probe_run_id).get()
        if not snapshot.exists:
            raise NotFoundError(f"blocker review for probe run {probe_run_id!r} was not found")
        return BlockerReview.model_validate(snapshot.to_dict())

    def append_agent_run(self, run: AgentRunRecord) -> None:
        self._collection("agent_runs").document(run.run_id).create(run.model_dump(mode="json"))

    def list_agent_runs(self, procedure_id: str | None = None) -> list[AgentRunRecord]:
        values = [
            AgentRunRecord.model_validate(snapshot.to_dict())
            for snapshot in self._collection("agent_runs").stream()
        ]
        if procedure_id is not None:
            values = [
                run
                for run in values
                if run.procedure_id == procedure_id or run.context_ref == procedure_id
            ]
        return sorted(values, key=lambda item: item.started_at)

    def append_procedure_version(self, version: ProcedureVersion) -> None:
        self._collection("procedure_versions").document(version.version_id).create(
            version.model_dump(mode="json")
        )

    def list_procedure_versions(self, procedure_id: str) -> list[ProcedureVersion]:
        values = [
            ProcedureVersion.model_validate(snapshot.to_dict())
            for snapshot in self._collection("procedure_versions").stream()
            if snapshot.to_dict().get("procedure_id") == procedure_id
        ]
        return sorted(values, key=lambda item: item.created_at)

    def append_audit_event(self, event: AuditEvent) -> None:
        self._collection("audit_events").document(event.event_id).create(
            event.model_dump(mode="json")
        )

    def list_audit_events(self, procedure_id: str | None = None) -> list[AuditEvent]:
        values = [
            AuditEvent.model_validate(snapshot.to_dict())
            for snapshot in self._collection("audit_events").stream()
        ]
        if procedure_id is not None:
            values = [event for event in values if event.procedure_id == procedure_id]
        return sorted(values, key=lambda item: item.created_at)

    def list_probe_runs(self, procedure_id: str) -> list[ProbeRun]:
        values = [
            ProbeRun.model_validate(snapshot.to_dict())
            for snapshot in self._collection("probe_runs").stream()
            if snapshot.to_dict().get("procedure_id") == procedure_id
        ]
        return sorted(values, key=lambda item: item.created_at)

    def list_blocker_reviews(self, procedure_id: str) -> list[BlockerReview]:
        run_ids = {run.probe_run_id for run in self.list_probe_runs(procedure_id)}
        values = [
            BlockerReview.model_validate(snapshot.to_dict())
            for snapshot in self._collection("blocker_reviews").stream()
            if snapshot.to_dict().get("run_id") in run_ids
        ]
        return sorted(values, key=lambda item: item.reviewed_at)

    def save_teacher_session(self, session: TeacherSession) -> None:
        self._collection("teacher_sessions").document(session.session_id).set(
            session.model_dump(mode="json")
        )

    def get_teacher_session(self, session_id: str) -> TeacherSession:
        snapshot = self._collection("teacher_sessions").document(session_id).get()
        if not snapshot.exists:
            raise NotFoundError(f"teacher session {session_id!r} was not found")
        return TeacherSession.model_validate(snapshot.to_dict())

    def save_media_draft(self, draft: MediaDraft) -> None:
        self._collection("media_drafts").document(draft.run_id).create(
            draft.model_dump(mode="json")
        )

    def get_media_draft(self, session_id: str) -> MediaDraft:
        snapshot = self._collection("media_drafts").document(session_id).get()
        if not snapshot.exists:
            raise NotFoundError(f"media draft for teacher session {session_id!r} was not found")
        return MediaDraft.model_validate(snapshot.to_dict())

    def save_demonstration_approval(self, approval: ApprovedDemonstration) -> None:
        self._collection("demonstration_approvals").document(approval.teacher_session_id).create(
            approval.model_dump(mode="json")
        )

    def get_demonstration_approval(self, session_id: str) -> ApprovedDemonstration:
        snapshot = self._collection("demonstration_approvals").document(session_id).get()
        if not snapshot.exists:
            raise NotFoundError(
                f"factual-record approval for teacher session {session_id!r} was not found"
            )
        return ApprovedDemonstration.model_validate(snapshot.to_dict())

    def latest_probe_run(self, procedure_id: str, phase: str) -> ProbeRun:
        matches = []
        for snapshot in self._collection("probe_runs").stream():
            value = snapshot.to_dict()
            if value.get("procedure_id") == procedure_id and value.get("phase") == phase:
                matches.append(ProbeRun.model_validate(value))
        if not matches:
            raise NotFoundError(f"no {phase} probe exists for procedure {procedure_id!r}")
        return max(matches, key=lambda item: item.created_at)

    def append_correction(self, correction: Correction) -> None:
        self._collection("corrections").document(correction.correction_id).create(
            correction.model_dump(mode="json")
        )

    def list_corrections(self, procedure_id: str) -> list[Correction]:
        values = [
            Correction.model_validate(snapshot.to_dict())
            for snapshot in self._collection("corrections").stream()
            if snapshot.to_dict().get("procedure_id") == procedure_id
        ]
        return sorted(values, key=lambda item: item.created_at)

    def save_learner_session(self, session: LearnerSession) -> None:
        self._collection("learner_sessions").document(session.session_id).set(
            session.model_dump(mode="json")
        )

    def get_learner_session(self, session_id: str) -> LearnerSession:
        snapshot = self._collection("learner_sessions").document(session_id).get()
        if not snapshot.exists:
            raise NotFoundError(f"learner session {session_id!r} was not found")
        return LearnerSession.model_validate(snapshot.to_dict())

    def append_learner_event(self, event: LearnerEvent) -> None:
        self._collection("learner_events").document(event.event_id).create(
            event.model_dump(mode="json")
        )

    def list_learner_events(self, session_id: str) -> list[LearnerEvent]:
        values = [
            LearnerEvent.model_validate(snapshot.to_dict())
            for snapshot in self._collection("learner_events").stream()
            if snapshot.to_dict().get("session_id") == session_id
        ]
        return sorted(values, key=lambda item: item.created_at)
