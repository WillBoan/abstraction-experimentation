"""First-order composition (§5.2): well-typed application generation via unification."""

from __future__ import annotations

import itertools

from arc_lab.program_search.search.composition import (
    TypedProgram,
    appfn_applications,
    applications,
    first_order_applications,
    hole_assignments,
    variadic_applications,
)
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.program import AppFn, Apply, Const, Input, PrimRef
from arc_lab.program_search.substrate.types import (
    BOOL,
    COLOR,
    GRID,
    INT,
    ArrowType,
    TypeVar,
    free_type_vars,
    list_type,
)

# Argument candidates: one pooled program per base type.
_INT = Const(value=1, value_type=INT)
_COLOR = Const(value=5, value_type=COLOR)
_GRID = Input()
_CANDS = [(_INT, INT), (_COLOR, COLOR), (_GRID, GRID)]

_INC = Primitive(name="inc", param_types=(INT,), return_type=INT, impl=lambda x: x)
_MK = Primitive(name="mk", param_types=(INT, COLOR), return_type=GRID, impl=lambda a, b: a)
_A = TypeVar("a")
_ID = Primitive(name="id", param_types=(_A,), return_type=_A, impl=lambda x: x)
_EQ = Primitive(name="eq", param_types=(_A, _A), return_type=BOOL, impl=lambda a, b: a)

# A variadic primitive: v(color, grid, grid, ...) -> grid.
_V = Primitive(
    name="v", param_types=(COLOR,), return_type=GRID, variadic_param=GRID, impl=lambda c, *gs: gs[0]
)
_GB = Apply(primitive="dup", args=(_GRID,))  # a second, distinct GRID-typed program
_VCANDS = [(_COLOR, COLOR), (_GRID, GRID), (_GB, GRID)]


def test_monomorphic_unary_matches_only_its_type() -> None:
    result = list(first_order_applications(_INC, _CANDS, itertools.count()))
    assert result == [(Apply(primitive="inc", args=(_INT,)), INT)]


def test_monomorphic_binary_picks_each_param_by_type() -> None:
    result = list(first_order_applications(_MK, _CANDS, itertools.count()))
    assert result == [(Apply(primitive="mk", args=(_INT, _COLOR)), GRID)]


def test_polymorphic_identity_matches_every_candidate_with_its_type() -> None:
    result = list(first_order_applications(_ID, _CANDS, itertools.count()))
    assert result == [
        (Apply(primitive="id", args=(_INT,)), INT),
        (Apply(primitive="id", args=(_COLOR,)), COLOR),
        (Apply(primitive="id", args=(_GRID,)), GRID),
    ]


def test_shared_type_var_forces_both_args_to_one_type() -> None:
    # eq : (a, a) -> bool — a is bound by the first arg, so the second must match it.
    result = list(first_order_applications(_EQ, _CANDS, itertools.count()))
    assert result == [
        (Apply(primitive="eq", args=(_INT, _INT)), BOOL),
        (Apply(primitive="eq", args=(_COLOR, _COLOR)), BOOL),
        (Apply(primitive="eq", args=(_GRID, _GRID)), BOOL),
    ]


def test_no_candidate_of_the_required_type_yields_nothing() -> None:
    bool_only = [(Const(value=True, value_type=BOOL), BOOL)]
    assert list(first_order_applications(_INC, bool_only, itertools.count())) == []


def test_variadic_enumerates_each_trailing_arity_up_to_max() -> None:
    result = list(variadic_applications(_V, _VCANDS, itertools.count(), max_arity=2))
    # arity 1: v(color, g) for g in {_GRID, _GB}; arity 2: v(color, g, g') over the 2x2 grid pairs.
    assert (Apply(primitive="v", args=(_COLOR, _GRID)), GRID) in result
    assert (Apply(primitive="v", args=(_COLOR, _GRID, _GB)), GRID) in result
    assert len(result) == 2 + 4
    assert all(vtype == GRID for _, vtype in result)


def test_variadic_respects_max_arity() -> None:
    result = list(variadic_applications(_V, _VCANDS, itertools.count(), max_arity=1))
    assert len(result) == 2  # only arity 1
    assert (Apply(primitive="v", args=(_COLOR, _GRID)), GRID) in result
    assert (Apply(primitive="v", args=(_COLOR, _GRID, _GRID)), GRID) not in result  # arity 2 absent


def test_appfn_applies_a_function_value_to_arguments() -> None:
    candidates: list[TypedProgram] = [(PrimRef(name="inc"), ArrowType((INT,), INT)), (_INT, INT)]
    result = list(appfn_applications(candidates, itertools.count()))
    assert (AppFn(fn=PrimRef(name="inc"), args=(_INT,)), INT) in result


