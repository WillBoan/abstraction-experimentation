"""S10: calibrate the breadth census against measured cost -- the standing gap.

The census's own claim (`ladders/breadth.py`) is "an INDICATOR for ranking, never a forecast".
That claim has never been tested against the batch's measured costs (the batch analysis's A8b
join broke and was abandoned when the top-unreachable defect took over). Here: for every ladder
whose committed report is UNCOMPROMISED (cost-paid-full is real, not truncated by an early stop),
join each rung's static census reading with its measured jump cost, and compute rank agreement.

Predictors tested, per rung searching at depth d over `L_{i-1}`:
- ``b1_full``      -- round-1 width as the search has it (the census's headline number)
- ``ratio``        -- the round-1 tax factor (b1_full / b1_min)
- ``b1_full ** d`` -- the naive depth-compounded width

Target: the report's measured ``jump_costs[rung]`` (cost-paid-full), excluding rungs whose demo
cells were censored (a truncated cost cannot calibrate anything).
"""

import json
from pathlib import Path

from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(vs: list[float]) -> list[float]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        rank = [0.0] * len(vs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rank[order[k]] = avg
            i = j + 1
        return rank

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


rows: list[tuple[str, str, int, int, float, int, bool]] = []
for name in sorted(ladder_paths()):
    report_path = LADDERS / name / "report.json"
    if not report_path.exists():
        continue
    report = json.loads(report_path.read_text())
    if report.get("compromises"):
        continue  # an early stop truncates cost-paid-full; nothing to calibrate against
    jump_costs = report["cost"]["jump_costs"]
    # censored rung cells: a truncated measured cost is a lower bound, excluded
    censored_rungs: set[str] = set()
    for row in report["cost_matrix"]:
        rung = row.get("rung")
        if not rung or rung == "top":
            continue
        for cell in row["columns"].values():
            if cell.get("censored"):
                censored_rungs.add(rung)
    spec = make_ladder(name)
    ctx = CheckContext(spec, corpus_backed=True)
    schedule = ctx.depth_schedule
    for rb in ctx.rung_breadth:
        cost = jump_costs.get(rb.name)
        if cost is None:
            continue
        depth = schedule[rb.level - 1]
        rows.append(
            (
                name,
                rb.name,
                rb.b1_full,
                depth,
                rb.ratio or 0.0,
                int(cost),
                rb.name in censored_rungs,
            )
        )

print(f"{'ladder':30} {'rung':18} {'b1_full':>8} {'d':>2} {'tax':>8} {'measured':>10}  cens")
for name, rung, b1, depth, ratio, cost, cens in rows:
    print(f"{name:30} {rung:18} {b1:>8,} {depth:>2} {ratio:>8.1f} {cost:>10,}  {'C' if cens else ''}")

usable = [(b1, d, r, c) for _, _, b1, d, r, c, cens in rows if not cens]
print(f"\nuncompromised rungs: {len(rows)}  usable (uncensored): {len(usable)}")
b1s = [float(b1) for b1, _, _, _ in usable]
depths = [d for _, d, _, _ in usable]
taxes = [r for _, _, r, _ in usable]
costs = [float(c) for _, _, _, c in usable]
compounded = [b1 ** d for (b1, d, _, _) in usable]
print(f"spearman(b1_full, measured)        = {spearman(b1s, costs):.3f}")
print(f"spearman(tax ratio, measured)      = {spearman(taxes, costs):.3f}")
print(f"spearman(b1_full^depth, measured)  = {spearman(compounded, costs):.3f}")
d2 = [(b1, c) for (b1, d, _, c) in usable if d == 2]
if len(d2) >= 3:
    print(
        f"spearman(b1_full, measured | d=2)  = "
        f"{spearman([float(b) for b, _ in d2], [float(c) for _, c in d2]):.3f}  (n={len(d2)})"
    )
