"""Price G2: what does an UNCOMPROMISED depth-3 top cell cost to exhaust?

The exhaust-semantics curve needs every cell run without a stop limit. This measures the
exhaustion cost of `dae9d2b5-split-halves-lean`'s top cell (depth 3, `pool_for_depth(30,3)=150`)
at a 10M guard -- either an exact cost-to-exhaust, or a proven `> 10M`. That number is ~the whole
marginal cost of an uncompromised re-run of the 2- and 3-rung members, so it prices the G2
decision. Direct engine drive; not a recorded run.
"""

import dataclasses

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import pool_for_depth

NAME = "dae9d2b5-split-halves-lean"
GUARD = 10_000_000

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
    solution_limit=None,
    solution_limit_mode="generation-end",
)
r = cfg.search_engine.run(
    train_examples=tuple(entry.task.train),
    library=lib,
    constraints=cfg.constraints,
    cost=cfg.cost,
    budget=b,
)
print(
    f"solved={bool(r.ranked_programs)}  considered={r.stats.considered:,}  "
    f"first_idx={r.stats.first_solution_index}  censored={r.stats.censored}",
    flush=True,
)
