"""A1: marginal rung value, in the currency the report says to read it in (cost-to-first)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind

rows = []
for name, d in reports().items():
    for m in d.get("comparisons", {}).get("marginal_rung_value", []):
        rows.append((kind(name), name, m["rung"], m.get("layer_above"),
                     m.get("own_tasks_to_first_without"), m.get("own_tasks_to_first_with"),
                     m.get("own_tasks_speedup"), m.get("ratio"), m.get("censored")))

print(f"{'kind':9} {'ladder':30} {'rung':18} {'to_first w/o':>12} {'with':>7} {'speedup':>9} {'paid-full ratio':>16}")
for k, n, rung, above, wo, wi, sp, ratio, cens in sorted(rows, key=lambda r: -(r[6] or 0)):
    sp_s = f"{sp:.2f}x" if sp is not None else "-"
    r_s = f"{ratio:.4f}" if ratio is not None else "-"
    print(f"{k:9} {n:30} {rung:18} {str(wo):>12} {str(wi):>7} {sp_s:>9} {r_s:>16}")

vals = [r[6] for r in rows if r[6] is not None]
big = [r for r in rows if (r[6] or 0) >= 2]
small = [r for r in rows if (r[6] or 0) < 2]
print(f"\n{len(rows)} rungs across {len({r[1] for r in rows})} ladders")
print(f"  speedup >= 2x : {len(big):3}  ({100*len(big)/len(rows):.0f}%)")
print(f"  speedup <  2x : {len(small):3}  ({100*len(small)/len(rows):.0f}%)")
if vals:
    vs = sorted(vals)
    print(f"  min {vs[0]:.2f}x  median {vs[len(vs)//2]:.2f}x  max {vs[-1]:.2f}x")
print("\npaid-full `ratio` spread (the currency the report warns is near-task-independent):")
rs = sorted(r[7] for r in rows if r[7] is not None)
print(f"  min {rs[0]:.4f}  max {rs[-1]:.4f}   -> spread {rs[-1]-rs[0]:.4f}")
