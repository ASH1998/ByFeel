from __future__ import annotations

from pathlib import Path

import pytest
from byfeel.media_ingest import (
    MAX_MODEL_MEDIA_BYTES,
    MEDIA_ANALYSIS_SYSTEM,
    DemonstrationEvent,
    FrameObservation,
    FrameSample,
    MediaAnalysis,
    MediaMetadata,
    SpeechMode,
    analyze_teacher_media,
    approve_media_draft,
)


class FakeExtractor:
    def __init__(self) -> None:
        self.frame_count: int | None = None

    def probe(self, source: Path) -> MediaMetadata:
        del source
        return MediaMetadata(
            duration_seconds=6,
            width=1080,
            height=1920,
            frames_per_second=60,
            audio_stream_present=True,
        )

    def extract(self, source, output, metadata, *, frame_count=9, include_audio):
        del source, metadata
        self.frame_count = frame_count
        frames = output / "frames"
        frames.mkdir()
        samples = []
        for index in range(2):
            path = frames / f"frame-{index}.jpg"
            path.write_bytes(f"frame-{index}".encode())
            samples.append(
                FrameSample(sample_id=f"frame-{index}", timestamp_seconds=index * 3, path=str(path))
            )
        audio = None
        if include_audio:
            audio = output / "audio.wav"
            audio.write_bytes(b"audio")
        return samples, audio


class FakeMediaClient:
    model = "gemini-lite-fake"
    usage: list[dict[str, int]] = []

    def __init__(self, *, teacher_spoke: bool = False) -> None:
        self.teacher_spoke = teacher_spoke
        self.media: list[tuple[bytes, str]] = []

    def generate_with_media(self, *, system, prompt, media, schema):
        del system, prompt, schema
        self.media = media
        return MediaAnalysis(
            teacher_spoke=self.teacher_spoke,
            spoken_transcript="Mix now." if self.teacher_spoke else None,
            initial_visible_inputs=["material one", "material two"],
            frame_observations=[
                FrameObservation(
                    sample_id="frame-0",
                    timestamp_seconds=0,
                    visible_materials=["material one", "material two"],
                    visible_tool_and_contact="A tool contacts material one.",
                    visible_state="The materials are separate.",
                ),
                FrameObservation(
                    sample_id="frame-1",
                    timestamp_seconds=3,
                    visible_materials=["combined material"],
                    visible_tool_and_contact="A tool contacts the combined material.",
                    visible_state="The materials appear combined.",
                ),
            ],
            events=[
                DemonstrationEvent(
                    event_id="event-1",
                    start_seconds=0,
                    end_seconds=3,
                    visible_action="The teacher combines the materials.",
                )
            ],
            factual_demonstration_draft=(
                "The teacher combines the materials and checks the visible result."
            ),
        )


def analyze(tmp_path: Path, speech_mode: str, *, teacher_spoke: bool = False):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    run = tmp_path / f"run-{speech_mode}"
    run.mkdir()
    client = FakeMediaClient(teacher_spoke=teacher_spoke)
    draft = analyze_teacher_media(
        client=client,
        source=source,
        run_dir=run,
        title="Test demo",
        domain="test",
        learner_goal="Finish safely",
        constraints=["Wear gloves"],
        speech_mode=speech_mode,
        extractor=FakeExtractor(),
    )
    return draft, client


def test_silent_ingest_sends_frames_without_audio_and_requires_approval(tmp_path: Path) -> None:
    draft, client = analyze(tmp_path, SpeechMode.SILENT)

    assert [content_type for _, content_type in client.media] == [
        "image/jpeg",
        "image/jpeg",
    ]
    assert draft.extracted_audio_path is None
    assert draft.human_approval_required is True
    assert draft.source_media_sent_to_model is False
    assert draft.model_payload_bytes == sum(len(data) for data, _ in client.media)
    assert all(not content_type.startswith("video/") for _, content_type in client.media)


