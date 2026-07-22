"""`cost_L(d)` with the pool freed — separating DEPTH cost from POOL STARVATION.

Sweep 1 (`frontier_sweep.py`) found that on three of four floors, rounds past depth 3 composed
*nothing*: once `max_pool` binds and no new entry survives eviction, the new-layer restriction
makes the next round exactly zero. So sweep 1 measured pool starvation, not the cost of depth —
which is precisely the standing caveat in the design doc (§5.3): "raising `depth_limit` without
raising `max_pool` measures pool starvation, not depth cost."

This sweep re-runs the same floors at a pool large enough not to bind, so the depth term is the
one being measured. `saturated` reports whether any round composed zero (the tell that the answer
is starvation again rather than exhaustion of the reachable space).

Usage: uv run python experiments/2026-07-22-tractability-frontier/artifacts/frontier_sweep_pool.py
"""

from __future__ import annotations

import time
from dataclasses import replace

from arc_lab.program_search.ladders.registry import make_ladder

FLOORS = [
    ("geometric", "al7-fast-tower"),
    ("layout+params", "al17-shift-frame-tall"),
    ("colour", "al1-mirror"),
]
POOLS = (400, 20_000)
DEPTHS = (2, 3, 4, 5)
GUARD = 5_000_000


def main() -> None:
    print(
        f"{'floor':14s} {'pool':>7s} {'d':>2s} {'considered':>12s} {'seconds':>8s} "
        f"{'final pool':>11s} {'saturated':>10s} {'censored':>9s}"
    )
    for label, ladder in FLOORS:
        spec = make_ladder(ladder)
        config = spec.reference_config
        floor = spec.floor()
        task = next(
            e.task
            for e in spec.train_corpus.entries
            if e.task.task_id == spec.rungs[0].demonstrations[0].task_id
        )
        for pool in POOLS:
            for depth in DEPTHS:
                budget = replace(
                    config.budget,
                    depth_limit=depth,
                    max_pool=pool,
                    considered_limit=GUARD,
                    considered_limit_mode="immediate",
                )
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
                generations = list(stats.generations)
                saturated = any(
                    g.get("composed") == 0 for g in generations[1:]
                )  # a round that built nothing
                final_pool = generations[-1].get("pool_size_end") if generations else None
                print(
                    f"{label:14s} {pool:>7,} {depth:>2d} {stats.considered:>12,} {elapsed:>8.1f} "
                    f"{str(final_pool):>11s} {str(saturated):>10s} {str(stats.censored):>9s}",
                    flush=True,
                )
                if stats.censored:
                    break


if __name__ == "__main__":
    main()
