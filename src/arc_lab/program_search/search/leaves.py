"""The round-0 leaves of a bottom-up search:

- the input grid
- the bound variables in scope (the open-term leaves)
- literal constants (derived from the **input grids in the contexts**, never the task outputs)
  - `finite-enumerate` (a bounded typed set)
  - `harvest-from-instance` (the literals present in the instance)
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Literal, TypeAlias

from arc_lab.core.geometry import Coord, Offset
from arc_lab.core.grid import Grid

from ..substrate.library import Library
from ..substrate.program import Const, Input, Program, Var
from ..substrate.types import (
    BOOL,
    COLOR,
    COORD,
    GRID,
    INT,
    OFFSET,
    ArrowType,
    Type,
    TypeCon,
)
from .context import Context
from .scope import Scope

#: Policies for how to source constants:
ConstantSource: TypeAlias = Literal[
    # finite-enumerate: Mint a fixed, typed, bounded set of constants: INT 0..max-dim, COLOR 0..9, BOOL {False, True}.
    "finite-enumerate",
    # harvest-from-instance: Mint the literals present in the instance: the colors used and the grid dimensions.
    "harvest-from-instance",
    # parameterize: Mints nothing in SEARCH (used in LEARN, not SEARCH).
    "parameterize",
]


#: Which base types each constant policy can supply as round-0 leaves, by type name — the ONE
#: statement of it. Read-side consumers (the coherence checker's reachability closure, the cost
#: forecaster) must ask here rather than restate it: when the addressing types arrived, three
#: separate copies of "int/color/bool" silently disagreed with what `_finite_enumerate` actually
#: mints, and a bundle using `translate` read as structurally dead.
CONSTANT_SOURCE_TYPES: dict[str, frozenset[str]] = {
    "finite-enumerate": frozenset({INT.name, COLOR.name, BOOL.name, COORD.name, OFFSET.name}),
    "harvest-from-instance": frozenset({INT.name, COLOR.name, COORD.name, OFFSET.name}),
    "parameterize": frozenset(),  # mints nothing in SEARCH
}

#: Every type any constant policy could supply — the union of the above.
CONSTANT_LEAF_TYPES: frozenset[str] = frozenset().union(*CONSTANT_SOURCE_TYPES.values())


def seed_leaves(
    scope: Scope,
    contexts: tuple[Context, ...],
    constant_sources: tuple[ConstantSource, ...],
    library: Library,
) -> Iterator[tuple[Program, Type]]:
    """The round-0 leaves: ``Input()``, the in-scope bound variables, and the policy constants.

    ``library`` gates *which* base-type constants a policy actually mints (:func:`_type_in_use`):
    a library with no ``BOOL``-typed primitive (and no ``if``) has no use for a ``BOOL`` leaf, and
    minting one anyway is pure dead weight in every pool it's absorbed into.
    """
    yield Input(), GRID
    for index in range(len(scope)):
        binder = scope.type_of(index)
        yield Var(index=index, value_type=binder), binder
    yield from policy_constants(_distinct_input_grids(contexts), constant_sources, library)


def policy_constants(
    grids: Iterable[Grid],
    constant_sources: tuple[ConstantSource, ...],
    library: Library,
) -> Iterator[tuple[Program, Type]]:
    """The constants the given sources would mint as round-0 leaves for these input grids.

    The one public view of the configured constant domain — the lint's literal-collapse check
    asks membership of it, and :func:`seed_leaves` delegates here, so the two can never drift.
    """
    materialized = list(grids)
    for source in constant_sources:
        if source == "finite-enumerate":
            yield from _finite_enumerate(materialized, library)
        elif source == "harvest-from-instance":
            yield from _harvest_from_instance(materialized, library)
        elif source == "parameterize":
            pass  # no-op here; `parameterize` only matters for LEARN, not SEARCH


def _type_in_use(vtype: Type, library: Library) -> bool:
    """Whether ``vtype`` occurs anywhere in ``library``'s primitive signatures — including nested
    inside a container or an arrow-typed hole (e.g. ``BOOL`` inside ``filter``'s ``(a -> bool)``
    predicate hole, not just as a bare top-level parameter) — gating which base-type constant
    leaves are worth minting at all."""

    def occurs(t: Type) -> bool:
        if t == vtype:
            return True
        if isinstance(t, ArrowType):
            return occurs(t.result) or any(occurs(param) for param in t.params)
        if isinstance(t, TypeCon):
            return any(occurs(arg) for arg in t.args)
        return False

    return any(
        occurs(primitive.return_type) or any(occurs(param) for param in primitive.param_types)
        for primitive in library.primitives
    )


def _finite_enumerate(grids: Iterable[Grid], library: Library) -> Iterator[tuple[Program, Type]]:
    """A fixed, typed, bounded set: ``INT`` 0..max-dim, ``COLOR`` 0..9, ``BOOL`` {False, True},
    ``COORD``/``OFFSET`` the 0..max-dim square — only for whichever of these base types ``library``
    actually uses somewhere.

    **The addressing types are quadratic in max-dim** ((d+1)^2 leaves), which is the honest mirror of
    the INT range rather than an arbitrary cap: bounding them smaller would silently put some
    programs out of reach. It moves work that the old two-INT-argument spelling paid at
    *composition* time to *leaf* time, so the reachable set is unchanged — but the round-0 pool is
    much larger, and a library using these on full-size ARC grids wants a ``max_pool`` to match.
    ``constant_sources`` is already opt-in for exactly this reason (``ladder_default_config``).
    """
    max_dimension = max((max(grid.height, grid.width) for grid in grids), default=0)
    if _type_in_use(INT, library):
        for value in range(max_dimension + 1):
            yield Const(value=value, value_type=INT), INT
    if _type_in_use(COLOR, library):
        for color in range(10):
            yield Const(value=color, value_type=COLOR), COLOR
    if _type_in_use(BOOL, library):
        for flag in (False, True):
            yield Const(value=flag, value_type=BOOL), BOOL
    if _type_in_use(COORD, library):
        for row in range(max_dimension + 1):
            for col in range(max_dimension + 1):
                yield Const(value=Coord(row, col), value_type=COORD), COORD
    if _type_in_use(OFFSET, library):
        for d_row in range(max_dimension + 1):
            for d_col in range(max_dimension + 1):
                yield Const(value=Offset(d_row, d_col), value_type=OFFSET), OFFSET


def _harvest_from_instance(
    grids: Iterable[Grid], library: Library
) -> Iterator[tuple[Program, Type]]:
    """The literals present in the instance: the colors used and the grid dimensions — only for
    whichever of ``COLOR``/``INT``/``COORD``/``OFFSET`` ``library`` actually uses somewhere.

    The addressing types harvest the *cross product of the observed dimensions*, which is the
    instance-scoped analogue of the INT set (and far smaller than ``finite-enumerate``'s square).
    Content-derived positions are a perceiver's job (``content_coords``), not a constant's.
    """
    want_color = _type_in_use(COLOR, library)
    want_int = _type_in_use(INT, library)
    want_coord = _type_in_use(COORD, library)
    want_offset = _type_in_use(OFFSET, library)
    if not (want_color or want_int or want_coord or want_offset):
        return
    colors: set[int] = set()
    dimensions: set[int] = set()
    for grid in grids:
        if want_color:
            colors.update(color for row in grid.to_list() for color in row)
        if want_int or want_coord or want_offset:
            dimensions.update((grid.height, grid.width))
    if want_color:
        for color in sorted(colors):
            yield Const(value=color, value_type=COLOR), COLOR
    if want_int:
        for dimension in sorted(dimensions):
            yield Const(value=dimension, value_type=INT), INT
    for first in sorted(dimensions):
        for second in sorted(dimensions):
            if want_coord:
                yield Const(value=Coord(first, second), value_type=COORD), COORD
            if want_offset:
                yield Const(value=Offset(first, second), value_type=OFFSET), OFFSET


def _distinct_input_grids(contexts: tuple[Context, ...]) -> list[Grid]:
    """The distinct input grids across the contexts, in first-seen order (deterministic)."""
    return list(dict.fromkeys(context.input_grid for context in contexts))
