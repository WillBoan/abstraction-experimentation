import dataclasses
from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.ladders.lang.load import draft_spec

spec = draft_spec(load_ladder("dae9d2b5-split-recolor"))
lib2 = spec.oracle_library(2)
entry = {e.task.task_id: e for e in spec.train_corpus.entries}["recolored_west-00"]
cfg = spec.reference_config

for max_pool in (150, 400, 1000, 4000):
    budget = dataclasses.replace(cfg.budget, depth_limit=2, max_pool=max_pool,
                                 considered_limit=3_000_000)
    result = cfg.search_engine.run(
        train_examples=tuple(entry.task.train), library=lib2,
        constraints=cfg.constraints, cost=cfg.cost, budget=budget)
    top = result.ranked_programs[0] if result.ranked_programs else None
    print(f"max_pool={max_pool:5}  solved={bool(result.ranked_programs)}  "
          f"considered={result.stats.considered:,}  best={top}")
