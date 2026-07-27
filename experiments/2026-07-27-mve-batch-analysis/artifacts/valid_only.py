"""Which of the 2026-07-27 batch findings survive the validity filter?"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind

def validity(d):
    if d.get("compromises"): return "compromised"
    if not d["certificate"].get("admitted"): return "rejected"
    tops = [r for r in d["cost_matrix"] if r.get("rung") == "top"]
    if tops:
        last = max(tops[0]["columns"], key=int)
        if tops[0]["columns"][last].get("solved") is False: return "top unreached"
    return None

R = reports()
valid = {n: d for n, d in R.items() if validity(d) is None}
print(f"valid ladders: {len(valid)} of {len(R)}  ({sum(1 for n in valid if kind(n)=='real')} real)\n")

print("== FINDING 1: marginal rung value (valid runs only)")
rows = [(m.get("own_tasks_speedup"), n, m["rung"]) for n, d in valid.items()
        for m in d["comparisons"].get("marginal_rung_value", []) if m.get("own_tasks_speedup")]
v = sorted(r[0] for r in rows)
lo = [r for r in rows if r[0] < 2]
print(f"   n={len(rows)}  min {v[0]:.2f}x  median {v[len(v)//2]:.2f}x  max {v[-1]:.2f}x")
print(f"   worth < 2x: {len(lo)}/{len(rows)} ({100*len(lo)/len(rows):.0f}%)   [was 57% on all runs]")
print("   top 5:", [f"{s:.0f}x {r}" for s, _, r in sorted(rows, reverse=True)[:5]])

print("\n== FINDING 2: the learned-vs-oracle gap (valid runs only)")
tot = rec = junk = 0
for n, d in valid.items():
    rr = d["rung_recovery"]; tot += len(rr); rec += sum(1 for x in rr if x["recovered"])
    minted = {m for t in d["climb_trace"] for m in (t.get("minted") or [])}
    matched = {m for x in rr for m in (x.get("matched_by") or [])}
    junk += len(minted - matched)
print(f"   rungs {tot}  recovered {rec} ({100*rec/tot:.0f}%)  junk mints {junk}")

print("\n== FINDING 3: real vs synthetic (valid runs only)")
for label in ("real", "synthetic"):
    sel = [d for n, d in valid.items() if kind(n) == label]
    if not sel: continue
    lo_ = [d["comparisons"]["loop_overhead_factor"] for d in sel]
    print(f"   {label:10} n={len(sel)}  loop-overhead {min(lo_):.2f}-{max(lo_):.2f}x  mean {sum(lo_)/len(lo_):.2f}x")

print("\n== FINDING 4: the granularity curves")
for task, members in (("dae9d2b5", ["dae9d2b5-split-halves-lean","dae9d2b5-split-asym-lean","dae9d2b5-split-recolor-lean"]),
                      ("94f9d214", ["94f9d214-nor-halves","94f9d214-nor-recolor"]),
                      ("fafffa47", ["fafffa47-nor-halves","fafffa47-nor-recolor"])):
    ok = [m for m in members if m in valid]
    print(f"   {task:10} valid members {len(ok)}/{len(members)}  {ok if ok else '-- NO VALID CURVE'}")
