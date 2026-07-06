"""Abstraction-formation experiments: starting primitives, targets, and a generated testbed.

An :class:`Experiment` is a controlled environment: a starting library, hand-authored
*target* abstractions (templates over the starting primitives — used only as observables,
for library 3 and the behavioral checker), and a deterministic synthetic testbed. The
runner learns a library on the train split (blind to the targets), then reports the three
soft indicators we agreed on — behavioral match to the targets, compression, and the
search-effort / enablement deltas across the three libraries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from arc_lab.core.dataset import Dataset
from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.analysis.compression import (
    CompressionMetric,
    TwoPartMDL,
    compression_ratio,
    speedup_ratio,
)
from arc_lab.solvers.dsl.analysis.runner import RunSummary
from arc_lab.solvers.dsl.learn.antiunify import AntiunifyPairs
from arc_lab.solvers.dsl.learn.harness import (
    CheckResult,
    check_abstractions,
    compare_libraries,
    enablement_transfer,
)
from arc_lab.solvers.dsl.learn.loop import LearnResult, learn
from arc_lab.solvers.dsl.learn.taskgen import GeneratedTask, Solution, make_task, write_testbed
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.cells import CELL_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Param, Program
from arc_lab.solvers.dsl.substrate.types import ValueType

_G = ValueType.GRID


@dataclass(frozen=True, slots=True)
class Experiment:
    name: str
    starting_library: Library
    targets: tuple[tuple[str, Program], ...]  # (name, template over starting primitives)
    tasks: tuple[GeneratedTask, ...]
    search: Search  # the wake / comparison search (finds the raw multi-step solution)
    enablement_search: Search  # a shallower budget: what only the learned library reaches
    cost: Cost
    note: str = ""
    metric: CompressionMetric | None = None  # governance objective (None -> flat baseline)


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    name: str
    learned: tuple[tuple[str, str], ...]  # (name, template str)
    check: CheckResult
    compare: dict[str, RunSummary]  # L1/L2/L3 at the experiment's search depth
    enablement: frozenset[str]  # tasks L2 solves at depth-1 that L1 does not

    def summary_lines(self) -> list[str]:
        base, learned = self.compare["L1"], self.compare["L2"]
        names = ", ".join(f"{n} = {t}" for n, t in self.learned) or "none"
        lines = [
            f"[{self.name}] learned {len(self.learned)} abstraction(s): {names}",
            f"  behavioral check vs targets: matched={list(self.check.matched)} "
            f"missed={list(self.check.missed)} novel={list(self.check.novel)}",
            f"  solved   L1={base.solved} L2={learned.solved} L3={self.compare['L3'].solved} "
            f"(of {base.total})",
            f"  DL       L1={base.description_length:.1f} L2={learned.description_length:.1f} "
            f"(compression x{compression_ratio(base.description_length, learned.description_length):.2f})",
            f"  considered L1={base.considered_total} L2={learned.considered_total} "
            f"(speedup x{speedup_ratio(base.considered_total, learned.considered_total):.2f})",
            f"  enablement (depth-1, L2 solves, L1 cannot): {len(self.enablement)} tasks",
        ]
        return lines


def run_experiment(
    experiment: Experiment,
    *,
    testbeds_root: Path,
    runs_root: Path,
    write: bool = True,
) -> ExperimentReport:
    """Generate the testbed, run the loop blind, then compute the three-library report."""
    if write:
        write_testbed(experiment.name, experiment.tasks, out_root=testbeds_root, note=experiment.note)

    train = [_task(g) for g in experiment.tasks if g.split == "train"]
    full = Dataset(name=experiment.name, tasks=tuple(_task(g) for g in experiment.tasks))

    result: LearnResult = learn(
        library=experiment.starting_library,
        search=experiment.search,
        tasks=train,
        proposer=AntiunifyPairs(),
        cost=experiment.cost,
        metric=experiment.metric,
    )

    starting = experiment.starting_library
    target_prims = [make_abstraction(n, t, starting) for n, t in experiment.targets]
    libraries = {
        "L1": starting,
        "L2": result.library,
        "L3": starting.extended(name=f"{starting.name}+targets", extra=tuple(target_prims)),
    }
    compare = compare_libraries(
        libraries,
        search=experiment.search,
        cost=experiment.cost,
        dataset=full,
        out_dir=runs_root,
        metric=experiment.metric,
    )

    # Enablement: at a shallow budget, what does the learned library reach that the base can't?
    shallow = compare_libraries(
        {"L1-shallow": starting, "L2-shallow": result.library},
        search=experiment.enablement_search,
        cost=experiment.cost,
        dataset=full,
        out_dir=runs_root,
        metric=experiment.metric,
    )
    return ExperimentReport(
        name=experiment.name,
        learned=tuple((p.name, str(p.template)) for p in result.abstractions),
        check=check_abstractions(list(result.abstractions), target_prims),
        compare=compare,
        enablement=enablement_transfer(shallow["L1-shallow"], shallow["L2-shallow"]),
    )


def _task(generated: GeneratedTask) -> Task:
    return Task.from_dict(generated.task_id, generated.spec)


# -- E1: rot90 from the D4 generators -----------------------------------


def _rot90_template() -> Program:
    return Apply("transpose", (Apply("flip_h", (Param(0, _G),)),))


def _rot90() -> Solution:
    return lambda g: Grid(np.rot90(g.array, 1))


def _small_grids() -> list[Grid]:
    """A deterministic pool of varied small grids (square / non-square)."""
    rows_pool = [
        [[1, 2], [3, 4]],
        [[1, 2, 3], [4, 5, 6]],
        [[5, 0], [0, 5], [1, 2]],
        [[2, 0, 1], [3, 4, 5]],
        [[7, 8], [9, 1]],
        [[1, 1, 2], [2, 3, 3]],
        [[4, 5], [6, 7], [8, 9]],
        [[0, 1, 2, 3]],
        [[3], [2], [1]],
        [[9, 8, 7], [6, 5, 4], [3, 2, 1]],
        [[1, 0], [0, 1]],
        [[2, 2, 2], [1, 1, 1]],
    ]
    return [Grid.from_list(rows) for rows in rows_pool]


def e1_rot90() -> Experiment:
    """E1 smoke test: starting {flip_h, transpose}, target rot90 (withheld)."""
    generators = Library(
        name="generators",
        primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("transpose")),
    )
    grids = _small_grids()
    solution = _rot90()
    tasks: list[GeneratedTask] = []
    for i, grid in enumerate(grids):
        split = "train" if i < 8 else "heldout"
        tasks.append(
            make_task(
                f"rot90-{i:02d}",
                label="rot90",
                split=split,
                solution=solution,
                train_inputs=[grid],
                test_inputs=[grid],
            )
        )
    return Experiment(
        name="e1-rot90",
        starting_library=generators,
        targets=(("rot90", _rot90_template()),),
        tasks=tuple(tasks),
        search=Enumerate(max_depth=2),
        enablement_search=Enumerate(max_depth=1),
        cost=ProgramSize(),
        note="E1 smoke: re-derive rot90 from the D4 generators {flip_h, transpose}.",
    )


# -- E2: fixed-cell swap_cells from {read, set_cell} --------------------


def _swap_solution(r1: int, c1: int, r2: int, c2: int) -> Solution:
    def swap(grid: Grid) -> Grid:
        array = grid.array.copy()
        v1, v2 = array[r1, c1], array[r2, c2]
        array[r1, c1], array[r2, c2] = v2, v1
        return Grid(array)

    return swap


def _swap_template(r1: int, c1: int, r2: int, c2: int) -> Program:
    """swap_cells as a closed template over read/set_cell (fixed cells = Int constants)."""
    p0 = Param(0, _G)
    i = ValueType.INT
    read_a = Apply("read", (p0, Const(r2, i), Const(c2, i)))
    read_b = Apply("read", (p0, Const(r1, i), Const(c1, i)))
    inner = Apply("set_cell", (p0, Const(r1, i), Const(c1, i), read_a))
    return Apply("set_cell", (inner, Const(r2, i), Const(c2, i), read_b))


def _two_by_two_grids(n: int) -> list[Grid]:
    """Deterministic varied 2x2 grids (distinct corner colors force `read` over constants)."""
    palette = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    grids = []
    for k in range(n):
        cells = [palette[(k + off) % len(palette)] for off in (0, 1, 2, 3)]
        grids.append(Grid.from_list([[cells[0], cells[1]], [cells[2], cells[3]]]))
    return grids


def _cell_search() -> Enumerate:
    # Depth 4 (swap is a 4-deep composition), coordinate ints on, and roomier pools so the
    # intermediate half-swap grid survives (the low-floor search cost, contained on 2x2).
    return Enumerate(max_depth=4, coord_ints=True, max_grid_args=64, max_pool=20000)


def e2_swap_cells() -> Experiment:
    """E2: starting {read, set_cell}, target fixed-cell swap_cells((0,0),(1,1)) (withheld)."""
    r1, c1, r2, c2 = 0, 0, 1, 1
    solution = _swap_solution(r1, c1, r2, c2)
    grids = _two_by_two_grids(32)  # 8 tasks x (3 train demos + 1 test)
    tasks: list[GeneratedTask] = []
    for t in range(8):
        pool = grids[t * 4 : t * 4 + 4]
        split = "train" if t < 6 else "heldout"
        tasks.append(
            make_task(
                f"swap-{t:02d}",
                label="swap_cells",
                split=split,
                solution=solution,
                train_inputs=pool[:3],
                test_inputs=pool[3:],
            )
        )
    return Experiment(
        name="e2-swap-cells",
        starting_library=CELL_LIBRARY,
        targets=(("swap_cells", _swap_template(r1, c1, r2, c2)),),
        tasks=tuple(tasks),
        search=_cell_search(),
        enablement_search=Enumerate(max_depth=1, coord_ints=True),
        cost=ProgramSize(),
        note="E2: re-derive fixed-cell swap_cells((0,0),(1,1)) from {read, set_cell}.",
    )


# -- E3: varied-column swap (earns variable-sharing) --------------------


def _swap_cols_solution(col_top: int, col_bot: int) -> Solution:
    def swap(grid: Grid) -> Grid:
        array = grid.array.copy()
        v1, v2 = array[0, col_top], array[1, col_bot]
        array[0, col_top], array[1, col_bot] = v2, v1
        return Grid(array)

    return swap


def _swap_cols_template() -> Program:
    """swap((0,X),(1,Y)) — the general template whose X,Y each appear twice (shared vars)."""
    p0 = Param(0, _G)
    x = Param(1, ValueType.INT)
    y = Param(2, ValueType.INT)
    row0, row1 = Const(0, ValueType.INT), Const(1, ValueType.INT)
    read_a = Apply("read", (p0, row1, y))  # read (1, Y)
    read_b = Apply("read", (p0, row0, x))  # read (0, X)
    inner = Apply("set_cell", (p0, row0, x, read_a))  # (0,X) <- orig(1,Y)
    return Apply("set_cell", (inner, row1, y, read_b))  # (1,Y) <- orig(0,X)


def _swap_cols_tasks() -> tuple[GeneratedTask, ...]:
    """8 tasks that vary the two swapped columns (so coordinates become shared params)."""
    grids = _two_by_two_grids(48)
    combos = [(0, 0), (0, 1), (1, 0), (1, 1)]
    ordered = [c for _ in range(2) for c in combos]  # each combo twice
    tasks: list[GeneratedTask] = []
    for t, (col_top, col_bot) in enumerate(ordered):
        pool = grids[t * 4 : t * 4 + 4]
        split = "train" if t < 6 else "heldout"
        tasks.append(
            make_task(
                f"swapcol-{t:02d}-{col_top}{col_bot}",
                label="swap_cols",
                split=split,
                solution=_swap_cols_solution(col_top, col_bot),
                train_inputs=pool[:3],
                test_inputs=pool[3:],
            )
        )
    return tuple(tasks)


def _swap_cols_experiment(name: str, metric: CompressionMetric | None, note: str) -> Experiment:
    return Experiment(
        name=name,
        starting_library=CELL_LIBRARY,
        targets=(("swap_cols", _swap_cols_template()),),
        tasks=_swap_cols_tasks(),
        search=_cell_search(),
        enablement_search=Enumerate(max_depth=1, coord_ints=True),
        cost=ProgramSize(),
        note=note,
        metric=metric,
    )


def e3_swap_cols() -> Experiment:
    """E3: general swap((0,X),(1,Y)) from {read, set_cell}; **flat** MDL (observes library bloat)."""
    return _swap_cols_experiment(
        "e3-swap-cols",
        None,  # flat CompressionMetric baseline
        "E3: general swap((0,X),(1,Y)) from {read, set_cell}, flat MDL. Variable-sharing "
        "works; flat library cost causes bloat (many marginal specialisations).",
    )


def e4_swap_cols_mdl() -> Experiment:
    """E4: E3 under **two-part MDL** (charges definition size) — does it stop the bloat?"""
    return _swap_cols_experiment(
        "e4-swap-cols-mdl",
        TwoPartMDL(),
        "E4: E3's environment under two-part MDL (definition cost) to test the anti-bloat term.",
    )


#: Experiment registry for the CLI (`arc-lab learn <name>`).
_REGISTRY = {
    "e1-rot90": e1_rot90,
    "e2-swap-cells": e2_swap_cells,
    "e3-swap-cols": e3_swap_cols,
    "e4-swap-cols-mdl": e4_swap_cols_mdl,
}


def make_experiment(name: str) -> Experiment:
    try:
        return _REGISTRY[name]()
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown experiment {name!r}; known: {known}") from None
