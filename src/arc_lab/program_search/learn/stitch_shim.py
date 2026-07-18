"""The sole boundary to Stitch (`stitch_core`): (de)serialize programs, run compression.

Stitch is a mature, De Bruijn-native, deterministic library-learning engine. This module is the
*only* place it is imported (lazily), so the stub-less compiled wheel's ``Any`` values are contained
here and the rest of the strict-typed codebase sees only typed `Program`/`Primitive` values.

Two directions:

* :func:`to_sexpr` — a `Program` to Stitch's s-expression (``$i`` De Bruijn vars, ``#j`` abstraction
  vars, ``(lam …)``, ``(f a b)``). The substrate was built Stitch-compatible, so ``Var``/``Param``/``Lam``
  already print in Stitch's notation; only ``Apply`` needs prefix form. The short-circuit ``If`` node
  encodes as the **reserved head symbol** ``if`` — ``(if c t e)`` — which Stitch antiunifies over like
  any other symbol.
* :func:`from_sexpr` — a Stitch s-expression back to a `Program`, **re-inferring types** (Stitch is
  untyped) from the library's primitive signatures, then :func:`_close_template`-ing so a free ``input``
  becomes a shared grid ``Param`` (Stitch leaves it free; our abstractions are closed templates). A
  ``(if c t e)`` decodes back to an :class:`If` node (symmetric with the encoder — never an eager
  ``Apply``), so invented abstractions may contain branching.

:func:`stitch_candidates` composes the two around :func:`_compress` to propose candidate abstraction
templates over the current library — the invention half; governance (which to adopt) stays with the
in-house :class:`AbstractionSelector`, so the cost model remains fully ours.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from arc_lab.program_search.learn.antiunify import AbstractionProposer, _close_template, _is_useful
from arc_lab.program_search.learn.telemetry import SleepCounters
from arc_lab.program_search.substrate.library import Library, Primitive
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
from arc_lab.program_search.substrate.types import (
    BOOL,
    GRID,
    INT,
    ArrowType,
    Substitution,
    Type,
    TypeCon,
    TypeVar,
    apply_subst,
    base_type,
    instantiate,
    unify,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_INT = INT

#: The reserved s-expression head for the short-circuit :class:`If` node. The library's ``if``
#: *entry* is the capability summoner (SEARCH-SPACE.md Table A); programs never carry an eager
#: ``Apply("if", …)`` — the enumerator mints ``If`` nodes — so the symbol is unambiguous here.
_IF_HEAD = "if"

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
        # A bool serializes to the bare token `true`/`false` (a valid Stitch terminal), not Python's
        # capitalized `str(True)` = "True" — which `from_sexpr` could not parse back. (bool ⊂ int, so
        # this branch must precede the int case.)
        if isinstance(program.value, bool):
            return "true" if program.value else "false"
        # A non-INT scalar keeps its type through untyped Stitch as a typed literal (`3:color`) —
        # one opaque terminal to Stitch, an exact Const to `from_sexpr` even in an untyped context.
        if program.value_type != _INT:
            return f"{program.value}:{program.value_type.name}"
        return str(program.value)
    if isinstance(program, Var):
        return f"${program.index}"
    if isinstance(program, Param):
        return f"x{program.index}"  # a closed terminal (see docstring); `#j` is Stitch-output only
    if isinstance(program, Lam):
        return f"(lam {to_sexpr(program.body)})"
    if isinstance(program, If):  # the reserved head — Stitch antiunifies over it like any symbol
        return f"({_IF_HEAD} {to_sexpr(program.cond)} {to_sexpr(program.then)} {to_sexpr(program.orelse)})"
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

    Types are re-inferred (Stitch is untyped) by Hindley-Milner unification. First-order idioms infer
    top-down from primitive signatures as before; a **higher-order** term — a metavar or bound var
    *applied* to arguments, ``(#j a…)`` / ``($i a…)`` — becomes an :class:`AppFn` whose head's *arrow*
    type is solved from its argument types (domain) and its context (codomain), unified across every
    use of that metavar (so ``#0`` in ``(#0 (#0 input))`` resolves to ``GRID -> GRID``). A bare
    primitive symbol in a value position becomes a :class:`PrimRef`. A ``(if c t e)`` decodes to the
    short-circuit :class:`If` node. A free ``input`` is then lifted to a shared grid ``Param`` and
    params renumbered (:func:`_close_template`).
    """
    tokens = _tokenize(sexpr)
    tree, rest = _parse(tokens, 0)
    if rest != len(tokens):
        raise ValueError(f"trailing tokens in s-expression: {sexpr!r}")
    ctx = _InferCtx(subst={}, metavars={}, bound=[], counter=itertools.count())
    program, _ = _infer(tree, library, None, ctx)
    return _close_template(_resolve_types(program, ctx.subst))


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


