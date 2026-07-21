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

from arc_lab.core.grid import Grid

from ..substrate.library import Library
from ..substrate.program import Const, Input, Program, Var
from ..substrate.types import BOOL, COLOR, GRID, INT, ArrowType, Type, TypeCon
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
    """A fixed, typed, bounded set: ``INT`` 0..max-dim, ``COLOR`` 0..9, ``BOOL`` {False, True} —
    only for whichever of these base types ``library`` actually uses somewhere."""
    if _type_in_use(INT, library):
        max_dimension = max((max(grid.height, grid.width) for grid in grids), default=0)
        for value in range(max_dimension + 1):
            yield Const(value=value, value_type=INT), INT
    if _type_in_use(COLOR, library):
        for color in range(10):
            yield Const(value=color, value_type=COLOR), COLOR
    if _type_in_use(BOOL, library):
        for flag in (False, True):
            yield Const(value=flag, value_type=BOOL), BOOL


def _harvest_from_instance(
    grids: Iterable[Grid], library: Library
) -> Iterator[tuple[Program, Type]]:
    """The literals present in the instance: the colors used and the grid dimensions — only for
    whichever of ``COLOR``/``INT`` ``library`` actually uses somewhere."""
    want_color = _type_in_use(COLOR, library)
    want_int = _type_in_use(INT, library)
    if not want_color and not want_int:
        return
    colors: set[int] = set()
    dimensions: set[int] = set()
    for grid in grids:
        if want_color:
            colors.update(color for row in grid.to_list() for color in row)
        if want_int:
            dimensions.update((grid.height, grid.width))
    if want_color:
        for color in sorted(colors):
            yield Const(value=color, value_type=COLOR), COLOR
    if want_int:
        for dimension in sorted(dimensions):
            yield Const(value=dimension, value_type=INT), INT


def _distinct_input_grids(contexts: tuple[Context, ...]) -> list[Grid]:
    """The distinct input grids across the contexts, in first-seen order (deterministic)."""
    return list(dict.fromkeys(context.input_grid for context in contexts))
