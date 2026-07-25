#!/usr/bin/env python3
# Pretrains sgd.py's OnlineLogReg on LogHub HDFS_v1. Ground truth is
# block-level but we score line-by-line, so lines are labeled by whether
# their event template has high lift toward block anomaly (naive block-label
# propagation only got AUC ~0.54 - see docs/results.md).
from __future__ import annotations

import argparse, csv, io, json, pathlib, random, re, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.engine.features.log_features import VECTOR_WIDTH, log_feature_vector  # noqa: E402
from backend.engine.models.classical.sgd import OnlineLogReg  # noqa: E402

BLOCK_RE = re.compile(r"blk_-?\d+")
MIN_LIFT = 5.0
MIN_SUPPORT = 20


def load_templates(zf: zipfile.ZipFile) -> dict:
    raw = zf.read("preprocessed/HDFS.log_templates.csv").decode()
    templates = {}
    for row in csv.DictReader(io.StringIO(raw)):
        templates[row["EventId"]] = row["EventTemplate"]
    return templates


def template_to_regex(template: str) -> re.Pattern:
    parts = [p for p in template.split("[*]") if p]
    return re.compile(".*".join(re.escape(p) for p in parts))


def signal_templates(zf: zipfile.ZipFile) -> set:
    raw = zf.read("preprocessed/Event_occurrence_matrix.csv").decode()
    reader = csv.reader(io.StringIO(raw))
    header = next(reader)
    event_cols = [c for c in header if re.fullmatch(r"E\d+", c)]
    idx = {c: header.index(c) for c in event_cols}
    label_idx = header.index("Label")

    total = anom = 0
    event_total = {c: 0 for c in event_cols}
    event_anom = {c: 0 for c in event_cols}
    for row in reader:
        total += 1
        is_anom = row[label_idx] == "Fail"
        anom += is_anom
        for c in event_cols:
            if int(row[idx[c]]) > 0:
                event_total[c] += 1
                event_anom[c] += is_anom

    base_rate = anom / total
    signal = set()
    for c in event_cols:
        if event_total[c] < MIN_SUPPORT:
            continue
        lift = (event_anom[c] / event_total[c]) / base_rate
        if lift >= MIN_LIFT:
            signal.add(c)
    return signal


def balanced_sample(rows, seed: int, neg_ratio: int = 1):
    rng = random.Random(seed)
    positive = [r for r in rows if r[1] == 1.0]
    negative = [r for r in rows if r[1] == 0.0]
    rng.shuffle(negative)
    negative = negative[: max(len(positive) * neg_ratio, 2000)]
    combined = positive + negative
    rng.shuffle(combined)
    return combined


def label_lines(zf: zipfile.ZipFile, matchers: dict, limit: int):
    """Returns (line, y) pairs: y=1 if the line matches a signal template."""
    out = []
    with zf.open("HDFS.log") as f:
        for raw in f:
            line = raw.decode(errors="ignore").rstrip("\n")
            if not BLOCK_RE.search(line):
                continue
            y = 1.0 if any(rx.search(line) for rx in matchers.values()) else 0.0
            out.append((line, y))
            if len(out) >= limit:
                break
    return out


def block_rollup_check(zf: zipfile.ZipFile, reg: OnlineLogReg, sample_blocks: int, seed: int):
    """Does max(line score in block) >= 0.5 predict the block's real label?"""
    raw = zf.read("preprocessed/anomaly_label.csv").decode()
    true_label = {row["BlockId"]: row["Label"] == "Anomaly" for row in csv.DictReader(io.StringIO(raw))}

    block_lines: dict = {}
    max_lines_scanned = sample_blocks * 200  # blocks average ~20 lines each, generous cap
    with zf.open("HDFS.log") as f:
        for i, raw_line in enumerate(f):
            if i >= max_lines_scanned or len(block_lines) >= sample_blocks * 2:
                break
            line = raw_line.decode(errors="ignore").rstrip("\n")
            m = BLOCK_RE.search(line)
            if not m:
                continue
            bid = m.group()
            if bid not in true_label:
                continue
            if bid not in block_lines and len(block_lines) >= sample_blocks:
                continue
            block_lines.setdefault(bid, []).append(line)

    rng = random.Random(seed)
    anomalous_blocks = [b for b in block_lines if true_label[b]]
    normal_blocks = [b for b in block_lines if not true_label[b]]
    rng.shuffle(normal_blocks)
    eval_blocks = anomalous_blocks + normal_blocks[: len(anomalous_blocks) * 4]

    tp = fp = tn = fn = 0
    for bid in eval_blocks:
        lines = block_lines[bid][:50]
        max_score = max(reg.predict_proba(log_feature_vector(ln)) for ln in lines)
        pred = max_score >= 0.5
        actual = true_label[bid]
        tp += pred and actual
        fp += pred and not actual
        tn += (not pred) and (not actual)
        fn += (not pred) and actual

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"n_blocks": len(eval_blocks), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": precision, "recall": recall}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdfs-zip", default=str(ROOT / "data" / "raw" / "hdfs" / "HDFS_v1.zip"))
    ap.add_argument("--limit", type=int, default=400_000)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rollup-blocks", type=int, default=3000)
    ap.add_argument("--out", default=str(ROOT / "backend" / "engine" / "models" / "artifacts" / "log_sgd.json"))
    args = ap.parse_args()

    with zipfile.ZipFile(args.hdfs_zip) as zf:
        templates = load_templates(zf)
        signal = signal_templates(zf)
        print(f"signal templates ({len(signal)}/{len(templates)}): {sorted(signal)}")
        matchers = {eid: template_to_regex(templates[eid]) for eid in signal}

        rows = label_lines(zf, matchers, args.limit)
        n_pos = sum(1 for _, y in rows if y == 1.0)
        print(f"loaded {len(rows)} lines, {n_pos} match a signal template ({n_pos/len(rows):.3%})")

        rng = random.Random(args.seed)
        rng.shuffle(rows)
        split = int(len(rows) * (1 - args.test_frac))
        train_rows, test_rows = rows[:split], rows[split:]
        train_rows = balanced_sample(train_rows, args.seed)
        print(f"balanced training set: {len(train_rows)} rows, "
              f"{sum(1 for _, y in train_rows if y == 1.0)} positive")

        reg = OnlineLogReg(n_features=VECTOR_WIDTH, lr=3e-2, l2=1e-5)
        train_feats = [(log_feature_vector(line), y) for line, y in train_rows]
        for _ in range(args.epochs):
            rng.shuffle(train_feats)
            for x, y in train_feats:
                reg.update(x, y)

        y_true, y_score = [], []
        for line, y in test_rows:
            y_true.append(y)
            y_score.append(reg.predict_proba(log_feature_vector(line)))

        from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

        y_pred = [1 if s >= 0.5 else 0 for s in y_score]
        metrics = {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "auc": roc_auc_score(y_true, y_score) if len(set(y_true)) > 1 else None,
            "n_train": len(train_rows),
            "n_test": len(test_rows),
            "n_test_positive": sum(y_true),
        }
        print("per-line metrics:", json.dumps(metrics, indent=2))

        rollup = block_rollup_check(zf, reg, args.rollup_blocks, args.seed)
        print("block-level rollup check:", json.dumps(rollup, indent=2))

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "weights": reg.w,
        "n_features": VECTOR_WIDTH,
        "trained_on": "LogHub HDFS_v1 (template-lift-labeled lines)",
        "signal_templates": sorted(signal),
        "metrics": metrics,
        "block_rollup_check": rollup,
    }, indent=2))

    from backend.engine.models.artifact_integrity import update_manifest
    update_manifest(out_path)

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
