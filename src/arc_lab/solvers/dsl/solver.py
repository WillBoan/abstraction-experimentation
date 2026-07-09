"""Program-search solvers: thin wiring over the substrate.

A :class:`ProgramSearchSolver` is defined entirely by a *(library, search)* pair.
This is where the three axes come together — pick a vocabulary, pick a strategy,
and the harness contract (:meth:`predict`) is satisfied automatically. Concrete
solvers are one-line configurations.
"""

from __future__ import annotations

from arc_lab.core.task import Task
from arc_lab.solvers.base import Prediction, Solver
from arc_lab.solvers.dsl.config import Config
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Input, Program
from arc_lab.solvers.dsl.trace import task_context

# When search finds nothing consistent, fall back to the identity program so we
# always return a well-formed (if usually wrong) grid rather than crashing.
_FALLBACK: Program = Input()


class ProgramSearchSolver(Solver):
    """
    A program-search solver is defined entirely by a *(library, search)* pair.
    The harness contract (:meth:`predict`) is satisfied automatically.
    """

    def __init__(
        self,
        *,
        library: Library,
        search: Search,
        cost: Cost | None = None,
        name: str = "program-search",
        config: Config | None = None,
    ) -> None:
        self.library = library
        self.search = search
        # The rank step: order candidate programs (lower cost first). Default is an
        # Occam prior (program size). A stable sort keeps proposal order on ties.
        self.cost = ProgramSize() if cost is None else cost
        self.name = name
        #: The declarative machinery this solver was built from, when built via
        #: :meth:`from_config` — carries the search params into a run's identity. ``None``
        #: for a solver constructed directly (e.g. over a learned library in a study).
        self.config = config

    @classmethod
    def from_config(cls, config: Config) -> ProgramSearchSolver:
        """Build a solver from a declarative :class:`~arc_lab.solvers.dsl.config.Config`."""
        return cls(
            library=config.resolve_library(),
            search=config.build_search(),
            cost=config.resolve_cost(),
            name=config.name,
            config=config,
        )

    def predict(self, task: Task) -> Prediction:
        # Bind the task id so the strategies' trace lines can be attributed to it.
        with task_context(task.task_id):
            candidates = list(self.search.find(task, self.library).programs) or [_FALLBACK]
            ranked = sorted(
                candidates, key=lambda program: self.cost.of(program, task, self.library)
            )
            return [
                [program.evaluate_grid(example.input, self.library) for program in ranked]
                for example in task.test
            ]
