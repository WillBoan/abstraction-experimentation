"""Leaf seeding (§5.1) and the literal constant sources (§6.3) of ARCHITECTURE.md.

The round-0 leaves of a bottom-up search: the input grid, the bound variables in scope (the open-term
leaves), and literal constants. Two sources inject ``Const`` nodes — ``finite-enumerate`` (a bounded
typed set) and ``harvest-from-instance`` (the literals present in the instance).

Constants are derived from the **input grids in the contexts**, never the task outputs: ``_enumerate``
is a pure function of ``(scope, contexts, budget)`` (§9), so it cannot see outputs. This costs nothing
in completeness — ``finite-enumerate`` covers every color, and output-specific dimensions are *derived*
by composition (size-general), not harvested as literals. Input-derived values generally
(``width(Input())``, most-common-color) are likewise compositions (§5.2), not leaves; ``parameterize``
mints nothing here (it belongs to ``learn/``, §14), its enum value kept only for a shared vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Literal, TypeAlias

from arc_lab.core.grid import Grid

from ..substrate.program import Const, Input, Program, Var
from ..substrate.types import BOOL, COLOR, GRID, INT, Type
from .context import Context
from .scope import Scope

#: A literal-constant policy. ``finite-enumerate`` / ``harvest-from-instance`` mint ``Const`` leaves;
#: ``parameterize`` mints nothing here (realized in ``learn/``) — kept for a shared config vocabulary.
ConstantSource: TypeAlias = Literal["finite-enumerate", "harvest-from-instance", "parameterize"]


def seed_leaves(
    scope: Scope,
    contexts: tuple[Context, ...],
    constant_sources: tuple[ConstantSource, ...],
) -> Iterator[tuple[Program, Type]]:
    """The round-0 leaves: ``Input()``, the in-scope bound variables, and the policy constants."""
    yield Input(), GRID
    for index in range(len(scope)):
        binder = scope.type_of(index)
        yield Var(index=index, value_type=binder), binder
    grids = _distinct_input_grids(contexts)
    for source in constant_sources:
        if source == "finite-enumerate":
            yield from _finite_enumerate(grids)
        elif source == "harvest-from-instance":
            yield from _harvest_from_instance(grids)
        # "parameterize" mints nothing here — realized in learn/ (§6.3, §14).


def _finite_enumerate(grids: Iterable[Grid]) -> Iterator[tuple[Program, Type]]:
    """A fixed, typed, bounded set: ``INT`` 0..max-dim, ``COLOR`` 0..9, ``BOOL`` {False, True}."""
    max_dimension = max((max(grid.height, grid.width) for grid in grids), default=0)
    for value in range(max_dimension + 1):
        yield Const(value=value, value_type=INT), INT
    for color in range(10):
        yield Const(value=color, value_type=COLOR), COLOR
    for flag in (False, True):
        yield Const(value=flag, value_type=BOOL), BOOL


def _harvest_from_instance(grids: Iterable[Grid]) -> Iterator[tuple[Program, Type]]:
    """The literals present in the instance: the colors used and the grid dimensions."""
    colors: set[int] = set()
    dimensions: set[int] = set()
    for grid in grids:
        colors.update(color for row in grid.to_list() for color in row)
        dimensions.update((grid.height, grid.width))
    for color in sorted(colors):
        yield Const(value=color, value_type=COLOR), COLOR
    for dimension in sorted(dimensions):
        yield Const(value=dimension, value_type=INT), INT


def _distinct_input_grids(contexts: tuple[Context, ...]) -> list[Grid]:
    """The distinct input grids across the contexts, in first-seen order (deterministic)."""
    return list(dict.fromkeys(context.input_grid for context in contexts))
