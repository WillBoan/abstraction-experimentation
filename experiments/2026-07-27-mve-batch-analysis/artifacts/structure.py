"""A2: is marginal rung value predicted by POSITION -- does the rung feed the top, or another rung?"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind

feeds_top, feeds_rung = [], []
for name, d in reports().items():
    for m in d.get("comparisons", {}).get("marginal_rung_value", []):
        sp, above = m.get("own_tasks_speedup"), m.get("layer_above")
        if sp is None:
            continue
        (feeds_top if above == "top" else feeds_rung).append((sp, name, m["rung"], above))

def summarise(label, rows):
    v = sorted(r[0] for r in rows)
    print(f"{label:34} n={len(v):2}  min {v[0]:8.2f}x  median {v[len(v)//2]:8.2f}x  max {v[-1]:9.2f}x")

print("MARGINAL VALUE BY POSITION IN THE LADDER")
summarise("rung feeds the TOP", feeds_top)
summarise("rung feeds ANOTHER RUNG", feeds_rung)
print()
print("Every rung that feeds another rung, sorted by value (the low band):")
for sp, n, rung, above in sorted(feeds_rung, key=lambda r: -r[0])[:8]:
    print(f"   {sp:7.2f}x  {kind(n):9} {n:30} {rung:16} -> {above}")
print()
print("Overlap test: does ANY rung-fed rung beat ANY top-fed rung?")
hi_rungfed = max(r[0] for r in feeds_rung)
lo_topfed = min(r[0] for r in feeds_top)
print(f"   best rung-fed = {hi_rungfed:.2f}x ; worst top-fed = {lo_topfed:.2f}x -> "
      f"{'SEPARATED' if hi_rungfed < lo_topfed else 'OVERLAP'}")
if hi_rungfed >= lo_topfed:
    print("   overlapping cases:")
    for sp, n, rung, above in sorted(feeds_top, key=lambda r: r[0]):
        if sp <= hi_rungfed:
            print(f"     top-fed but low: {sp:6.2f}x  {n} / {rung}")
