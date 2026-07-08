"""Phase E: the general enumerator consumes higher-order (function-typed) abstractions.

`Enumerate(higher_order=True)` fills a function-typed argument from a pool of library primitives
referenced first-class (PrimRefs), pruned by arrow-type unification. The test object is
``twice(grid, fn) = fn(fn(grid))`` — it applies its function argument *twice*, which first-order
composition cannot do at depth 1. So with the library ``{rot90, twice}`` and target ``rot180``, only
the higher-order search reaches it; the first-order default is byte-identical to before (it can't fill
the function-typed hole, so `twice` is skipped — exactly as `build_grid`'s FN param is skipped today).
"""

from __future__ import annotations

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import AppFn, Param, Program
from arc_lab.solvers.dsl.substrate.types import ArrowType, ValueType

_G = ValueType.GRID
_GG = ArrowType((_G,), _G)  # GRID -> GRID

# twice(grid=#0, fn=#1) = fn(fn(grid))  — #1 is a GRID -> GRID function-typed hole, applied twice.
_TWICE: Program = AppFn(Param(1, _GG), (AppFn(Param(1, _GG), (Param(0, _G),)),))


def _rot180_task() -> Task:
    grid = [[1, 2], [3, 4]]
    return Task.from_dict(
        "rot180", {"train": [{"input": grid, "output": [[4, 3], [2, 1]]}], "test": [{"input": grid}]}
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
