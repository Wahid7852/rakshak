# Tests QuarantineManager: round trip, tamper detection, no-data-loss guarantee.
from __future__ import annotations

import json

import pytest

from backend.engine.quarantine import QuarantineManager


@pytest.fixture
def qm(tmp_path):
    return QuarantineManager(tmp_path / "quarantine")


def test_none_falls_back_to_default_dir(tmp_path, monkeypatch):
    import backend.engine.quarantine as quarantine_module

    fake_default = tmp_path / "default-quarantine"
    monkeypatch.setattr(quarantine_module, "DEFAULT_QUARANTINE_DIR", fake_default)

    qm = QuarantineManager(None)

    assert qm.dir == fake_default
    assert fake_default.exists()


def test_quarantine_removes_original_and_stores_encrypted_copy(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    sample.write_bytes(b"malicious payload")

    entry = qm.quarantine_file(sample, reason="test")

    assert entry is not None
    assert not sample.exists()
    enc_path = qm.dir / entry.quarantine_file
    assert enc_path.exists()
    assert b"malicious" not in enc_path.read_bytes()  # actually encrypted, not just copied


def test_quarantine_nonexistent_file_returns_none(qm, tmp_path):
    assert qm.quarantine_file(tmp_path / "does_not_exist.bin", reason="test") is None


def test_restore_round_trips_original_content(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    original = b"malicious payload with real content"
    sample.write_bytes(original)

    entry = qm.quarantine_file(sample, reason="test")
    assert qm.restore_file(entry.quarantine_id) is True
    assert sample.read_bytes() == original


def test_restore_unknown_id_returns_false(qm):
    assert qm.restore_file("not-a-real-id") is False


def test_restore_refuses_to_overwrite_existing_file(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    sample.write_bytes(b"original")
    entry = qm.quarantine_file(sample, reason="test")

    sample.write_bytes(b"something else is here now")
    assert qm.restore_file(entry.quarantine_id) is False


def test_tampered_db_is_rejected_not_trusted(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    sample.write_bytes(b"malicious payload")
    entry = qm.quarantine_file(sample, reason="original-reason")

    # tamper with the on-disk db directly, bypassing the HMAC
    db_path = qm.dir / "quarantine_db.json"
    raw = json.loads(db_path.read_text())
    raw["entries"][entry.quarantine_id]["reason"] = "tampered-reason"
    db_path.write_text(json.dumps(raw))

    # a fresh manager loading this tampered db must not trust it
    qm2 = QuarantineManager(qm.dir)
    assert qm2.list_quarantined() == []


def test_remove_file_deletes_entry_and_encrypted_blob(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    sample.write_bytes(b"malicious payload")
    entry = qm.quarantine_file(sample, reason="test")
    enc_path = qm.dir / entry.quarantine_file

    assert qm.remove_file(entry.quarantine_id) is True

    assert not enc_path.exists()
    assert qm.list_quarantined() == []


def test_remove_file_unknown_id_returns_false(qm):
    assert qm.remove_file("not-a-real-id") is False


def test_restore_rejects_tampered_encrypted_blob(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    sample.write_bytes(b"malicious payload")
    entry = qm.quarantine_file(sample, reason="test")

    enc_path = qm.dir / entry.quarantine_file
    enc_path.write_bytes(b"not a real fernet token")

    assert qm.restore_file(entry.quarantine_id) is False
    # tampering shouldn't silently drop the record - it stays listed until
    # someone investigates, rather than vanishing along with the unrecoverable blob
    assert len(qm.list_quarantined()) == 1
    assert qm.is_quarantined(sample) is True


def test_restore_to_explicit_dest_path(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    original = b"malicious payload with real content"
    sample.write_bytes(original)
    entry = qm.quarantine_file(sample, reason="test")

    dest = tmp_path / "restored" / "evil-restored.bin"
    assert qm.restore_file(entry.quarantine_id, dest_path=dest) is True
    assert dest.read_bytes() == original
    assert not sample.exists()  # restored to dest_path, not the original location


def test_list_and_is_quarantined(qm, tmp_path):
    sample = tmp_path / "evil.bin"
    sample.write_bytes(b"malicious payload")
    qm.quarantine_file(sample, reason="test")

    assert len(qm.list_quarantined()) == 1
    assert qm.is_quarantined(sample) is True
    assert qm.is_quarantined(tmp_path / "unrelated.bin") is False
