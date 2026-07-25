# Tests that RAKSHAK_MODEL_STATE_DIR redirects the online-learning checkpoint
# paths, needed for Docker deployments where the installed package tree isn't
# writable by the runtime user.
from pathlib import Path

from backend.engine.models.classical.hst import _resolve_state_path as hst_resolve_state_path
from backend.engine.models.classical.ngram import _resolve_state_path as ngram_resolve_state_path


def test_hst_state_path_honors_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RAKSHAK_MODEL_STATE_DIR", str(tmp_path))
    assert hst_resolve_state_path("hst_state.joblib") == tmp_path / "hst_state.joblib"


def test_ngram_state_path_honors_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RAKSHAK_MODEL_STATE_DIR", str(tmp_path))
    assert ngram_resolve_state_path("ngram_state.joblib") == tmp_path / "ngram_state.joblib"


def test_state_path_defaults_without_override(monkeypatch):
    monkeypatch.delenv("RAKSHAK_MODEL_STATE_DIR", raising=False)
    default_dir = Path("/some/default/dir")
    assert hst_resolve_state_path("hst_state.joblib", default_dir) == default_dir / "hst_state.joblib"
