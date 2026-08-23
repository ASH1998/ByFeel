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
            references = [
                evidence
                for checkpoint in step.checkpoints
                for evidence in checkpoint.evidence_refs
                if evidence.source == "teacher"
            ][:3]
            if references:
                reference_images = [
                    (self._evidence_store.get(reference), reference.content_type)
                    for reference in references
                ]
                comparison_prompt = (
                    f"{prompt}\n\nIMAGE ORDER: The first {len(references)} image(s) are "
                    "teacher-approved references. The final image is the learner snapshot. "
                    "Compare the learner snapshot against the references and set visual_state."
                )
                return self._client.generate_with_images(
                    system=CHECKPOINT_SYSTEM,
                    prompt=comparison_prompt,
                    images=[
                        *reference_images,
                        (image, observation.evidence.content_type),
                    ],
                    schema=CheckpointEvaluation,
                )
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
