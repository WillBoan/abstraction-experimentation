"""C6: WHY the full forecaster under-reads -- the real funnel vs the modelled rounds.

C5 found the full forecaster is both worse at ranking (rho +0.24 vs the census's +0.80) and a
systematic UNDER-reader (median 0.19x, worst 0.01x). Its own docstring names the candidate
mechanism: `_capped` models `max_pool` as a proportional shrink, and once the modelled census stops
growing, the new-layer restriction (`PROD(now) - PROD(before)`) makes every deeper round's term
structurally ZERO -- so a saturated forecast is a lower bound, not a prediction ("~0.15x of actual
at saturation", measured 2026-07-22).

Tested here by driving the REAL engine on the C3 controlled pair's cell and comparing its
per-generation funnel to the forecaster's per-round model, at both pools. If the engine's round 2
is large while the model's is ~0, saturation is confirmed as the mechanism -- and the fix direction
follows: the modelled census stops GROWING but its CONTENT still turns over, so the new-layer term
must be computed against what the pool now holds, not against its size.

Direct engine drive (not a recorded run) -- the same diagnostic pattern as the batch analysis's
`pool_vs_top_reachability.py`. Cost: the cells are 12k / 230k considered, i.e. seconds.
"""

from __future__ import annotations

import dataclasses

from arc_lab.program_search.execution.forecast_cost import forecast_cost
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import make_ladder

NAME = "dae9d2b5-split-recolor-lean"
RUNG = "west"

spec = make_ladder(NAME)
ctx = CheckContext(spec, corpus_backed=True)
task_id = ctx.demo_targets[RUNG][0][0]
entry = ctx.by_id[task_id]
cfg = spec.reference_config
level = 0  # `west` is rung 1, so its search runs over L_0 (the bare floor)
library = spec.oracle_library(level)
depth = ctx.depth_schedule[level]

print(f"cell: {NAME} / rung {RUNG} / task {task_id} @ L_{level}, depth {depth}")
print(f"floor: {sorted(library.names())}\n")

for pool in (30, 150):
    budget = dataclasses.replace(
        cfg.budget, depth_limit=depth, max_pool=pool, considered_limit=5_000_000
    )
    result = cfg.search_engine.run(
        train_examples=tuple(entry.task.train),
        library=library,
        constraints=cfg.constraints,
        cost=cfg.cost,
        budget=budget,
    )
    stats = result.stats
    config = cfg.with_(library=library, budget=budget, learn=None)
    fc = forecast_cost(config, entry.task)

    print("=" * 92)
    print(f"max_pool = {pool}")
    print("=" * 92)
    print(f"  MEASURED total considered : {stats.considered:>12,}")
    print(f"  FORECAST total considered : {fc.total_considered:>12,}   "
          f"({fc.total_considered / stats.considered:.3f}x)")
    print(f"  forecaster saturated_at   : {fc.saturated_at}")
    print()
    print(f"  {'round':>5} | {'ENGINE composed':>16} {'entered_pool':>13} | "
          f"{'MODEL composed':>15} {'entered_pool':>13}")
    print(f"  {'-' * 5} | {'-' * 16} {'-' * 13} | {'-' * 15} {'-' * 13}")
    n = max(len(stats.generations), len(fc.rounds))
    for i in range(n):
        gen = stats.generations[i] if i < len(stats.generations) else {}
        rnd = fc.rounds[i] if i < len(fc.rounds) else None
        e_comp = gen.get("composed", "")
        e_pool = gen.get("entered_pool", "")
        m_comp = f"{rnd.composed:,}" if rnd else ""
        m_pool = f"{rnd.entered_pool:,}" if rnd else ""
        e_comp_s = f"{e_comp:,}" if isinstance(e_comp, int) else str(e_comp)
        e_pool_s = f"{e_pool:,}" if isinstance(e_pool, int) else str(e_pool)
        print(f"  {i:>5} | {e_comp_s:>16} {e_pool_s:>13} | {m_comp:>15} {m_pool:>13}")
    print()
    for i, rnd in enumerate(fc.rounds):
        if i == 0:
            continue
        print(f"    model round {i} census (capped at {pool}): "
              f"{dict(rnd.census)}  dominant: {rnd.dominant}")
    if fc.flags:
        print("\n  forecaster flags:")
        for flag in fc.flags:
            print(f"    - {flag}")
    print()
