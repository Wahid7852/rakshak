# Provides tooling support for bench router.
#!/usr/bin/env python
from __future__ import annotations
import argparse, asyncio, os, time, random
from statistics import mean
from backend.orchestrator.decision import Router, Event
from tools.eval.metrics import percentiles

async def run_load(kind: str, n: int, concurrency: int):
    router = Router()
    sem = asyncio.Semaphore(concurrency)
    rnd = random.Random(123)

    async def one(i: int):
        async with sem:
            if kind == "log":
                payload = f"auth attempt {i} from 10.0.{i%255}.{(i*7)%255}"
                ctx = {}
            else:
                size = 64*1024 if i%3 else 256*1024
                payload = (b"MZ" if i%5==0 else b"OK") + os.urandom(size)
                ctx = {"path": f"sample_{i}.bin"}
            t0 = time.perf_counter()
            d = await router.decide(Event(kind=kind, payload=payload, context=ctx))
            return (time.perf_counter()-t0)*1000.0

    ts = []
    tasks = [asyncio.create_task(one(i)) for i in range(n)]
    for t in asyncio.as_completed(tasks):
        ts.append(await t)
    return ts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["log","file"], required=True)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    ts = asyncio.run(run_load(args.kind, args.n, args.concurrency))
    pct = percentiles(ts)
    print(f"n={len(ts)} avg_ms={mean(ts):.2f} p50={pct['p50']:.2f} p95={pct['p95']:.2f} p99={pct['p99']:.2f}")

if __name__ == "__main__":
    main()
