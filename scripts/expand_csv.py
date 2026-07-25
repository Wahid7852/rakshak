# Runs developer script support for expand csv.
import pandas as pd, numpy as np, pathlib
p = pathlib.Path(r"data\\processed\\features\\flows_v0.csv")
df = pd.read_csv(p)
if len(df) < 2:
    n = 40
    num = df.select_dtypes(include=["number"]).columns
    base = df.iloc[[0]].copy()
    copies = [base.copy() for _ in range(n-1)]
    for c in num:
        b = float(base[c]) if c in base.columns else 0.0
        noise = np.random.normal(0, 0.05*max(abs(b),1.0), size=n-1)
        for i,cp in enumerate(copies):
            cp[c] = b + float(noise[i])
    df = pd.concat([base] + copies, ignore_index=True)
df.to_csv(p, index=False)
print(f"Wrote {len(df)} rows to {p}")
