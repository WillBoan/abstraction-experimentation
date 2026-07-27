"""C1-C4: join the static breadth census to measured per-cell cost, and decompose the agreement.

The census (`ladders/breadth.py`) claims to be "an INDICATOR for ranking, never a forecast", to be
read "to RANK floors and to compare a ladder against itself". Neither half has ever been tested.
The batch analysis's A8b join broke and was abandoned; a first pass
(`experiments/2026-07-27-mve-completion/artifacts/census_calibration.py`) reported a pooled
Spearman of 0.881 but carries four defects this script fixes:

1. **Target mismatch.** It used `report.cost.jump_costs[rung]`, which SUMS `considered` over all of
   a rung's demonstration tasks -- while `CheckContext.rung_breadth` prices only `targets[0]`, the
   FIRST demo task's grids. A census built on one task was compared against a cost summed over n.
   Here the target is the cell for the SAME (rung, task) the census was built on.
2. **Confounded correlation.** Pooling all rungs mixes BETWEEN-ladder variation (b1 spans 2 ->
   1,315, the "rank floors" claim) with WITHIN-ladder variation (b1 rises by exactly +1 per rung,
   because a level's library grows by one gifted rung -- the "compare a ladder against itself"
   claim). They are separate claims with separate stakes; decomposed below.
3. **A degenerate predictor.** It reported `spearman(b1**depth, measured)` alongside
   `spearman(b1, measured)` as if a comparison. Every uncensored row is depth 2, so `b1**2` is a
   monotone transform of `b1` and the two are EQUAL by construction (0.881 = 0.881). Dropped.
4. **No pool variable.** `max_pool` is a first-order cost driver the census cannot see -- and the
   batch contains a controlled pair that isolates it exactly (C3).
"""

from __future__ import annotations

import json
from pathlib import Path

