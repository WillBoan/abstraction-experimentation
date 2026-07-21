"""The curated equation registry: every law behaviorally verified, D4 table derived not stated."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.program_search.analysis.equations import (
    BASE_EQUATIONS,
    D4_NAMES,
    Equation,
    canonical_d4_word,
    d4_compose,
    verify_equation,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.layout import CONCAT_H, CONCAT_V
from arc_lab.program_search.substrate.program import Apply, Param
from arc_lab.program_search.substrate.types import GRID

_LIB = Library(name="d4+concat", primitives=(*D4_LIBRARY.primitives, CONCAT_H, CONCAT_V))

#: Four same-shape, asymmetric, pairwise-distinct probe grids — aligned for every combinator, so
#: each law's both sides evaluate; asymmetry separates the D4 orbit.
_PROBES = (
    (
        Grid.from_list([[1, 2, 3], [4, 5, 6]]),
        Grid.from_list([[7, 8, 9], [1, 3, 5]]),
        Grid.from_list([[2, 4, 6], [8, 1, 2]]),
        Grid.from_list([[9, 7, 5], [3, 1, 8]]),
    ),
)


def test_every_curated_equation_holds_behaviorally() -> None:
    for equation in BASE_EQUATIONS:
        assert verify_equation(equation, _LIB, _PROBES), equation.name


def test_identity_binding_rejects_a_swapped_argument_law() -> None:
    # flip_h distributes over concat_h by SWAPPING the halves; the unswapped spelling is wrong,
    # and the argument-permutation tolerance of the behavioral checker would have accepted it --
    # which is exactly why verify_equation binds positionally.
    wrong = Equation(
        "flip_h-over-concat_h-unswapped",
        Apply("flip_h", (Apply("concat_h", (Param(0, GRID), Param(1, GRID))),)),
        Apply("concat_h", (Apply("flip_h", (Param(0, GRID),)), Apply("flip_h", (Param(1, GRID),)))),
    )
    assert not verify_equation(wrong, _LIB, _PROBES)


def test_a_law_never_exercised_does_not_verify() -> None:
    # The interchange law's shape side-condition: LHS defined, RHS not (1+2 vs 2+1 row splits).
    # A binding set that never exercises both sides is a vacuous non-verification, not a pass.
    misaligned = (
        (
            Grid.from_list([[1, 2]]),
            Grid.from_list([[3, 4], [5, 6]]),
            Grid.from_list([[7, 8], [9, 1]]),
            Grid.from_list([[2, 3]]),
        ),
    )
    interchange = next(eq for eq in BASE_EQUATIONS if eq.name == "concat-interchange")
    assert not verify_equation(interchange, _LIB, misaligned)


def test_the_derived_d4_table_matches_the_group() -> None:
    assert d4_compose("flip_h", "flip_v") == "rot180"
    assert d4_compose("flip_v", "flip_h") == "rot180"
    assert d4_compose("rot90", "rot90") == "rot180"
    assert d4_compose("transpose", "transpose") == "identity"
    assert d4_compose("identity", "flip_h") == "flip_h"
    # Closed: every composition is one of the eight (the import-time derivation already raised
    # otherwise; this keeps the property stated where a reader looks for it).
    for outer in D4_NAMES:
        for inner in D4_NAMES:
            assert d4_compose(outer, inner) in D4_NAMES


def test_canonical_words_are_single_primitives_or_empty() -> None:
    assert canonical_d4_word("identity") == ()
    assert canonical_d4_word("rot90") == ("rot90",)
