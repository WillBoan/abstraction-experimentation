"""The curated equational theory of the base primitives — reduction rules for the rewrite lint.

Every floor carries an equational theory (the D4 group law, distribution of flips over layout
combinators), and a ladder must be designed modulo it: a template that a few known equations
rewrite to something shallow is a skip path the depth sandwich cannot see. This registry states
the theory *explicitly* — each :class:`Equation` is oriented left-to-right as a terminating
reduction — and the D4 composition table is DERIVED at import time from the primitives' own
implementations (applied to a fixed asymmetric marker grid), so it cannot drift from
``substrate/primitives/geometry.py``; a non-closed or ambiguous table raises at import.

Deliberately excluded from v1, with rationale:

- **map/filter/fold fusion** — the substrate has no ``compose`` primitive, so ``map f . map g ==
  map (f . g)`` is not expressible as a first-order rewrite and never depth-reducing here; no
  batch floor is higher-order yet.
- **concat associativity** — needed by no known firing; adding it costs normalization steps on
  every layout ladder.

The **concat interchange** law carries a shape side-condition (its right side can be undefined
where its left is defined), so it is sound for *normal-form comparison* only when every reported
witness is behaviorally confirmed afterwards — which is exactly what the rewrite lint does.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Library, Value
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Param, Program
from arc_lab.program_search.substrate.types import GRID

_A = Param(0, GRID)
_B = Param(1, GRID)
_C = Param(2, GRID)
_D = Param(3, GRID)


@dataclass(frozen=True, slots=True)
class Equation:
    """One oriented reduction: ``lhs`` (a pattern over contiguous ``Param``s) rewrites to ``rhs``.

    ``rhs`` may use only ``lhs``'s params. Orientation is part of the theory: each rule must be
    part of a terminating system (involutions shrink; flip-distribution pushes flips toward the
    leaves; the interchange sorts ``concat_v`` above ``concat_h``).
    """

    name: str
    lhs: Program
    rhs: Program


def _unary(name: str, arg: Program) -> Program:
    return Apply(name, (arg,))


BASE_EQUATIONS: Final[tuple[Equation, ...]] = (
    # Involutions (also derivable from the D4 pass; kept as explicit fast rules).
    Equation("flip_h-involution", _unary("flip_h", _unary("flip_h", _A)), _A),
    Equation("flip_v-involution", _unary("flip_v", _unary("flip_v", _A)), _A),
    # Flips distribute over the layout combinators, pushed toward the leaves.
    Equation(
        "flip_h-over-concat_h",
        _unary("flip_h", Apply("concat_h", (_A, _B))),
        Apply("concat_h", (_unary("flip_h", _B), _unary("flip_h", _A))),
    ),
    Equation(
        "flip_h-over-concat_v",
        _unary("flip_h", Apply("concat_v", (_A, _B))),
        Apply("concat_v", (_unary("flip_h", _A), _unary("flip_h", _B))),
    ),
    Equation(
        "flip_v-over-concat_v",
        _unary("flip_v", Apply("concat_v", (_A, _B))),
        Apply("concat_v", (_unary("flip_v", _B), _unary("flip_v", _A))),
    ),
    Equation(
        "flip_v-over-concat_h",
        _unary("flip_v", Apply("concat_h", (_A, _B))),
        Apply("concat_h", (_unary("flip_v", _A), _unary("flip_v", _B))),
    ),
    # Block interchange: sorts concat_v above concat_h. SHAPE SIDE-CONDITION -- see module doc.
    Equation(
        "concat-interchange",
        Apply("concat_h", (Apply("concat_v", (_A, _B)), Apply("concat_v", (_C, _D)))),
        Apply("concat_v", (Apply("concat_h", (_A, _C)), Apply("concat_h", (_B, _D)))),
    ),
)

#: The eight D4 primitive names, in the substrate's own preference order.
D4_NAMES: Final[tuple[str, ...]] = tuple(p.name for p in D4_LIBRARY.primitives)

#: A fixed asymmetric non-square marker: all eight D4 transforms of it are pairwise distinct,
#: which is what makes the composition table derivable by identification.
_MARKER: Final[Grid] = Grid.from_list([[1, 2, 3], [4, 5, 6]])


def _derive_d4_table() -> dict[tuple[str, str], str]:
    imaged: dict[str, Grid] = {}
    for name in D4_NAMES:
        image = D4_LIBRARY.get(name).impl(_MARKER)
        assert isinstance(image, Grid)
        imaged[name] = image
    by_image = {grid: name for name, grid in imaged.items()}
    if len(by_image) != len(D4_NAMES):
        raise RuntimeError("D4 marker grid does not separate the eight transforms")
    table: dict[tuple[str, str], str] = {}
    for outer in D4_NAMES:
        for inner in D4_NAMES:
            composed = D4_LIBRARY.get(outer).impl(imaged[inner])
            element = by_image.get(composed) if isinstance(composed, Grid) else None
            if element is None:
                raise RuntimeError(f"D4 not closed under composition at ({outer}, {inner})")
            table[(outer, inner)] = element
    return table


_D4_TABLE: Final[dict[tuple[str, str], str]] = _derive_d4_table()


def d4_compose(outer: str, inner: str) -> str:
    """The single D4 element equal to ``outer . inner`` (group-table lookup)."""
    return _D4_TABLE[(outer, inner)]


def canonical_d4_word(element: str) -> tuple[str, ...]:
    """The canonical spelling of a D4 element as a primitive chain.

    Every element IS one primitive in this substrate, so the word is one name — or empty for
    ``identity`` (an identity chain collapses to its operand outright).
    """
    if element not in _D4_TABLE.values() and element not in D4_NAMES:
        raise KeyError(element)
    return () if element == "identity" else (element,)


def verify_equation(
    equation: Equation, library: Library, bindings: Sequence[tuple[Value, ...]]
) -> bool:
    """Behaviorally verify the law: on every binding where BOTH sides evaluate, values agree —
    and at least one binding must exercise both sides (no vacuous pass).

    Identity binding, deliberately: ``Param(i)`` takes ``binding[i]`` positionally. The
    argument-permutation tolerance of ``analysis/behavioral.py``'s checker would accept a law
    with swapped concat arguments, which is exactly the kind of drift this must catch.
    """
    exercised = 0
    for binding in bindings:
        left = _try_evaluate(equation.lhs, library, binding)
        right = _try_evaluate(equation.rhs, library, binding)
        if left is _UNDEFINED or right is _UNDEFINED:
            continue
        exercised += 1
        if left != right:
            return False
    return exercised > 0


_UNDEFINED: Final[object] = object()

#: Closed templates never consult the outer grid; a fixed dummy satisfies ``evaluate``.
_DUMMY_GRID: Final[Grid] = Grid.from_list([[0]])


def _try_evaluate(template: Program, library: Library, binding: tuple[Value, ...]) -> object:
    try:
        return template.evaluate(_DUMMY_GRID, library, tuple(binding))
    except Exception:
        return _UNDEFINED
