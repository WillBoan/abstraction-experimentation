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
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from arc_lab.solvers.dsl.analysis.compression import CompressionMetric
    from arc_lab.solvers.dsl.learn.antiunify import AbstractionProposer
    from arc_lab.solvers.dsl.learn.sleep import SleepStrategy

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
        max_depth, beam_width, members = (
            data.get("max_depth"),
            data.get("beam_width"),
            data.get("members"),
        )
        return SearchSpec(
            kind=str(data["kind"]),
            max_depth=max_depth if isinstance(max_depth, int) else None,
            beam_width=beam_width if isinstance(beam_width, int) else None,
            members=tuple(str(m) for m in members) if isinstance(members, list) else (),
        )


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """The governance objective as data: flat per-primitive MDL, or two-part (charges definitions)."""

    kind: str = "flat"  # "flat" | "two-part"
    bits_per_primitive: float = 1.0
    cost: str = "program-size"

    def build(self) -> CompressionMetric:
        from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, TwoPartMDL

        cost = resolve_cost(self.cost)
        if self.kind == "flat":
            return CompressionMetric(cost=cost, bits_per_primitive=self.bits_per_primitive)
        if self.kind == "two-part":
            return TwoPartMDL(cost=cost, bits_per_primitive=self.bits_per_primitive)
        raise ValueError(f"unknown metric kind: {self.kind!r}")

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "bits_per_primitive": self.bits_per_primitive, "cost": self.cost}

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> MetricSpec:
        bpp = data.get("bits_per_primitive")
        cost = data.get("cost")
        return MetricSpec(
            kind=str(data.get("kind", "flat")),
            bits_per_primitive=float(bpp) if isinstance(bpp, (int, float)) else 1.0,
            cost=str(cost) if isinstance(cost, str) else "program-size",
        )


@dataclass(frozen=True, slots=True)
class ProposerSpec:
    """The abstraction-invention plug point as data.

    ``kind``: ``antiunify-pairs`` (± ``bound_var_safe``) · ``frequent-subtree`` (``min_frequency``) ·
    ``search-scoped`` (mines subtrees the *search* can compose — needs the wake search) · ``stitch``
    (the external engine; ``iterations``/``max_arity``/``threads``/``first_order``).
    """

    kind: str = "antiunify-pairs"
    bound_var_safe: bool = False
    min_frequency: int = 2
    iterations: int = 5
    max_arity: int = 3
    threads: int = 1
    first_order: bool = True

    def build(self, search: Search) -> AbstractionProposer:
        from arc_lab.solvers.dsl.learn.antiunify import (
            AntiunifyPairs,
            FrequentSubtree,
            SearchScopedFrequentSubtree,
        )

        if self.kind == "antiunify-pairs":
            return AntiunifyPairs(bound_var_safe=self.bound_var_safe)
        if self.kind == "frequent-subtree":
            return FrequentSubtree(min_frequency=self.min_frequency)
        if self.kind == "search-scoped":
            composes = getattr(search, "composes_signature", None)
            if composes is None:
                raise ValueError("search-scoped proposer needs a search with composes_signature")
            return SearchScopedFrequentSubtree(composes=composes)
        if self.kind == "stitch":
            from arc_lab.solvers.dsl.learn.stitch_shim import StitchProposer

            return StitchProposer(
                iterations=self.iterations,
                max_arity=self.max_arity,
                threads=self.threads,
                first_order=self.first_order,
            )
        raise ValueError(f"unknown proposer kind: {self.kind!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "bound_var_safe": self.bound_var_safe,
            "min_frequency": self.min_frequency,
            "iterations": self.iterations,
            "max_arity": self.max_arity,
            "threads": self.threads,
            "first_order": self.first_order,
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> ProposerSpec:
        def _int(key: str, default: int) -> int:
            v = data.get(key)
            return v if isinstance(v, int) and not isinstance(v, bool) else default

        def _bool(key: str, default: bool) -> bool:
            v = data.get(key)
            return v if isinstance(v, bool) else default

        return ProposerSpec(
            kind=str(data.get("kind", "antiunify-pairs")),
            bound_var_safe=_bool("bound_var_safe", False),
            min_frequency=_int("min_frequency", 2),
            iterations=_int("iterations", 5),
            max_arity=_int("max_arity", 3),
            threads=_int("threads", 1),
            first_order=_bool("first_order", True),
        )


@dataclass(frozen=True, slots=True)
class SleepSpec:
    """The whole sleep step as data: which strategy, its proposer(s), and its governance metric."""

    kind: str = "greedy-mdl"  # "greedy-mdl" | "refactoring"
    proposer: ProposerSpec = field(default_factory=ProposerSpec)
    refactor_proposer: ProposerSpec | None = None  # required for "refactoring"
    metric: MetricSpec = field(default_factory=MetricSpec)
    name_prefix: str = "abs"

    def build(self, search: Search) -> SleepStrategy:
        from arc_lab.solvers.dsl.learn.selection import GreedyMDL
        from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep, RefactoringSleep

        metric = self.metric.build()
        if self.kind == "greedy-mdl":
            return GreedyMDLSleep(
                self.proposer.build(search),
                selector=GreedyMDL(),
                metric=metric,
                name_prefix=self.name_prefix,
            )
        if self.kind == "refactoring":
            if self.refactor_proposer is None:
                raise ValueError("refactoring sleep needs a refactor_proposer")
            return RefactoringSleep(
                self.proposer.build(search),
                self.refactor_proposer.build(search),
                selector=GreedyMDL(),
                metric=metric,
                name_prefix=self.name_prefix,
            )
        raise ValueError(f"unknown sleep kind: {self.kind!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "proposer": self.proposer.to_dict(),
            "refactor_proposer": None
            if self.refactor_proposer is None
            else self.refactor_proposer.to_dict(),
            "metric": self.metric.to_dict(),
            "name_prefix": self.name_prefix,
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> SleepSpec:
        proposer_raw = data.get("proposer")
        refactor_raw = data.get("refactor_proposer")
        metric_raw = data.get("metric")
        return SleepSpec(
            kind=str(data.get("kind", "greedy-mdl")),
            proposer=ProposerSpec.from_dict(proposer_raw)
            if isinstance(proposer_raw, Mapping)
            else ProposerSpec(),
            refactor_proposer=ProposerSpec.from_dict(refactor_raw)
            if isinstance(refactor_raw, Mapping)
            else None,
            metric=MetricSpec.from_dict(metric_raw)
            if isinstance(metric_raw, Mapping)
            else MetricSpec(),
            name_prefix=str(data.get("name_prefix", "abs")),
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
