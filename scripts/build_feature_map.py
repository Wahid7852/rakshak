# flake8: noqa: E501
from __future__ import annotations
import json, hashlib, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "schema.json"
EMB_PATH = ROOT / "config" / "embedding.yaml"
OUT_PATH = ROOT / "config" / "feature_map.json"

def canonical_hash(obj) -> str:
    c = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(c).hexdigest()

def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    feats = list(schema["features"])
    fmap = {name: idx for idx, name in enumerate(feats)}
    emb = yaml.safe_load(EMB_PATH.read_text(encoding="utf-8")) if EMB_PATH.exists() else {}
    out = {
        "schema_version": schema.get("schema_version"),
        "schema_hash": canonical_hash(schema),
        "embedding": emb,
        "embedding_hash": canonical_hash(emb) if emb else "",
        "feature_order": feats,
        "feature_index": fmap
    }
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[build_feature_map] wrote {OUT_PATH} with {len(feats)} features")

if __name__ == "__main__":
    main()
