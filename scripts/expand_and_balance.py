# Runs developer script support for expand and balance.
import pandas as pd, numpy as np, pathlib
p = pathlib.Path(r"data\\processed\\features\\flows_v0.csv")
df = pd.read_csv(p)

# If no label, synthesize one
if "label" not in df.columns:
    num = df.select_dtypes(include=["number"]).columns
    if len(num) == 0:
        raise SystemExit("No numeric cols to synthesize label from; add a real 'label' column.")
    base = df[num[0]]
    df["label"] = (base > base.median()).astype(int)

# If too few rows, duplicate with small noise and BALANCE labels
if len(df) < 40:
    n = 40
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    base = df.iloc[[0]].copy()
    copies = [base.copy() for _ in range(n-1)]
    rng = np.random.default_rng(42)
    for c in num_cols:
        b = float(base[c]) if c in base.columns else 0.0
        noise = rng.normal(0, 0.05*max(abs(b),1.0), size=n-1)
        for i, cp in enumerate(copies):
            cp[c] = b + float(noise[i])

    df = pd.concat([base] + copies, ignore_index=True)

    # Rebalance labels: 20 zeros, 20 ones (alternate)
    df["label"] = 0
    df.loc[df.index[::2], "label"] = 1  # 1,0,1,0,...
    # If "proto" exists, randomize a bit to avoid a single category
    if "proto" in df.columns:
        df["proto"] = np.where(df.index % 3 == 0, "tcp",
                         np.where(df.index % 3 == 1, "udp", "icmp"))

df.to_csv(p, index=False)
print(f"Wrote {len(df)} rows to {p} with label counts:", df["label"].value_counts().to_dict())
