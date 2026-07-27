import dataclasses
from arc_lab.program_search.ladders.registry import make_ladder

for name in ("94f9d214-nor-recolor", "dae9d2b5-split-halves-lean"):
    spec = make_ladder(name)
    k = len(spec.rungs)
    lib = spec.oracle_library(k)
    sched = spec.depth_schedule()
    entry = {e.task.task_id: e for e in spec.train_corpus.entries}[spec.top.task_ids[0]]
    cfg = spec.reference_config
    print(f"== {name}  schedule={sched}  top searched at depth {sched[-1]}", flush=True)
    for pool in (30, 60, 150):
        b = dataclasses.replace(cfg.budget, depth_limit=sched[-1], max_pool=pool,
                                considered_limit=5_000_000)
        r = cfg.search_engine.run(train_examples=tuple(entry.task.train), library=lib,
                                  constraints=cfg.constraints, cost=cfg.cost, budget=b)
        print(f"   max_pool={pool:4}  solved={bool(r.ranked_programs):5}  "
              f"considered={r.stats.considered:>9,}", flush=True)
