"""Learned abstractions: closed templates folded into first-class primitives.

A learned abstraction is a *named factoring of a recurring pattern* — captured as a
**closed template** (a :class:`~arc_lab.solvers.dsl.substrate.program.Program` whose holes
are :class:`~arc_lab.solvers.dsl.substrate.program.Param` nodes and which contains no
:class:`~arc_lab.solvers.dsl.substrate.program.Input`) and exposed as an ordinary typed
:class:`~arc_lab.solvers.dsl.substrate.library.Primitive`, so search composes it exactly
like a hand-coded one (``Enumerate`` dispatches on types only, never on provenance).

Keeping the definition as *data* (the template) rather than an opaque Python closure is
what lets a learned entry be serialised (``library.json``), costed — its size feeds the
MDL library term — and abstracted over again. The ``impl`` is a thin evaluator of that
template with its arguments bound to the ``Param`` holes.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.library import Library, Primitive, Value
from arc_lab.solvers.dsl.substrate.program import Input, Param, Program
from arc_lab.solvers.dsl.substrate.types import ValueType

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


def _param_types(template: Program) -> tuple[ValueType, ...]:
    """The template's hole types in index order; validates closed + contiguous indices.

    A repeated ``Param`` index (the variable-sharing case, e.g. one grid fed to several
    positions) is fine as long as its type is consistent — it still counts as one argument.
    """
    by_index: dict[int, ValueType] = {}
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
