# Provides tooling support for eval runner.
#!/usr/bin/env python
from __future__ import annotations
import argparse, asyncio, csv, json, os, time, pathlib
from dataclasses import dataclass
from typing import Dict, List, Any, Tuple

from backend.orchestrator.decision import Router, Event
from tools.eval.metrics import compute_binary, percentiles, auc_approx

@dataclass
class Item:
    kind: str            # "log" | "file"
    payload: Any
    context: Dict[str, Any]
    label: int           # 0 benign, 1 malicious
    uid: str

def _read_lines_with_label(txt_path: str, label: int) -> List[Item]:
    items: List[Item] = []
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for i, ln in enumerate(f):
            ln = ln.strip()
            if not ln: continue
            items.append(Item("log", ln, {}, label, f"log:{pathlib.Path(txt_path).name}:{i}"))
    return items

def _read_files_labeled(dir_benign: str, dir_mal: str) -> List[Item]:
    items: List[Item] = []
    for root, _, files in os.walk(dir_benign):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, "rb") as f:
                b = f.read()
            items.append(Item("file", b, {"path": p}, 0, f"file:{fn}:0"))
    for root, _, files in os.walk(dir_mal):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, "rb") as f:
                b = f.read()
            items.append(Item("file", b, {"path": p}, 1, f"file:{fn}:1"))
    return items

async def _score(router: Router, item: Item) -> Tuple[float,float,str,str,float]:
    t0 = time.perf_counter()
    d = await router.decide(Event(kind=item.kind, payload=item.payload, context=item.context))
    dt_ms = (time.perf_counter() - t0) * 1000.0
    return d.score, d.confidence, d.verdict, d.used, dt_ms

async def run_eval(args):
    out_dir = pathlib.Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    router = Router()  # uses your cascade + budgets

    # Gather items
    items: List[Item] = []
    if args.log_benign:
        items += _read_lines_with_label(args.log_benign, 0)
    if args.log_mal:
        items += _read_lines_with_label(args.log_mal, 1)
    if args.file_benign and args.file_malicious:
        items += _read_files_labeled(args.file_benign, args.file_malicious)

    if not items:
        raise SystemExit("No items to evaluate. Provide at least one source.")

    # Inference loop
    labels, preds, scores, confs, useds = [], [], [], [], []
    latencies = []
    rows = []

    for it in items:
        s, c, v, used, dt = await _score(router, it)
        pred = 1 if s >= 0.5 else 0
        labels.append(it.label); preds.append(pred)
        scores.append(s); confs.append(c); useds.append(used); latencies.append(dt)
        rows.append({
            "uid": it.uid, "kind": it.kind, "label": it.label,
            "score": round(s,6), "confidence": round(c,6), "verdict": v, "used": used,
            "latency_ms": round(dt,3), "path": it.context.get("path", "")
        })

    # Metrics
    bm = compute_binary(labels, preds)
    lat = percentiles(latencies)
    auc = auc_approx(labels, scores)

    # Write CSV
    csv_path = out_dir / "eval_preds.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # Write JSON report
    rpt = {
        "counts": {"n": len(labels)},
        "metrics": {
            "accuracy": round(bm.accuracy,4),
            "precision": round(bm.precision,4),
            "recall": round(bm.recall,4),
            "f1": round(bm.f1,4),
            "tp": bm.tp, "tn": bm.tn, "fp": bm.fp, "fn": bm.fn,
            "auc": None if auc is None else round(auc,4)
        },
        "latency_ms": {k: round(v,2) for k,v in lat.items()},
        "notes": "Scores >= 0.5 → malicious. Confidence-weighted cascade; QSVM only activates for borderline files."
    }
    with open(out_dir / "eval_report.json", "w", encoding="utf-8") as f:
        json.dump(rpt, f, indent=2)

    print(f"[OK] wrote {csv_path}")
    print(f"[OK] wrote {out_dir/'eval_report.json'}")
    print("summary:", json.dumps(rpt, indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-benign", help="path to benign log lines (txt)")
    ap.add_argument("--log-mal", help="path to malicious/suspicious log lines (txt)")
    ap.add_argument("--file-benign", help="dir with benign files")
    ap.add_argument("--file-malicious", help="dir with malicious/suspicious files")
    ap.add_argument("--out", default="artifacts/eval")
    args = ap.parse_args()
    asyncio.run(run_eval(args))

if __name__ == "__main__":
    main()
