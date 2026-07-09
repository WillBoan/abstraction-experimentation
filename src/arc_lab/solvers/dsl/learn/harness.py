"""The three-library harness: compare solvers, and behaviorally check learned vs target.

Two independent tools, both keeping targets as *observables* (never a training signal):

* :func:`check_abstractions` — did the learned library reproduce the target abstractions?
  Compared **behaviorally** (observational equivalence over a fixed input battery), not by
  program shape: two entries match iff they agree on every battery input. Reports the
  target∩learned (matched), target minus learned (missed), and learned minus target (novel — the
  surprising, and welcome, case).
* :func:`compare_libraries` — run the starting / learned / target-augmented libraries as
  three solvers (holding search + cost fixed) and return their run summaries, so solve /
  `considered` / description-length deltas are read off the recorded artifacts.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

from arc_lab.core.dataset import Dataset
from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.analysis.compression import CompressionMetric
from arc_lab.solvers.dsl.analysis.runner import RunSummary, execute
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.cost import Cost
from arc_lab.solvers.dsl.solver import ProgramSearchSolver
from arc_lab.solvers.dsl.substrate.library import Library, Primitive, Value
from arc_lab.solvers.dsl.substrate.types import COLOR, GRID, INT, Type

#: A fixed, varied battery for observational equivalence (square + non-square + singleton).
_TEST_GRIDS: tuple[Grid, ...] = (
    Grid.from_list([[1, 2], [3, 4]]),
    Grid.from_list([[1, 2, 3], [4, 5, 6]]),
    Grid.from_list([[5, 0], [0, 5], [1, 2]]),
    Grid.from_list([[7]]),
)
_TEST_COLORS: tuple[int, ...] = (0, 1, 2, 5, 9)
_TEST_INTS: tuple[int, ...] = (0, 1, 2, 3)
_MAX_BATTERY = 400  # cap the arg-combination product for high-arity abstractions


def _battery(param_types: tuple[Type, ...]) -> list[tuple[Value, ...]]:
    # Base-typed inputs only; a function-typed (arrow) parameter has no test battery yet — behavioral
    # signatures over higher-order primitives are a later (Phase E) concern.
    pools: dict[Type, tuple[Value, ...]] = {
        GRID: _TEST_GRIDS,
        COLOR: _TEST_COLORS,
        INT: _TEST_INTS,
    }
    combos = itertools.product(*(pools[t] for t in param_types))
    return list(itertools.islice(combos, _MAX_BATTERY))


def _cell(value: Value | None) -> object:
    if isinstance(value, Grid):
        return ("grid", value.shape, value.array.tobytes())
    return value


def behavioral_signature(primitive: Primitive) -> tuple[object, ...]:
    """The primitive's I/O over its battery — its observational identity (errors → None)."""
    signature: list[object] = []
    for args in _battery(primitive.param_types):
        try:
            result: Value | None = primitive.impl(*args)
        except Exception:
            # An erroring input is a legitimate battery cell (out-of-bounds coord, etc.);
            # target and learned must agree there too, so record None and continue.
            result = None
        signature.append(_cell(result))
    return tuple(signature)


@dataclass(frozen=True, slots=True)
class CheckResult:
    matched: tuple[str, ...]  # target names a learned abstraction reproduces
    missed: tuple[str, ...]  # target names nothing learned reproduces
    novel: tuple[str, ...]  # learned abstractions matching no target (the surprises)


def check_abstractions(learned: list[Primitive], targets: list[Primitive]) -> CheckResult:
    """Behaviorally match learned abstractions against target abstractions."""
    learned_sigs = {p.name: (p.param_types, behavioral_signature(p)) for p in learned}
    matched: list[str] = []
    missed: list[str] = []
    used: set[str] = set()
    for target in targets:
        want = (target.param_types, behavioral_signature(target))
        hit = next(
            (name for name, sig in learned_sigs.items() if sig == want and name not in used),
            None,
        )
        if hit is not None:
            matched.append(target.name)
            used.add(hit)
        else:
            missed.append(target.name)
    novel = [name for name in learned_sigs if name not in used]
    return CheckResult(tuple(matched), tuple(missed), tuple(novel))


def compare_libraries(
    libraries: dict[str, Library],
    *,
    search: Search,
    cost: Cost,
    dataset: Dataset,
    out_dir: Path,
    metric: CompressionMetric | None = None,
) -> dict[str, RunSummary]:
    """Run each named library as a solver over ``dataset`` and return the run summaries."""
    summaries: dict[str, RunSummary] = {}
    for name, library in libraries.items():
        solver = ProgramSearchSolver(library=library, search=search, cost=cost, name=name)
        summary, _ = execute(solver, dataset, out_dir=out_dir, metric=metric)
        summaries[name] = summary
    return summaries
