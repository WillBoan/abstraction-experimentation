"""A3: is marginal rung value driven by what the rung's own step must REDISCOVER?

Hypothesis from the A1/A2 data: `own_tasks_speedup` is `to_first_without / to_first_with`, and the
`with` side is near-constant (finding a one-step call to a gifted abstraction). So the spread is
entirely in `without` -- the cost of rediscovering the rung's own body from the layer below. That
should be dominated by the CONSTANT BATTERY the body has to search: a colour pair is 10x10, a list
index is a handful.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import reports, kind
from arc_lab.program_search.ladders.registry import make_ladder, ladder_paths
from arc_lab.program_search.substrate.program import Const
from arc_lab.program_search.substrate.types import COLOR, INT, OFFSET, COORD, BOOL

BATTERY = {COLOR.name: 10, INT.name: "dim", OFFSET.name: "dim^2", COORD.name: "dim^2", BOOL.name: 2}

specs = {}
for name in ladder_paths():
    try:
        specs[name] = make_ladder(name)
    except Exception:
        pass

rows = []
for name, d in reports().items():
    spec = specs.get(name)
    if spec is None:
        continue
    by_rung = {r.name: r for r in spec.rungs}
    for m in d.get("comparisons", {}).get("marginal_rung_value", []):
        rung = by_rung.get(m["rung"])
        sp = m.get("own_tasks_speedup")
        if rung is None or sp is None:
            continue
        consts = [n for n in rung.template.walk() if isinstance(n, Const)]
        types = sorted({str(getattr(c, "value_type", "?")) for c in consts})
        big = any(str(getattr(c, "value_type", "")) in (COLOR.name, OFFSET.name, COORD.name)
                  for c in consts)
        rows.append((sp, kind(name), name, m["rung"], len(consts), ",".join(types) or "-", big))

print(f"{'speedup':>10}  {'kind':9} {'ladder':30} {'rung':16} {'#const':>6} const-types")
for sp, k, n, rung, nc, types, big in sorted(rows, key=lambda r: -r[0]):
    print(f"{sp:9.2f}x  {k:9} {n:30} {rung:16} {nc:>6} {types}")

big_v = sorted(r[0] for r in rows if r[6])
small_v = sorted(r[0] for r in rows if not r[6])
def s(label, v):
    if v:
        print(f"{label:44} n={len(v):2}  min {v[0]:7.2f}x  median {v[len(v)//2]:8.2f}x  max {v[-1]:9.2f}x")
print()
print("SPLIT BY WHETHER THE RUNG BINDS A LARGE-BATTERY CONSTANT (colour / offset / coord)")
s("binds a large-battery constant", big_v)
s("binds none (structural or small-int only)", small_v)
if big_v and small_v:
    print(f"  separation: worst large-battery {big_v[0]:.2f}x vs best structural {small_v[-1]:.2f}x -> "
          f"{'CLEAN' if big_v[0] > small_v[-1] else 'OVERLAP'}")