@dataclass
class _InferCtx:
    """Mutable state threaded through type re-inference: the unifier + each hole/var's solved type."""

    subst: Substitution
    metavars: dict[
        int, Type
    ]  # #j -> its (shared, unification-refined) type; term-global (Stitch's)
    #: The De Bruijn binder stack: ``bound[-1]`` is the innermost ``lam``'s variable, so ``$i`` reads
    #: ``bound[-1 - i]``. A *stack* (not a flat index->type map) is essential — two ``$0``\\ s under
    #: different binders are different variables and must not be unified with each other.
    bound: list[Type]
    counter: itertools.count[int]


def _fresh(ctx: _InferCtx) -> TypeVar:
    return TypeVar(f"?t{next(ctx.counter)}")


def _bound_var_type(ctx: _InferCtx, index: int) -> Type:
    """The type of De Bruijn ``$index`` in the current binder scope (``ctx.bound[-1 - index]``)."""
    if not 0 <= index < len(ctx.bound):
        raise ValueError(f"bound variable ${index} out of scope (binder depth {len(ctx.bound)})")
    return ctx.bound[-1 - index]


def _instantiate_sig(prim: Primitive, ctx: _InferCtx) -> tuple[tuple[Type, ...], Type | None, Type]:
    """A primitive's ``(param_types, variadic, return_type)`` with all type variables renamed fresh.

    Bundling the whole signature into one :class:`ArrowType` before :func:`instantiate` keeps a shared
    variable name coherent *within* this use while making it independent of any *other* use (so a
    polymorphic primitive applied twice in one body doesn't cross-contaminate its two instantiations).
    For today's monomorphic primitives this is a structural no-op.
    """
    variadic = prim.variadic_param
    tail = (variadic,) if variadic is not None else ()
    bundled = instantiate(ArrowType((*prim.param_types, *tail), prim.return_type), ctx.counter)
    assert isinstance(bundled, ArrowType)  # instantiate preserves the ArrowType shape
    n = len(prim.param_types)
    return bundled.params[:n], (bundled.params[n] if variadic is not None else None), bundled.result


def _unify_into(ctx: _InferCtx, t1: Type, t2: Type) -> None:
    result = unify(t1, t2, ctx.subst)
    if result is None:
        raise ValueError(f"type error: cannot unify {t1} and {t2}")
    ctx.subst = result


