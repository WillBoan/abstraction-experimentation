"""The sole boundary to Stitch (`stitch_core`): (de)serialize programs, run compression.

Stitch is a mature, De Bruijn-native, deterministic library-learning engine. This module is the
*only* place it is imported (lazily), so the stub-less compiled wheel's ``Any`` values are contained
here and the rest of the strict-typed codebase sees only typed `Program`/`Primitive` values.

Two directions:

* :func:`to_sexpr` — a `Program` to Stitch's s-expression (``$i`` De Bruijn vars, ``#j`` abstraction
  vars, ``(lam …)``, ``(f a b)``). The substrate was built Stitch-compatible, so ``Var``/``Param``/``Lam``
  already print in Stitch's notation; only ``Apply`` needs prefix form.
* :func:`from_sexpr` — a Stitch s-expression back to a `Program`, **re-inferring types** (Stitch is
  untyped) from the library's primitive signatures, then :func:`_close_template`-ing so a free ``input``
  becomes a shared grid ``Param`` (Stitch leaves it free; our abstractions are closed templates).

:func:`stitch_candidates` composes the two around :func:`_compress` to propose candidate abstraction
templates over the current library — the invention half; governance (which to adopt) stays with the
in-house :class:`AbstractionSelector`, so the cost model remains fully ours.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from arc_lab.solvers.dsl.learn.antiunify import AbstractionProposer, _close_template, _is_useful
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import (
    AppFn,
    Apply,
    Const,
    Input,
    Lam,
    Param,
    PrimRef,
    Program,
    Var,
)
from arc_lab.solvers.dsl.substrate.types import Type, ValueType

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_INT = ValueType.INT

#: A parsed s-expression: an atom (leaf token) or a list (application / binder).
SExpr: TypeAlias = "str | list[SExpr]"


# --------------------------------------------------------------------------- #
# Program -> Stitch s-expression                                              #
# --------------------------------------------------------------------------- #
def to_sexpr(program: Program) -> str:
    """Serialize a `Program` to a Stitch *input* s-expression string.

    A `Param` (``#j``) is encoded as a distinct **terminal** ``x{j}``, not ``#j``: Stitch input must
    be a closed term, and ``#j`` metavars are only legal in the abstraction *bodies Stitch emits*
    (which :func:`from_sexpr` decodes back to ``Param``). Encoding a definition's params as opaque
    terminals is exactly what lets the library's own definitions be fed to Stitch for refactoring.
    """
    if isinstance(program, Input):
        return "input"
    if isinstance(program, Const):
        return str(program.value)
    if isinstance(program, Var):
        return f"${program.index}"
    if isinstance(program, Param):
        return f"x{program.index}"  # a closed terminal (see docstring); `#j` is Stitch-output only
    if isinstance(program, Lam):
        return f"(lam {to_sexpr(program.body)})"
    if isinstance(program, PrimRef):
        return program.name  # a primitive as a value is its bare symbol (higher-order head)
    if isinstance(program, AppFn):
        return f"({to_sexpr(program.fn)} {' '.join(to_sexpr(a) for a in program.args)})"
    if isinstance(program, Apply):
        if not program.args:
            return program.primitive
        return f"({program.primitive} {' '.join(to_sexpr(a) for a in program.args)})"
    raise TypeError(f"cannot serialize node: {type(program).__name__}")


# --------------------------------------------------------------------------- #
# Stitch s-expression -> Program (with type re-inference)                      #
# --------------------------------------------------------------------------- #
def from_sexpr(sexpr: str, library: Library) -> Program:
    """Parse a Stitch s-expression into a closed `Program` template over ``library``.

    Types are re-inferred top-down from primitive signatures (Stitch is untyped); a free ``input``
    is lifted to a shared grid ``Param`` and all params are renumbered contiguously
    (:func:`_close_template`), so the result is a valid, minimal-arity abstraction template.
    """
    tokens = _tokenize(sexpr)
    tree, rest = _parse(tokens, 0)
    if rest != len(tokens):
        raise ValueError(f"trailing tokens in s-expression: {sexpr!r}")
    return _close_template(_to_program(tree, library, None))


def _tokenize(sexpr: str) -> list[str]:
    return sexpr.replace("(", " ( ").replace(")", " ) ").split()


def _parse(tokens: Sequence[str], i: int) -> tuple[SExpr, int]:
    """Recursive-descent parse from ``tokens[i]``; returns (node, next-index)."""
    if i >= len(tokens):
        raise ValueError("unexpected end of s-expression")
    tok = tokens[i]
    if tok == "(":
        items: list[SExpr] = []
        i += 1
        while i < len(tokens) and tokens[i] != ")":
            node, i = _parse(tokens, i)
            items.append(node)
        if i >= len(tokens):
            raise ValueError("unbalanced '(' in s-expression")
        return items, i + 1  # skip ')'
    if tok == ")":
        raise ValueError("unexpected ')' in s-expression")
    return tok, i + 1


def _to_program(node: SExpr, library: Library, expected: Type | None) -> Program:
    """Convert a parsed node to a `Program`, threading the expected type down to the leaves."""
    if isinstance(node, str):
        return _atom_to_program(node, library, expected)
    if not node:
        raise ValueError("empty application in s-expression")
    head, args = node[0], node[1:]
    if head == "lam":
        if len(args) != 1:
            raise ValueError(f"lam takes one body, got {len(args)}")
        return Lam(_to_program(args[0], library, None))
    if not isinstance(head, str):
        raise ValueError(f"application head must be a symbol, got {head!r}")
    prim = library.get(head)  # raises KeyError if it references an unknown (e.g. nested fn_k)
    arg_types = _arg_types(prim.param_types, prim.variadic_param, len(args))
    return Apply(
        head, tuple(_to_program(a, library, t) for a, t in zip(args, arg_types, strict=True))
    )


def _atom_to_program(atom: str, library: Library, expected: Type | None) -> Program:
    if atom == "input":
        return Input()
    if atom.startswith("#"):
        return Param(int(atom[1:]), expected or _INT)
    if atom.startswith("$"):
        return Var(int(atom[1:]), expected or _INT)
    if _is_int_literal(atom):  # a literal is always base-typed
        return Const(int(atom), expected if isinstance(expected, ValueType) else _INT)
    if atom in library:  # a nullary primitive used as a value
        return Apply(atom, ())
    raise ValueError(f"unknown atom {atom!r} (not input/#j/$i/literal/primitive)")


def _arg_types(
    param_types: tuple[Type, ...], variadic: Type | None, n: int
) -> tuple[Type | None, ...]:
    """Expected type per argument position, extending a variadic tail with its element type."""
    return tuple(param_types[i] if i < len(param_types) else variadic for i in range(n))


def _is_int_literal(atom: str) -> bool:
    return atom.lstrip("-").isdigit()


# --------------------------------------------------------------------------- #
# Stitch compression (the stitch_core boundary)                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class StitchAbstraction:
    """A Stitch-returned abstraction: its name, s-expression body, and arity."""

    name: str
    body: str
    arity: int


def _compress(
    sexprs: list[str],
    *,
    iterations: int,
    max_arity: int,
    first_order: bool,
    threads: int,
) -> list[StitchAbstraction]:
    """Run ``stitch_core.compress`` and return its abstractions as typed values.

    The lazy import + the ``Any``-to-typed extraction are confined here so ``mypy --strict`` sees
    only :class:`StitchAbstraction` beyond this boundary. ``first_order`` disables curried metavars
    (higher-order holes); ``threads`` is chosen by the caller's determinism check.
    """
    import stitch_core  # lazy: optional dependency, contained to this module

    result = stitch_core.compress(
        sexprs,
        iterations=iterations,
        max_arity=max_arity,
        threads=threads,
        no_curried_metavars=first_order,
        silent=True,
    )
    raw = getattr(result, "abstractions", None)
    if raw is None:
        raw = result.json["abstractions"]
    out: list[StitchAbstraction] = []
    for a in raw:
        name = a["name"] if isinstance(a, dict) else a.name
        body = a["body"] if isinstance(a, dict) else a.body
        arity = a["arity"] if isinstance(a, dict) else a.arity
        out.append(StitchAbstraction(name=str(name), body=str(body), arity=int(arity)))
    return out


def stitch_candidates(
    programs: list[Program],
    library: Library,
    *,
    first_order: bool = True,
    iterations: int = 5,
    max_arity: int = 3,
    threads: int = 1,
) -> list[Program]:
    """Propose candidate abstraction templates by compressing ``programs`` with Stitch.

    Serialize, compress, deserialize each abstraction body back to a closed template over ``library``,
    and keep the useful ones. Abstractions that reference *other* Stitch abstractions (Stitch's own
    hierarchy, ``fn_k``) are skipped for now — a known first-order limitation, logged never silent:
    resolving Stitch's hierarchy, and consuming the higher-order abstractions it builds atop it, travels
    with the higher-order substrate (the interesting hierarchies are themselves higher-order). Governance
    (which candidate earns a name) is the caller's selector.
    """
    sexprs = [to_sexpr(p) for p in programs]
    templates: list[Program] = []
    for abstraction in _compress(
        sexprs, iterations=iterations, max_arity=max_arity, first_order=first_order, threads=threads
    ):
        try:
            template = from_sexpr(abstraction.body, library)
        except (KeyError, ValueError) as exc:
            logger.debug(
                "skipping Stitch abstraction %s (%s): %s", abstraction.name, exc, abstraction.body
            )
            continue
        if _is_useful(template):
            templates.append(template)
    return templates


class StitchProposer(AbstractionProposer):
    """Propose abstraction candidates by Stitch compression — a drop-in `AbstractionProposer`.

    Wired behind the existing proposer seam so an in-house selector (e.g. :class:`GreedyMDL`) governs
    the result: Stitch invents, our cost model decides. Library refactoring (also feeding the library's
    *definitions*) is the sleep strategy's concern — this just compresses whatever it is given.
    """

    def __init__(
        self,
        *,
        first_order: bool = True,
        iterations: int = 5,
        max_arity: int = 3,
        threads: int = 1,
    ) -> None:
        self.first_order = first_order
        self.iterations = iterations
        self.max_arity = max_arity
        self.threads = threads

    def propose(self, programs: list[Program], library: Library) -> list[Program]:
        return stitch_candidates(
            programs,
            library,
            first_order=self.first_order,
            iterations=self.iterations,
            max_arity=self.max_arity,
            threads=self.threads,
        )
