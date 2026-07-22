"""Where is the tractability frontier, really? `cost_L(d)` measured on four representative floors.

The AL plan's first correction says the depth-2/3 jump convention was a design habit, never a
measured limit (the 50k `considered_limit` guard that produced it arrived at the END of the batch,
and al14's diagnosis showed it was three orders too small). This sweep replaces the folklore with
a table: for each floor, enumerate to depth 2..5 and record what it actually costs.

The engine runs `_enumerate` once for the whole `depth_limit` (no iterative deepening), so the cost
is depth-driven whether or not the task solves — which is what makes this `cost_L(d)`, not
`cost_to_solution`.

Also records the forecast for each cell. The forecaster was backtested at depths <= 4 (the
reference budgets); the depth-5 cells here test it OUTSIDE that range, which is exactly where a
planning instrument has to hold if it is going to be trusted to price a cell nobody has run.

Usage: uv run python experiments/2026-07-22-tractability-frontier/artifacts/frontier_sweep.py
"""

from __future__ import annotations

import time
from dataclasses import replace

from arc_lab.program_search.execution.forecast_cost import forecast_cost
from arc_lab.program_search.ladders.registry import make_ladder

#: (label, ladder whose FLOOR we borrow, what makes it interesting)
FLOORS = [
    ("geometric", "al7-fast-tower", "concat_h/concat_v/flip_h/flip_v — param-free, arity 2"),
    ("layout+params", "al17-shift-frame-tall", "concat_v/translate/pad — INT+COLOR params"),
    ("colour", "al1-mirror", "flip_h/flip_v/map_color — 2 COLOR params"),
    ("cell", "al14-cell-row-grid", "read/set_cell/sub — arity 4, the al14 floor"),
]

DEPTHS = (2, 3, 4, 5)

#: Generous enough that "censored" means genuinely expensive, small enough to finish this century.
#: ~4 minutes per cell at the measured ~20k candidates/s.
GUARD = 5_000_000


def main() -> None:
    print(
        f"{'floor':14s} {'d':>2s} {'considered':>12s} {'seconds':>8s} {'cand/s':>9s} "
        f"{'censored':>9s} {'solved':>7s} {'forecast':>14s} {'fc/actual':>10s}"
    )
    for label, ladder, _note in FLOORS:
        spec = make_ladder(ladder)
        config = spec.reference_config
        floor = spec.floor()
        task = next(
            e.task
            for e in spec.train_corpus.entries
            if e.task.task_id == spec.rungs[0].demonstrations[0].task_id
        )
        for depth in DEPTHS:
            budget = replace(
                config.budget,
                depth_limit=depth,
                considered_limit=GUARD,
                considered_limit_mode="immediate",
            )
            cell = replace(config, library=floor, budget=budget)
            forecast = forecast_cost(cell, task)
            started = time.time()
            result = config.search_engine.run(
                train_examples=task.train,
                library=floor,
                constraints=config.constraints,
                cost=config.cost,
                budget=budget,
            )
            elapsed = time.time() - started
            stats = result.stats
            ratio = forecast.total_considered / stats.considered if stats.considered else 0.0
            print(
                f"{label:14s} {depth:>2d} {stats.considered:>12,} {elapsed:>8.1f} "
                f"{stats.considered / max(elapsed, 1e-9):>9,.0f} {str(stats.censored):>9s} "
                f"{str(bool(result.ranked_programs)):>7s} {forecast.total_considered:>14,} "
                f"{ratio:>10.2f}",
                flush=True,
            )
            if stats.censored:
                break  # deeper cells on this floor only censor harder


if __name__ == "__main__":
    main()
