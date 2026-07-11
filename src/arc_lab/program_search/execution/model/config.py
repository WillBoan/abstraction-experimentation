"""``Config``: the machinery of a run, as content-hashable data.

``Config = library x search_engine x constraints x cost x attempts_per_test x learn?``.
``learn is None`` ⇒ a SEARCH run; set ⇒ a LEARN run — the discriminator is *in* the
identity, so the two can never collide on a ``run_id``. There is no ``Solver`` class:
the execution layer drives ``Config`` directly (EXECUTION.md).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.serde import Registry, from_data, to_data
from arc_lab.program_search.search.constraints import Constraint
from arc_lab.program_search.search.cost import Cost, ProgramSize
from arc_lab.program_search.search.search_engine import SearchEngine
from arc_lab.program_search.substrate.library import Library


def default_registry() -> dict[str, type]:
    """The known component kinds, resolved lazily so mid-refactor modules import late."""
    from arc_lab.program_search.search.budget import Budget
    from arc_lab.program_search.search.search_engine import (
        BeamBottomUpSearchEngine,
        BottomUpSearchEngine,
    )

    components: tuple[type, ...] = (
        BottomUpSearchEngine,
        BeamBottomUpSearchEngine,
        Budget,
        ProgramSize,
        LearnSpec,
    )
    return {component.__name__: component for component in components}


@dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    """The machinery (HOW) of a recorded run — frozen, content-hashable."""

    library: Library
    search_engine: SearchEngine
    constraints: tuple[Constraint, ...] = ()
    cost: Cost = field(default_factory=ProgramSize)
    #: k programs tried per test input (official ARC rule: 2). In the identity —
    #: solve-rate depends on it. Flows to ``predict()``.
    attempts_per_test: int = 2
    #: None ⇒ SEARCH run; set ⇒ LEARN run.
    learn: LearnSpec | None = None

    def with_(self, **overrides: Any) -> Config:
        """A copy with fields overridden — how a study derives its grid cells."""
        return dataclasses.replace(self, **overrides)

    def to_dict(self) -> dict[str, object]:
        """The canonical serialisation — feeds the ``run_id`` content hash."""
        return {
            "library": self.library.to_dict(),
            "search_engine": to_data(self.search_engine),
            "constraints": [to_data(constraint) for constraint in self.constraints],
            "cost": to_data(self.cost),
            "attempts_per_test": self.attempts_per_test,
            "learn": to_data(self.learn) if self.learn is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object], *, registry: Registry | None = None) -> Config:
        """Reconstruct from :meth:`to_dict` output (components resolved via ``registry``)."""
        reg = default_registry() if registry is None else registry
        library_data = data.get("library")
        engine_data = data.get("search_engine")
        constraints_data = data.get("constraints")
        cost_data = data.get("cost")
        attempts = data.get("attempts_per_test")
        learn_data = data.get("learn")
        if (
            not isinstance(library_data, Mapping)
            or not isinstance(engine_data, Mapping)
            or not isinstance(constraints_data, list)
            or not isinstance(cost_data, Mapping)
            or not isinstance(attempts, int)
            or not (learn_data is None or isinstance(learn_data, Mapping))
        ):
            raise ValueError(f"malformed Config data: {data!r}")

        search_engine = from_data(engine_data, reg)
        cost = from_data(cost_data, reg)
        constraints: list[Constraint] = []
        for constraint_data in constraints_data:
            if not isinstance(constraint_data, Mapping):
                raise ValueError(f"malformed constraint entry: {constraint_data!r}")
            constraint = from_data(constraint_data, reg)
            if not isinstance(constraint, Constraint):
                raise ValueError(f"constraint reconstructed to wrong type: {constraint_data!r}")
            constraints.append(constraint)
        learn = from_data(learn_data, reg) if learn_data is not None else None
        if (
            not isinstance(search_engine, SearchEngine)
            or not isinstance(cost, Cost)
            or not (learn is None or isinstance(learn, LearnSpec))
        ):
            raise ValueError(f"Config components reconstructed to wrong types: {data!r}")
        return cls(
            library=Library.from_dict(library_data),
            search_engine=search_engine,
            constraints=tuple(constraints),
            cost=cost,
            attempts_per_test=attempts,
            learn=learn,
        )
