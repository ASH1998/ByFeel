"""Persistence interfaces and deterministic in-memory implementations."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Protocol, TypeVar

from pydantic import BaseModel

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

    def get_probe_run(self, probe_run_id: str) -> ProbeRun: ...

    def append_blocker_review(self, review: BlockerReview) -> None: ...

    def get_blocker_review(self, probe_run_id: str) -> BlockerReview: ...

    def append_agent_run(self, run: AgentRunRecord) -> None: ...

    def list_agent_runs(self, procedure_id: str | None = None) -> list[AgentRunRecord]: ...

    def append_procedure_version(self, version: ProcedureVersion) -> None: ...

    def list_procedure_versions(self, procedure_id: str) -> list[ProcedureVersion]: ...

    def append_audit_event(self, event: AuditEvent) -> None: ...

    def list_audit_events(self, procedure_id: str | None = None) -> list[AuditEvent]: ...

    def list_probe_runs(self, procedure_id: str) -> list[ProbeRun]: ...

    def list_blocker_reviews(self, procedure_id: str) -> list[BlockerReview]: ...

    def save_teacher_session(self, session: TeacherSession) -> None: ...

    def get_teacher_session(self, session_id: str) -> TeacherSession: ...

    def save_media_draft(self, draft: MediaDraft) -> None: ...

    def get_media_draft(self, session_id: str) -> MediaDraft: ...

    def save_demonstration_approval(self, approval: ApprovedDemonstration) -> None: ...

    def get_demonstration_approval(self, session_id: str) -> ApprovedDemonstration: ...

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
        self._agent_runs: dict[str, AgentRunRecord] = {}
        self._blocker_reviews: dict[str, BlockerReview] = {}
        self._teacher_sessions: dict[str, TeacherSession] = {}
        self._media_drafts: dict[str, MediaDraft] = {}
        self._demonstration_approvals: dict[str, ApprovedDemonstration] = {}
        self._procedure_versions: dict[str, ProcedureVersion] = {}
        self._audit_events: dict[str, AuditEvent] = {}
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

    def get_probe_run(self, probe_run_id: str) -> ProbeRun:
        with self._lock:
            try:
                return self._copy(self._probe_runs[probe_run_id])
            except KeyError as exc:
                raise NotFoundError(f"probe run {probe_run_id!r} was not found") from exc

    def append_blocker_review(self, review: BlockerReview) -> None:
        with self._lock:
            if review.run_id in self._blocker_reviews:
                raise ConflictError("blocker review history is immutable")
            self._blocker_reviews[review.run_id] = self._copy(review)

    def get_blocker_review(self, probe_run_id: str) -> BlockerReview:
        with self._lock:
            try:
                return self._copy(self._blocker_reviews[probe_run_id])
            except KeyError as exc:
                raise NotFoundError(
                    f"blocker review for probe run {probe_run_id!r} was not found"
                ) from exc

    def append_agent_run(self, run: AgentRunRecord) -> None:
        with self._lock:
            if run.run_id in self._agent_runs:
                raise ConflictError("agent run history is append-only")
            self._agent_runs[run.run_id] = self._copy(run)

    def list_agent_runs(self, procedure_id: str | None = None) -> list[AgentRunRecord]:
        with self._lock:
            values = self._agent_runs.values()
            if procedure_id is not None:
                values = [
                    run
                    for run in values
                    if run.procedure_id == procedure_id or run.context_ref == procedure_id
                ]
            values = sorted(values, key=lambda item: item.started_at)
            return [self._copy(item) for item in values]

    def append_procedure_version(self, version: ProcedureVersion) -> None:
        with self._lock:
            if version.version_id in self._procedure_versions:
                raise ConflictError("procedure version history is append-only")
            self._procedure_versions[version.version_id] = self._copy(version)

    def list_procedure_versions(self, procedure_id: str) -> list[ProcedureVersion]:
        with self._lock:
            values = [
                item
                for item in self._procedure_versions.values()
                if item.procedure_id == procedure_id
            ]
            return [self._copy(item) for item in sorted(values, key=lambda item: item.created_at)]

    def append_audit_event(self, event: AuditEvent) -> None:
        with self._lock:
            if event.event_id in self._audit_events:
                raise ConflictError("audit history is append-only")
            self._audit_events[event.event_id] = self._copy(event)

    def list_audit_events(self, procedure_id: str | None = None) -> list[AuditEvent]:
        with self._lock:
            values = self._audit_events.values()
            if procedure_id is not None:
                values = [event for event in values if event.procedure_id == procedure_id]
            return [self._copy(item) for item in sorted(values, key=lambda item: item.created_at)]

    def list_probe_runs(self, procedure_id: str) -> list[ProbeRun]:
        with self._lock:
            values = [run for run in self._probe_runs.values() if run.procedure_id == procedure_id]
            return [self._copy(item) for item in sorted(values, key=lambda item: item.created_at)]

    def list_blocker_reviews(self, procedure_id: str) -> list[BlockerReview]:
        run_ids = {run.probe_run_id for run in self.list_probe_runs(procedure_id)}
        with self._lock:
            values = [
                review for review in self._blocker_reviews.values() if review.run_id in run_ids
            ]
            return [self._copy(item) for item in sorted(values, key=lambda item: item.reviewed_at)]

    def save_teacher_session(self, session: TeacherSession) -> None:
        with self._lock:
            self._teacher_sessions[session.session_id] = self._copy(session)

    def get_teacher_session(self, session_id: str) -> TeacherSession:
        with self._lock:
            try:
                return self._copy(self._teacher_sessions[session_id])
            except KeyError as exc:
                raise NotFoundError(f"teacher session {session_id!r} was not found") from exc

    def save_media_draft(self, draft: MediaDraft) -> None:
        with self._lock:
            if draft.run_id in self._media_drafts:
                raise ConflictError("teacher media draft is immutable")
            self._media_drafts[draft.run_id] = self._copy(draft)

    def get_media_draft(self, session_id: str) -> MediaDraft:
        with self._lock:
            try:
                return self._copy(self._media_drafts[session_id])
            except KeyError as exc:
                raise NotFoundError(
                    f"media draft for teacher session {session_id!r} was not found"
                ) from exc

    def save_demonstration_approval(self, approval: ApprovedDemonstration) -> None:
        with self._lock:
            if approval.teacher_session_id in self._demonstration_approvals:
                raise ConflictError("factual-record approval is immutable")
            self._demonstration_approvals[approval.teacher_session_id] = self._copy(approval)

    def get_demonstration_approval(self, session_id: str) -> ApprovedDemonstration:
        with self._lock:
            try:
                return self._copy(self._demonstration_approvals[session_id])
            except KeyError as exc:
                raise NotFoundError(
                    f"factual-record approval for teacher session {session_id!r} was not found"
                ) from exc

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
