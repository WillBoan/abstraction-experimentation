import dataclasses
from arc_lab.core.task import Example
from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.ladders.lang.load import draft_spec
from arc_lab.program_search.substrate.program import Apply, Input

for name, rung_call in [("dae9d2b5-split-recolor", "west"), ("dae9d2b5-halves-union", "west")]:
    spec = draft_spec(load_ladder(name))
    lib = spec.oracle_library(1)                      # floor + west
    prim = {p.name: p for p in lib.primitives}[rung_call]
    print(f"\n== {name}: {rung_call}")
    print("   param_types:", [str(t) for t in prim.param_types], "-> ", prim.return_type)
    print("   template:", prim.template)
    entry = {e.task.task_id: e for e in spec.train_corpus.entries}[f"{rung_call}-00"]
    sol = Apply(rung_call, (Input(),))
    exs = tuple(Example(input=ex.input, output=sol.evaluate(ex.input, lib)) for ex in entry.task.train)
    cfg = spec.reference_config
    budget = dataclasses.replace(cfg.budget, depth_limit=1, considered_limit=3_000_000)
    r = cfg.search_engine.run(train_examples=exs, library=lib, constraints=cfg.constraints,
                              cost=cfg.cost, budget=budget)
    print(f"   depth-1 search for {rung_call}(input): solved={bool(r.ranked_programs)} "
          f"considered={r.stats.considered:,} best={r.ranked_programs[0] if r.ranked_programs else None}")
