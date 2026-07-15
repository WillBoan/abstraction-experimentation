"""Leaf seeding (§5.1) and the literal constant sources (§6.3)."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.leaves import seed_leaves
from arc_lab.program_search.search.scope import Scope
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Const, Input, Var
from arc_lab.program_search.substrate.types import BOOL, COLOR, GRID, INT, Type

# A 2x3 grid, so the max dimension is 3.
_G = Grid.from_list([[1, 2, 3], [4, 5, 6]])
_CONTEXTS = (Context(_G),)

#: An empty library — fine wherever ``constant_sources`` is ``()``/``("parameterize",)``, since
#: neither ever consults the library at all.
_NO_PRIMITIVES = Library(name="empty", primitives=())


def _library_using(*types: Type) -> Library:
    """A minimal library with one dummy unary primitive per given type (as both its param and
    return type) — just enough for ``_type_in_use`` to see that type as "in use"."""
    return Library(
        name="uses",
        primitives=tuple(
            Primitive(name=f"prim_{i}", param_types=(t,), return_type=t, impl=lambda x: x)
            for i, t in enumerate(types)
        ),
    )


#: Uses all three base types ``finite-enumerate``/``harvest-from-instance`` can mint — so gating
#: never strips anything, preserving the original (pre-gating) assertions below.
_ALL_TYPES = _library_using(INT, COLOR, BOOL)


def test_input_is_the_first_leaf_and_the_only_one_without_sources() -> None:
    assert list(seed_leaves(Scope(), _CONTEXTS, (), _NO_PRIMITIVES)) == [(Input(), GRID)]


def test_scope_variables_are_seeded_with_their_types_de_bruijn_order() -> None:
    scope = Scope().extend(INT).extend(COLOR)  # $1 = INT (outer), $0 = COLOR (inner)
    assert list(seed_leaves(scope, _CONTEXTS, (), _NO_PRIMITIVES)) == [
        (Input(), GRID),
        (Var(index=0, value_type=COLOR), COLOR),  # innermost = De Bruijn 0
        (Var(index=1, value_type=INT), INT),
    ]


def test_finite_enumerate_is_a_typed_bounded_set() -> None:
    leaves = list(seed_leaves(Scope(), _CONTEXTS, ("finite-enumerate",), _ALL_TYPES))
    assert (Const(value=0, value_type=INT), INT) in leaves
    assert (Const(value=3, value_type=INT), INT) in leaves  # up to max dimension
    assert (Const(value=4, value_type=INT), INT) not in leaves  # not beyond it
    assert (Const(value=9, value_type=COLOR), COLOR) in leaves
    assert (Const(value=10, value_type=COLOR), COLOR) not in leaves
    assert (Const(value=True, value_type=BOOL), BOOL) in leaves
    assert (Const(value=False, value_type=BOOL), BOOL) in leaves


def test_finite_enumerate_only_mints_base_types_the_library_uses() -> None:
    # Only INT is used anywhere in this library — COLOR/BOOL leaves would be permanently inert.
    leaves = list(seed_leaves(Scope(), _CONTEXTS, ("finite-enumerate",), _library_using(INT)))
    assert (Const(value=0, value_type=INT), INT) in leaves
    assert not any(vtype == COLOR for _, vtype in leaves)
    assert not any(vtype == BOOL for _, vtype in leaves)


def test_harvest_emits_only_instance_colors_and_dimensions() -> None:
    # Two context input grids: colors {3,7} and {5}; dims from 2x2 -> {2}, from 1x3 -> {1, 3}.
    contexts = (
        Context(Grid.from_list([[3, 3], [7, 3]])),
        Context(Grid.from_list([[5, 5, 5]])),
    )
    leaves = list(seed_leaves(Scope(), contexts, ("harvest-from-instance",), _ALL_TYPES))
    for color in (3, 5, 7):
        assert (Const(value=color, value_type=COLOR), COLOR) in leaves
    assert (Const(value=0, value_type=COLOR), COLOR) not in leaves  # absent color
    for dimension in (1, 2, 3):
        assert (Const(value=dimension, value_type=INT), INT) in leaves


def test_harvest_only_mints_base_types_the_library_uses() -> None:
    # Only INT is used anywhere in this library — harvested COLOR leaves would be permanently inert.
    contexts = (Context(Grid.from_list([[3, 3], [7, 3]])),)
    leaves = list(seed_leaves(Scope(), contexts, ("harvest-from-instance",), _library_using(INT)))
    assert (Const(value=2, value_type=INT), INT) in leaves  # the 2x2 grid's dimension
    assert not any(vtype == COLOR for _, vtype in leaves)


def test_parameterize_mints_nothing() -> None:
    assert list(seed_leaves(Scope(), _CONTEXTS, ("parameterize",), _NO_PRIMITIVES)) == [
        (Input(), GRID)
    ]
