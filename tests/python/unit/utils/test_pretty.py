# Tests JSON pretty-printing utilities.
import json

from src.utils.pretty import load_json, pretty_json


def test_pretty_json_sorts_keys_and_indents():
    text = pretty_json({"b": 1, "a": {"z": 2}}, indent=2)

    assert text.splitlines()[1] == '  "a": {'
    assert json.loads(text) == {"b": 1, "a": {"z": 2}}


def test_load_json_from_file(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text('{"ok": true}', encoding="utf-8")

    assert load_json(path) == {"ok": True}
