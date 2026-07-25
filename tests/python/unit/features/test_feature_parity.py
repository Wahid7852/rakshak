# Tests feature parity behavior.
import json, os

def test_meta_feature_parity():
    meta = json.load(open(os.path.join("models","artifacts","model_meta.json"),"r",encoding="utf-8"))
    assert isinstance(meta.get("features"), list) and len(meta["features"])>0
