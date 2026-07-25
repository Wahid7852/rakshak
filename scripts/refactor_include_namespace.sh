#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$PWD}"
APPLY="${APPLY:-}"
INC="$ROOT/include"
DEST="$INC/rakshak"

if [[ ! -d "$INC" ]]; then echo "[ERROR] include/ not found"; exit 2; fi
mkdir -p "$DEST"

# Move
shopt -s dotglob
for e in "$INC"/*; do
  name="$(basename "$e")"
  [[ "$name" == "rakshak" ]] && continue
  echo "[MOVE] $e -> $DEST/$name"
  if [[ "${2:-}" == "--apply" || "$APPLY" == "1" ]]; then
    mkdir -p "$DEST/$name"
    if [[ -d "$e" ]]; then
      mv "$e"/* "$DEST/$name"/ 2>/dev/null || true
      rmdir "$e" 2>/dev/null || true
    else
      mv "$e" "$DEST/$name"
    fi
  fi
done

# Build list of moved headers
mapfile -d '' HEADERS < <(find "$DEST" -type f \( -name '*.h' -o -name '*.hpp' -o -name '*.hh' -o -name '*.ipp' \) -print0)
declare -a OLDREL=()
for f in "${HEADERS[@]}"; do
  rel="${f#$INC/}"; rel="${rel#rakshak/}"
  OLDREL+=("$rel")
done

# Rewrite includes
rewrite() {
  local file="$1"
  local tmp; tmp="$(mktemp)"
  local changed=0
  while IFS= read -r line; do
    if [[ "$line" =~ ^[[:space:]]*#include[[:space:]]*[\"\<]([^\"\>]+)[\"\>].*$ ]]; then
      inc="${BASH_REMATCH[1]}"
      [[ "$inc" == rakshak/* ]] && { echo "$line"; continue; }
      for old in "${OLDREL[@]}"; do
        if [[ "$inc" == "$old" ]]; then
          line="${line/$inc/rakshak\/$inc}"; changed=1; break
        fi
      done
    fi
    echo "$line"
  done < "$file" > "$tmp"
  if [[ "${2:-}" == "--apply" || "$APPLY" == "1" ]]; then
    [[ $changed -eq 1 ]] && mv "$tmp" "$file" || rm -f "$tmp"
  else
    rm -f "$tmp"
  fi
}

while IFS= read -r -d '' f; do
  rewrite "$f" "$2"
done < <(find "$ROOT" -type f \( -name '*.c' -o -name '*.cc' -o -name '*.cpp' -o -name '*.cxx' -o -name '*.h' -o -name '*.hh' -o -name '*.hpp' -o -name '*.ipp' -o -name 'CMakeLists.txt' -o -name '*.cmake' \) -print0)

echo "[DONE] (use --apply to write changes)"
