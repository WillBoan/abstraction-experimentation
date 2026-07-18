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

from collections.abc import Sequence

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
from arc_lab.program_search.substrate.types import Type

# The template is closed (no Input), so the outer input grid is never consulted while
# evaluating it; a fixed dummy stands in for evaluate's required grid parameter.
_DUMMY_GRID: Grid = Grid.from_list([[0]])


def make_abstraction(name: str, template: Program, library: Library) -> Primitive:
    """Build a :class:`Primitive` that evaluates ``template`` with args bound to its Params.

    ``library`` must contain every primitive the template references (its lower atoms); the
    ``impl`` closes over it. The template must be *closed* (no ``Input``) and use contiguous
    param indices ``0..n-1`` with a consistent type per index — enforced here.
    """
    param_types = _param_types(template)
    return_type = template.result_type(library)
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


def _rebuild(node: Program, children: tuple[Program, ...]) -> Program:
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
    return _rebuild(node, tuple(_substitute(child, args) for child in children))


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
    """

    def go(node: Program) -> Program:
        if isinstance(node, Apply):
            unfolded_args = tuple(go(arg) for arg in node.args)
            template = library.get(node.primitive).template if node.primitive in library else None
            if template is not None and (expand is None or node.primitive in expand):
                return go(substitute_params(template, unfolded_args))
            return Apply(primitive=node.primitive, args=unfolded_args)
        children = node.children()
        if not children:
            return node
        return _rebuild(node, tuple(go(child) for child in children))

    return go(program)
