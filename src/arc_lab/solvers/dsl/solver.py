"""Program-search solvers: thin wiring over the substrate.

A :class:`ProgramSearchSolver` is defined entirely by a *(library, search)* pair.
This is where the three axes come together — pick a vocabulary, pick a strategy,
and the harness contract (:meth:`predict`) is satisfied automatically. Concrete
solvers are one-line configurations.
"""

from __future__ import annotations

from arc_lab.core.task import Task
from arc_lab.solvers.base import Prediction, Solver
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.composite import CompositeSearch
from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.search.overlay import OverlaySearch
from arc_lab.solvers.dsl.search.single_apply import SingleApply
from arc_lab.solvers.dsl.search.tile import TileSearch
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.color import MAP_COLOR
from arc_lab.solvers.dsl.substrate.primitives.combinators import COMBINATORS
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.scaling import SCALE
from arc_lab.solvers.dsl.substrate.program import Input, Program, evaluate_grid

# When search finds nothing consistent, fall back to the identity program so we
# always return a well-formed (if usually wrong) grid rather than crashing.
_FALLBACK: Program = Input()

#: D4 transforms plus the overlay and tile combinators.
SYMMETRY_LIBRARY = D4_LIBRARY.extended(name="d4+combinators", extra=COMBINATORS)

#: D4 transforms plus atomic color and scaling primitives, for composition search.
ATOMIC_LIBRARY = D4_LIBRARY.extended(name="atomic", extra=(MAP_COLOR, SCALE))


class ProgramSearchSolver(Solver):
    """Solve a task by searching a library for a consistent program."""

    def __init__(self, *, library: Library, search: Search, name: str = "program-search") -> None:
        self.library = library
        self.search = search
        self.name = name

    def predict(self, task: Task) -> Prediction:
        programs = self.search.find(task, self.library) or [_FALLBACK]
        return [
            [evaluate_grid(program, example.input, self.library) for program in programs]
            for example in task.test
        ]


class GeometricSearchSolver(ProgramSearchSolver):
    """Whole-grid geometric-transform search: the D4 library, single application."""

    def __init__(self) -> None:
        super().__init__(library=D4_LIBRARY, search=SingleApply(), name="dsl")


class SymmetrySearchSolver(ProgramSearchSolver):
    """D4 single transforms plus the overlay (symmetry-repair) and tile combinators."""

    def __init__(self) -> None:
        super().__init__(
            library=SYMMETRY_LIBRARY,
            search=CompositeSearch([SingleApply(), OverlaySearch(), TileSearch()]),
            name="dsl-sym",
        )


class SynthesisSolver(ProgramSearchSolver):
    """Typed bottom-up enumeration of composed programs over the atomic vocabulary.

    Solves 11/400 ARC-1 train tasks: the D4 seven plus four found via the atomic
    primitives (scale, map_color). Empirically, ``max_depth=2`` composition adds
    *no* further solves over ``max_depth=1`` on this vocabulary — sequential
    ``map_color`` cannot express a color swap, D4 is closed under composition, and
    scaling rarely needs composing. The engine itself composes to any depth (see
    the depth-2 tests); realising a real-data benefit needs richer primitives
    (a color permutation, cropping, object extraction), which is the next step.
    """

    def __init__(self, *, max_depth: int = 2) -> None:
        super().__init__(
            library=ATOMIC_LIBRARY,
            search=Enumerate(max_depth=max_depth),
            name="dsl-synth",
        )