def _infer(
    node: SExpr, library: Library, expected: Type | None, ctx: _InferCtx
) -> tuple[Program, Type]:
    """Build a `Program` from a parsed node and infer its type, unifying constraints into ``ctx``."""
    if isinstance(node, str):
        return _infer_atom(node, library, expected, ctx)
    if not node:
        raise ValueError("empty application in s-expression")
    head, args = node[0], node[1:]
    if head == "lam":
        if len(args) != 1:
            raise ValueError(f"lam takes one body, got {len(args)}")
        # A lambda binds one variable ($0 in its body). Seed that variable's domain from an expected
        # arrow hole when we have one (so a lam filling a `(dom) -> cod` parameter types precisely and
        # its bound var starts from `dom`), else a fresh var to be solved from how the body uses $0.
        if isinstance(expected, ArrowType) and len(expected.params) == 1:
            domain, codomain = expected.params[0], expected.result
        else:
            domain, codomain = _fresh(ctx), None
        ctx.bound.append(domain)  # push: this lam is now the innermost binder for its body
        body, body_type = _infer(args[0], library, codomain, ctx)
        ctx.bound.pop()
        if codomain is not None:
            _unify_into(ctx, body_type, codomain)
            return Lam(param_type=domain, body=body), ArrowType((domain,), codomain)
        # No arrow context: the lambda's type is still a precise arrow (the new Lam carries its
        # param_type), solved from how the body used $0 — no opaque FN fallback needed.
        return Lam(param_type=domain, body=body), ArrowType((domain,), body_type)
    if head == _IF_HEAD:  # the reserved branching head — decode to the short-circuit If node
        if len(args) != 3:
            raise ValueError(f"if takes (cond then orelse), got {len(args)} args")
        cond, cond_type = _infer(args[0], library, BOOL, ctx)
        _unify_into(ctx, cond_type, BOOL)
        branch_expected = expected if expected is not None else _fresh(ctx)
        then, then_type = _infer(args[1], library, branch_expected, ctx)
        _unify_into(ctx, then_type, branch_expected)
        orelse, orelse_type = _infer(args[2], library, branch_expected, ctx)
        _unify_into(ctx, orelse_type, branch_expected)
        return If(cond=cond, then=then, orelse=orelse), branch_expected
    if not isinstance(head, str):
        raise ValueError(f"application head must be a symbol, got {head!r}")
    if head[:1] in ("#", "$"):  # higher-order application: a hole/var applied to arguments -> AppFn
        arg_progs, arg_types = _infer_args(args, library, ctx)
        result = _fresh(ctx)
        applied: Type = ArrowType(tuple(arg_types), result)
        index = int(head[1:])
        if head[0] == "#":  # a metavar hole applied as a function: its type is term-global
            if index in ctx.metavars:
                _unify_into(ctx, ctx.metavars[index], applied)
            else:
                ctx.metavars[index] = applied
            fn: Program = Param(index, ctx.metavars[index])
        else:  # a bound var applied as a function: its type comes from its binder on the stack
            head_type = _bound_var_type(ctx, index)
            _unify_into(ctx, head_type, applied)
            fn = Var(index, head_type)
        if expected is not None:
            _unify_into(ctx, result, expected)
        return AppFn(fn, tuple(arg_progs)), result
    prim = library.get(head)  # first-order application; KeyError for an unknown symbol (e.g. fn_k)
    # Arity: first-order Stitch can emit a *partial* application (it curries — a fixed trailing arg
    # reappears per call site), which is not a valid n-ary Apply in our non-curried DSL. Reject it here
    # rather than build a malformed, unevaluable node that only a downstream guard catches by accident.
    if prim.is_variadic:
        if len(args) < prim.arity:
            raise ValueError(f"{head!r} expects at least {prim.arity} args, got {len(args)}")
    elif len(args) != prim.arity:
        raise ValueError(f"{head!r} expects {prim.arity} args, got {len(args)}")
    param_types, variadic, return_type = _instantiate_sig(prim, ctx)
    arg_expected = _arg_types(param_types, variadic, len(args))
    arg_progs = []
    for arg, want in zip(args, arg_expected, strict=True):
        arg_prog, arg_type = _infer(arg, library, want, ctx)
        if want is not None:
            _unify_into(ctx, arg_type, want)
        arg_progs.append(arg_prog)
    if expected is not None:
        _unify_into(ctx, return_type, expected)
    return Apply(head, tuple(arg_progs)), return_type


def _infer_atom(
    atom: str, library: Library, expected: Type | None, ctx: _InferCtx
) -> tuple[Program, Type]:
    if atom == "input":
        if expected is not None:
            _unify_into(ctx, GRID, expected)
        return Input(), GRID
    if atom[:1] == "#":  # a metavar hole used as a value: type is term-global (shared across uses)
        index = int(atom[1:])
        t = ctx.metavars.setdefault(index, expected if expected is not None else _fresh(ctx))
        if expected is not None:
            _unify_into(ctx, t, expected)
        return Param(index, t), t
    if atom[:1] == "$":  # a bound var used as a value: its type comes from its binder on the stack
        index = int(atom[1:])
        t = _bound_var_type(ctx, index)
        if expected is not None:
            _unify_into(ctx, t, expected)
        return Var(index, t), t
    if atom in ("true", "false"):  # a bool literal decodes to a BOOL Const (inverse of to_sexpr)
        if expected is not None:
            _unify_into(ctx, BOOL, expected)
        return Const(atom == "true", BOOL), BOOL
    if (typed := _typed_literal(atom)) is not None:  # `3:color` — exact regardless of context
        value, base = typed
        if expected is not None:
            _unify_into(ctx, base, expected)
        return Const(value, base), base
    if _is_int_literal(atom):  # a bare literal is INT (non-INT scalars encode as typed literals)
        base = expected if isinstance(expected, TypeCon) and not expected.args else _INT
        return Const(int(atom), base), base
    if atom in library:  # a primitive referenced as a first-class function value
        prim = library.get(atom)
        arrow: Type = ArrowType(tuple(prim.param_types), prim.return_type)
        if expected is not None:
            _unify_into(ctx, arrow, expected)
        return PrimRef(atom), arrow
    raise ValueError(f"unknown atom {atom!r} (not input/#j/$i/bool/int-literal/primitive)")


