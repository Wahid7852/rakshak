#!/usr/bin/env bash
# Appends lines from samples/sample-auth.log to a target file every couple of
# seconds, so you can point Settings -> Log path at the target and watch
# RAKSHAK's Log Analysis page tail it live. Ctrl+C to stop.
#
# Usage: samples/simulate_tail.sh /path/to/watched.log
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/samples/sample-auth.log"
TARGET="${1:?usage: simulate_tail.sh /path/to/watched.log}"

touch "$TARGET"
echo "Appending lines from $SOURCE to $TARGET every 2s. Ctrl+C to stop."
while IFS= read -r line; do
    echo "$line" >> "$TARGET"
    sleep 2
done < "$SOURCE"
