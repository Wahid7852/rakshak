# Runs developer script support for refactor include namespace.
#!/usr/bin/env python3
# (See in-code docstring for usage)
import argparse, os, re, shutil, sys
from pathlib import Path

SRC_EXTS = {".c",".cc",".cxx",".cpp",".h",".hh",".hpp",".ipp",".mm",".m"}
CMAKE_FILES = {"CMakeLists.txt"}

def list_files(base: Path):
    for p in base.rglob("*"):
        if p.is_file():
            yield p

def main():
    import textwrap
    parser = argparse.ArgumentParser(description="Move headers from include/ -> include/rakshak/ and rewrite #include lines.")
    parser.add_argument("--root", default=".", help="Repo root containing include/")
    parser.add_argument("--apply", action="store_true", help="Write changes (otherwise dry-run)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    include_root = root / "include"
    dest_root = include_root / "rakshak"
    if not include_root.exists():
        print(f"[ERROR] {include_root} not found"); return 2

    moved_map = {}  # old (rel to include/) -> new ("rakshak/<old>")

    # build move plan
    for child in include_root.iterdir():
        if child.name == "rakshak":
            continue
        if child.is_dir():
            for p in child.rglob("*"):
                if p.is_file() and p.suffix in (".h",".hpp",".hh",".ipp"):
                    rel = p.relative_to(include_root).as_posix()
                    moved_map[rel] = f"rakshak/{rel}"
        elif child.is_file() and child.suffix in (".h",".hpp",".hh",".ipp"):
            rel = child.relative_to(include_root).as_posix()
            moved_map[rel] = f"rakshak/{rel}"

    if moved_map:
        print("[PLAN] Move headers:")
        for k in sorted(moved_map.keys()):
            print("  -", k, "->", moved_map[k])
    else:
        print("[INFO] No headers to move (maybe already under include/rakshak).")

    # move
    if args.apply and moved_map:
        dest_root.mkdir(parents=True, exist_ok=True)
        for child in include_root.iterdir():
            if child.name == "rakshak":
                continue
            target = dest_root / child.name
            if child.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                for p in child.iterdir():
                    shutil.move(str(p), str(target / p.name))
                try: child.rmdir()
                except OSError: pass
            else:
                shutil.move(str(child), str(target))

    # rewrite includes
    rewrite_keys = set(moved_map.keys())
    # also allow basenames like MainWindow.h
    for k in list(rewrite_keys):
        if "/" not in k: rewrite_keys.add(k)

    inc_re = re.compile(r'^(?P<lead>\s*#\s*include\s*[<"])(?P<path>[^">]+)(?P<trail>[>"].*)$')
    changed = []
    scanned = 0

    for p in list_files(root):
        if p.suffix not in SRC_EXTS and p.name not in CMAKE_FILES and p.suffix != ".cmake":
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        orig = txt
        if p.suffix in SRC_EXTS:
            def repl(m):
                path = m.group("path").replace("\\","/")
                if path.startswith("rakshak/"): return m.group(0)
                if path in rewrite_keys:
                    return f'{m.group("lead")}rakshak/{path}{m.group("trail")}'
                return m.group(0)
            txt = "\n".join(inc_re.sub(repl, line) for line in txt.splitlines())
        if p.name in CMAKE_FILES or p.suffix == ".cmake":
            for old,new in moved_map.items():
                txt = txt.replace(f"include/{old}", f"include/{new}")
        if txt != orig:
            changed.append(str(p.relative_to(root)))
            if args.apply:
                p.write_text(txt, encoding="utf-8")
        scanned += 1

    print(f"[SUMMARY] scanned {scanned} files")
    if moved_map:
        print(f"[SUMMARY] headers moved: {len(moved_map)}{' (dry-run)' if not args.apply else ''}")
    if changed:
        print(f"[SUMMARY] files updated: {len(changed)}{' (dry-run)' if not args.apply else ''}")
        for c in changed[:20]: print("  -", c)
        if len(changed) > 20: print(f"  ... and {len(changed)-20} more")
    if not args.apply:
        print("[DRY-RUN] Re-run with --apply to write changes.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