def _infer_args(
    args: Sequence[SExpr], library: Library, ctx: _InferCtx
) -> tuple[list[Program], list[Type]]:
    progs: list[Program] = []
    types: list[Type] = []
    for arg in args:
        prog, arg_type = _infer(arg, library, None, ctx)
        progs.append(prog)
        types.append(arg_type)
    return progs, types


def _resolve_types(program: Program, subst: Substitution) -> Program:
    """Rebuild ``program`` with every hole/var's carried type substituted to its solved form."""
    if isinstance(program, Param):
        return Param(program.index, apply_subst(subst, program.value_type))
    if isinstance(program, Var):
        return Var(program.index, apply_subst(subst, program.value_type))
    if isinstance(program, Apply):
        return Apply(program.primitive, tuple(_resolve_types(a, subst) for a in program.args))
    if isinstance(program, If):
        return If(
            cond=_resolve_types(program.cond, subst),
            then=_resolve_types(program.then, subst),
            orelse=_resolve_types(program.orelse, subst),
        )
    if isinstance(program, AppFn):
        return AppFn(
            _resolve_types(program.fn, subst), tuple(_resolve_types(a, subst) for a in program.args)
        )
    if isinstance(program, Lam):
        return Lam(
            param_type=apply_subst(subst, program.param_type),
            body=_resolve_types(program.body, subst),
        )
    return program  # Input / Const / PrimRef: no carried type variables


def _arg_types(
    param_types: tuple[Type, ...], variadic: Type | None, n: int
) -> tuple[Type | None, ...]:
    """Expected type per argument position, extending a variadic tail with its element type."""
    return tuple(param_types[i] if i < len(param_types) else variadic for i in range(n))


def _is_int_literal(atom: str) -> bool:
    return atom.lstrip("-").isdigit()


def _typed_literal(atom: str) -> tuple[int, TypeCon] | None:
    """Parse a typed scalar literal ``<int>:<base-type>`` (e.g. ``3:color``), or ``None``.

    The inverse of :func:`to_sexpr`'s non-INT Const encoding. An unknown type name raises
    (:func:`base_type` is fail-fast), which is right: the token can only come from our own encoder.
    """
    head, sep, name = atom.partition(":")
    if not sep or not _is_int_literal(head):
        return None
    return int(head), base_type(name)


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
    (higher-order holes). ``threads`` defaults to ``1`` because only single-threaded compression is
    guaranteed reproducible — the regression locks depend on it; ``> 1`` trades that for speed and a
    caller wanting it must verify determinism itself (there is a twice-run test that does so at 1).
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
    and keep the useful ones. A body that fails to deserialize is skipped and logged at ``DEBUG``
    (silent under this repo's default logging) — this covers both abstractions referencing *other*
    Stitch abstractions (its own ``fn_k`` hierarchy) and, now, arity-invalid partial applications
    (:func:`from_sexpr` rejects them). Resolving Stitch's hierarchy, and consuming the higher-order
    abstractions it builds atop it, travels with the higher-order substrate (the interesting hierarchies
    are themselves higher-order). Governance (which candidate earns a name) is the caller's selector.
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


@dataclass(frozen=True, slots=True, kw_only=True)
class StitchProposer(AbstractionProposer):
    """Propose abstraction candidates by Stitch compression — a drop-in `AbstractionProposer`.

    Wired behind the existing proposer seam so an in-house selector (e.g. :class:`GreedyMDL`) governs
    the result: Stitch invents, our cost model decides. Library refactoring (also feeding the library's
    *definitions*) is the learn engine's concern — this just compresses whatever it is given.
    """

    first_order: bool = True
    iterations: int = 5
    max_arity: int = 3
    threads: int = 1

    def propose(
        self,
        programs: list[Program],
        library: Library,
        *,
        counters: SleepCounters | None = None,
    ) -> list[Program]:
        # counters: Stitch's cost isn't pair-based, so it leaves antiunify_pair_count untouched;
        # the proposals it returns are still tallied by the selector (proposal_count).
        return stitch_candidates(
            programs,
            library,
            first_order=self.first_order,
            iterations=self.iterations,
            max_arity=self.max_arity,
            threads=self.threads,
        )
