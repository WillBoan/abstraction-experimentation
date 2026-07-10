"""Abstraction-formation experiments: starting primitives, targets, and a generated testbed.

An :class:`StudySpec` is a controlled environment: a starting library, hand-authored
*target* abstractions (templates over the starting primitives — used only as observables,
for library 3 and the behavioral checker), and a deterministic synthetic testbed. The
runner learns a library on the train split (blind to the targets), then reports the three
soft indicators we agreed on — behavioral match to the targets, compression, and the
search-effort / enablement deltas across the three libraries.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from arc_lab.core.dataset import Dataset
from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.analysis.compression import compression_ratio, speedup_ratio
from arc_lab.solvers.dsl.analysis.runner import RunSummary
from arc_lab.solvers.dsl.analysis.transfer import (
    Usefulness,
    enablement_transfer,
    heldout_transfer,
    train_usefulness,
)
from arc_lab.solvers.dsl.config import MetricSpec, ProposerSpec, SleepSpec
from arc_lab.solvers.dsl.learn.harness import (
    CheckResult,
    check_abstractions,
    compare_libraries,
)
from arc_lab.solvers.dsl.learn.loop import LearnResult, learn
from arc_lab.solvers.dsl.learn.taskgen import GeneratedTask, Solution, make_task, write_testbed
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.build_grid_search import BuildGridSearch
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY, BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.cells import CELL_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import GRID, INT

_G = GRID


@dataclass(frozen=True, slots=True)
class StudySpec:
    name: str
    starting_library: Library
    targets: tuple[tuple[str, Program], ...]  # (name, template over starting primitives)
    tasks: tuple[GeneratedTask, ...]
    search: Search  # the wake / comparison search (finds the raw multi-step solution)
    enablement_search: Search  # a shallower budget: what only the learned library reaches
    cost: Cost
    note: str = ""
    #: The whole sleep step as data (invention + governance). Default: greedy-MDL + antiunify + flat.
    sleep: SleepSpec = field(default_factory=SleepSpec)


@dataclass(frozen=True, slots=True)
class StudyReport:
    name: str
    learned: tuple[tuple[str, str], ...]  # (name, template str)
    check: CheckResult
    compare: dict[str, RunSummary]  # L1/L2/L3 at the experiment's search depth
    enablement: frozenset[str]  # tasks L2 solves at depth-1 that L1 does not
    heldout: frozenset[str]  # held-out tasks L2 solves at depth-1 that L1 cannot — the GRADE
    usefulness: Usefulness  # train-side proxy governance may consume (keeps the grade clean)

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
            f"  enablement (depth-1, same-corpus): {len(self.enablement)} tasks",
            f"  held-out transfer (GRADE): {len(self.heldout)} task(s)",
            f"  train usefulness: speedup x{self.usefulness.speedup:.2f}, "
            f"enabled {len(self.usefulness.enabled)} train task(s)",
        ]
        return lines


def run_study(
    experiment: StudySpec,
    *,
    testbeds_root: Path,
    runs_root: Path,
    write: bool = True,
) -> StudyReport:
    """Generate the testbed, run the loop blind, then compute the three-library report."""
    if write:
        write_testbed(
            experiment.name, experiment.tasks, out_root=testbeds_root, note=experiment.note
        )

    train = [_task(g) for g in experiment.tasks if g.split == "train"]
    full = Dataset.of(experiment.name, tuple(_task(g) for g in experiment.tasks))

    sleep = experiment.sleep.build(experiment.search)
    metric = experiment.sleep.metric.build()
    result: LearnResult = learn(
        library=experiment.starting_library,
        search=experiment.search,
        tasks=train,
        sleep=sleep,
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
        libraries,
        search=experiment.search,
        cost=experiment.cost,
        dataset=full,
        out_dir=runs_root,
        metric=metric,
    )

    # Enablement: at a shallow budget, what does the learned library reach that the base can't?
    shallow = compare_libraries(
        {"L1-shallow": starting, "L2-shallow": result.library},
        search=experiment.enablement_search,
        cost=experiment.cost,
        dataset=full,
        out_dir=runs_root,
        metric=metric,
    )
    base_shallow, aug_shallow = shallow["L1-shallow"], shallow["L2-shallow"]
    train_ids = frozenset(g.task_id for g in experiment.tasks if g.split == "train")
    heldout_ids = frozenset(g.task_id for g in experiment.tasks if g.split == "heldout")
    return StudyReport(
        name=experiment.name,
        learned=tuple((p.name, str(p.template)) for p in result.abstractions),
        check=check_abstractions(list(result.abstractions), target_prims),
        compare=compare,
        enablement=enablement_transfer(base_shallow, aug_shallow),
        heldout=heldout_transfer(base_shallow, aug_shallow, heldout_ids),
        usefulness=train_usefulness(
            compare["L1"], compare["L2"], base_shallow, aug_shallow, train_ids
        ),
    )


def _task(generated: GeneratedTask) -> Task:
    return Task.from_dict(generated.task_id, generated.spec)


@dataclass(frozen=True, slots=True)
class CorrelationPoint:
    """One experiment's place on the compression↔transfer plane."""

    name: str
    compression: float  # L1->L2 DL ratio: the process signal (also the governance objective)
    transfer: int  # held-out tasks newly solved: the grade
    train_speedup: float  # train-side usefulness proxy
    learned: int  # abstractions minted


