"""Codec completeness (ARCHITECTURE.md section 11.6): every node kind must encode + decode.

The register's invariant, enforced by test rather than memory: a `Program` node kind the
s-expression codec cannot carry means sleep silently cannot compress programs containing it.
The coverage assertions below are keyed by node kind and checked against
``Program.__subclasses__()``, so adding a node kind fails this file until BOTH directions are
extended (and `to_sexpr`/`from_sexpr` themselves fail loudly on an entry with no codec rule).

Two deliberate asymmetries, asserted explicitly rather than papered over:

* ``Param`` encodes as the closed terminal ``x{j}`` (Stitch *input* must be closed); the decode
  side is Stitch's *output* metavar ``#j``.
* ``Input`` never appears in decoded output: `from_sexpr` closes templates, lifting a free
  ``input`` to the shared grid ``Param``.
"""

from __future__ import annotations

from arc_lab.program_search.learn.stitch_shim import from_sexpr, to_sexpr
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    Const,
    If,
    Input,
    Lam,
    Param,
    PrimRef,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import BOOL, COLOR, GRID, INT, ArrowType

_G2G = ArrowType((GRID,), GRID)

#: The ENCODE table: one exemplar per node kind and its exact s-expression.
_ENCODE: dict[type[Program], tuple[Program, str]] = {
    Input: (Input(), "input"),
    Const: (Const(3, COLOR), "3:color"),  # non-INT scalar: the typed-literal notation
    Param: (Param(0, GRID), "x0"),  # closed Stitch-input terminal; the decode side is `#0`
    Apply: (Apply("rot90", (Input(),)), "(rot90 input)"),
    If: (If(cond=Const(True, BOOL), then=Const(1, INT), orelse=Const(2, INT)), "(if true 1 2)"),
    Var: (Var(0, GRID), "$0"),
    Lam: (Lam(param_type=GRID, body=Var(0, GRID)), "(lam $0)"),
    AppFn: (AppFn(Param(0, _G2G), (Input(),)), "(x0 input)"),  # head Param is `x0` too (closed)
    PrimRef: (PrimRef("rot90"), "rot90"),
}

#: The DECODE table: an s-expression whose decoded tree must CONTAIN the node kind.
#: ``Input`` is absent by design (lifted to Param; asserted separately below).
_DECODE: dict[type[Program], str] = {
    Const: "3:color",
    Param: "(rot90 #0)",
    Apply: "(rot90 input)",
    If: "(if true 1 2)",
    Var: "(#0 (lam $0))",
    Lam: "(#0 (lam $0))",
    AppFn: "(#0 input)",
    PrimRef: "(#0 rot90)",
}


def _node_kinds() -> set[type[Program]]:
    # `@dataclass(slots=True)` re-creates each class, leaving the pre-dataclass original in
    # `__subclasses__` until GC — canonicalize through the defining module's namespace.
    import arc_lab.program_search.substrate.program as program_module

    kinds: set[type[Program]] = set()
    for cls in Program.__subclasses__():
        canonical = getattr(program_module, cls.__name__, cls)
        assert isinstance(canonical, type) and issubclass(canonical, Program)
        kinds.add(canonical)
    return kinds


def test_encode_covers_every_node_kind() -> None:
    assert set(_ENCODE) == _node_kinds(), "new node kind: add it to _ENCODE (and the codec)"
    for kind, (program, sexpr) in _ENCODE.items():
        assert to_sexpr(program) == sexpr, f"{kind.__name__} encoded unexpectedly"


def test_decode_covers_every_producible_node_kind() -> None:
    assert set(_DECODE) == _node_kinds() - {Input}, (
        "new node kind: add it to _DECODE (and the codec)"
    )
    for kind, sexpr in _DECODE.items():
        decoded = from_sexpr(sexpr, D4_LIBRARY)
        assert any(isinstance(node, kind) for node in decoded.walk()), (
            f"{kind.__name__} absent from decode of {sexpr!r}"
        )


def test_free_input_decodes_to_the_lifted_param() -> None:
    assert from_sexpr("input", D4_LIBRARY) == Param(0, GRID)


def test_dict_serde_round_trips_every_node_kind() -> None:
    # The JSON codec (run records, library serde) carries the same completeness invariant.
    for kind, (program, _) in _ENCODE.items():
        assert Program.from_dict(program.to_dict()) == program, f"{kind.__name__} dict round-trip"


def test_typed_literal_round_trips_exactly() -> None:
    assert to_sexpr(Const(3, COLOR)) == "3:color"
    assert from_sexpr("3:color", D4_LIBRARY) == Const(3, COLOR)


def test_typed_literal_survives_an_untyped_context() -> None:
    # The formerly lossy edge: an arg of a metavar-headed application has no expected type.
    decoded = from_sexpr("(#0 3:color)", D4_LIBRARY)
    consts = [node for node in decoded.walk() if isinstance(node, Const)]
    assert consts == [Const(3, COLOR)]


def test_bare_int_is_int_in_an_untyped_context() -> None:
    decoded = from_sexpr("(#0 3)", D4_LIBRARY)
    consts = [node for node in decoded.walk() if isinstance(node, Const)]
    assert consts == [Const(3, INT)]
