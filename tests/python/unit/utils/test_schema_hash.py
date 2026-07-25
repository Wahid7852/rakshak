# Tests schema hash behavior.

import json, hashlib, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
SCHEMA_PATH = ROOT / "configs" / "schema.json"
SCHEMA_HASH_PATH = ROOT / "configs" / "schema_hash.txt"

def canonical_hash(obj) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def test_schema_version_and_hash():
    assert SCHEMA_PATH.exists(), "configs/schema.json missing"
    cfg = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "schema_version" in cfg and isinstance(cfg["schema_version"], str)
    assert "features" in cfg and isinstance(cfg["features"], list) and len(cfg["features"]) > 0
    h = canonical_hash(cfg)
    recorded = SCHEMA_HASH_PATH.read_text(encoding="utf-8").strip()
    assert h == recorded, "Schema changed—bump schema_version and update schema_hash.txt"
