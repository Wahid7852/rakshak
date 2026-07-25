# Checks lightweight repository style conventions.
from __future__ import annotations
import argparse, re, sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "build", "generated"}
IMPORT_RE = re.compile(r"^import\s+")


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix in {".py", ".proto"}:
            yield path


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def check_first_line(path: Path, lines: list[str]) -> list[str]:
    if not lines:
        return [f"{path}: empty file needs a first-line purpose comment"]
    offset = 1 if lines[0].startswith("#!") else 0
    if len(lines) <= offset:
        return [f"{path}: empty file needs a first-line purpose comment"]
    first = lines[offset].strip()
    if path.suffix == ".py" and not first.startswith("# "):
        return [f"{path}: first non-shebang line must be a purpose comment starting with '# '"]
    if path.suffix == ".proto" and not first.startswith("// "):
        return [f"{path}: first line must be a purpose comment starting with '// '"]
    return []


def check_imports(path: Path, lines: list[str]) -> list[str]:
    if path.suffix != ".py":
        return []

    errors = []
    previous_plain_import = False
    for lineno, line in enumerate(lines, start=1):
        if IMPORT_RE.match(line):
            if " ," in line or ",  " in line:
                errors.append(f"{path}:{lineno}: compact imports should use ', ' spacing")
            if previous_plain_import:
                errors.append(f"{path}:{lineno}: combine adjacent plain import lines when practical")
            previous_plain_import = True
            continue
        if not line.strip() or line.startswith("#") or not IMPORT_RE.match(line):
            previous_plain_import = False
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check lightweight RAKSHAK style rules")
    parser.parse_args()

    errors = []
    for path in iter_files():
        lines = read_lines(path)
        errors.extend(check_first_line(path, lines))
        errors.extend(check_imports(path, lines))

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("style checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
