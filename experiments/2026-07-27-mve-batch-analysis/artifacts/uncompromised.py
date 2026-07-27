"""Loop overhead, restricted to runs whose numbers actually mean what the metric claims.

Three filters, each for a stated reason:
  - no COMPROMISE: `solution-limit` stops the chain and the climb at different points, so
    `end_to_end / marginal` stops being a ratio of like quantities (measured 2026-07-27: one member
    reported 0.30x -- end-to-end BELOW marginal, structurally impossible for "every wake re-searches
    every task").
  - ADMITTED: a rejected structure's climb is measuring something else.
  - TOP REACHED: a climb that never solves the goal has not run the loop the factor describes.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind

rows, excluded = [], []
for n, d in reports().items():
    comp = [c["code"] for c in d.get("compromises", [])]
    adm = d["certificate"].get("admitted")
    tops = [r for r in d["cost_matrix"] if r.get("rung") == "top"]
    top_ok = None
    if tops:
        last = max(tops[0]["columns"], key=int)
        top_ok = tops[0]["columns"][last].get("solved")
    lo = d.get("comparisons", {}).get("loop_overhead_factor")
    k = len(d.get("rung_recovery", []))
    reason = ("compromised: " + ",".join(comp)) if comp else (
        "not admitted" if not adm else ("top never solved" if top_ok is False else None))
    if reason or lo is None:
        excluded.append((n, reason or "no loop factor"))
    else:
        rows.append((k, lo, kind(n), n, d["cost"]["laddered_marginal_considered"],
                     d["cost"]["laddered_end_to_end_considered"]))

print("VALID FOR LOOP OVERHEAD (uncompromised, admitted, top reached)")
print(f"  {'rungs':>5} {'overhead':>9} {'kind':10} {'ladder':30} {'marginal':>10} {'end-to-end':>11}")
for k, lo, kd, n, m, e in sorted(rows):
    print(f"  {k:>5} {lo:>8.2f}x {kd:10} {n:30} {m:>10,} {e:>11,}")
print(f"\n  n = {len(rows)}   real = {sum(1 for r in rows if r[2]=='real')}   "
      f"synthetic = {sum(1 for r in rows if r[2]=='synthetic')}")
v = sorted(r[1] for r in rows)
if v:
    print(f"  min {v[0]:.2f}x  median {v[len(v)//2]:.2f}x  max {v[-1]:.2f}x")
by_k = {}
for k, lo, *_ in rows:
    by_k.setdefault(k, []).append(lo)
print("\n  by rung count:")
for k in sorted(by_k):
    x = by_k[k]
    print(f"    {k} rungs: mean {sum(x)/len(x):.2f}x  (n={len(x)}, {min(x):.2f}-{max(x):.2f})")

print(f"\nEXCLUDED ({len(excluded)}):")
for n, why in sorted(excluded):
    print(f"  {n:32} {why}")
