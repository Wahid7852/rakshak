# Tests features behavior.
import pytest

from src.features import entropy, extract_features_for_file


def test_entropy_all_equal_bytes(tmp_path):
    f = tmp_path / "all_zero.bin"
    f.write_bytes(bytes([0]) * 1024)
    ent = entropy(f.read_bytes())
    assert ent == pytest.approx(0.0, abs=1e-9)


def test_entropy_varied_bytes(tmp_path):
    f = tmp_path / "varied.bin"
    data = bytes(range(256)) * 4
    f.write_bytes(data)
    ent = entropy(f.read_bytes())
    assert ent > 0.0


def test_extract_features_file(tmp_path):
    f = tmp_path / "sample.bin"
    f.write_bytes(b"AAAAAAAABBBBBBBBCCCCCCCC")
    feats = extract_features_for_file(f)
    assert "file" in feats and feats["file"] == "sample.bin"
    assert "entropy" in feats