def compression_transfer_correlation(
    names: Sequence[str], *, testbeds_root: Path, runs_root: Path
) -> list[CorrelationPoint]:
    """Run each named experiment and collect ``(compression, transfer)`` — the diagnostic that
    tests the MDL premise (*does compression predict transfer?*) and surfaces the E8 divergence,
    where compression rises while the held-out grade does not.
    """
    points: list[CorrelationPoint] = []
    for name in names:
        report = run_study(make_study(name), testbeds_root=testbeds_root, runs_root=runs_root)
        base, learned = report.compare["L1"], report.compare["L2"]
        points.append(
            CorrelationPoint(
                name=name,
                compression=compression_ratio(base.description_length, learned.description_length),
                transfer=len(report.heldout),
                train_speedup=report.usefulness.speedup,
                learned=len(report.learned),
            )
        )
    return points


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


def e1_rot90() -> StudySpec:
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
    return StudySpec(
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
    i = INT
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


def e2_swap_cells() -> StudySpec:
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
    return StudySpec(
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
    x = Param(1, INT)
    y = Param(2, INT)
    row0, row1 = Const(0, INT), Const(1, INT)
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


def _swap_cols_experiment(name: str, sleep: SleepSpec, note: str) -> StudySpec:
    return StudySpec(
        name=name,
        starting_library=CELL_LIBRARY,
        targets=(("swap_cols", _swap_cols_template()),),
        tasks=_swap_cols_tasks(),
        search=_cell_search(),
        enablement_search=Enumerate(max_depth=1, coord_ints=True),
        cost=ProgramSize(),
        note=note,
        sleep=sleep,
    )


def e3_swap_cols() -> StudySpec:
    """E3: general swap((0,X),(1,Y)) from {read, set_cell}; **flat** MDL (observes library bloat)."""
    return _swap_cols_experiment(
        "e3-swap-cols",
        SleepSpec(),  # flat MDL baseline (default proposer + metric)
        "E3: general swap((0,X),(1,Y)) from {read, set_cell}, flat MDL. Variable-sharing "
        "works; flat library cost causes bloat (many marginal specialisations).",
    )


def e4_swap_cols_mdl() -> StudySpec:
    """E4: E3 under **two-part MDL** (charges definition size) — does it stop the bloat?"""
    return _swap_cols_experiment(
        "e4-swap-cols-mdl",
        SleepSpec(metric=MetricSpec(kind="two-part")),
        "E4: E3's environment under two-part MDL (definition cost) to test the anti-bloat term.",
    )


# -- E5 / E6: re-derive D4 as build_grid programs (pixels->D4) -----------
#
# Starting from the cell-render floor (no D4 primitive), does the loop re-derive geometry as
# *size-general* build_grid programs? E5 targets rot90 alone (the minimal re-derivation); E6 the
# full D4 ladder (and whether a shared `mirror_index` idiom is invented — the bootstrap).

_I = INT
_C0, _C1 = Var(0, _I), Var(1, _I)  # De Bruijn: $0 = column j (inner), $1 = row i (outer)


def _w(g: Program) -> Program:
    return Apply("width", (g,))


def _h(g: Program) -> Program:
    return Apply("height", (g,))


def _mirror(n: Program, k: Program) -> Program:
    return Apply("sub", (Apply("sub", (n, k)), Const(1, _I)))  # (n - k) - 1, the reflection idiom


def _bg(g: Program, dh: Program, dw: Program, row: Program, col: Program) -> Program:
    """build_grid(dh, dw, lam(lam(read(g, row, col)))) — a coordinate-lambda geometry program."""
    return Apply("build_grid", (dh, dw, Lam(Lam(Apply("read", (g, row, col))))))


def _d4_targets(g: Program) -> dict[str, Program]:
    """Each D4 member as a size-general build_grid template over grid ``g`` (observables only)."""
    return {
        "transpose": _bg(g, _w(g), _h(g), _C0, _C1),
        "flip_h": _bg(g, _h(g), _w(g), _C1, _mirror(_w(g), _C0)),
        "flip_v": _bg(g, _h(g), _w(g), _mirror(_h(g), _C1), _C0),
        "rot90": _bg(g, _w(g), _h(g), _C0, _mirror(_w(g), _C1)),
        "rot180": _bg(g, _h(g), _w(g), _mirror(_h(g), _C1), _mirror(_w(g), _C0)),
        "rot270": _bg(g, _w(g), _h(g), _mirror(_h(g), _C0), _C1),
    }


def _d4_solutions() -> dict[str, Solution]:
    return {
        "transpose": lambda g: Grid(g.array.T),
        "flip_h": lambda g: Grid(np.fliplr(g.array)),
        "flip_v": lambda g: Grid(np.flipud(g.array)),
        "rot90": lambda g: Grid(np.rot90(g.array, 1)),
        "rot180": lambda g: Grid(np.rot90(g.array, 2)),
        "rot270": lambda g: Grid(np.rot90(g.array, 3)),
    }


def _nonsquare_grids() -> list[Grid]:
    """Non-square grids, both dims >= 2, so a *single* demo pins the size-general program.

    Non-square rules out width/height ambiguity; both dims >= 2 rules out *degenerate* grids
    (a dim of 1 makes a bound coordinate constant, so the search would fit a literal where the
    general program uses a variable — different programs per grid, which antiunify over-generalises).
    """
    rows_pool = [
        [[1, 2, 3], [4, 5, 6]],  # 2x3
        [[5, 0], [0, 5], [1, 2]],  # 3x2
        [[2, 0, 1], [3, 4, 5]],  # 2x3
        [[4, 5], [6, 7], [8, 9]],  # 3x2
        [[1, 1, 2], [2, 3, 3]],  # 2x3
        [[7, 8, 9, 0], [1, 2, 3, 4]],  # 2x4
        [[1, 2], [3, 4], [5, 6], [7, 8]],  # 4x2
        [[9, 8, 7], [6, 5, 4]],  # 2x3
    ]
    return [Grid.from_list(rows) for rows in rows_pool]


def _d4_tasks(
    members: tuple[str, ...], *, n_train: int, n_heldout: int
) -> tuple[GeneratedTask, ...]:
    """Multi-shape demo tasks: each shows a member on **three varied shapes**, so the solved
    program must be *size-general* (one coordinate formula fitting every shape). A single grid
    can't pin it — many formulas coincide on one grid's cells — but three shapes force the true
    program, which is then identical across tasks: the recurrence antiunify mines and mints.
    """
    solutions = _d4_solutions()
    grids = _nonsquare_grids()
    n = len(grids)
    tasks: list[GeneratedTask] = []
    for member in members:
        for k in range(n_train + n_heldout):
            demos = [grids[(k + off) % n] for off in range(3)]  # a window of 3 varied shapes
            tasks.append(
                make_task(
                    f"{member}-{k:02d}",
                    label=member,
                    split="train" if k < n_train else "heldout",
                    solution=solutions[member],
                    train_inputs=demos,
                    test_inputs=[grids[(k + 3) % n]],
                )
            )
    return tuple(tasks)


def e5_rederive_rot90() -> StudySpec:
    """E5: re-derive rot90 as a build_grid program from the cell floor (no D4 primitive)."""
    return StudySpec(
        name="e5-rederive-rot90",
        starting_library=BUILD_LIBRARY,
        targets=(("rot90", _d4_targets(Param(0, _G))["rot90"]),),
        tasks=_d4_tasks(("rot90",), n_train=4, n_heldout=2),
        search=BuildGridSearch(),
        enablement_search=Enumerate(max_depth=1),
        cost=ProgramSize(),
        note="E5: re-derive rot90 as a size-general build_grid program from the cell-render floor.",
    )


_D4_MEMBERS = ("transpose", "flip_h", "flip_v", "rot90", "rot180", "rot270")


def _d4_ladder_experiment(name: str, sleep: SleepSpec, note: str) -> StudySpec:
    """The full-D4-ladder environment; e6 and e7 differ only in the antiunify proposer."""
    targets = _d4_targets(Param(0, _G))
    return StudySpec(
        name=name,
        starting_library=BUILD_LIBRARY,
        targets=tuple((m, targets[m]) for m in _D4_MEMBERS),
        tasks=_d4_tasks(_D4_MEMBERS, n_train=3, n_heldout=1),
        search=BuildGridSearch(),
        enablement_search=Enumerate(max_depth=1),
        cost=ProgramSize(),
        sleep=sleep,  # two-part MDL charges each abstraction its definition size
        note=note,
    )


def e6_rederive_d4() -> StudySpec:
    """E6: full D4 ladder with the naive proposer — antiunify hoists bound vars, so re-derivation breaks."""
    return _d4_ladder_experiment(
        "e6-rederive-d4",
        SleepSpec(metric=MetricSpec(kind="two-part")),  # naive antiunify-pairs proposer (default)
        "E6: re-derive the full D4 ladder as build_grid programs. Whole-program antiunification "
        "over-generalises across members (a bound-var scope violation); governance prefers the "
        "broken abstraction. The negative that motivates E7.",
    )


def e7_rederive_d4_safe() -> StudySpec:
    """E7: E6's environment with the **lambda-safe** proposer — clean full-D4 re-derivation."""
    return _d4_ladder_experiment(
        "e7-rederive-d4-safe",
        SleepSpec(
            proposer=ProposerSpec(bound_var_safe=True),  # refuse to hole subterms with a bound $i
            metric=MetricSpec(kind="two-part"),
        ),
        "E7: E6 under a bound-var-safe proposer (won't lift $i into an abstraction arg). Only the "
        "sound per-member recurrences mint, so the D4 ladder re-derives cleanly. mirror_index still "
        "does not emerge — that needs a frequent-subtree proposer.",
    )


# -- E8 / E9: the mirror_index bootstrap (frequent-subtree proposer x grammar) ----------
#
# E7 re-derived the D4 ladder but left it *uncompressed* (DL x0.79): six separate whole-member
# abstractions, no shared idiom, because whole-program antiunification can't mine a recurring
# *subterm*. E8/E9 swap in FrequentSubtree (mines proper subtrees) and a primitive-driven
# BuildGridSearch (so a minted coordinate abstraction is actually *used*). The grammar is the
# axis: E8 = sub-only, E9 = the honest affine family (sub+add+mul, a wider search / worse cliff).


def _mirror_bootstrap_experiment(
    name: str, starting_library: Library, note: str, *, main_beam: int, tight_beam: int
) -> StudySpec:
    """The mirror_index-bootstrap environment; E8 and E9 differ in the starting grammar (+ beam).

    The single observable is `mirror_index` itself — the loop mints only the shared coordinate idiom
    (FrequentSubtree excludes program roots, so no whole-member abstractions pre-empt it). Enablement
    uses a *tight-beam* BuildGridSearch: once mirror_index exists the reflection is a depth-1 coordinate,
    so L2 clears the beam cliff that L1 (raw depth-2 `sub(sub(n,k),1)`) cannot — the search-speedup payoff.
    The affine grammar (E9) needs a *wider* `main_beam` just to solve a reflection once and seed the
    loop — that 128->224 gap is the measured cost of add/mul, not a confound.
    """
    search = BuildGridSearch(beam_width=main_beam)
    return StudySpec(
        name=name,
        starting_library=starting_library,
        targets=(("mirror_index", _mirror(Param(0, _I), Param(1, _I))),),
        tasks=_d4_tasks(_D4_MEMBERS, n_train=3, n_heldout=1),
        search=search,
        enablement_search=BuildGridSearch(beam_width=tight_beam),
        cost=ProgramSize(),
        # STOPGAP: mine only idioms the coordinate search can reuse (INT^n->INT), derived from the
        # search itself — not a declared type. See MACHINERY.md for the divergence + the general fix.
        sleep=SleepSpec(
            proposer=ProposerSpec(kind="search-scoped"),
            metric=MetricSpec(kind="two-part"),  # mirror_index must earn its definition size
        ),
        note=note,
    )


def e8_mirror_index_sub() -> StudySpec:
    """E8: does a frequent-subtree proposer invent mirror_index and compress the D4 ladder? (sub-only.)"""
    return _mirror_bootstrap_experiment(
        "e8-mirror-index-sub",
        BUILD_LIBRARY,
        "E8: E7's D4 ladder under the frequent-subtree proposer. Whole-program antiunification (E7) "
        "left the ladder uncompressed (x0.79); does mining the recurring subterm invent mirror_index "
        "= sub(sub(#0,#1),1), compress the ladder, and dissolve the beam cliff?",
        main_beam=128,  # E7's environment: sub-only solves the ladder at 128
        tight_beam=64,  # sub@64 = transpose only; sub+mirror@64 = the whole ladder
    )


def e9_mirror_index_affine() -> StudySpec:
    """E9: E8 on the honest *affine* grammar (sub+add+mul) — a wider search; same bootstrap question."""
    return _mirror_bootstrap_experiment(
        "e9-mirror-index-affine",
        BUILD_AFFINE_LIBRARY,
        "E9: E8's bootstrap on the affine coordinate grammar (sub+add+mul). add/mul widen the base "
        "search so the reflection is cut even at beam 128 (the chicken-and-egg: no mirror example to "
        "mine from); beam 224 seeds it once. Is the same mirror_index invented, and its speedup larger?",
        main_beam=224,  # affine needs >=224 to solve a reflection at all (<=192 fails) — the add/mul cost
        tight_beam=128,  # affine@128 = transpose only; affine+mirror@128 = the whole ladder
    )


def e10_stitch_refactor() -> StudySpec:
    """E10: does **Stitch library refactoring** recover a composable mirror_index *without* the
    type-scoping stopgap? E8's sub-only environment, but the sleep step is the two-phase
    :class:`RefactoringSleep` — in-house `FrequentSubtree` mines the read-bodies, then Stitch
    antiunifies their differing perceiver into the general (first-order) mirror_index, our ``TwoPartMDL``
    governing. A *labelled first-order stopgap* (see `RefactoringSleep`): the clean single-pass
    corpus-mining is higher-order, deferred to the higher-order phase. Needs the optional wheel to run."""
    search = BuildGridSearch(beam_width=128)
    return StudySpec(
        name="e10-stitch-refactor",
        starting_library=BUILD_LIBRARY,
        targets=(("mirror_index", _mirror(Param(0, _I), Param(1, _I))),),
        tasks=_d4_tasks(_D4_MEMBERS, n_train=3, n_heldout=1),
        search=search,
        enablement_search=BuildGridSearch(beam_width=64),
        cost=ProgramSize(),
        # No search-scoped gag: refactoring recovers mirror_index on merit. Phase 1 (in-house
        # FrequentSubtree) mints the closed read-bodies; phase 2 (Stitch) antiunifies their differing
        # perceiver (width/height) into the general, composable mirror_index.
        sleep=SleepSpec(
            kind="refactoring",
            proposer=ProposerSpec(kind="frequent-subtree"),
            refactor_proposer=ProposerSpec(kind="stitch", first_order=True, iterations=1),
            metric=MetricSpec(kind="two-part"),
        ),
        note="E10: Stitch library refactoring recovers mirror_index without the type-scoping stopgap.",
    )


#: StudySpec registry for the CLI (`arc-lab learn <name>`).
_REGISTRY = {
    "e1-rot90": e1_rot90,
    "e2-swap-cells": e2_swap_cells,
    "e3-swap-cols": e3_swap_cols,
    "e4-swap-cols-mdl": e4_swap_cols_mdl,
    "e5-rederive-rot90": e5_rederive_rot90,
    "e6-rederive-d4": e6_rederive_d4,
    "e7-rederive-d4-safe": e7_rederive_d4_safe,
    "e8-mirror-index-sub": e8_mirror_index_sub,
    "e9-mirror-index-affine": e9_mirror_index_affine,
    "e10-stitch-refactor": e10_stitch_refactor,
}


def make_study(name: str) -> StudySpec:
    try:
        return _REGISTRY[name]()
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown experiment {name!r}; known: {known}") from None
