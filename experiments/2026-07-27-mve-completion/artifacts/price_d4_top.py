"""Price G3: what does the NOR depth-4 top actually cost to FIND at a raised guard?

The 2-rung NOR members censor at 2M with the top unfound. This measures whether the top is
findable at all within 30M considered at the schedule's own pool (`pool_for_depth(30, 4) = 750`),
with an immediate stop -- so the answer is either an exact cost-to-first or a proven `> 30M` bound.
Direct engine drive (same pattern as the batch analysis's `pool_vs_top_reachability.py`);
not a recorded run.
"""

import dataclasses

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import pool_for_depth

NAME = "94f9d214-nor-halves"
GUARD = 30_000_000

spec = make_ladder(NAME)
k = len(spec.rungs)
lib = spec.oracle_library(k)
sched = spec.depth_schedule()
entry = {e.task.task_id: e for e in spec.train_corpus.entries}[spec.top.task_ids[0]]
cfg = spec.reference_config
depth = sched[-1]
pool = pool_for_depth(cfg.budget.max_pool, depth)
print(f"== {NAME}  schedule={sched}  top at depth {depth}, pool {pool}, guard {GUARD:,}", flush=True)
b = dataclasses.replace(
    cfg.budget,
    depth_limit=depth,
    max_pool=pool,
    considered_limit=GUARD,
    solution_limit=1,
    solution_limit_mode="immediate",
)
r = cfg.search_engine.run(
    train_examples=tuple(entry.task.train),
    library=lib,
    constraints=cfg.constraints,
    cost=cfg.cost,
    budget=b,
)
solved = bool(r.ranked_programs)
print(
    f"solved={solved}  considered={r.stats.considered:,}  "
    f"first_idx={r.stats.first_solution_index}  censored={r.stats.censored}",
    flush=True,
)
if solved:
    print("program:", r.ranked_programs[0], flush=True)
