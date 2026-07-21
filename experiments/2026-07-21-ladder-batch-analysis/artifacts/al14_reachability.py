"""Can al14's Floor reach generation 3 on ONE r1 task? Bounded, one task, no run recorded."""
import dataclasses, time
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.search.tracking import SearchTracker

spec = make_ladder("al14-cell-row-grid")
task = next(e.task for e in spec.train_corpus.entries if e.task.task_id.startswith("move_cell_up-00"))
cfg = spec.reference_config
for cap, pool in ((3_000_000, 2000), (3_000_000, 20000)):
    budget = dataclasses.replace(cfg.budget, considered_limit=cap,
                                 considered_limit_mode="immediate", max_pool=pool)
    tracker = SearchTracker()
    t = time.time()
    res = cfg.search_engine.run(train_examples=task.train, library=spec.floor(),
                                constraints=(), cost=cfg.cost, budget=budget, tracker=tracker)
    dt = time.time() - t
    gens = tracker.to_stats(engine="probe").generations if hasattr(tracker, "to_stats") else None
    print(f"max_pool={pool:>6} cap={cap:,}  {dt:6.1f}s  solved={bool(res.ranked_programs)}  "
          f"considered={tracker.considered:,}  rate={tracker.considered/max(dt,1e-9):,.0f}/s", flush=True)
    for g in (gens or []):
        print(f"    gen {g.generation}: composed={g.composed:,} entered_pool={g.entered_pool:,} "
              f"deduped={g.deduped:,} pool={g.pool_size:,}", flush=True)
