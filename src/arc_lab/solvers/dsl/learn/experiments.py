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
from arc_lab.solvers.dsl.analysis.compression import compression_ratio, speedup_ratio
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
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Param, Program
from arc_lab.solvers.dsl.substrate.types import ValueType

_G = ValueType.GRID


@dataclass(frozen=True, slots=True)
class Experiment:
    name: str
    starting_library: Library
    targets: tuple[tuple[str, Program], ...]  # (name, template over starting primitives)
    tasks: tuple[GeneratedTask, ...]
    search: Search
    cost: Cost
    note: str = ""


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    name: str
    learned: tuple[tuple[str, str], ...]  # (name, template str)
    check: CheckResult
    compare: dict[str, RunSummary]  # L1/L2/L3 at the experiment's search depth
    enablement: frozenset[str]  # tasks L2 solves at depth-1 that L1 does not

    def summary_lines(self) -> list[str]:
        base, learned = self.compare["L1"], self.compare["L2"]
        lines = [
            f"[{self.name}] learned: {[f'{n} = {t}' for n, t in self.learned] or 'none'}",
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
    )

    starting = experiment.starting_library
    target_prims = [make_abstraction(n, t, starting) for n, t in experiment.targets]
    libraries = {
        "L1": starting,
        "L2": result.library,
        "L3": starting.extended(name=f"{starting.name}+targets", extra=tuple(target_prims)),
    }
    compare = compare_libraries(
        libraries, search=experiment.search, cost=experiment.cost, dataset=full, out_dir=runs_root
    )

    # Enablement: at a depth-1 budget, what does the learned library reach that the base can't?
    depth1 = compare_libraries(
        {"L1-d1": starting, "L2-d1": result.library},
        search=Enumerate(max_depth=1),
        cost=experiment.cost,
        dataset=full,
        out_dir=runs_root,
    )
    return ExperimentReport(
        name=experiment.name,
        learned=tuple((p.name, str(p.template)) for p in result.abstractions),
        check=check_abstractions(list(result.abstractions), target_prims),
        compare=compare,
        enablement=enablement_transfer(depth1["L1-d1"], depth1["L2-d1"]),
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
        cost=ProgramSize(),
        note="E1 smoke: re-derive rot90 from the D4 generators {flip_h, transpose}.",
    )


#: Experiment registry for the CLI (`arc-lab learn <name>`).
_REGISTRY = {"e1-rot90": e1_rot90}


def make_experiment(name: str) -> Experiment:
    try:
        return _REGISTRY[name]()
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown experiment {name!r}; known: {known}") from None