from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder
from arc_lab.program_search.ladders.run import pool_for_depth

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

    if len(xs) < 2:
        return float("nan")
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def median(vs: list[float]) -> float:
    s = sorted(vs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


class Row:
    __slots__ = (
        "b1_full",
        "b1_min",
        "censored",
        "depth",
        "ladder",
        "measured",
        "pool",
        "rung",
        "task",
    )

    def __init__(self, **kw: object) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


rows: list[Row] = []
skipped: list[tuple[str, str]] = []

for name in sorted(ladder_paths()):
    report_path = LADDERS / name / "report.json"
    if not report_path.exists():
        skipped.append((name, "no committed report"))
        continue
    report = json.loads(report_path.read_text())
    if report.get("compromises"):
        codes = ",".join(c["code"] for c in report["compromises"])
        skipped.append((name, f"compromised: {codes}"))
        continue

    spec = make_ladder(name)
    ctx = CheckContext(spec, corpus_backed=True)
    schedule = ctx.depth_schedule
    configured_pool = spec.reference_config.budget.max_pool

    # cost_matrix -> {(task_id, level): cell}
    cells: dict[tuple[str, str], dict] = {}
    for row in report["cost_matrix"]:
        for level, cell in row["columns"].items():
            cells[(row["task_id"], level)] = cell

    for rb in ctx.rung_breadth:
        # The census prices `demo_targets[rung][0]`; join to THAT task's cell, at the level the
        # rung's own search runs on (rung at level i searches over L_{i-1}).
        targets = ctx.demo_targets[rb.name]
        if not targets:
            continue
        task_id = targets[0][0]
        level = rb.level - 1
        cell = cells.get((task_id, str(level)))
        if cell is None:
            skipped.append((f"{name}/{rb.name}", f"no cell for {task_id}@L{level}"))
            continue
        depth = schedule[level]
        rows.append(
            Row(
                ladder=name,
                rung=rb.name,
                task=task_id,
                b1_full=rb.b1_full,
                b1_min=rb.b1_min,
                depth=depth,
                pool=pool_for_depth(configured_pool, depth),
                measured=cell["considered"],
                censored=bool(cell["censored"]),
            )
        )

print("=" * 100)
print("C1 -- the corrected join (uncompromised reports; measured = the cell the census priced)")
print("=" * 100)
print(
    f"{'ladder':30} {'rung':17} {'b1_full':>8} {'b1_min':>7} {'tax':>8} "
    f"{'d':>2} {'pool':>5} {'measured':>10} {'cost/b1':>8}  cens"
)
for r in rows:
    tax = r.b1_full / r.b1_min if r.b1_min else float("nan")
    per = r.measured / r.b1_full if r.b1_full else float("nan")
    print(
        f"{r.ladder:30} {r.rung:17} {r.b1_full:>8,} {r.b1_min:>7,} {tax:>8.1f} "
        f"{r.depth:>2} {r.pool:>5} {r.measured:>10,} {per:>8.1f}  {'C' if r.censored else ''}"
    )
if skipped:
    print("\nexcluded:")
    for what, why in skipped:
        print(f"  {what:40} {why}")

usable = [r for r in rows if not r.censored]
print(f"\njoined rungs: {len(rows)}   usable (uncensored): {len(usable)}")
depths = sorted({r.depth for r in usable})
print(f"depths present among usable rows: {depths}")

print()
print("=" * 100)
print("C2 -- rank agreement, DECOMPOSED (the census makes two separate claims)")
print("=" * 100)

pooled = spearman([float(r.b1_full) for r in usable], [float(r.measured) for r in usable])
print(f"\n(a) POOLED over all rungs         spearman(b1_full, measured) = {pooled:+.3f}  (n={len(usable)})")
print("    ^ the first pass's number. Confounded: mixes the two claims below.")

# BETWEEN-ladder: one point per ladder -- the "rank floors" claim.
by_ladder: dict[str, list[Row]] = {}
for r in usable:
    by_ladder.setdefault(r.ladder, []).append(r)
lad_b1 = [median([float(r.b1_full) for r in rs]) for rs in by_ladder.values()]
lad_cost = [median([float(r.measured) for r in rs]) for rs in by_ladder.values()]
between = spearman(lad_b1, lad_cost)
print(f"\n(b) BETWEEN ladders (median/ladder) spearman = {between:+.3f}  (n={len(by_ladder)} ladders)")
print('    ^ the census\'s "RANK FLOORS" claim. This is the one that matters for choosing a floor.')
for (lname, rs), b1, cost in zip(by_ladder.items(), lad_b1, lad_cost, strict=True):
    print(f"      {lname:30} med b1 {b1:>9,.0f}   med measured {cost:>11,.0f}   pool {rs[0].pool}")

# WITHIN-ladder: the "compare a ladder against itself" claim.
print('\n(c) WITHIN each ladder -- the "compare a ladder against ITSELF" claim:')
within: list[float] = []
for lname, rs in by_ladder.items():
    if len(rs) < 3:
        print(f"      {lname:30} n={len(rs)} (too few rungs to rank)")
        continue
    rho = spearman([float(r.b1_full) for r in rs], [float(r.measured) for r in rs])
    within.append(rho)
    b1s = [r.b1_full for r in rs]
    costs = [r.measured for r in rs]
    print(
        f"      {lname:30} rho {rho:+.3f}   b1 range {min(b1s):,}-{max(b1s):,} "
        f"(spread {max(b1s) - min(b1s):+,})   measured range {min(costs):,}-{max(costs):,}"
    )
if within:
    print(f"      median within-ladder rho = {median(within):+.3f}  (n={len(within)} ladders)")

print()
print("=" * 100)
print("C3 -- what the census is BLIND to: a controlled pair, same census, different pool")
print("=" * 100)
pair = [r for r in usable if r.ladder in ("dae9d2b5-split-recolor", "dae9d2b5-split-recolor-lean")]
by_rung: dict[str, list[Row]] = {}
for r in pair:
    by_rung.setdefault(r.rung, []).append(r)
print(f"\n{'rung':17} {'b1_full':>8}  {'pool 150':>12} {'pool 30':>10} {'ratio':>8}")
for rung, rs in by_rung.items():
    if len(rs) != 2:
        continue
    fat = next(r for r in rs if r.pool == 150)
    lean = next(r for r in rs if r.pool == 30)
    assert fat.b1_full == lean.b1_full, "census must be identical for this to be controlled"
    print(
        f"{rung:17} {fat.b1_full:>8,}  {fat.measured:>12,} {lean.measured:>10,} "
        f"{fat.measured / lean.measured:>7.1f}x"
    )
print(
    "\nSame ladder, same floor, same rungs, same depth schedule -> BYTE-IDENTICAL census readings.\n"
    "Measured cost differs by the ratio above, entirely from `max_pool`. The census cannot see it."
)

print()
print("=" * 100)
print("C4 -- the mechanism: does cost track b1, or does the pool bind?")
print("=" * 100)
print(
    "\nIf round 1 floods the pool (b1 >> pool), round 2 composes over a POOL-SIZED census, so\n"
    "cost ~ b1 + g(pool, library) -- additive in b1, not multiplicative. Test: cost/b1 should\n"
    "COLLAPSE for rows where b1/pool is large, and the residual (cost - b1) should cluster by pool.\n"
)
print(f"{'ladder':30} {'rung':17} {'b1/pool':>8} {'cost/b1':>9} {'cost-b1':>11}")
for r in sorted(usable, key=lambda r: r.b1_full / r.pool):
    print(
        f"{r.ladder:30} {r.rung:17} {r.b1_full / r.pool:>8.2f} "
        f"{r.measured / r.b1_full:>9.1f} {r.measured - r.b1_full:>11,}"
    )

flooded = [r for r in usable if r.b1_full / r.pool >= 1.0]
unflooded = [r for r in usable if r.b1_full / r.pool < 1.0]
print(
    f"\n  pool-FLOODED rows (b1 >= pool, n={len(flooded)}): "
    f"median cost/b1 = {median([r.measured / r.b1_full for r in flooded]):.1f}"
    if flooded
    else "\n  no flooded rows"
)
print(
    f"  pool-SLACK rows  (b1 <  pool, n={len(unflooded)}): "
    f"median cost/b1 = {median([r.measured / r.b1_full for r in unflooded]):.1f}"
    if unflooded
    else "  no slack rows"
)
if flooded and unflooded:
    print(
        "\n  If these two medians differ substantially, cost/b1 is NOT a floor constant and the\n"
        "  census's units cannot be converted to a cost forecast without the pool."
    )
