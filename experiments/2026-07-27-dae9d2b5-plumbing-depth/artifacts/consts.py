import dataclasses
from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.ladders.lang.load import draft_spec
from arc_lab.program_search.search.leaves import policy_constants
from arc_lab.program_search.substrate.program import Apply, Const, Input
from arc_lab.program_search.substrate.types import COLOR, INT

spec = draft_spec(load_ladder("dae9d2b5-split-recolor"))
lib2 = spec.oracle_library(2)
entry = {e.task.task_id: e for e in spec.train_corpus.entries}["recolored_west-00"]
grids = [ex.input for ex in entry.task.train]
cfg = spec.reference_config

consts = list(policy_constants(grids, cfg.search_engine.constant_sources, lib2))
colors = sorted(c.value for c, t in consts if t == COLOR)
ints = sorted(c.value for c, t in consts if t == INT)
print("COLOR minted:", colors)
print("INT minted:", ints)

# Can the engine reach the two ingredients separately?
for label, sol, depth in [
    ("west(input)", Apply("west", (Input(),)), 1),
    ("map_color(west(input),4,6)", Apply("map_color", (Apply("west", (Input(),)), Const(4, COLOR), Const(6, COLOR))), 2),
    ("map_color(input,4,6)", Apply("map_color", (Input(), Const(4, COLOR), Const(6, COLOR))), 1),
]:
    from arc_lab.core.task import Example, Task
    exs = tuple(Example(input=ex.input, output=sol.evaluate(ex.input, lib2)) for ex in entry.task.train)
    budget = dataclasses.replace(cfg.budget, depth_limit=depth, considered_limit=3_000_000)
    r = cfg.search_engine.run(train_examples=exs, library=lib2, constraints=cfg.constraints,
                              cost=cfg.cost, budget=budget)
    best = r.ranked_programs[0] if r.ranked_programs else None
    print(f"  depth {depth}: {label:32} solved={bool(r.ranked_programs)} considered={r.stats.considered:,} best={best}")