def test_appfn_partial_application_of_a_curried_value_yields_a_function() -> None:
    curried = ArrowType((INT,), ArrowType((INT,), INT))
    candidates: list[TypedProgram] = [(PrimRef(name="adder"), curried), (_INT, INT)]
    result = list(appfn_applications(candidates, itertools.count()))
    assert (AppFn(fn=PrimRef(name="adder"), args=(_INT,)), ArrowType((INT,), INT)) in result


def test_appfn_ignores_non_function_candidates() -> None:
    assert list(appfn_applications([(_INT, INT)], itertools.count())) == []


def test_applications_dispatches_by_variadicity() -> None:
    fixed = list(applications(_INC, _CANDS, itertools.count(), max_arity=5))
    assert fixed == [(Apply(primitive="inc", args=(_INT,)), INT)]  # fixed-arity ignores max_arity
    variadic = list(applications(_V, _VCANDS, itertools.count(), max_arity=1))
    assert (Apply(primitive="v", args=(_COLOR, _GRID)), GRID) in variadic


# -- hole_assignments (§5.3): pinning a function-hole's type vars from sibling arguments ---------

_LIST_INT = Const(value=0, value_type=list_type(INT))  # a List[int]-typed candidate (any program)
_B = TypeVar("b")
_ACC = TypeVar("acc")

# map : (a -> b, List[a]) -> List[b] — hole at index 0; siblings: index 1 (List[a]).
_MAP = Primitive(
    name="map",
    param_types=(ArrowType((_A,), _B), list_type(_A)),
    return_type=list_type(_B),
    impl=lambda f, xs: xs,
)

# fold : (acc -> a -> acc, acc, List[a]) -> acc — hole at index 0; siblings: index 1 (acc), index 2
# (List[a]) — two siblings jointly pinning both of the hole's binder types.
_FOLD = Primitive(
    name="fold",
    param_types=(ArrowType((_ACC,), ArrowType((_A,), _ACC)), _ACC, list_type(_A)),
    return_type=_ACC,
    impl=lambda f, seed, xs: seed,
)

# apply_const : (a -> b, GRID) -> GRID — hole at index 0, but its vars (a, b) appear in NO sibling.
_APPLY_CONST = Primitive(
    name="apply_const",
    param_types=(ArrowType((_A,), _B), GRID),
    return_type=GRID,
    impl=lambda f, g: g,
)


def test_hole_assignments_pins_the_hole_from_one_sibling() -> None:
    candidates: list[TypedProgram] = [(_LIST_INT, list_type(INT)), (_GRID, GRID)]
    result = list(hole_assignments(_MAP, 0, candidates, itertools.count()))
    matches = [(siblings, hole) for siblings, hole, _ in result if siblings == (_LIST_INT,)]
    assert matches, result
    _, hole_type = matches[0]
    assert isinstance(hole_type, ArrowType)
    assert hole_type.params == (INT,)  # `a` pinned to INT; `b` (the result) stays free


def test_hole_assignments_pins_both_binders_from_two_siblings() -> None:
    seed = Const(value=5, value_type=COLOR)
    candidates: list[TypedProgram] = [(seed, COLOR), (_LIST_INT, list_type(INT))]
    result = list(hole_assignments(_FOLD, 0, candidates, itertools.count()))
    matches = [
        (siblings, hole, ret) for siblings, hole, ret in result if siblings == (seed, _LIST_INT)
    ]
    assert matches, result
    _, hole_type, return_type = matches[0]
    assert isinstance(hole_type, ArrowType)
    assert hole_type.params == (COLOR,)
    assert isinstance(hole_type.result, ArrowType)
    assert hole_type.result.params == (INT,)
    assert hole_type.result.result == COLOR  # the accumulator's type, shared with the return type
    assert return_type == COLOR


def test_hole_assignments_leaves_an_unshared_variable_free() -> None:
    candidates: list[TypedProgram] = [(_GRID, GRID)]
    result = list(hole_assignments(_APPLY_CONST, 0, candidates, itertools.count()))
    # The only sibling is GRID-typed, sharing no variable with the hole `a -> b` — both stay free.
    assert len(result) == 1
    siblings, hole_type, return_type = result[0]
    assert siblings == (_GRID,)
    assert isinstance(hole_type, ArrowType)
    assert free_type_vars(hole_type)
    assert return_type == GRID  # apply_const's return type doesn't involve a/b at all
