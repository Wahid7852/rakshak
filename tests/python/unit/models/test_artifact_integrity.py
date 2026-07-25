# Tests the SHA-256 manifest check that guards pretrained model artifacts.
import json

import pytest

from backend.engine.models.artifact_integrity import (
    ArtifactIntegrityError,
    is_lfs_pointer,
    sha256_file,
    update_manifest,
    verify,
)


def test_verify_passes_for_untampered_artifact(tmp_path, monkeypatch):
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"trusted model bytes")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"model.joblib": sha256_file(artifact)}))

    import backend.engine.models.artifact_integrity as integrity_module
    monkeypatch.setattr(integrity_module, "MANIFEST_PATH", manifest_path)

    verify(artifact)  # should not raise


def test_verify_rejects_tampered_artifact(tmp_path, monkeypatch):
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"trusted model bytes")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"model.joblib": sha256_file(artifact)}))

    import backend.engine.models.artifact_integrity as integrity_module
    monkeypatch.setattr(integrity_module, "MANIFEST_PATH", manifest_path)

    artifact.write_bytes(b"attacker-swapped bytes")
    with pytest.raises(ArtifactIntegrityError):
        verify(artifact)


def test_verify_rejects_artifact_missing_from_manifest(tmp_path, monkeypatch):
    artifact = tmp_path / "unlisted.joblib"
    artifact.write_bytes(b"never hashed")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({}))

    import backend.engine.models.artifact_integrity as integrity_module
    monkeypatch.setattr(integrity_module, "MANIFEST_PATH", manifest_path)

    with pytest.raises(ArtifactIntegrityError):
        verify(artifact)


def test_update_manifest_records_current_hash(tmp_path, monkeypatch):
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"v1")
    manifest_path = tmp_path / "manifest.json"

    import backend.engine.models.artifact_integrity as integrity_module
    monkeypatch.setattr(integrity_module, "MANIFEST_PATH", manifest_path)

    update_manifest(artifact)
    verify(artifact)  # passes right after update_manifest

    artifact.write_bytes(b"v2")
    with pytest.raises(ArtifactIntegrityError):
        verify(artifact)  # stale entry rejects the new content

    update_manifest(artifact)
    verify(artifact)  # passes again after re-recording


def test_shipped_manifest_matches_current_artifacts():
    """Drift check, same idea as test_schema_hash.py: catches a forgotten
    update_manifest() call after retraining. Skips instead of failing when the
    artifacts are git-lfs pointers rather than real content - that's a checkout
    setting (CI's actions/checkout runs with lfs: false), not drift, and
    diffing a pointer's hash against the real content's hash is never going to
    match no matter how current the manifest is."""
    from backend.engine.models.artifact_integrity import MANIFEST_PATH, load_manifest

    manifest = load_manifest()
    assert manifest, "manifest.json is empty or missing"
    for name, expected_hash in manifest.items():
        artifact_path = MANIFEST_PATH.parent / name
        assert artifact_path.exists(), f"{name} listed in manifest but missing on disk"
        if is_lfs_pointer(artifact_path):
            pytest.skip(f"{name} is an unfetched git-lfs pointer, not real content (checkout ran with lfs: false)")
        assert sha256_file(artifact_path) == expected_hash, f"{name} drifted from manifest.json"
