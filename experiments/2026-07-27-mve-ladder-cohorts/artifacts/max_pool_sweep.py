import dataclasses, time
from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.ladders.lang.load import draft_spec

spec = draft_spec(load_ladder("dae9d2b5-split-recolor"))
lib2 = spec.oracle_library(2)
entry = {e.task.task_id: e for e in spec.train_corpus.entries}["recolored_west-00"]
cfg = spec.reference_config
intended = "map_color(west(input), 4, 6)"

for max_pool in (20, 30, 40, 60, 100, 150):
    budget = dataclasses.replace(cfg.budget, depth_limit=2, max_pool=max_pool,
                                 considered_limit=3_000_000)
    t0 = time.time()
    r = cfg.search_engine.run(train_examples=tuple(entry.task.train), library=lib2,
                              constraints=cfg.constraints, cost=cfg.cost, budget=budget)
    best = str(r.ranked_programs[0]) if r.ranked_programs else None
    print(f"max_pool={max_pool:4}  considered={r.stats.considered:>9,}  {time.time()-t0:5.1f}s  "
          f"as_intended={best == intended}  best={best}")
