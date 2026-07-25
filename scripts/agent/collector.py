#!/usr/bin/env python3
# Local collector agent: tails employee event logs and forwards them to the
# central RAKSHAK node. Runs on the machine being monitored, not on the
# central node - one process per machine, per the "central node + thin
# collector agents" architecture, not "one RAKSHAK per employee".
#
# Pure stdlib (urllib, json) so it has no dependency on the rakshak-backend
# package or a Python virtualenv on the monitored machine - it's the same
# file-tail-then-HTTP-POST shape on Windows or Linux, no OS-specific APIs.
# Real Windows Event Log / USN-journal collection is a documented stretch
# goal, not built here - see hackathon/technical-approach.md.
#
# Usage:
#     python scripts/agent/collector.py --source samples/insider/logs \
#         --server http://127.0.0.1:8080 --api-key dev-key
#
#     # process what's currently on disk and exit, instead of polling forever
#     python scripts/agent/collector.py --source samples/insider/logs/EMP007.jsonl --once
import argparse, json, logging, os, sys, time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

logger = logging.getLogger("rakshak.collector")

DEFAULT_SERVER = "http://127.0.0.1:8080"
DEFAULT_BATCH_SIZE = 50
DEFAULT_INTERVAL_S = 2.0
DEFAULT_TIMEOUT_S = 5.0


class OffsetStore:
    """Tracks how many bytes of each source file this agent has already
    forwarded, so a restart resumes instead of re-sending or dropping events.
    One JSON file, not per-source state files - simple and fine at this scale.
    """

    def __init__(self, path: Path):
        self._path = path
        self._offsets: Dict[str, int] = {}
        if path.exists():
            try:
                self._offsets = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("offset store %s unreadable, starting fresh", path)

    def get(self, source: Path) -> int:
        return self._offsets.get(str(source), 0)

    def set(self, source: Path, offset: int) -> None:
        self._offsets[str(source)] = offset
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._offsets), encoding="utf-8")


def _read_new_lines(path: Path, offsets: OffsetStore) -> tuple[List[str], int]:
    """Returns (new lines, byte offset just past the last complete line read).
    Does NOT persist the offset - the caller only does that once it knows the
    lines were actually delivered, otherwise a rejected/failed send would be
    silently treated as sent on the next poll."""
    start = offsets.get(path)
    size = path.stat().st_size
    if size < start:
        start = 0  # file was rotated/truncated - restart from the top
    lines: List[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(start)
        for line in f:
            if line.endswith("\n"):
                lines.append(line.strip())
            else:
                break  # partial line at EOF, wait for the writer to finish it
        new_offset = f.tell()
    return lines, new_offset


def _parse_events(lines: List[str]) -> List[dict]:
    events = []
    for line in lines:
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("skipping unparsable line: %.120s", line)
    return events


def _post_batch(server: str, api_key: str, events: List[dict], timeout_s: float) -> Optional[dict]:
    url = f"{server.rstrip('/')}/v1/insider/ingest"
    if urlsplit(url).scheme not in ("http", "https"):
        logger.error("refusing non-http(s) --server URL: %s", server)
        return None

    body = json.dumps({"events": events}).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "x-api-key": api_key},
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:  # nosec B310 - scheme checked above
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        logger.error("ingest rejected batch of %d: HTTP %s %s", len(events), exc.code, exc.reason)
    except URLError as exc:
        logger.error("could not reach %s: %s", server, exc.reason)
    return None


def _discover_sources(source: Path) -> List[Path]:
    if source.is_dir():
        return sorted(source.glob("*.jsonl"))
    return [source]


def _flush_all(events: List[dict], server: str, api_key: str, batch_size: int, timeout_s: float) -> bool:
    """Sends every event, chunked to batch_size. All-or-nothing: if any chunk
    fails, stops and reports failure so the caller doesn't advance its offset -
    the whole read gets retried next cycle. That can re-send chunks that did
    succeed just before the failure, but a rare duplicate event is a far
    smaller problem for an anomaly baseline than a silently dropped one."""
    for start in range(0, len(events), batch_size):
        batch = events[start : start + batch_size]
        result = _post_batch(server, api_key, batch, timeout_s)
        if result is None:
            return False
        logger.info("forwarded %d event(s), server accepted=%s", len(batch), result.get("accepted"))
    return True


def run(
    source: Path,
    server: str,
    api_key: str,
    state_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    interval_s: float = DEFAULT_INTERVAL_S,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    once: bool = False,
) -> None:
    offsets = OffsetStore(state_path)
    logger.info("collector watching %s -> %s (state: %s)", source, server, state_path)

    while True:
        for path in _discover_sources(source):
            if not path.exists():
                continue
            lines, new_offset = _read_new_lines(path, offsets)
            events = _parse_events(lines)
            if events and _flush_all(events, server, api_key, batch_size, timeout_s):
                offsets.set(path, new_offset)

        if once:
            return
        time.sleep(interval_s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="a *.jsonl file or a directory of them")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--api-key", default=None, help="defaults to $RAKSHAK_API_KEY, then 'dev-key'")
    parser.add_argument("--state-dir", type=Path, default=None, help="defaults to <source>/.collector-state")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S)
    parser.add_argument("--once", action="store_true", help="process what's on disk now, then exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    api_key = args.api_key or os.environ.get("RAKSHAK_API_KEY", "dev-key")
    state_dir = args.state_dir or (args.source if args.source.is_dir() else args.source.parent)
    state_path = state_dir / ".collector-state.json"

    if not args.source.exists():
        logger.error("source does not exist: %s", args.source)
        return 1

    try:
        run(
            args.source,
            args.server,
            api_key,
            state_path,
            batch_size=args.batch_size,
            interval_s=args.interval,
            once=args.once,
        )
    except KeyboardInterrupt:
        logger.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
