"""Phase D: the substrate can represent, evaluate, serialize, and mint a higher-order abstraction.

The test object is ``mirror_dim(grid, coord, dim) = (dim(grid) - coord) - 1`` — a closed template whose
third hole ``dim`` is *function-typed* (``GRID -> INT``, e.g. ``width``/``height``), applied to the grid
via :class:`AppFn`. Consuming such an abstraction in *search* is Phase E; here we only show the substrate
holds it: it evaluates, round-trips the canonical (JSON) serializer, serializes to a Stitch s-expr, and
mints with the arrow recorded (not the opaque ``FN`` tag). Parsing a higher-order s-expr *back* (Stitch's
curried metavars) is Phase F, so `from_sexpr` round-tripping is not asserted here.
"""

from __future__ import annotations

from arc_lab.solvers.dsl.learn.stitch_shim import from_sexpr, to_sexpr
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import (
    AppFn,
    Apply,
    Const,
    Input,
    Param,
    PrimRef,
    Program,
)
from arc_lab.solvers.dsl.substrate.types import GRID, INT, ArrowType

from arc_lab.core.grid import Grid

_G, _I = GRID, INT
_DIM = ArrowType((_G,), _I)  # a GRID -> INT perceiver

# mirror_dim(grid=#0, coord=#1, dim=#2) = (dim(grid) - coord) - 1  — #2 is a function-typed hole.
_TEMPLATE: Program = Apply(
    "sub",
    (
        Apply("sub", (AppFn(Param(2, _DIM), (Param(0, _G),)), Param(1, _I))),
        Const(1, _I),
    ),
)


def test_make_abstraction_records_the_arrow_typed_hole() -> None:
    prim = make_abstraction("mirror_dim", _TEMPLATE, BUILD_LIBRARY)
    # The function-typed hole is recorded as its arrow (GRID -> INT), not the opaque FN tag.
    assert prim.param_types == (_G, _I, _DIM)
    assert prim.return_type == _I


def test_higher_order_abstraction_evaluates_over_a_battery() -> None:
    prim = make_abstraction("mirror_dim", _TEMPLATE, BUILD_LIBRARY)
    library = BUILD_LIBRARY.extended(name="build+mirror_dim", extra=(prim,))
    # Apply it with `width` passed first-class (a PrimRef) into the function-typed hole.
    program: Program = Apply("mirror_dim", (Input(), Const(0, _I), PrimRef("width")))
    for width in (2, 3, 5):
        grid = Grid.from_list([list(range(width))])  # 1 x width
        # mirror_dim(grid, 0, width) = (width(grid) - 0) - 1 = width - 1
        assert program.evaluate(grid, library) == width - 1


def test_higher_order_program_round_trips_the_json_serializer() -> None:
    # The arrow-typed Param, the AppFn, and the PrimRef all survive to_dict -> from_dict.
    assert Program.from_dict(_TEMPLATE.to_dict()) == _TEMPLATE
    program: Program = Apply("mirror_dim", (Input(), Const(0, _I), PrimRef("width")))
    assert Program.from_dict(program.to_dict()) == program
    # The arrow serializes to a tagged dict (base types stay bare strings — cf. test_types).
    assert Param(2, _DIM).to_dict()["value_type"] == {"arrow": ["grid"], "result": "int"}


def test_higher_order_serializes_to_a_stitch_sexpr() -> None:
    assert to_sexpr(PrimRef("width")) == "width"  # a primitive as a value is its bare symbol
    assert to_sexpr(AppFn(Param(2, _DIM), (Param(0, _G),))) == "(x2 x0)"  # apply a hole to an arg
    assert to_sexpr(_TEMPLATE) == "(sub (sub (x2 x0) x1) 1)"


def test_from_sexpr_infers_a_higher_order_abstraction() -> None:
    # (#0 (#0 input)) — a metavar applied to its own result on `input`. Inference must resolve #0 to
    # GRID -> GRID (domain from `input`, codomain unified across both uses), yielding a `twice`
    # template (fn: GRID -> GRID, grid: GRID) -> GRID whose body is fn(fn(grid)).
    prim = make_abstraction("twice", from_sexpr("(#0 (#0 input))", D4_LIBRARY), D4_LIBRARY)
    assert ArrowType((_G,), _G) in prim.param_types  # the hole recovered as an arrow, not opaque FN
    assert _G in prim.param_types  # and the lifted grid parameter
    # Behaviorally fn(fn(grid)): twice(&rot90, input) applies rot90 twice == rot180.
    library = D4_LIBRARY.extended(name="d4+twice", extra=(prim,))
    grid = Grid.from_list([[1, 2], [3, 4]])
    applied: Program = Apply("twice", (PrimRef("rot90"), Input()))
    assert applied.evaluate(grid, library) == Grid.from_list([[4, 3], [2, 1]])  # rot180
