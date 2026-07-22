"""Micro-probe batteries: ONE cell, ONE factor changed — single-factor cost attribution.

The 2026-07-21 read-across inferred what drives jump cost by comparing ladders that differed in
several ways at once (the al4-proposer and shared-al5-floor confounds are the cautionary examples),
and the 2026-07-22 frontier sweep then showed that even a clean two-factor sweep can measure the
wrong thing: at a bound `max_pool`, deeper rounds compose zero and the reading is starvation, not
depth. So this harness holds EVERYTHING fixed — same task, same budget, same constant policy — and
moves one factor per cell:

  A.  arity       — one extra GRID -> GRID primitive of arity 1..5 (the product law, slot by slot)
  A2. slot types  — arity pinned at 3, only the TYPES filling the slots moving (INT vs COLOR)
  B.  constants   — the constant-source policy, read against the census width it actually mints
  C.  if-tax      — the `if` summoner present vs absent
  D.  arity trade — one arity-3 primitive vs the two arity-2 primitives spelling the same function

Battery E (the higher-order tax) lives in the sibling `hof_probe.py`, which imports this harness.

Two design choices make the numbers comparable:

* **The task is deliberately unsolvable from every floor here.** A solved search can stop early
  (`solution_limit`), so a cell that happens to solve would be cheaper for a reason that has
  nothing to do with the factor under test. Unsolvable means every cell pays the full depth: this
  measures `cost_L(d)`, the thing the factor is supposed to move.
* **Every cell reports saturation and censoring.** A round that composed nothing means `max_pool`
  bound and the deeper rounds are decorative — the reading is starvation and must not be compared.
  A censored cell's `considered` is the guard, not a measurement, and is printed as a lower bound.

Usage: uv run python experiments/2026-07-22-micro-probes/artifacts/micro_probes.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.execution.forecast_cost import forecast_cost
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.leaves import ConstantSource, seed_leaves
from arc_lab.program_search.search.scope import Scope
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import GRID, INT

CONFIG = PRESETS["synth"]
GUARD = 2_000_000
POOL = 20_000

#: Three unary GRID -> GRID primitives and nothing else: no parameters, no constants of their own,
#: so anything a battery adds is the whole of what it costs.
BASE_NAMES = ("flip_h", "flip_v", "rot90")

#: The arity ladder: all GRID -> GRID, so each cell's survivors land in the SAME census bucket and
#: only the number of argument slots (and the types filling them) differs.
ARITY_LADDER = (
    ("identity", 1),
    ("scale", 2),
    ("translate", 3),
    ("set_cell", 4),
    ("move_cell", 5),
)


def _grids() -> tuple[Grid, ...]:
    """Two small, asymmetric input grids. Small on purpose: `finite-enumerate` mints INT 0..max-dim,
    so grid size is itself a constant-domain knob and has to be held fixed across every battery."""
    return (
        Grid.from_list([[1, 2, 0], [0, 3, 0], [4, 0, 5]]),
        Grid.from_list([[0, 7, 0], [6, 0, 8], [0, 9, 0]]),
    )


def unsolvable_task() -> Task:
    """A task no floor here can solve: the output is a colour that appears in no input.

    Cost, not cost-to-solution, is what these batteries compare, and an early stop on a lucky solve
    would corrupt exactly that.
    """
    target = Grid.from_list([[8, 8], [8, 8]])
    return Task(
        task_id="micro-probe-unsolvable",
        train=tuple(Example(input=g, output=target) for g in _grids()),
        test=(),
    )


def library(name: str, extra: tuple[str, ...] = (), custom: tuple[Primitive, ...] = ()) -> Library:
    names = (*BASE_NAMES, *extra)
    return Library(name=name, primitives=(*(BASE_PRIMITIVES[n] for n in names), *custom))


@dataclass(frozen=True, slots=True)
class Cell:
    label: str
    considered: int
    seconds: float
    round_composed: tuple[int, ...]
    leaves: int
    censored: bool
    saturated_at: int | None
    #: What `execution/forecast_cost` predicts round 1 composes — the product law, stated in
    #: advance. Round 1 is where the law is testable without survival entering: the pool is exactly
    #: the round-0 leaves, so the prediction is arithmetic, not calibration.
    predicted_round_1: int

    @property
    def actual_round_1(self) -> int:
        return self.round_composed[1] if len(self.round_composed) > 1 else 0

    @property
    def usable(self) -> bool:
        """A cell whose number means what the battery says it means."""
        return not self.censored and self.saturated_at is None


def run_cell(
    label: str,
    lib: Library,
    *,
    depth: int,
    sources: tuple[ConstantSource, ...] | None = None,
    max_arity: int = 2,
    task: Task | None = None,
    engine: BottomUpSearchEngine | None = None,
) -> Cell:
    engine = CONFIG.search_engine if engine is None else engine
    if sources is not None:
        engine = replace(engine, constant_sources=sources)
    subject = task if task is not None else unsolvable_task()
    budget = Budget(
        depth_limit=depth,
        max_arity=max_arity,
        max_pool=POOL,
        considered_limit=GUARD,
        considered_limit_mode="immediate",
    )
    started = time.time()
    result = engine.run(
        train_examples=subject.train,
        library=lib,
        constraints=CONFIG.constraints,
        cost=CONFIG.cost,
        budget=budget,
    )
    elapsed = time.time() - started
    generations = list(result.stats.generations)
    composed = tuple(
        g["composed"] if isinstance(g.get("composed"), int) else 0  # type: ignore[misc]
        for g in generations
    )
    saturated_at = next(
        (
            index
            for index, g in enumerate(generations)
            if index > 0 and g.get("composed") == 0 and not g.get("incomplete")
        ),
        None,
    )
    contexts = tuple(Context(example.input) for example in subject.train)
    leaves = sum(1 for _ in seed_leaves(Scope(()), contexts, engine.constant_sources, lib))
    forecast = forecast_cost(
        replace(CONFIG, library=lib, search_engine=engine, budget=budget, learn=None),
        subject,
        depth_limit=1,
    )
    return Cell(
        label=label,
        considered=result.stats.considered,
        seconds=elapsed,
        round_composed=composed,
        leaves=leaves,
        censored=result.stats.censored,
        saturated_at=saturated_at,
        predicted_round_1=forecast.rounds[1].composed if len(forecast.rounds) > 1 else 0,
    )


def show(title: str, note: str, cells: list[Cell]) -> None:
    print(f"\n## {title}\n")
    print(note)
    print()
    header = (
        f"{'cell':26s} {'leaves':>7s} {'considered':>12s} {'x base':>7s} {'secs':>7s} "
        f"{'r1 pred':>9s} {'r1 real':>9s} "
    )
    print(header + f"{'per round':>28s}  flags")
    base = next((c.considered for c in cells if c.usable), 0) or 1
    for cell in cells:
        flags = []
        if cell.censored:
            flags.append(f">= GUARD ({GUARD:,}) — LOWER BOUND")
        if cell.saturated_at is not None:
            flags.append(f"SATURATED at round {cell.saturated_at} — starvation, not cost")
        if cell.predicted_round_1 != cell.actual_round_1:
            flags.append("r1 prediction MISSED")
        rounds = ",".join(f"{n:,}" for n in cell.round_composed)
        ratio = f"{cell.considered / base:>6.1f}x" if cell.usable else "     -"
        print(
            f"{cell.label:26s} {cell.leaves:>7,} {cell.considered:>12,} {ratio:>7s} "
            f"{cell.seconds:>7.1f} {cell.predicted_round_1:>9,} {cell.actual_round_1:>9,} "
            f"{rounds:>28s}  {'; '.join(flags)}",
            flush=True,
        )


def battery_arity(depth: int) -> None:
    """A: one extra GRID -> GRID primitive, arity 1..5. Everything else identical."""
    cells = [run_cell("base (3 unary)", library("base"), depth=depth)]
    for name, arity in ARITY_LADDER:
        cells.append(
            run_cell(f"+ {name} (arity {arity})", library(f"base+{name}", (name,)), depth=depth)
        )
    show(
        f"A. Arity tax (depth {depth})",
        "Each cell = the base floor plus ONE primitive. All GRID -> GRID, so survivors land in the\n"
        "same census bucket and the only thing moving is the number of argument slots.",
        cells,
    )


def battery_slot_types(depth: int) -> None:
    """A2: arity held FIXED at 3, only the slot types moving.

    Battery A cannot separate "one more slot" from "a slot drawn from a wider type": `set_cell`
    has a COLOR slot (10 constants) where `move_cell` has only INT ones (4), so its arity-4 cell
    is not simply cheaper-because-shallower. This battery pins arity and moves nothing but the
    types, which is the only way to say which of the two the product law is really about.
    """
    cells = [
        run_cell("base (3 unary)", library("base"), depth=depth),
        run_cell(
            "+ translate (grid,int,int)", library("base+translate", ("translate",)), depth=depth
        ),
        run_cell("+ pad (grid,int,color)", library("base+pad", ("pad",)), depth=depth),
        run_cell(
            "+ map_color (grid,col,col)", library("base+map_color", ("map_color",)), depth=depth
        ),
    ]
    show(
        f"A2. Same arity, different slot types (depth {depth})",
        "Three arity-3 GRID -> GRID primitives. Identical arity, identical return bucket; the only\n"
        "difference is whether a slot draws from INT (0..max-dim, so 4 here) or COLOR (0..9, so 10).",
        cells,
    )


def battery_constants(depth: int) -> None:
    """B: the constant-source policy, at a fixed library with two INT slots to fill."""
    lib = library("base+translate", ("translate",))
    cells = [
        run_cell("no constants", lib, depth=depth, sources=()),
        run_cell("harvest-from-instance", lib, depth=depth, sources=("harvest-from-instance",)),
        run_cell("finite-enumerate", lib, depth=depth, sources=("finite-enumerate",)),
        run_cell(
            "both",
            lib,
            depth=depth,
            sources=("finite-enumerate", "harvest-from-instance"),
        ),
    ]
    show(
        f"B. Constant-domain width (depth {depth})",
        "Fixed library (base + `translate`: two INT slots), fixed task; only the constant policy\n"
        "moves. `leaves` is the round-0 census the policy actually mints — the measured width the\n"
        "cost should be read against, rather than a width chosen in advance.",
        cells,
    )


def battery_if(depth: int) -> None:
    """C: the `if` summoner present vs absent, at an otherwise identical floor."""
    cells = [
        run_cell("base", library("base"), depth=depth),
        run_cell("base + if", library("base+if", ("if",)), depth=depth),
        run_cell("base + gt", library("base+gt", ("gt",)), depth=depth),
        run_cell("base + gt + if", library("base+gt+if", ("gt", "if")), depth=depth),
    ]
    show(
        f"C. If-tax (depth {depth})",
        "`if` is not an ordinary primitive: it summons an `If` node over a BOOL condition x every\n"
        "ORDERED same-typed branch pair, so its term is quadratic in the pool where a primitive's\n"
        "is a product of type populations. `gt` is included to supply real BOOL conditions — with\n"
        "no BOOL producer the only conditions are the two enumerated literals.",
        cells,
    )


def _translate_h() -> Primitive:
    base = BASE_PRIMITIVES["translate"]

    def impl(grid: object, dx: object) -> object:
        return base.impl(grid, dx, 0)

    return Primitive(name="translate_h", param_types=(GRID, INT), return_type=GRID, impl=impl)


def _translate_v() -> Primitive:
    base = BASE_PRIMITIVES["translate"]

    def impl(grid: object, dy: object) -> object:
        return base.impl(grid, 0, dy)

    return Primitive(name="translate_v", param_types=(GRID, INT), return_type=GRID, impl=impl)


def battery_arity_trade(depth: int) -> None:
    """D: the same function, two spellings — one arity-3 primitive or two arity-2 ones.

    `translate(g, dx, dy) == translate_v(translate_h(g, dx), dy)`, so the two floors express the
    same set of translations. The arity-3 floor reaches any translation in ONE round; the arity-2
    floor needs two. Which is cheaper is the trade the design doc leaves open.
    """
    cells = [
        run_cell("arity-3 `translate`", library("base+translate", ("translate",)), depth=depth),
        run_cell(
            "arity-2 x2 (h then v)",
            library("base+translate_hv", custom=(_translate_h(), _translate_v())),
            depth=depth,
        ),
    ]
    show(
        f"D. Arity trade (depth {depth})",
        "Same expressible set of translations, two spellings. The arity-3 floor spends one round;\n"
        "the arity-2 floor spends two rounds but a narrower product per round.",
        cells,
    )


def main() -> None:
    print(f"# Micro-probe batteries — pool {POOL:,}, guard {GUARD:,}, task deliberately unsolvable")
    for depth in (2, 3):
        battery_arity(depth)
    battery_slot_types(2)
    battery_slot_types(3)
    battery_constants(2)
    battery_constants(3)
    battery_if(2)
    battery_if(3)
    battery_arity_trade(2)
    battery_arity_trade(3)


if __name__ == "__main__":
    main()
