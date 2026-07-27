"""``make_abstraction``'s return type when no signature is supplied.

``Program.result_type`` reports a primitive's DECLARED return type without unification, so a
template rooted at a POLYMORPHIC primitive reads as a free type variable: ``nth(split_h(g), 0)``
derives ``a``, not ``grid``, even though ``split_h : (Grid) -> List[Grid]`` pins it completely.

That is not a cosmetic mistyping. An abstraction whose result is an unpinned type variable is not
rejected by the enumerator -- it is silently SKIPPED (``unpinned_type_var_mode='reject'``, the
default in every preset), so it costs nothing, finds nothing and reports nothing. Discovered
2026-07-26 on the first ladder rung ever rooted at a list accessor
(``dae9d2b5-split-recolor``'s ``west``): the ladder linted 98 checks clean and its consumer's wake
searched the whole depth-2 space without ever composing the rung it had been gifted.
"""

from __future__ import annotations

from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Const, Param
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import GRID, INT, TypeVar

SPLIT_H = BASE_PRIMITIVES["split_h"]
NTH = BASE_PRIMITIVES["nth"]
HEAD = BASE_PRIMITIVES["head"]

FLOOR = Library(name="floor", primitives=(SPLIT_H, NTH, HEAD, MAP_COLOR, D4_LIBRARY.get("flip_h")))


def test_a_polymorphic_root_is_pinned_by_its_argument() -> None:
    # `nth : (List[a], Int) -> a` alone says `a`; `split_h : (Grid) -> List[Grid]` pins `a := grid`.
    template = Apply("nth", (Apply("split_h", (Param(0, GRID),)), Const(0, INT)))
    primitive = make_abstraction("west", template, FLOOR)
    assert primitive.return_type == GRID
    assert primitive.param_types == (GRID,)


def test_the_pin_survives_a_wrapper() -> None:
    # The unification has to thread through the enclosing call, not just read the root's argument.
    template = Apply("head", (Apply("split_h", (Param(0, GRID),)),))
    assert make_abstraction("west", template, FLOOR).return_type == GRID


def test_a_monomorphic_root_is_untouched() -> None:
    # The refinement must be exactly that: every abstraction in the batch before this bug was
    # rooted monomorphically, and their types (hence library serialisation, hence run identity)
    # must not move. `flip_h` already says `grid` without any unification.
    template = Apply("flip_h", (Param(0, GRID),))
    assert make_abstraction("flipped", template, FLOOR).return_type == GRID


def test_an_unpinnable_root_still_reports_a_variable() -> None:
    # Inference REFINES; it does not invent. With nothing to pin `a` -- the list itself is the
    # parameter -- the honest answer is still a type variable, and the caller must pass a signature.
    template = Apply("head", (Param(0, GRID),))  # a Grid where a list is wanted: nothing pins `a`
    assert isinstance(make_abstraction("first", template, FLOOR).return_type, TypeVar)


def test_a_declared_signature_still_wins() -> None:
    # The `.ladder` path states its signature and elaboration verifies it; inference is the floor
    # for callers that have none (the learn engines mint from search results), never an override.
    template = Apply("nth", (Apply("split_h", (Param(0, GRID),)), Const(0, INT)))
    primitive = make_abstraction("west", template, FLOOR, signature=((GRID,), GRID))
    assert primitive.return_type == GRID
