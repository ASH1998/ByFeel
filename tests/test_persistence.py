from __future__ import annotations

from copy import deepcopy

import pytest
from byfeel.evidence import CloudStorageEvidenceStore, InMemoryEvidenceStore
from byfeel.firestore_repository import FirestoreRepository
from byfeel.models import Procedure, ProcedureStep
from byfeel.repositories import ConflictError

PNG = b"\x89PNG\r\n\x1a\nbyfeel-test-image"


class FakeSnapshot:
    def __init__(self, value: dict | None) -> None:
        self._value = deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return deepcopy(self._value)


class FakeDocument:
    def __init__(self, client, path: str) -> None:
        self.client = client
        self.path = path

    def collection(self, name: str):
        return FakeCollection(self.client, f"{self.path}/{name}")

    def get(self):
        return FakeSnapshot(self.client.values.get(self.path))

    def set(self, value):
        self.client.values[self.path] = deepcopy(value)

    def create(self, value):
        if self.path in self.client.values:
            raise RuntimeError("already exists")
        self.client.values[self.path] = deepcopy(value)


class FakeCollection:
    def __init__(self, client, path: str) -> None:
        self.client = client
        self.path = path

    def document(self, name: str):
        return FakeDocument(self.client, f"{self.path}/{name}")

    def stream(self):
        depth = self.path.count("/") + 1
        return [
            FakeSnapshot(value)
            for path, value in self.client.values.items()
            if path.startswith(f"{self.path}/") and path.count("/") == depth
        ]


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.values: dict[str, dict] = {}

    def collection(self, name: str):
        return FakeCollection(self, name)


class FakeBlob:
    def __init__(self, bucket, name: str) -> None:
        self.bucket = bucket
        self.name = name

    def upload_from_string(self, data, *, content_type, if_generation_match):
        assert if_generation_match == 0
        if self.name in self.bucket.values:
            raise RuntimeError("overwrite attempted")
        self.bucket.values[self.name] = (bytes(data), content_type)

    def download_as_bytes(self):
        return self.bucket.values[self.name][0]


class FakeBucket:
    def __init__(self) -> None:
        self.values: dict[str, tuple[bytes, str]] = {}

    def blob(self, name: str):
        return FakeBlob(self, name)


class FakeStorageClient:
    def __init__(self) -> None:
        self.fake_bucket = FakeBucket()

    def bucket(self, name: str):
        assert name == "byfeel-evidence-775995990601"
        return self.fake_bucket


def sample_procedure() -> Procedure:
    return Procedure(
        id="persisted-fold",
        title="Persisted fold",
        domain="test",
        learner_goal="Verify persistence",
        steps=[ProcedureStep(step_id="step-1", order=1, action="Fold", confidence=1)],
    )


def test_firestore_repository_is_scoped_to_test_namespace() -> None:
    client = FakeFirestoreClient()
    repository = FirestoreRepository(namespace="pytest-run", client=client)
    procedure = sample_procedure()
    repository.save_procedure(procedure)

    expected_path = "byfeel_test_runs/pytest-run/procedures/persisted-fold"
    assert set(client.values) == {expected_path}
    assert repository.get_procedure(procedure.id).id == procedure.id
    updated = procedure.model_copy(update={"title": "Updated fold"})
    repository.save_procedure(updated, expected_updated_at=procedure.updated_at.isoformat())
    assert repository.get_procedure(procedure.id).title == "Updated fold"
    with pytest.raises(ConflictError):
        repository.save_procedure(procedure, expected_updated_at="stale")
    assert not hasattr(repository, "delete_procedure")


def test_cloud_evidence_is_unique_test_data_and_checksum_verified() -> None:
    client = FakeStorageClient()
    store = CloudStorageEvidenceStore(
        bucket_name="byfeel-evidence-775995990601",
        namespace="pytest-run",
        client=client,
    )
    reference = store.put(PNG, content_type="image/png", source="test")
    assert reference.object_name.startswith("test-data/pytest-run/evidence-")
    assert store.get(reference) == PNG
    assert not hasattr(store, "delete")


def test_evidence_validation_rejects_spoofed_or_oversized_media() -> None:
    store = InMemoryEvidenceStore()
    with pytest.raises(ValueError, match="does not match"):
        store.put(b"not a png", content_type="image/png", source="test")
    with pytest.raises(ValueError, match="JPEG, PNG, or WebP"):
        store.put(PNG, content_type="text/plain", source="test")
