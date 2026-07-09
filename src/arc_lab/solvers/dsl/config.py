"""Config: the machinery of a run as *data* — a declarative (library x search x cost) spec.

A :class:`Config` names the wiring (which library, which search strategy, which cost) and
carries the search *parameters* as data, so it is frozen, hashable, diffable, and sweepable —
unlike a solver subclass, which welds the wiring into a class. :data:`PRESETS` reproduce the
historical solvers as named ``Config`` values; :meth:`ProgramSearchSolver.from_config` builds
a live solver from one.

This is where the "decouple parameters from wiring" goal lands: ``max_depth`` / ``beam_width``
are fields on the (data) :class:`SearchSpec`, overridable via :meth:`Config.with_param`, instead
of constructor literals frozen inside a subclass.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.composite import CompositeSearch
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.search.enumerate import BeamSearch, Enumerate
from arc_lab.solvers.dsl.search.overlay import OverlaySearch
from arc_lab.solvers.dsl.search.single_apply import SingleApply
from arc_lab.solvers.dsl.search.tile import TileSearch
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.color import MAP_COLOR
from arc_lab.solvers.dsl.substrate.primitives.combinators import COMBINATORS
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.scaling import SCALE

#: D4 transforms plus the overlay and tile combinators.
SYMMETRY_LIBRARY = D4_LIBRARY.extended(name="d4+combinators", extra=COMBINATORS)
#: D4 transforms plus atomic color and scaling primitives, for composition search.
ATOMIC_LIBRARY = D4_LIBRARY.extended(name="atomic", extra=(MAP_COLOR, SCALE))

#: The vocabulary axis, addressed by name (a run selects a whole pre-built library today).
LIBRARIES: dict[str, Library] = {
    "d4": D4_LIBRARY,
    "symmetry": SYMMETRY_LIBRARY,
    "atomic": ATOMIC_LIBRARY,
}

#: The cost axis, addressed by name.
COSTS: dict[str, Callable[[], Cost]] = {
    "program-size": ProgramSize,
}


def resolve_library(name: str) -> Library:
    """Resolve a library name to its live :class:`Library`."""
    try:
        return LIBRARIES[name]
    except KeyError:
        known = ", ".join(sorted(LIBRARIES))
        raise KeyError(f"unknown library {name!r}; known: {known}") from None


def resolve_cost(name: str) -> Cost:
    """Resolve a cost name to a fresh :class:`Cost`."""
    try:
        return COSTS[name]()
    except KeyError:
        known = ", ".join(sorted(COSTS))
        raise KeyError(f"unknown cost {name!r}; known: {known}") from None


@dataclass(frozen=True, slots=True)
class SearchSpec:
    """A declarative search-strategy spec: the ``kind`` plus its scalar parameters.

    ``members`` names the leaf kinds for ``kind="composite"``. Parameters left ``None`` fall
    back to each strategy's historical default at :meth:`build` time.
    """

    kind: str
    max_depth: int | None = None
    beam_width: int | None = None
    members: tuple[str, ...] = ()

    def build(self, cost: Cost) -> Search:
        """Construct the live :class:`Search`. ``cost`` is used only by cost-guided kinds."""
        if self.kind == "single_apply":
            return SingleApply()
        if self.kind == "overlay":
            return OverlaySearch()
        if self.kind == "tile":
            return TileSearch()
        if self.kind == "composite":
            return CompositeSearch([SearchSpec(kind=m).build(cost) for m in self.members])
        if self.kind == "enumerate":
            return Enumerate(max_depth=self.max_depth if self.max_depth is not None else 2)
        if self.kind == "beam":
            return BeamSearch(
                cost=cost,
                beam_width=self.beam_width if self.beam_width is not None else 16,
                max_depth=self.max_depth if self.max_depth is not None else 2,
            )
        raise ValueError(f"unknown search kind: {self.kind!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "max_depth": self.max_depth,
            "beam_width": self.beam_width,
            "members": list(self.members),
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> SearchSpec:
        max_depth, beam_width, members = data.get("max_depth"), data.get("beam_width"), data.get("members")
        return SearchSpec(
            kind=str(data["kind"]),
            max_depth=max_depth if isinstance(max_depth, int) else None,
            beam_width=beam_width if isinstance(beam_width, int) else None,
            members=tuple(str(m) for m in members) if isinstance(members, list) else (),
        )


@dataclass(frozen=True, slots=True)
class Config:
    """The machinery of a run as data: ``library x search x cost`` (+ params)."""

    name: str
    library: str
    search: SearchSpec
    cost: str = "program-size"

    def resolve_library(self) -> Library:
        return resolve_library(self.library)

    def resolve_cost(self) -> Cost:
        return resolve_cost(self.cost)

    def build_search(self) -> Search:
        return self.search.build(self.resolve_cost())

    def with_param(self, *, max_depth: int | None = None, beam_width: int | None = None) -> Config:
        """Return a copy with search parameters overridden (e.g. ``with_param(max_depth=1)``)."""
        search = replace(
            self.search,
            max_depth=self.search.max_depth if max_depth is None else max_depth,
            beam_width=self.search.beam_width if beam_width is None else beam_width,
        )
        return replace(self, search=search)

    def to_dict(self) -> dict[str, object]:
        """Canonical serialisation — the machinery identity that feeds a run's ``run_id``."""
        return {
            "name": self.name,
            "library": self.library,
            "search": self.search.to_dict(),
            "cost": self.cost,
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> Config:
        search_raw = data["search"]
        if not isinstance(search_raw, Mapping):
            raise ValueError("malformed config: 'search' must be a mapping")
        cost = data.get("cost")
        return Config(
            name=str(data["name"]),
            library=str(data["library"]),
            search=SearchSpec.from_dict(search_raw),
            cost=str(cost) if isinstance(cost, str) else "program-size",
        )


#: Named machinery presets — the historical solvers, now as data (Phase 7 wires the registry).
PRESETS: dict[str, Config] = {
    "dsl": Config(name="dsl", library="d4", search=SearchSpec(kind="single_apply")),
    "dsl-sym": Config(
        name="dsl-sym",
        library="symmetry",
        search=SearchSpec(kind="composite", members=("single_apply", "overlay", "tile")),
    ),
    "dsl-synth": Config(
        name="dsl-synth", library="atomic", search=SearchSpec(kind="enumerate", max_depth=2)
    ),
    "dsl-beam": Config(
        name="dsl-beam",
        library="atomic",
        search=SearchSpec(kind="beam", beam_width=16, max_depth=2),
    ),
}
