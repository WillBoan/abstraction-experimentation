"""Read-side strengthening pass over the claim list (no new runs).

T1 (A4/A9): __const__ share of considered, across every cell that carries by_primitive.
T2 (A6/A2): per-added-rung growth at fixed depth vs the added rung's template arity/constants.
T3 (B3):    marginal-rung-value predictor shoot-out: constant-battery vs arity vs #consts vs position.
T4 (C2/C3): every raw arm on disk: bound-or-measured ratio vs d_raw and floor size.
"""

import json
from pathlib import Path

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.substrate.program import Const, Param

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"

BIG_BATTERY = {"color", "offset", "coord"}

reports: dict[str, dict] = {}
for d in sorted(LADDERS.iterdir()):
    p = d / "report.json"
    if p.exists():
        reports[d.name] = json.loads(p.read_text())

specs = {}
for name in reports:
    try:
        specs[name] = make_ladder(name)
    except Exception:
        pass


def rung_meta(spec, rung_name):
    for r in spec.rungs:
        if r.name == rung_name:
            consts = [n for n in r.template.walk() if isinstance(n, Const)]
            params = [n for n in r.template.walk() if isinstance(n, Param)]
            big = any(
                str(getattr(c, "value_type", "")).lower() in BIG_BATTERY for c in consts
            )
            return len(params), len(consts), big
    return None


print("=" * 70)
print("T1 -- __const__ share of considered, every cell with by_primitive")
print("=" * 70)
shares = []
for name, r in reports.items():
    for row in r["cost_matrix"]:
        for lv, cell in row["columns"].items():
            for bp in cell.get("by_primitive", []):
                if bp["primitive"] == "__const__":
                    shares.append((bp["share"], name, row["task_id"], lv))
shares.sort()
if shares:
    n = len(shares)
    vals = [s[0] for s in shares]
    print(f"cells with attribution: {n}")
    for q in (0, 10, 25, 50, 75, 90, 100):
        i = min(n - 1, (q * n) // 100)
        print(f"  p{q:>3}: __const__ share {vals[i]:.4f}")
    print(f"  cells with share > 0.9: {sum(v > 0.9 for v in vals)}/{n}")
    print(f"  cells with share > 0.99: {sum(v > 0.99 for v in vals)}/{n}")
    print("  lowest 3:", [(f"{s:.3f}", nm, t) for s, nm, t, _ in shares[:3]])

print()
print("=" * 70)
print("T2 -- per-added-rung growth at fixed depth vs the added rung's shape")
print("     (exhaustive, uncompromised reports only; growth L_(i-1)->L_i)")
print("=" * 70)
t2 = []
for name, r in reports.items():
    if r.get("compromises"):
        continue
    spec = specs.get(name)
    if spec is None:
        continue
    row = r["cost_matrix"][0]
    cols = row["columns"]
    levels = sorted(cols, key=int)
    cens = any(cols[lv]["censored"] for lv in levels)
    if cens:
        continue
    for i in range(1, len(levels)):
        a, b = cols[levels[i - 1]]["considered"], cols[levels[i]]["considered"]
        if not a:
            continue
        rung = spec.rungs[i - 1]
        meta = rung_meta(spec, rung.name)
        if meta is None:
            continue
        arity, nconst, big = meta
        t2.append((b / a, arity, nconst, big, name, rung.name))
print(f"{'growth':>8} {'arity':>5} {'#const':>6} {'big-battery':>11}  ladder/rung")
for g, arity, nconst, big, name, rung in sorted(t2, key=lambda x: -x[0]):
    print(f"{g:7.2f}x {arity:>5} {nconst:>6} {str(big):>11}  {name}/{rung}")
by_arity: dict[int, list[float]] = {}
for g, arity, *_ in t2:
    by_arity.setdefault(arity, []).append(g)
print("median growth by minted arity:")
for arity in sorted(by_arity):
    v = sorted(by_arity[arity])
    print(f"  arity {arity}: n={len(v)}  median {v[len(v) // 2]:.2f}x  max {v[-1]:.2f}x")

print()
print("=" * 70)
print("T3 -- marginal-rung-value predictor shoot-out (own_tasks_speedup)")
print("=" * 70)
rows = []
for name, r in reports.items():
    spec = specs.get(name)
    if spec is None:
        continue
    for m in r.get("comparisons", {}).get("marginal_rung_value", []):
        sp = m.get("own_tasks_speedup")
        meta = rung_meta(spec, m["rung"])
        if sp is None or meta is None:
            continue
        arity, nconst, big = meta
        top_fed = m.get("layer_above") == "top"
        rows.append((sp, arity, nconst, big, top_fed))
print(f"rungs with data: {len(rows)}")


def split(label, pred):
    yes = sorted(sp for sp, *rest in rows if pred(rest))
    no = sorted(sp for sp, *rest in rows if not pred(rest))
    def med(v):
        return v[len(v) // 2] if v else float("nan")
    overlap = "OVERLAP" if yes and no and (yes[0] < no[-1]) else "clean"
    print(
        f"  {label:38} yes: n={len(yes):2} med {med(yes):7.2f}x  |  "
        f"no: n={len(no):2} med {med(no):7.2f}x  ratio {med(yes) / med(no) if no else 0:6.1f}x  [{overlap}]"
    )


split("binds big-battery constant", lambda r: r[2])
split("binds >=1 constant of any type", lambda r: r[1] >= 1)
split("minted arity >= 2", lambda r: r[0] >= 2)
split("top-fed (consumer is the top)", lambda r: r[3])

print()
print("=" * 70)
print("T4 -- every raw arm on disk")
print("=" * 70)
print(f"{'ladder':34} {'d_raw':>5} {'floor':>5} {'ratio':>12} {'kind':>12} {'sound':>5}")
for name, r in reports.items():
    arm = r.get("cost", {}).get("raw_arm")
    if not arm:
        continue
    spec = specs.get(name)
    floor_n = "?"
    if spec is not None:
        try:
            floor_n = len(list(spec.floor().primitives))
        except Exception:
            floor_n = "?"
    d_raw = (r.get("shape", {}).get("raw_depth_profile") or ["?"])[0]
    ratio = arm.get("amortization_ratio")
    kind = arm.get("amortization_ratio_kind")
    print(
        f"{name:34} {d_raw!s:>5} {floor_n!s:>5} {ratio!s:>12} {kind!s:>12} {arm.get('sound')!s:>5}"
    )
