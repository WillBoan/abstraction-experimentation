"""Does an IMMEDIATE solution_limit collapse the cost of the cells that solve?

The chain pays cost-paid-full everywhere: `west-00` at L_0 finds its solution at candidate index
178 and still enumerates 230,497. That waste is the default `solution_limit_mode='generation-end'`
(the retained solution is the cheapest of its generation). `immediate` stops at the first.
"""
import dataclasses, time
from arc_lab.program_search.ladders.registry import make_ladder

for name, level_pool in (("94f9d214-nor-recolor", 150), ("dae9d2b5-split-recolor-lean", 30)):
    spec = make_ladder(name)
    k = len(spec.rungs)
    sched = spec.depth_schedule()
    cfg = spec.reference_config
    lib = spec.oracle_library(k)
    top_id = spec.top.task_ids[0]
    entry = {e.task.task_id: e for e in spec.train_corpus.entries}[top_id]
    print(f"== {name}: TOP at L_{k}, depth {sched[-1]}, max_pool {level_pool}", flush=True)
    for sl, mode in ((None, "generation-end"), (1, "generation-end"), (1, "immediate")):
        b = dataclasses.replace(cfg.budget, depth_limit=sched[-1], max_pool=level_pool,
                                considered_limit=20_000_000, solution_limit=sl,
                                solution_limit_mode=mode)
        t0 = time.time()
        r = cfg.search_engine.run(train_examples=tuple(entry.task.train), library=lib,
                                  constraints=cfg.constraints, cost=cfg.cost, budget=b)
        st = r.stats
        print(f"   solution_limit={str(sl):4} mode={mode:14} solved={bool(r.ranked_programs):5} "
              f"considered={st.considered:>10,}  first_idx={st.first_solution_index}  "
              f"{time.time()-t0:6.1f}s", flush=True)
