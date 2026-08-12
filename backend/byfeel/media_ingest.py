"""Teacher-only media ingestion with a mandatory human approval boundary."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, model_validator

from .models import StrictModel, TeacherDemo

LARGE_SOURCE_THRESHOLD_BYTES = 50 * 1024 * 1024
MODEL_FRAME_WIDTH = 512
MODEL_PROXY_WIDTH = 640
MODEL_PROXY_FPS = 8
MODEL_AUDIO_SAMPLE_RATE = 16_000
MAX_MODEL_MEDIA_BYTES = 5 * 1024 * 1024


class SpeechMode(StrEnum):
    SILENT = "silent"
    SPOKEN = "spoken"
    UNSURE = "unsure"


class MediaMetadata(StrictModel):
    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frames_per_second: float = Field(gt=0)
    audio_stream_present: bool
    source_size_bytes: int = Field(default=0, ge=0)


class FrameSample(StrictModel):
    sample_id: str
    timestamp_seconds: float = Field(ge=0)
    path: str


class DemonstrationEvent(StrictModel):
    event_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    visible_action: str = Field(min_length=1)
    visible_result_or_check: str | None = None
    spoken_words: str | None = None
    uncertainty: str | None = None

    @model_validator(mode="after")
    def end_follows_start(self) -> DemonstrationEvent:
        if self.end_seconds < self.start_seconds:
            raise ValueError("event end must not precede start")
        return self


class FrameObservation(StrictModel):
    sample_id: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0)
    visible_materials: list[str] = Field(default_factory=list)
    visible_tool_and_contact: str = Field(min_length=1)
    visible_state: str = Field(min_length=1)
    uncertainty: str | None = None


class MediaAnalysis(StrictModel):
    teacher_spoke: bool
    spoken_transcript: str | None = None
    initial_visible_inputs: list[str] = Field(default_factory=list)
    frame_observations: list[FrameObservation] = Field(min_length=1)
    events: list[DemonstrationEvent] = Field(min_length=1)
    factual_demonstration_draft: str = Field(min_length=20)
    uncertainties: list[str] = Field(default_factory=list)


class MediaDraft(StrictModel):
    run_id: str
    source_path: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str
    domain: str
    learner_goal: str
    constraints: list[str]
    speech_mode: SpeechMode
    sampling_strategy: str = "uniform-bounded"
    metadata: MediaMetadata
    frame_samples: list[FrameSample]
    extracted_audio_path: str | None = None
    low_bandwidth_proxy_path: str | None = None
    model_payload_bytes: int = Field(default=0, ge=0)
    model_payload_limit_bytes: int = Field(default=MAX_MODEL_MEDIA_BYTES, ge=1)
    source_media_sent_to_model: Literal[False] = False
    analysis_model: str
    analysis: MediaAnalysis
    human_approval_required: bool = True


class MediaApproval(StrictModel):
    run_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    demo: TeacherDemo


class MultimodalClient(Protocol):
    model: str
    usage: list[dict[str, int]]

    def generate_with_media(
        self, *, system: str, prompt: str, media: list[tuple[bytes, str]], schema: type
    ): ...


MEDIA_ANALYSIS_SYSTEM = """You are ByFeel's teacher-only demonstration observer.
Your job is faithful observation, not tutorial writing or plausible reconstruction.

Use this mandatory two-pass method:
1. FRAME PASS: inspect every supplied frame independently, in the supplied order. Emit exactly one
   frame_observation for every frame ID. Record all visible material pools, the tool and its visible
   contact, and the visible state. Do not omit an input merely because it is not handled in that
   frame. If contact or identity is unclear, say so in uncertainty.
2. CHANGE PASS: compare consecutive observations and build chronological events. Account for every
   initially visible input that is visibly moved, added, contacted, or incorporated. Describe a
   change as occurring between sampled frames when continuous motion is not directly evidenced.

