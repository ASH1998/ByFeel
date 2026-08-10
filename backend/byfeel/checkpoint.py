"""Gemini-backed learner checkpoint evaluation."""

from __future__ import annotations

from .evidence import EvidenceStore
from .gemini import GeminiStructuredClient
from .models import (
    CheckpointEvaluation,
    LearnerObservation,
    LearnerProcedure,
    LearnerStep,
)
from .prompts import CHECKPOINT_SYSTEM, checkpoint_prompt


class GeminiCheckpointEvaluator:
    def __init__(
        self, client: GeminiStructuredClient, evidence_store: EvidenceStore | None = None
    ) -> None:
        self._client = client
        self._evidence_store = evidence_store

    def evaluate(
        self,
        *,
        procedure: LearnerProcedure,
        step: LearnerStep,
        observation: LearnerObservation,
    ) -> CheckpointEvaluation:
        del procedure  # Deliberately limited to the current learner-facing step.
        prompt = checkpoint_prompt(step, observation)
        if observation.evidence is not None:
            if self._evidence_store is None:
                raise ValueError("checkpoint evidence store is not configured")
            image = self._evidence_store.get(observation.evidence)
            return self._client.generate_with_image(
                system=CHECKPOINT_SYSTEM,
                prompt=prompt,
                image=image,
                content_type=observation.evidence.content_type,
                schema=CheckpointEvaluation,
            )
        return self._client.generate(
            system=CHECKPOINT_SYSTEM,
            prompt=prompt,
            schema=CheckpointEvaluation,
        )
