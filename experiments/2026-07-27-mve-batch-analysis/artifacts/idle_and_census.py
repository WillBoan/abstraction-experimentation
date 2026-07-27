"""A8: the rungs that bought neither speed nor reachability; and does the breadth census RANK?"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind
from arc_lab.program_search.ladders.registry import make_ladder, ladder_paths

R = reports()
print("=" * 96)
print("A8a  RUNGS THAT BOUGHT NEITHER SPEED (<2x) NOR REACHABILITY (enabled nothing)")
print("=" * 96)
for n, d in R.items():
    comp = d.get("comparisons", {})
    en, mv = comp.get("enablement", {}), {m["rung"]: m for m in comp.get("marginal_rung_value", [])}
    for i, r in enumerate(d.get("rung_recovery", []), start=1):
        rung = r["rung"]
        sp = (mv.get(rung) or {}).get("own_tasks_speedup")
        if sp is not None and sp < 2 and not en.get(str(i), []):
            print(f"  {kind(n):9} {n:30} r_{i} {rung:16} speedup={sp:.2f}x  enabled=[]")

print()
print("=" * 96)
print("A8b  DOES THE STATIC BREADTH CENSUS RANK AGAINST MEASURED COST? (per-rung, real ladders)")
print("=" * 96)
pairs = []
for n, d in R.items():
    try:
        spec = make_ladder(n)
    except Exception:
        continue
    shape = spec.lint()
    breadth = {b.name: b for b in getattr(shape, "rung_breadth", ()) or ()}
    jump = d["cost"].get("jump_costs") or {}
    to_first = d["cost"].get("jump_costs_to_first") or {}
    for rung_name, b in breadth.items():
        measured = to_first.get(rung_name) or jump.get(rung_name)
        if measured:
            pairs.append((b.b1_full, b.b1_min, b.b1_full / max(b.b1_min, 1), measured, n, rung_name))

pairs.sort(key=lambda p: -p[2])
print(f"  {'b1 full':>8} {'b1 min':>7} {'tax':>9} {'measured to-first':>18}  ladder / rung")
for bf, bm, tax, meas, n, rn in pairs[:18]:
    print(f"  {bf:>8,} {bm:>7,} {tax:>8.1f}x {meas:>18,}  {n} / {rn}")

if len(pairs) >= 4:
    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        rk = [0] * len(xs)
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk
    tax_r, meas_r = rank([p[2] for p in pairs]), rank([p[3] for p in pairs])
    nn = len(pairs)
    d2 = sum((a - b) ** 2 for a, b in zip(tax_r, meas_r))
    rho = 1 - 6 * d2 / (nn * (nn * nn - 1))
    print(f"\n  Spearman rank correlation (census tax vs measured cost-to-first), n={nn}: rho = {rho:+.3f}")
    print("  (the census ships labelled an INDICATOR for RANKING, never a prediction -- this tests exactly that claim)")
