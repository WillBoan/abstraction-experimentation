"""A4-A7: loop overhead vs cut density, enablement, real-vs-synthetic, and the zero-gap question."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind, REAL

R = reports()

print("=" * 100)
print("A4  LOOP OVERHEAD vs RUNG COUNT   (end-to-end / marginal: what the loop costs above the ideal)")
print("=" * 100)
rows = []
for n, d in R.items():
    c, comp = d["cost"], d.get("comparisons", {})
    lo = comp.get("loop_overhead_factor")
    k = len(d.get("rung_recovery", []))
    if lo is not None:
        rows.append((k, lo, kind(n), n, c.get("laddered_marginal_considered"),
                     c.get("laddered_end_to_end_considered")))
for k, lo, kd, n, marg, e2e in sorted(rows):
    print(f"  rungs={k}  overhead={lo:5.2f}x  {kd:9} {n:30} marginal={marg:>9,} end-to-end={e2e:>10,}")
by_k = {}
for k, lo, *_ in rows:
    by_k.setdefault(k, []).append(lo)
print("\n  mean overhead by rung count:")
for k in sorted(by_k):
    v = by_k[k]
    print(f"    {k} rungs: {sum(v)/len(v):.2f}x   (n={len(v)}, spread {min(v):.2f}-{max(v):.2f})")

print()
print("=" * 100)
print("A5  ENABLEMENT -- what a rung bought when it did NOT buy speed")
print("=" * 100)
low_but_enabling = 0
low_total = 0
for n, d in R.items():
    en = d.get("comparisons", {}).get("enablement", {})
    mv = {m["rung"]: m for m in d.get("comparisons", {}).get("marginal_rung_value", [])}
    rungs = [r["rung"] for r in d.get("rung_recovery", [])]
    for i, rung in enumerate(rungs, start=1):
        sp = (mv.get(rung) or {}).get("own_tasks_speedup")
        enabled = en.get(str(i), [])
        if sp is not None and sp < 2:
            low_total += 1
            if enabled:
                low_but_enabling += 1
print(f"  rungs worth < 2x in cost-to-first: {low_total}")
print(f"    ...of which STILL enabled tasks the layer above could not otherwise reach: {low_but_enabling}")
print(f"    ...of which enabled nothing at all: {low_total - low_but_enabling}")

print()
print("=" * 100)
print("A6  REAL vs SYNTHETIC")
print("=" * 100)
for label in ("real", "synthetic"):
    sel = [d for n, d in R.items() if kind(n) == label and d["certificate"].get("admitted")]
    lo = [d["comparisons"]["loop_overhead_factor"] for d in sel
          if d.get("comparisons", {}).get("loop_overhead_factor") is not None]
    dc = [d["cost"].get("budget_compression_depth") for d in sel]
    dc = [x for x in dc if x is not None]
    iters = [len(d.get("climb_trace", [])) for d in sel]
    print(f"  {label:9} admitted={len(sel):2}  loop-overhead mean {sum(lo)/len(lo):.2f}x  "
          f"climb iters mean {sum(iters)/len(iters):.1f}")

print()
print("=" * 100)
print("A7  THE LEARNED-vs-ORACLE GAP")
print("=" * 100)
tot = rec = junk = 0
for n, d in R.items():
    rr = d.get("rung_recovery", [])
    tot += len(rr)
    rec += sum(1 for r in rr if r.get("recovered"))
    minted = {m for t in d.get("climb_trace", []) for m in (t.get("minted") or [])}
    matched = {m for r in rr for m in (r.get("matched_by") or [])}
    junk += len(minted - matched)
print(f"  rungs across all admitted ladders: {tot}")
print(f"  recovered:                          {rec}  ({100*rec/tot:.1f}%)")
print(f"  NOT recovered:                      {tot - rec}")
print(f"  minted abstractions matching NO intended rung (junk): {junk}")
