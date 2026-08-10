"""Persistence interfaces and deterministic in-memory implementations."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .models import Correction, LearnerEvent, LearnerSession, ProbeRun, Procedure

ModelT = TypeVar("ModelT", bound=BaseModel)


class NotFoundError(LookupError):
    """Requested domain object does not exist."""


class ConflictError(RuntimeError):
    """Optimistic concurrency precondition failed."""


class ByFeelRepository(Protocol):
    def save_procedure(
        self, procedure: Procedure, *, expected_updated_at: str | None = None
    ) -> None: ...

    def get_procedure(self, procedure_id: str) -> Procedure: ...

    def save_probe_run(self, run: ProbeRun) -> None: ...

    def latest_probe_run(self, procedure_id: str, phase: str) -> ProbeRun: ...

    def append_correction(self, correction: Correction) -> None: ...

    def list_corrections(self, procedure_id: str) -> list[Correction]: ...

    def save_learner_session(self, session: LearnerSession) -> None: ...

    def get_learner_session(self, session_id: str) -> LearnerSession: ...

    def append_learner_event(self, event: LearnerEvent) -> None: ...

    def list_learner_events(self, session_id: str) -> list[LearnerEvent]: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._procedures: dict[str, Procedure] = {}
        self._probe_runs: dict[str, ProbeRun] = {}
        self._corrections: dict[str, Correction] = {}
        self._sessions: dict[str, LearnerSession] = {}
        self._events: dict[str, LearnerEvent] = {}
        self._lock = RLock()

    @staticmethod
    def _copy(value: ModelT) -> ModelT:
        return deepcopy(value)

    def save_procedure(
        self, procedure: Procedure, *, expected_updated_at: str | None = None
    ) -> None:
        with self._lock:
            current = self._procedures.get(procedure.id)
            if expected_updated_at is not None and (
                current is None or current.updated_at.isoformat() != expected_updated_at
            ):
                raise ConflictError("procedure was modified by another request")
            self._procedures[procedure.id] = self._copy(procedure)

    def get_procedure(self, procedure_id: str) -> Procedure:
        with self._lock:
            try:
                return self._copy(self._procedures[procedure_id])
            except KeyError as exc:
                raise NotFoundError(f"procedure {procedure_id!r} was not found") from exc

    def save_probe_run(self, run: ProbeRun) -> None:
        with self._lock:
            self._probe_runs[run.probe_run_id] = self._copy(run)

    def latest_probe_run(self, procedure_id: str, phase: str) -> ProbeRun:
        with self._lock:
            matches = [
                run
                for run in self._probe_runs.values()
                if run.procedure_id == procedure_id and run.phase == phase
            ]
            if not matches:
                raise NotFoundError(f"no {phase} probe exists for procedure {procedure_id!r}")
            return self._copy(max(matches, key=lambda item: item.created_at))

    def append_correction(self, correction: Correction) -> None:
        with self._lock:
            if correction.correction_id in self._corrections:
                raise ConflictError("correction history is append-only")
            self._corrections[correction.correction_id] = self._copy(correction)

    def list_corrections(self, procedure_id: str) -> list[Correction]:
        with self._lock:
            values = [
                item for item in self._corrections.values() if item.procedure_id == procedure_id
            ]
            return [self._copy(item) for item in sorted(values, key=lambda item: item.created_at)]

    def save_learner_session(self, session: LearnerSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = self._copy(session)

    def get_learner_session(self, session_id: str) -> LearnerSession:
        with self._lock:
            try:
                return self._copy(self._sessions[session_id])
            except KeyError as exc:
                raise NotFoundError(f"learner session {session_id!r} was not found") from exc

    def append_learner_event(self, event: LearnerEvent) -> None:
        with self._lock:
            if event.event_id in self._events:
                raise ConflictError("learner event history is append-only")
            self._events[event.event_id] = self._copy(event)

    def list_learner_events(self, session_id: str) -> list[LearnerEvent]:
        with self._lock:
            values = [item for item in self._events.values() if item.session_id == session_id]
            return [self._copy(item) for item in sorted(values, key=lambda item: item.created_at)]
