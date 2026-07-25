# Verifies pretrained model artifacts against a committed SHA-256 manifest.
from __future__ import annotations
import hashlib, json
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "artifacts" / "manifest.json"


class ArtifactIntegrityError(Exception):
    """Raised when an artifact's hash doesn't match the committed manifest."""


def is_lfs_pointer(path: Path) -> bool:
    """Whether path is an unfetched git-lfs pointer file rather than real content.

    These artifacts are lfs-tracked (see .gitattributes); a checkout done with
    `lfs: false` (CI's default) leaves a ~130-byte text pointer on disk instead
    of the real binary. verify() correctly treats that as a hash mismatch - a
    pointer isn't the artifact - but callers that specifically want to tell
    "not fetched" apart from "tampered" can check this first.
    """
    try:
        with open(path, "rb") as f:
            return f.read(100).startswith(b"version https://git-lfs.github.com/spec/v1")
    except OSError:
        return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def update_manifest(path: Path) -> None:
    """Record path's current hash in the manifest. Called by training scripts
    right after writing a new artifact, so retraining doesn't leave the loader
    thinking the fresh artifact is tampered."""
    manifest = load_manifest()
    manifest[path.name] = sha256_file(path)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(path: Path) -> None:
    """Raise ArtifactIntegrityError if path's hash doesn't match the manifest.

    Only covers artifacts actually listed in manifest.json - the online-learning
    checkpoints (hst_state.joblib, ngram_state.joblib) are rewritten by the running
    service itself and deliberately excluded; a static hash would just go stale.
    """
    manifest = load_manifest()
    name = path.name
    if name not in manifest:
        raise ArtifactIntegrityError(f"{name} is not in the artifact manifest")
    actual = sha256_file(path)
    if actual != manifest[name]:
        raise ArtifactIntegrityError(
            f"{name} hash {actual} does not match manifest {manifest[name]}"
        )
