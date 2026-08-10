from __future__ import annotations

from hashlib import sha256

from byfeel.checkpoint import GeminiCheckpointEvaluator
from byfeel.models import (
    Checkpoint,
    CheckpointDecision,
    CheckpointEvaluation,
    CheckpointModality,
    EvidenceRef,
    LearnerObservation,
    Procedure,
    ProcedureStep,
    VisualCheckpointState,
)


def evidence(name: str, data: bytes, source: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=name,
        object_name=name,
        content_type="image/png",
        sha256=sha256(data).hexdigest(),
        size_bytes=len(data),
        source=source,
    )


class FakeEvidenceStore:
    def __init__(self, values: dict[str, bytes]) -> None:
        self.values = values

    def get(self, reference: EvidenceRef) -> bytes:
        return self.values[reference.object_name]


class MultiImageClient:
    def __init__(self) -> None:
        self.prompt = ""
        self.images: list[tuple[bytes, str]] = []

    def generate_with_images(self, *, system, prompt, images, schema):
        del system, schema
        self.prompt = prompt
        self.images = images
        return CheckpointEvaluation(
            decision=CheckpointDecision.ADVANCE,
            visual_state=VisualCheckpointState.READY,
            confidence=0.95,
            explanation="The learner paint matches the approved ready reference.",
            teacher_derived=True,
        )


def test_checkpoint_compares_teacher_references_before_learner_image() -> None:
    teacher_data = b"teacher-reference"
    learner_data = b"learner-snapshot"
    teacher = evidence("teacher.png", teacher_data, "teacher")
    learner = evidence("learner.png", learner_data, "learner")
    procedure = Procedure(
        id="banana-panic",
        title="Banana Panic",
        domain="paint mixing",
        learner_goal="Match the teacher result",
        steps=[
            ProcedureStep(
                step_id="mix",
                order=1,
                action="Mix until uniform and compare with the target.",
                completion_conditions=["The mixture matches the approved target."],
                checkpoints=[
                    Checkpoint(
                        checkpoint_id="color-match",
                        modality=CheckpointModality.VISUAL,
                        description="Compare the uniform mixture with the target.",
                        evidence_refs=[teacher],
                        confidence=1,
                    )
                ],
                confidence=1,
            )
        ],
    )
    client = MultiImageClient()
    evaluator = GeminiCheckpointEvaluator(
        client,
        FakeEvidenceStore({teacher.object_name: teacher_data, learner.object_name: learner_data}),
    )

    result = evaluator.evaluate(
        procedure=procedure.learner_view(),
        step=procedure.learner_view().steps[0],
        observation=LearnerObservation(
            step_id="mix",
            description="The paint is uniform.",
            evidence=learner,
        ),
    )

    assert result.visual_state == VisualCheckpointState.READY
    assert [image for image, _ in client.images] == [teacher_data, learner_data]
    assert "first 1 image(s)" in client.prompt
    assert "final image is the learner snapshot" in client.prompt