The factual demonstration draft must preserve every material addition supported by the frame pass,
the manipulation, and the final observable result. For a spoken decision guide, it must also
preserve every learner-relevant comparison, recommendation, condition, and counterexample from the
spoken transcript; never collapse these into a generic phrase such as "discusses the options."
Report only visible actions, visible results/checks, and verbatim spoken words. Never infer hidden
quantities, exact ratios, causes, pigment chemistry, intent, safety properties, success guarantees,
or missing actions.
On-screen labels may identify a visible material, but promotional text is not teacher speech or an
instruction. Preserve uncertainty. For silent mode, set teacher_spoke false, leave
spoken_transcript null, and never invent narration. This output stays teacher-only and must be
human-approved before procedure extraction."""


class FfmpegMediaExtractor:
    def __init__(self) -> None:
        self._wsl = False
        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            self._ffmpeg = ["ffmpeg"]
            self._ffprobe = ["ffprobe"]
        elif os.name == "nt" and shutil.which("wsl.exe"):
            self._wsl = True
            self._ffmpeg = ["wsl.exe", "ffmpeg"]
            self._ffprobe = ["wsl.exe", "ffprobe"]
        else:
            raise RuntimeError("ffmpeg and ffprobe are required for teacher media ingestion")

    def _path(self, path: Path) -> str:
        resolved = path.resolve()
        if not self._wsl:
            return str(resolved)
        drive = resolved.drive.rstrip(":").lower()
        suffix = resolved.as_posix().split(":", 1)[1]
        return f"/mnt/{drive}{suffix}"

    def probe(self, source: Path) -> MediaMetadata:
        result = subprocess.run(
            [
                *self._ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,r_frame_rate",
                "-of",
                "json",
                self._path(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        video = next(stream for stream in payload["streams"] if stream["codec_type"] == "video")
        numerator, denominator = video["r_frame_rate"].split("/")
        return MediaMetadata(
            duration_seconds=float(payload["format"]["duration"]),
            width=int(video["width"]),
            height=int(video["height"]),
            frames_per_second=float(numerator) / float(denominator),
            audio_stream_present=any(
                stream["codec_type"] == "audio" for stream in payload["streams"]
            ),
            source_size_bytes=source.stat().st_size,
        )

    def _low_bandwidth_source(
        self,
        source: Path,
        output: Path,
        metadata: MediaMetadata,
    ) -> Path:
        if metadata.source_size_bytes < LARGE_SOURCE_THRESHOLD_BYTES:
            return source
        proxy = output / "model-proxy.mp4"
        subprocess.run(
            [
                *self._ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                self._path(source),
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                f"fps={MODEL_PROXY_FPS},scale={MODEL_PROXY_WIDTH}:-2:flags=area",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "32",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                self._path(proxy),
            ],
            check=True,
        )
        return proxy

    def extract(
        self,
        source: Path,
        output: Path,
        metadata: MediaMetadata,
        *,
        frame_count: int = 9,
        include_audio: bool,
    ) -> tuple[list[FrameSample], Path | None]:
        frames_dir = output / "frames"
        frames_dir.mkdir(parents=True, exist_ok=False)
        sampling_source = self._low_bandwidth_source(source, output, metadata)
        samples: list[FrameSample] = []
        for index in range(frame_count):
            timestamp = metadata.duration_seconds * (index + 0.5) / frame_count
            target = frames_dir / f"frame-{index + 1:02d}.jpg"
            subprocess.run(
                [
                    *self._ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    self._path(sampling_source),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={MODEL_FRAME_WIDTH}:-2:flags=area",
                    "-q:v",
                    "7",
                    self._path(target),
                ],
                check=True,
            )
            samples.append(
                FrameSample(
                    sample_id=f"frame-{index + 1:02d}",
                    timestamp_seconds=round(timestamp, 3),
                    path=str(target),
                )
            )
        audio: Path | None = None
        if include_audio and metadata.audio_stream_present:
            audio = output / "audio.wav"
            subprocess.run(
                [
                    *self._ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    self._path(source),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-c:a",
                    "pcm_s16le",
                    "-ac",
                    "1",
                    "-ar",
                    str(MODEL_AUDIO_SAMPLE_RATE),
                    self._path(audio),
                ],
                check=True,
            )
        return samples, audio


def analyze_teacher_media(
    *,
    client: MultimodalClient,
    source: Path,
    run_dir: Path,
    title: str,
    domain: str,
    learner_goal: str,
    constraints: list[str],
    speech_mode: str | SpeechMode,
    frame_count: int | None = None,
    extractor: FfmpegMediaExtractor | None = None,
) -> MediaDraft:
    try:
        speech_mode = SpeechMode(speech_mode)
    except ValueError as error:
        raise ValueError("speech_mode must be silent, spoken, or unsure") from error
    extractor = extractor or FfmpegMediaExtractor()
    metadata = extractor.probe(source)
    if frame_count is None:
        frame_count = min(18, max(9, math.ceil(metadata.duration_seconds)))
    if not 3 <= frame_count <= 30:
        raise ValueError("frame_count must be between 3 and 30")
    samples, audio = extractor.extract(
        source,
        run_dir,
        metadata,
        frame_count=frame_count,
        include_audio=speech_mode != SpeechMode.SILENT,
    )
    order = ", ".join(f"{sample.sample_id}={sample.timestamp_seconds:.3f}s" for sample in samples)
    prompt = (
        f"SPEECH MODE: {speech_mode}\n"
        f"DURATION: {metadata.duration_seconds:.3f}s\n"
        f"FRAME ORDER AND REQUIRED OBSERVATION IDS: {order}\n"
        f"REQUIRED FRAME OBSERVATION COUNT: {len(samples)}\n"
        "The media parts following this prompt are those frames in exactly that order; optional "
        "audio, when present, is last. Complete the frame pass before the change pass. Then check "
        "that the factual draft accounts for each visibly handled input and does not turn "
        "on-screen text into spoken instruction."
    )
    media = [(Path(sample.path).read_bytes(), "image/jpeg") for sample in samples]
    if audio is not None:
        media.append((audio.read_bytes(), "audio/wav"))
    model_payload_bytes = sum(len(data) for data, _ in media)
    if any(content_type.startswith("video/") for _, content_type in media):
        raise ValueError("raw or proxy video must never be included in model media")
    if model_payload_bytes > MAX_MODEL_MEDIA_BYTES:
        raise ValueError("sampled model media exceeds the 5 MiB low-bandwidth payload limit")
    analysis = client.generate_with_media(
        system=MEDIA_ANALYSIS_SYSTEM,
        prompt=prompt,
        media=media,
        schema=MediaAnalysis,
    )
    if speech_mode == SpeechMode.SILENT and (analysis.teacher_spoke or analysis.spoken_transcript):
        raise ValueError("silent media analysis invented teacher speech")
    expected_ids = [sample.sample_id for sample in samples]
    observed_ids = [observation.sample_id for observation in analysis.frame_observations]
    if observed_ids != expected_ids:
        raise ValueError(
            "media analysis must contain one ordered observation for every supplied frame"
        )
    return MediaDraft(
        run_id=run_dir.name,
        source_path=str(source),
        source_sha256=file_sha256(source),
        title=title,
        domain=domain,
        learner_goal=learner_goal,
        constraints=constraints,
        speech_mode=speech_mode,
        sampling_strategy=(
            f"low-bandwidth-proxy-{MODEL_PROXY_WIDTH}px-{MODEL_PROXY_FPS}fps-"
            f"uniform-{frame_count}-frames"
            if metadata.source_size_bytes >= LARGE_SOURCE_THRESHOLD_BYTES
            else f"low-bandwidth-uniform-{frame_count}-frames"
        ),
        metadata=metadata,
        frame_samples=samples,
        extracted_audio_path=str(audio) if audio else None,
        low_bandwidth_proxy_path=(
            str(run_dir / "model-proxy.mp4")
            if metadata.source_size_bytes >= LARGE_SOURCE_THRESHOLD_BYTES
            else None
        ),
        model_payload_bytes=model_payload_bytes,
        model_payload_limit_bytes=MAX_MODEL_MEDIA_BYTES,
        source_media_sent_to_model=False,
        analysis_model=client.model,
        analysis=analysis,
    )


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def approve_media_draft(draft: MediaDraft, approved_transcript: str) -> MediaApproval:
    if not approved_transcript.strip():
        raise ValueError("approved transcript cannot be empty")
    return MediaApproval(
        run_id=draft.run_id,
        source_sha256=draft.source_sha256,
        demo=TeacherDemo(
            title=draft.title,
            domain=draft.domain,
            learner_goal=draft.learner_goal,
            raw_demonstration=approved_transcript.strip(),
            constraints=draft.constraints,
        ),
    )