def test_spoken_ingest_sends_frames_and_audio(tmp_path: Path) -> None:
    draft, client = analyze(tmp_path, SpeechMode.SPOKEN, teacher_spoke=True)

    assert [content_type for _, content_type in client.media] == [
        "image/jpeg",
        "image/jpeg",
        "audio/wav",
    ]
    assert draft.analysis.spoken_transcript == "Mix now."


def test_silent_ingest_rejects_invented_speech(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invented teacher speech"):
        analyze(tmp_path, SpeechMode.SILENT, teacher_spoke=True)


def test_ingest_rejects_missing_or_reordered_frame_observations(tmp_path: Path) -> None:
    class MissingFrameClient(FakeMediaClient):
        def generate_with_media(self, **kwargs):
            analysis = super().generate_with_media(**kwargs)
            return analysis.model_copy(
                update={"frame_observations": analysis.frame_observations[:1]}
            )

    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    run = tmp_path / "run-missing-frame"
    run.mkdir()
    with pytest.raises(ValueError, match="one ordered observation for every supplied frame"):
        analyze_teacher_media(
            client=MissingFrameClient(),
            source=source,
            run_dir=run,
            title="Test demo",
            domain="test",
            learner_goal="Finish safely",
            constraints=["Wear gloves"],
            speech_mode=SpeechMode.SILENT,
            extractor=FakeExtractor(),
        )


def test_human_approval_creates_canonical_teacher_demo(tmp_path: Path) -> None:
    draft, _ = analyze(tmp_path, SpeechMode.SILENT)
    approval = approve_media_draft(
        draft,
        "The teacher silently combines the materials and checks the visible result.",
    )

    assert approval.demo.raw_demonstration.startswith("The teacher silently")
    assert approval.demo.constraints == ["Wear gloves"]
    assert approval.source_sha256 == draft.source_sha256
    learner_input = approval.demo.model_dump_json()
    assert "source.mp4" not in learner_input
    assert draft.source_sha256 not in learner_input
    assert "frame-" not in learner_input


def test_duration_aware_sampling_is_bounded_and_can_be_overridden(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    extractor = FakeExtractor()
    run = tmp_path / "run-default-count"
    run.mkdir()
    draft = analyze_teacher_media(
        client=FakeMediaClient(),
        source=source,
        run_dir=run,
        title="Test demo",
        domain="test",
        learner_goal="Finish safely",
        constraints=[],
        speech_mode=SpeechMode.SILENT,
        extractor=extractor,
    )

    assert extractor.frame_count == 9
    assert draft.sampling_strategy == "low-bandwidth-uniform-9-frames"


def test_ingest_rejects_model_media_above_low_bandwidth_cap(tmp_path: Path) -> None:
    class OversizedExtractor(FakeExtractor):
        def extract(self, source, output, metadata, *, frame_count=9, include_audio):
            samples, audio = super().extract(
                source,
                output,
                metadata,
                frame_count=frame_count,
                include_audio=include_audio,
            )
            Path(samples[0].path).write_bytes(b"x" * (MAX_MODEL_MEDIA_BYTES + 1))
            return samples, audio

    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    run = tmp_path / "run-oversized"
    run.mkdir()
    with pytest.raises(ValueError, match="5 MiB low-bandwidth payload limit"):
        analyze_teacher_media(
            client=FakeMediaClient(),
            source=source,
            run_dir=run,
            title="Test demo",
            domain="test",
            learner_goal="Finish safely",
            constraints=[],
            speech_mode=SpeechMode.SILENT,
            extractor=OversizedExtractor(),
        )


def test_spoken_media_prompt_preserves_decision_rules_not_generic_summary() -> None:
    assert "comparison, recommendation, condition, and counterexample" in MEDIA_ANALYSIS_SYSTEM
    assert 'generic phrase such as "discusses the options."' in MEDIA_ANALYSIS_SYSTEM
