"""Phase E: the general enumerator consumes higher-order (function-typed) abstractions.

`Enumerate(higher_order=True)` fills a function-typed argument from a pool of library primitives
referenced first-class (PrimRefs), pruned by arrow-type unification. The test object is
``twice(grid, fn) = fn(fn(grid))`` — it applies its function argument *twice*, which first-order
composition cannot do at depth 1. So with the library ``{rot90, twice}`` and target ``rot180``, only
the higher-order search reaches it; the first-order default is byte-identical to before (it can't fill
the function-typed hole, so `twice` is skipped — exactly as `build_grid`'s FN param is skipped today).
"""

from __future__ import annotations

from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import AppFn, Param, Program
from arc_lab.solvers.dsl.substrate.types import GRID, ArrowType

from arc_lab.core.task import Task

_G = GRID
_GG = ArrowType((_G,), _G)  # GRID -> GRID

# twice(grid=#0, fn=#1) = fn(fn(grid))  — #1 is a GRID -> GRID function-typed hole, applied twice.
_TWICE: Program = AppFn(Param(1, _GG), (AppFn(Param(1, _GG), (Param(0, _G),)),))

# thrice(fn=#0, grid=#1) = fn(fn(fn(grid))) — applies its GRID -> GRID function argument three times.
_THRICE: Program = AppFn(
    Param(0, _GG), (AppFn(Param(0, _GG), (AppFn(Param(0, _GG), (Param(1, _G),)),)),)
)


def _rot180_task() -> Task:
    grid = [[1, 2], [3, 4]]
    return Task.from_dict(
        "rot180",
        {"train": [{"input": grid, "output": [[4, 3], [2, 1]]}], "test": [{"input": grid}]},
    )


def _hof_library() -> Library:
    rot90 = D4_LIBRARY.get("rot90")  # GRID -> GRID
    twice = make_abstraction("twice", _TWICE, D4_LIBRARY)  # (GRID, GRID -> GRID) -> GRID
    return Library(name="hof-test", primitives=(rot90, twice))


def test_first_order_enumerate_cannot_fill_the_function_typed_hole() -> None:
    # No function pool -> twice is skipped (its arrow param is unfillable) -> rot180 out of reach at
    # depth 1 from {input, rot90(input)}. This is the existing first-order behavior, unchanged.
    assert Enumerate(max_depth=1).find(_rot180_task(), _hof_library()).programs == ()


def test_higher_order_enumerate_consumes_the_function_typed_abstraction() -> None:
    # twice(input, &rot90) = rot90(rot90(input)) = rot180(input) — reached at depth 1 only because the
    # perceiver is applied twice *inside* the abstraction, which first-order composition cannot.
    result = Enumerate(max_depth=1, higher_order=True).find(_rot180_task(), _hof_library())
    assert len(result.programs) == 1
    solution = str(result.programs[0])
    assert "twice" in solution and "&rot90" in solution  # the HO abstraction, filled with a PrimRef


def test_unification_prunes_ill_typed_function_candidates() -> None:
    # width : GRID -> INT must NOT be offered for twice's GRID -> GRID hole. With only width available
    # (no GRID -> GRID primitive), the higher-order search finds nothing — the arrow types don't unify.
    twice = make_abstraction("twice", _TWICE, D4_LIBRARY)
    library = Library(name="mistyped", primitives=(BUILD_LIBRARY.get("width"), twice))
    assert Enumerate(max_depth=1, higher_order=True).find(_rot180_task(), library).programs == ()


# -- Phase G: Lam-synthesis (synthesize *new* function values, not just reference library ones) --------


def _thrice_library() -> Library:
    thrice = make_abstraction("thrice", _THRICE, D4_LIBRARY)  # (GRID -> GRID, GRID) -> GRID
    return Library(name="rot90+thrice", primitives=(D4_LIBRARY.get("rot90"), thrice))


def test_lam_synthesis_supplies_a_function_no_primitive_provides() -> None:
    # Over <rot90>, reaching rot180 via `thrice` needs the *rot180 function* (rot180^3 = rot180) — and
    # rot180 is not a library primitive, so only a *synthesized* `lam(rot90(rot90($0)))` can fill the
    # hole. first-order (rot180 needs depth 2) and PrimRef-only (thrice(&rot90,input)=rot270) both fail.
    library, task = _thrice_library(), _rot180_task()
    assert Enumerate(max_depth=1).find(task, library).programs == ()  # first-order
    assert (
        Enumerate(max_depth=1, higher_order=True).find(task, library).programs == ()
    )  # PrimRef-only
    solved = Enumerate(max_depth=1, higher_order=True, synthesize_functions=True).find(
        task, library
    )
    assert len(solved.programs) == 1
    program = str(solved.programs[0])
    assert "thrice" in program and "lam" in program  # consumed a *synthesized* composed function


def test_function_pool_dedups_synthesized_functions_by_behavior() -> None:
    # lam(rot90($0)) behaves exactly like &rot90, so the pool keeps one candidate per behavior (the
    # smaller PrimRef wins); the rot180 composite, which no primitive provides, survives.
    engine = Enumerate(higher_order=True, synthesize_functions=True)
    gg = {str(ref) for ref, arrow in engine._function_pool(_thrice_library()) if arrow == _GG}
    assert "&rot90" in gg  # the primitive wins the rot90 behavior
    assert "lam(rot90($0))" not in gg  # the behaviorally-redundant lambda is deduped away
    assert any(r.startswith("lam(rot90(rot90(") for r in gg)  # the rot180 composite survives
