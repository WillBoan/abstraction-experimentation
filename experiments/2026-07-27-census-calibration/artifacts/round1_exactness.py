"""C7: is round 1 EXACT, as `breadth.py` documents it to be?

`breadth.py`'s module docstring states: "Two exact quantities per rung ... **round-1 composition
counts**", and "Round 1 is exact, and it UNDERSTATES badly [at depth]". The whole read-side
discipline in LADDER-PROCESS rests on that: the census is trusted as an exact round-1 width and
distrusted only as a depth forecast.

C6 measured the engine composing **131** at round 1 on a cell whose `b1_full` reads **1,211**.
Either the comparison is wrong (the two count different things) or the exactness claim is false.
This isolates it per primitive over the identical leaf census.
"""

from __future__ import annotations

import dataclasses

from arc_lab.program_search.execution.forecast_cost import round_terms
from arc_lab.program_search.ladders.breadth import _leaf_census, rung_breadth
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import make_ladder

NAME = "dae9d2b5-split-recolor-lean"
RUNG = "west"

spec = make_ladder(NAME)
ctx = CheckContext(spec, corpus_backed=True)
task_id, target = ctx.demo_targets[RUNG][0]
entry = ctx.by_id[task_id]
cfg = spec.reference_config
library = spec.oracle_library(0)
grids = [ex.input for ex in entry.task.train]
sources = tuple(cfg.search_engine.constant_sources)
max_arity = cfg.budget.max_arity

census = _leaf_census(grids, sources, library)
print(f"leaf census (breadth.py): {{{', '.join(f'{getattr(t, "name", t)}: {n}' for t, n in census.items())}}}")
print(f"total leaves = {sum(census.values())}   max_arity = {max_arity}\n")

print("round_terms() per primitive over that census:")
terms = round_terms(library, census, max_arity)
total = 0
for primitive, count in sorted(terms, key=lambda kv: -kv[1]):
    total += count
    sig = ", ".join(getattr(t, "name", str(t)) for t in primitive.param_types)
    ret = getattr(primitive.return_type, "name", str(primitive.return_type))
    variadic = " [variadic]" if primitive.is_variadic else ""
    print(f"  {primitive.name:12} ({sig}) -> {ret}{variadic:11}  count = {count:>7,}")
print(f"  {'TOTAL':12} {'':40} {total:>7,}   <- this is b1_full\n")

rb = rung_breadth(1, RUNG, library, target, grids, sources, max_arity)
print(f"rung_breadth().b1_full = {rb.b1_full:,}\n")

budget = dataclasses.replace(cfg.budget, depth_limit=1, max_pool=30, considered_limit=5_000_000)
result = cfg.search_engine.run(
    train_examples=tuple(entry.task.train),
    library=library,
    constraints=cfg.constraints,
    cost=cfg.cost,
    budget=budget,
)
print("ENGINE, same floor, same task, depth_limit=1:")
for i, gen in enumerate(result.stats.generations):
    print(f"  generation {i}: {dict(gen)}")
print(f"  total considered = {result.stats.considered:,}")

engine_round1 = (
    result.stats.generations[1].get("composed") if len(result.stats.generations) > 1 else None
)
print()
print("=" * 84)
if engine_round1:
    print(f"round-1 composed:  MODEL {total:,}   ENGINE {engine_round1:,}   "
          f"ratio {total / engine_round1:.2f}x")
print("=" * 84)
