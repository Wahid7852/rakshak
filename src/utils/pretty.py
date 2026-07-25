# Formats JSON data for readable output.
import argparse, json, sys
from pathlib import Path
from typing import Any


def pretty_json(obj: Any, *, indent: int = 2, sort_keys: bool = True) -> str:
    """Return a stable, human-readable JSON string."""
    return json.dumps(obj, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


def load_json(path: Path) -> Any:
    """Load JSON from a file, using stdin when path is '-'."""
    if str(path) == "-":
        return json.load(sys.stdin)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pretty-print a JSON file or stdin")
    parser.add_argument("path", type=Path, help="JSON file path, or '-' for stdin")
    parser.add_argument("--indent", type=int, default=2)
    parser.add_argument("--no-sort", action="store_true", help="Preserve input key order")
    args = parser.parse_args()

    print(pretty_json(load_json(args.path), indent=args.indent, sort_keys=not args.no_sort))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
