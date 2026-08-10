"""Evidence storage with strict test-data and media boundaries."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Literal, Protocol
from uuid import uuid4

from .models import EvidenceRef

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_EVIDENCE_BYTES = 5 * 1024 * 1024
NAMESPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")


class EvidenceStore(Protocol):
    def put(
        self,
        data: bytes,
        *,
        content_type: str,
        source: Literal["teacher", "learner", "test"],
    ) -> EvidenceRef: ...

    def get(self, evidence: EvidenceRef) -> bytes: ...


def validate_evidence(data: bytes, content_type: str) -> None:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("evidence must be JPEG, PNG, or WebP")
    if not data:
        raise ValueError("evidence cannot be empty")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise ValueError("evidence exceeds the 5 MiB limit")
    if content_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("evidence content does not match image/png")
    if content_type == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("evidence content does not match image/jpeg")
    if content_type == "image/webp" and not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        raise ValueError("evidence content does not match image/webp")


class InMemoryEvidenceStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(
        self,
        data: bytes,
        *,
        content_type: str,
        source: Literal["teacher", "learner", "test"],
    ) -> EvidenceRef:
        validate_evidence(data, content_type)
        evidence_id = f"evidence-{uuid4().hex}"
        object_name = f"memory/{evidence_id}{ALLOWED_IMAGE_TYPES[content_type]}"
        self._objects[object_name] = data
        return EvidenceRef(
            evidence_id=evidence_id,
            object_name=object_name,
            content_type=content_type,
            sha256=sha256(data).hexdigest(),
            size_bytes=len(data),
            source=source,
        )

    def get(self, evidence: EvidenceRef) -> bytes:
        try:
            data = self._objects[evidence.object_name]
        except KeyError as exc:
            raise LookupError(f"evidence {evidence.evidence_id!r} was not found") from exc
        if sha256(data).hexdigest() != evidence.sha256:
            raise ValueError("evidence checksum mismatch")
        return data


class CloudStorageEvidenceStore:
    """Bucket object I/O restricted to a unique test-data namespace."""

    def __init__(self, *, bucket_name: str, namespace: str, client=None) -> None:
        if not NAMESPACE_PATTERN.fullmatch(namespace):
            raise ValueError("invalid test-data namespace")
        if bucket_name != "byfeel-evidence-775995990601":
            raise ValueError("only the approved ByFeel evidence bucket is allowed")
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._bucket = client.bucket(bucket_name)
        self._prefix = f"test-data/{namespace}/"

    def put(
        self,
        data: bytes,
        *,
        content_type: str,
        source: Literal["teacher", "learner", "test"],
    ) -> EvidenceRef:
        validate_evidence(data, content_type)
        evidence_id = f"evidence-{uuid4().hex}"
        object_name = f"{self._prefix}{evidence_id}{ALLOWED_IMAGE_TYPES[content_type]}"
        blob = self._bucket.blob(object_name)
        blob.upload_from_string(data, content_type=content_type, if_generation_match=0)
        return EvidenceRef(
            evidence_id=evidence_id,
            object_name=object_name,
            content_type=content_type,
            sha256=sha256(data).hexdigest(),
            size_bytes=len(data),
            source=source,
        )

    def get(self, evidence: EvidenceRef) -> bytes:
        if not evidence.object_name.startswith(self._prefix):
            raise ValueError("evidence object is outside the configured test namespace")
        data = self._bucket.blob(evidence.object_name).download_as_bytes()
        if sha256(data).hexdigest() != evidence.sha256:
            raise ValueError("evidence checksum mismatch")
        return data
