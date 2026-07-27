"""C5: does the FULL forecaster beat the round-1 census on the same cells?

C3/C4 showed the census's blindness is `max_pool`, and that the blindness is first-order (19-26x on
a controlled pair; median cost/b1 6.2x apart between pool-flooded and pool-slack rows). The repo
already carries a static model that DOES model the pool: `execution/forecast_cost`, which adds the
new-layer restriction, per-round survival, and `_capped` (max_pool as a proportional shrink).

So the standing gap ("the breadth census has never been calibrated against measured cost") has a
sharper form than "how good is the census": it is **does the existing full model already close the
gap, or is a new instrument needed?** Same cells as `census_join.py`, same measured targets, no new
runs. Both predictors are STATIC -- neither runs a search.

`forecast_cost` is run in its no-run mode (DEFAULT_SURVIVAL = 0.44, the batch-median funnel rate),
which is the mode a lint could actually use.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from arc_lab.program_search.execution.forecast_cost import forecast_cost
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


results: list[tuple[str, str, int, int, int, int, bool]] = []

for name in sorted(ladder_paths()):
    report_path = LADDERS / name / "report.json"
    if not report_path.exists():
        continue
    report = json.loads(report_path.read_text())
    if report.get("compromises"):
        continue

    spec = make_ladder(name)
    ctx = CheckContext(spec, corpus_backed=True)
    schedule = ctx.depth_schedule
    configured_pool = spec.reference_config.budget.max_pool

    cells: dict[tuple[str, str], dict] = {}
    for row in report["cost_matrix"]:
        for level, cell in row["columns"].items():
            cells[(row["task_id"], level)] = cell

    for rb in ctx.rung_breadth:
        targets = ctx.demo_targets[rb.name]
        if not targets:
            continue
        task_id = targets[0][0]
        level = rb.level - 1
        cell = cells.get((task_id, str(level)))
        entry = ctx.by_id.get(task_id)
        if cell is None or entry is None:
            continue
        depth = schedule[level]
        pool = pool_for_depth(configured_pool, depth)
        config = spec.reference_config.with_(
            library=spec.oracle_library(level),
            budget=replace(
                spec.reference_config.budget, depth_limit=depth, max_pool=pool
            ),
            learn=None,
        )
        try:
            fc = forecast_cost(config, entry.task)
        except NotImplementedError as exc:  # pragma: no cover - diagnostic path
            print(f"  !! {name}/{rb.name}: {exc}")
            continue
        results.append(
            (
                name,
                rb.name,
                rb.b1_full,
                fc.total_considered,
                cell["considered"],
                pool,
                bool(cell["censored"]),
            )
        )

usable = [r for r in results if not r[6]]

print("=" * 104)
print("C5 -- census (round-1 width) vs the FULL forecaster, against the same measured cells")
print("=" * 104)
print(
    f"\n{'ladder':30} {'rung':17} {'pool':>5} {'b1_full':>8} {'forecast':>10} "
    f"{'measured':>10} {'fc/meas':>8}"
)
for name, rung, b1, pred, meas, pool, _cens in usable:
    print(
        f"{name:30} {rung:17} {pool:>5} {b1:>8,} {pred:>10,} {meas:>10,} "
        f"{pred / meas:>7.2f}x"
    )

preds = [float(r[3]) for r in usable]
meass = [float(r[4]) for r in usable]
b1s = [float(r[2]) for r in usable]

print(f"\nn = {len(usable)} cells")
print(f"  spearman(b1_full,  measured) = {spearman(b1s, meass):+.3f}   <- the census")
print(f"  spearman(forecast, measured) = {spearman(preds, meass):+.3f}   <- the full model")

ratios = [p / m for p, m in zip(preds, meass, strict=True)]
print("\nAccuracy of the full forecaster (predicted / measured):")
print(f"  median  {median(ratios):.2f}x")
print(f"  range   {min(ratios):.2f}x .. {max(ratios):.2f}x")
within2 = sum(1 for r in ratios if 0.5 <= r <= 2.0)
within10 = sum(1 for r in ratios if 0.1 <= r <= 10.0)
print(f"  within 2x  : {within2}/{len(ratios)}")
print(f"  within 10x : {within10}/{len(ratios)}")

# The controlled pair -- the case the census provably cannot call.
print("\nThe C3 controlled pair (identical census, 19-26x measured spread):")
print(f"  {'ladder':32} {'rung':17} {'b1':>7} {'forecast':>10} {'measured':>10} {'fc/meas':>8}")
for name, rung, b1, pred, meas, _pool, _c in usable:
    if name in ("dae9d2b5-split-recolor", "dae9d2b5-split-recolor-lean"):
        print(
            f"  {name:32} {rung:17} {b1:>7,} {pred:>10,} {meas:>10,} {pred / meas:>7.2f}x"
        )
print(
    "\n  The census reads these 8 cells as ~identical (b1 1,211-1,214). If the forecaster's\n"
    "  numbers separate the two pools, the pool-blindness is FIXED by a model that already exists."
)
