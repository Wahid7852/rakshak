# Runs developer script support for runner.
"""RAKSHAK runner - process auth/threat logs in real-time using ML models."""
import os, sys
from pathlib import Path

# Add repository root to Python path before any local imports
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import time, json, argparse, math
from collections import defaultdict, deque

try:
    from parser.syslog_parser import parse_line
    from models.hst import HalfSpaceForest
    from models.ngram import NGramModel
    from models.sgd import OnlineLogReg
    from models.fuse import fuse
except ImportError as e:
    print(f"Error importing RAKSHAK modules: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    sys.exit(1)



WINDOW_SEC = 60
SLIDE_SEC = 5

def now_monotonic():
    return time.time()

class SlidingStats:
    def __init__(self):
        self.events = deque()
        self.counts = defaultdict(int)
        self.users = defaultdict(set)

    def add(self, t, etype, user=None):
        self.events.append((t, etype, user))
        self.counts[etype] += 1
        if user:
            self.users['user'].add(user)

    def evict(self, t_now):
        cutoff = t_now - WINDOW_SEC
        while self.events and self.events[0][0] < cutoff:
            _, etype, user = self.events.popleft()
            self.counts[etype] -= 1
            if user and user in self.users['user']:
                # no need to delete aggressively; refreshed on feature read
                pass

    def features(self, t_now):
        self.evict(t_now)
        invalid_user = max(0, self.counts.get('invalid_user', 0))
        failed_password = max(0, self.counts.get('failed_password', 0))
        preauth_close = max(0, self.counts.get('preauth_close', 0))
        distinct_users = len(self.users['user'])
        total = invalid_user + failed_password + preauth_close + 1e-6
        failed_rate = failed_password / total
        # burstiness proxy = max count per SLIDE in window (approx via counts)
        burstiness = max(invalid_user, failed_password, preauth_close)
        # inter-arrival approximated by average gap between events
        gaps = []
        last = None
        for (ts, _, _) in list(self.events)[-50:]:
            if last is not None:
                gaps.append(ts - last)
            last = ts
        if not gaps:
            inter_mean = WINDOW_SEC
            inter_var = 0.0
        else:
            inter_mean = sum(gaps)/len(gaps)
            inter_var = sum((g - inter_mean)**2 for g in gaps)/len(gaps)
        return [invalid_user, failed_password, distinct_users, preauth_close,
                failed_rate, burstiness, inter_mean, inter_var]

def weak_label(feat):
    invalid_user, failed_password, distinct_users, preauth_close, failed_rate, burstiness, inter_mean, inter_var = feat
    # conservative local rule
    if distinct_users >= 3 or invalid_user >= 5 or failed_password >= 5:
        return 1
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", type=str, default=None, help="Read logs from file instead of stdin")
    ap.add_argument("--tau_lo", type=float, default=0.55)
    ap.add_argument("--tau_hi", type=float, default=0.75)
    ap.add_argument("--audit", type=str, default="alerts.ndjson")
    args = ap.parse_args()

    hsf = HalfSpaceForest(n_trees=30, height_limit=9, seed=7)
    ngram_by_host = defaultdict(lambda: NGramModel(n=3, decay=0.999))
    sgd = OnlineLogReg(n_features=8, lr=1e-4, l2=1e-4)
    per_ip = defaultdict(SlidingStats)

    audit = open(args.audit, "a", buffering=1)

    def process_line(line, tstamp):
        p = parse_line(line)
        if not p:
            return
        key = (p.host, p.src_ip or "none")
        ss = per_ip[key]
        ss.add(tstamp, p.event_type, p.username)

        # update sequence model per-host
        ngram = ngram_by_host[p.host]
        ngram.update(p.template_id)

        # feature vector
        feat = ss.features(tstamp)

        # model updates
        hsf.update(feat)
        a_hst = hsf.score(feat)
        a_seq = ngram.seq_score([p.template_id])  # short-term anomaly proxy

        # online supervised (weak) label
        y = weak_label(feat)
        sgd.update(feat, y)
        p_sgd = sgd.predict_proba(feat)

        score = fuse(a_hst, a_seq, p_sgd)
        sev = "LOW"
        if score >= args.tau_hi:
            sev = "HIGH"
        elif score >= args.tau_lo:
            sev = "MEDIUM"

        if sev != "LOW":
            rec = {
                "ts": tstamp,
                "host": p.host,
                "src_ip": p.src_ip,
                "username": p.username,
                "event": p.event_type,
                "score": round(score, 3),
                "severity": sev,
                "reasons": {
                    "invalid_user": feat[0],
                    "failed_password": feat[1],
                    "distinct_users": feat[2],
                    "preauth_close": feat[3]
                },
                "template": p.template_id,
                "raw": line.strip()
            }
            print(json.dumps(rec), flush=True)
            audit.write(json.dumps(rec) + "\n")

    if args.from_file:
        try:
            with open(args.from_file, "r", encoding="utf-8", errors="replace") as f:
                t0 = now_monotonic()
                for i, line in enumerate(f):
                    t = t0 + i
                    process_line(line, t)
        except UnicodeDecodeError:
            try:
                with open(args.from_file, "r", encoding="latin-1") as f:
                    t0 = now_monotonic()
                    for i, line in enumerate(f):
                        t = t0 + i
                        process_line(line, t)
            except UnicodeDecodeError:
                print(f"Failed to decode file {args.fromfile} with utf-8 and latin-1 encodings. Please check the file encoding.", file=sys.stderr)
    else:
        for line in sys.stdin:
            process_line(line, nowmonotonic())

if __name__ == "__main__":
    main()
