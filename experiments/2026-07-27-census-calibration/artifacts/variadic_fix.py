"""C8: the defect C7 isolated, and the one-line fix -- verified against the engine on every cell.

`forecast_cost._slot_types` builds a variadic primitive's argument tuples by replicating
``param_types[-1]`` -- the last DECLARED parameter. But a variadic primitive declares its repeated
tail type in its own field, ``Primitive.variadic_param``:

    OVERLAY = Primitive(param_types=(COLOR,), return_type=GRID, variadic_param=GRID)

So ``overlay : (Color, Grid...) -> Grid`` is modelled as replicating COLOR (10 leaves) when the
engine replicates GRID (1 leaf): 10 + 10^2 + 10^3 = 1,110 modelled against 30 actual, and
``b1_full`` reads 1,211 where the engine composes 131 (9.24x).

This is upstream of BOTH instruments -- ``breadth.round_terms`` and the forecaster share
``_slot_types`` -- so it inflates the breadth census's headline numbers and the forecaster together.
The fix is to read the declared field. Verified below on every uncompromised rung cell by driving
the real engine at ``depth_limit=1`` and comparing round-1 ``composed`` against both models.
"""

from __future__ import annotations

import dataclasses
import json
from math import prod
from pathlib import Path

from arc_lab.program_search.execution import forecast_cost as fc_mod
from arc_lab.program_search.ladders.breadth import _leaf_census
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.types import Type, TypeVar

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"


def fixed_slot_types(primitive: Primitive, max_arity: int) -> list[tuple[Type, ...]]:
    """`_slot_types` with the tail type read from the field that declares it."""
    if not primitive.is_variadic:
        return [primitive.param_types]
    tail = primitive.variadic_param
    if tail is None:  # pragma: no cover - is_variadic guarantees otherwise
        return [()]
    return [(*primitive.param_types, *([tail] * extra)) for extra in range(max_arity)]


def round_one(library: Library, census: dict, max_arity: int, *, fix: bool) -> int:
    slot_fn = fixed_slot_types if fix else fc_mod._slot_types
    total = 0
    for primitive in library.primitives:
        if primitive.name == fc_mod.BRANCHING_ENTRY:
            continue
        for slots in slot_fn(primitive, max_arity):
            total += prod(
                sum(census.values()) if isinstance(t, TypeVar) else census.get(t, 0) for t in slots
            )
    return total


print(f"{'ladder':30} {'rung':17} {'engine':>8} {'current':>9} {'fixed':>8}  {'cur/eng':>8} {'fix/eng':>8}")
print("-" * 92)

rows: list[tuple[str, str, int, int, int]] = []
for name in sorted(ladder_paths()):
    if not (LADDERS / name / "report.json").exists():
        continue
    if json.loads((LADDERS / name / "report.json").read_text()).get("compromises"):
        continue
    spec = make_ladder(name)
    ctx = CheckContext(spec, corpus_backed=True)
    cfg = spec.reference_config
    sources = tuple(getattr(cfg.search_engine, "constant_sources", ()))
    max_arity = cfg.budget.max_arity

    for rb in ctx.rung_breadth:
        targets = ctx.demo_targets[rb.name]
        if not targets:
            continue
        task_id, _target = targets[0]
        entry = ctx.by_id.get(task_id)
        if entry is None:
            continue
        library = spec.oracle_library(rb.level - 1)
        grids = [ex.input for ex in entry.task.train]
        census = _leaf_census(grids, sources, library)

        budget = dataclasses.replace(
            cfg.budget, depth_limit=1, max_pool=10_000_000, considered_limit=50_000_000
        )
        result = cfg.search_engine.run(
            train_examples=tuple(entry.task.train),
            library=library,
            constraints=cfg.constraints,
            cost=cfg.cost,
            budget=budget,
        )
        gens = result.stats.generations
        if len(gens) < 2 or not isinstance(gens[1].get("composed"), int):
            continue
        engine = gens[1]["composed"]
        current = round_one(library, census, max_arity, fix=False)
        fixed = round_one(library, census, max_arity, fix=True)
        rows.append((name, rb.name, engine, current, fixed))
        print(
            f"{name:30} {rb.name:17} {engine:>8,} {current:>9,} {fixed:>8,}  "
            f"{current / engine:>7.2f}x {fixed / engine:>7.2f}x"
        )

print("-" * 92)
exact_now = sum(1 for _, _, e, c, _ in rows if c == e)
exact_fix = sum(1 for _, _, e, _, f in rows if f == e)
print(f"\nn = {len(rows)} rung cells (round-1 `composed`, pool raised so nothing truncates)")
print(f"  EXACT under the current model : {exact_now}/{len(rows)}")
print(f"  EXACT under the fixed model   : {exact_fix}/{len(rows)}")
worst_now = max((c / e for _, _, e, c, _ in rows), default=0)
worst_fix = max((f / e for _, _, e, _, f in rows), default=0)
print(f"  worst over-count, current     : {worst_now:.2f}x")
print(f"  worst over-count, fixed       : {worst_fix:.2f}x")

affected = [r for r in rows if r[3] != r[4]]
print(f"\n  cells the fix MOVES: {len(affected)}/{len(rows)}")
for name, rung, engine, current, fixed in affected:
    print(f"    {name:30} {rung:17} {current:>9,} -> {fixed:>8,}  (engine {engine:,})")
