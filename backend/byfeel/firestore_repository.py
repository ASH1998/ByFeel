"""Firestore repository restricted to an existing database and test namespace."""

from __future__ import annotations

from .evidence import NAMESPACE_PATTERN
from .models import Correction, LearnerEvent, LearnerSession, ProbeRun, Procedure
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
