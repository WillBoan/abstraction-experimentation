"""Learned abstractions: closed templates folded into first-class primitives.

A learned abstraction is a *named factoring of a recurring pattern* — captured as a
**closed template** (a :class:`~arc_lab.program_search.substrate.program.Program` whose holes
are :class:`~arc_lab.program_search.substrate.program.Param` nodes and which contains no
:class:`~arc_lab.program_search.substrate.program.Input`) and exposed as an ordinary typed
:class:`~arc_lab.program_search.substrate.library.Primitive`, so search composes it exactly
like a hand-coded one (``Enumerate`` dispatches on types only, never on provenance).

Keeping the definition as *data* (the template) rather than an opaque Python closure is
what lets a learned entry be serialised (``library.json``), costed — its size feeds the
MDL library term — and abstracted over again. The ``impl`` is a thin evaluator of that
template with its arguments bound to the ``Param`` holes.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Library, Primitive, Value
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    If,
    Input,
    Lam,
    Param,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import (
    ArrowType,
    Substitution,
    Type,
    apply_subst,
    free_type_vars,
    instantiate,
    unify,
)

# The template is closed (no Input), so the outer input grid is never consulted while
# evaluating it; a fixed dummy stands in for evaluate's required grid parameter.
_DUMMY_GRID: Grid = Grid.from_list([[0]])


def make_abstraction(
    name: str,
    template: Program,
    library: Library,
    *,
    signature: tuple[tuple[Type, ...], Type] | None = None,
) -> Primitive:
    """Build a :class:`Primitive` that evaluates ``template`` with args bound to its Params.

    ``library`` must contain every primitive the template references (its lower atoms); the
    ``impl`` closes over it. The template must be *closed* (no ``Input``) and use contiguous
    param indices ``0..n-1`` with a consistent type per index — enforced here, always.

    ``signature`` supplies ``(param_types, return_type)`` when the caller already knows them and
    the template alone cannot recover them. That is not an optimisation but a correctness fix:
    ``Program.result_type`` reports a primitive's DECLARED return type without unification, so a
    template rooted at a polymorphic primitive (``map``, ``filter``, ``head``, ...) derives a free
    type variable — ``map(f, gs)`` yields ``list[b]``, never ``list[grid]``. Both callers do know:
    a `.ladder` rung states its signature and elaboration verifies it by unification, and a
    serialised library carries the signature it was minted with. Without it, any abstraction over
    a polymorphic combinator mints unusably.
    """
    derived = _param_types(template)  # validates closed + contiguous, whatever the signature says
    if signature is None:
        param_types, return_type = derived, _derived_return_type(template, library)
    else:
        param_types, return_type = signature
        if len(param_types) != len(derived):
            raise ValueError(
                f"{name}: signature declares {len(param_types)} parameter(s) but the template "
                f"uses {len(derived)}"
            )
    snapshot = library

    def impl(*args: Value) -> Value:
        return template.evaluate(_DUMMY_GRID, snapshot, tuple(args))

    return Primitive(
        name=name,
        param_types=param_types,
        return_type=return_type,
        impl=impl,
        template=template,
    )


def _derived_return_type(template: Program, library: Library) -> Type:
    """The abstraction's return type when no signature was supplied.

    ``Program.result_type`` reports a primitive's DECLARED return type without unification, so a
    template rooted at a polymorphic primitive derives a free type variable: ``nth(split_h(g), 0)``
    reads as ``a``, never ``grid``, even though ``split_h : (Grid) -> List[Grid]`` pins it. An
    abstraction minted with an unpinned result is not rejected -- it is silently SKIPPED by the
    enumerator (``unpinned_type_var_mode='reject'``, the default in every preset), so it costs
    nothing, finds nothing, and reports nothing. A ladder whose rung is minted that way lints
    perfectly and cannot be climbed.

    So when the declared reading leaves free variables, re-derive by unification and take the
    result if it pins strictly more. Deliberately a REFINEMENT rather than a replacement: a
    template rooted at a monomorphic primitive (every abstraction in the batch before
    ``dae9d2b5-split-*``) keeps byte-identical types, and therefore identical library
    serialisation and run identity.

    Callers that already know the signature should still pass it -- a `.ladder` rung states one
    and elaboration verifies it. This is the floor for the callers that cannot: the learn engines,
    which mint from search results with no declaration anywhere.
    """
    declared = template.result_type(library)
    if not free_type_vars(declared):
        return declared
    inferred = _infer_type(template, library, {}, itertools.count())
    if inferred is None:
        return declared
    resolved = apply_subst({}, inferred)
    return resolved if len(free_type_vars(resolved)) < len(free_type_vars(declared)) else declared


def _infer_type(
    node: Program, library: Library, subst: Substitution, counter: itertools.count[int]
) -> Type | None:
    """Hindley-Milner-style inference for one node, threading ``subst``. ``None`` = give up.

    Only the node kinds that can pin a polymorphic root are inferred; anything else falls back to
    its declared reading, which is what the caller would have used anyway. Giving up is always
    safe -- the caller keeps the unrefined type.
    """
    if isinstance(node, Apply):
        primitive = library.get(node.primitive)
        expected = list(primitive.param_types)
        if primitive.variadic_param is not None:
            expected += [primitive.variadic_param] * (len(node.args) - len(expected))
        if len(expected) != len(node.args):
            return None
        fresh = instantiate(ArrowType(tuple(expected), primitive.return_type), counter)
        if not isinstance(fresh, ArrowType):  # pragma: no cover -- instantiate preserves shape
            return None
        for argument, want in zip(node.args, fresh.params, strict=True):
            got = _infer_type(argument, library, subst, counter)
            if got is None:
                return None
            unified = unify(want, got, subst)
            if unified is None:
                return None
            # `unify` returns the SAME mapping when nothing new binds, so copy before clearing --
            # otherwise the clear empties the very dict the update reads back from.
            merged = dict(unified)
            subst.clear()
            subst.update(merged)
        return apply_subst(subst, fresh.result)
    if isinstance(node, If):
        for branch in (node.then, node.orelse):
            inferred = _infer_type(branch, library, subst, counter)
            if inferred is not None and not free_type_vars(inferred):
                return inferred
        return None
    if isinstance(node, (Lam, AppFn, Var)):
        return None  # higher-order: the binder types are the enumerator's business, not ours
    return node.result_type(library)


def _param_types(template: Program) -> tuple[Type, ...]:
    """The template's hole types in index order; validates closed + contiguous indices.

    A repeated ``Param`` index (the variable-sharing case, e.g. one grid fed to several
    positions) is fine as long as its type is consistent — it still counts as one argument.
    A hole may be arrow-typed (a function-typed parameter — the higher-order case).
    """
    by_index: dict[int, Type] = {}
    for node in template.walk():
        if isinstance(node, Input):
            raise ValueError("abstraction template must be closed (no Input node)")
        if isinstance(node, Param):
            existing = by_index.get(node.index)
            if existing is not None and existing != node.value_type:
                raise ValueError(f"Param {node.index} used with inconsistent types")
            by_index[node.index] = node.value_type
    n = len(by_index)
    if set(by_index) != set(range(n)):
        raise ValueError(f"param indices must be contiguous 0..{n - 1}, got {sorted(by_index)}")
    return tuple(by_index[i] for i in range(n))


def rebuild(node: Program, children: tuple[Program, ...]) -> Program:
    """Reconstruct a constructor node with its children replaced (programs are frozen).

    Only the four constructor kinds reach here; leaves (``Input``/``Const``/``Param``/``Var``/
    ``PrimRef``) have no children and are handled by the callers before dispatching here.
    """
    if isinstance(node, Apply):
        return Apply(primitive=node.primitive, args=children)
    if isinstance(node, If):
        return If(cond=children[0], then=children[1], orelse=children[2])
    if isinstance(node, Lam):
        return Lam(param_type=node.param_type, body=children[0])
    if isinstance(node, AppFn):
        return AppFn(fn=children[0], args=children[1:])
    raise TypeError(f"cannot rebuild non-constructor node: {type(node).__name__}")


def _would_capture(template: Program, args: Sequence[Program]) -> bool:
    """Whether substituting ``args`` into ``template``'s ``Param`` holes could capture a
    lambda-bound ``Var``: only possible when the template binds a ``Lam`` *and* some arg carries a
    free ``Var`` that the binder would shadow. For the non-HO templates v1 ladders use (no ``Lam``)
    this is always ``False``; the guard raises rather than silently miscomputing De Bruijn indices
    if it ever would (HO-abstraction unfolding needs index shifting, not yet built)."""
    if not any(isinstance(node, Lam) for node in template.walk()):
        return False
    return any(isinstance(node, Var) for arg in args for node in arg.walk())


def substitute_params(template: Program, args: Sequence[Program]) -> Program:
    """Structurally replace each ``Param(i)`` in ``template`` with ``args[i]``, returning a
    ``Program`` — the structural analogue of what :meth:`Program.evaluate` does binding *values*
    into ``Param`` holes (``program.py``), but producing an expanded AST rather than a value.

    Simultaneous substitution (an inserted subtree is never re-scanned for params). Correct as
    long as no substituted ``Param`` sits under a ``Lam`` binder while its arg carries a lambda
    ``Var`` — that would need De Bruijn shifting; :func:`_would_capture` guards it.
    """
    if _would_capture(template, args):
        raise NotImplementedError(
            "substitute_params into a higher-order template (with a Lam) using Var-bearing args "
            "needs De Bruijn shifting, not built; v1 ladders use non-HO floors"
        )
    return _substitute(template, args)


def _substitute(node: Program, args: Sequence[Program]) -> Program:
    if isinstance(node, Param):
        return args[node.index]
    children = node.children()
    if not children:
        return node  # Input / Const / Var / PrimRef — leaves carrying no params
    return rebuild(node, tuple(_substitute(child, args) for child in children))


def unfold_program(
    program: Program, library: Library, *, expand: frozenset[str] | None = None
) -> Program:
    """Expand abstraction calls back into their templates — the inverse of :func:`make_abstraction`.

    At each ``Apply(name, args)`` whose ``library`` entry is a learned abstraction (has a
    ``.template``) and whose ``name`` is in ``expand`` (or ``expand is None`` = all abstractions),
    substitute the *recursively-unfolded* args into a fresh copy of the template, then recurse into
    the result. ``expand=None`` unfolds all the way down to floor primitives (the ``d_raw`` form);
    ``expand={r_i}`` expands exactly ``r_i``'s call sites, leaving ``r_i``'s template's own
    references to ``r_{i-1}`` folded (the inlined double-jump form). Terminates because a template
    only references strictly-lower abstractions (libraries are built by extension, never cyclic).

    Memoized by node identity: a shared subtree unfolds once, and its expansion is shared in the
    output too. Deeply-nested abstraction calls (a ladder top wrapping a rung tens of times)
    otherwise materialize millions of distinct objects, which every later traversal then pays
    for; with the memo the output's DISTINCT node count stays near the sum of template sizes,
    while ``==``/hash semantics are untouched (identical structure either way).
    """
    # The memo VALUE keeps a strong reference to the keyed node: intermediate nodes built during
    # unfolding are otherwise freed, and a recycled id() would alias a fresh node to a stale
    # entry (id is only unique among live objects).
    memo: dict[int, tuple[Program, Program]] = {}

    def go(node: Program) -> Program:
        key = id(node)
        cached = memo.get(key)
        if cached is not None and cached[0] is node:
            return cached[1]
        result = _unfold_one(node, go, library, expand)
        memo[key] = (node, result)
        return result

    return go(program)


def _unfold_one(
    node: Program,
    go: Callable[[Program], Program],
    library: Library,
    expand: frozenset[str] | None,
) -> Program:
    if isinstance(node, Apply):
        unfolded_args = tuple(go(arg) for arg in node.args)
        template = library.get(node.primitive).template if node.primitive in library else None
        if template is not None and (expand is None or node.primitive in expand):
            return go(substitute_params(template, unfolded_args))
        return Apply(primitive=node.primitive, args=unfolded_args)
    children = node.children()
    if not children:
        return node
    return rebuild(node, tuple(go(child) for child in children))
