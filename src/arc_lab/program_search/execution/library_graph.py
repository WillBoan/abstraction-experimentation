"""``library_graph``: a type-flow DAG for a bundle of primitives — nodes are types, edges are
primitives, rendered as Graphviz DOT or Mermaid text.

Built on the same fixed-point reachability computation as ``check_coherence.py``
(``type_closure.py``) — a reachable/dead type in the graph is exactly a reachable/dead type in the
coherence report, so the two tools tell one consistent story: the graph is the *picture*, the
coherence check is the *verdict*.

**Scope: data types only.** A primitive's function-typed (``ArrowType``) parameters — the
``build_grid``/``map``/``filter``/``fold``/``sort_by`` holes — are omitted from the edges a
primitive contributes; a hole is a search-time body slot, not a data-flow consumption, and its own
internal vocabulary is a per-hole *local* search space (``check_coherence.py``'s hole-fill check),
not a global type relationship this graph could show without misrepresenting it as one. Primitives
with an omitted hole are named in :attr:`LibraryGraph.flags`, mirroring ``estimate_cost.py``'s
convention of flagging an approximation rather than silently dropping information.

**Polymorphism.** A bare ``TypeVar`` param/return (``eq: (a, a) -> bool``, ``if: (bool, a, a) ->
a``) collapses to one synthetic ``any`` node, styled distinctly — it isn't a real value type, just
"whatever's already reachable."
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from arc_lab.program_search.execution.type_closure import compute_closure, leaf_seed_names
from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.types import ArrowType, Type, TypeCon, TypeVar

#: The synthetic node standing in for "a value of any type" — where a bare ``TypeVar`` param or
#: return type would otherwise need a node that doesn't correspond to a real value type.
_POLY_NODE = "any"
#: The synthetic node for a primitive with no data-typed source at all (none exist in the
#: substrate today; kept so a future nullary primitive doesn't silently vanish from the graph).
_NULLARY_NODE = "∅"

NodeKind = Literal["type", "synthetic"]


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One type-flow DAG node: a type-constructor name, or a synthetic stand-in (§ module doc)."""

    node_id: str
    label: str
    reachable: bool
    kind: NodeKind = "type"


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One type-flow DAG edge: all primitives that consume ``source`` and produce ``target``,
    bundled onto a single edge (D4's eight ``grid -> grid`` transforms are one edge, not eight)."""

    source: str
    target: str
    primitives: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LibraryGraph:
    """The full type-flow DAG for one library under one ``constant_sources`` assumption."""

    library_name: str
    constant_sources: tuple[ConstantSource, ...]
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    flags: tuple[str, ...]


def _node_id_for_type(t: Type) -> str | None:
    """The graph node a type maps to: its constructor name, the synthetic poly node for a bare
    ``TypeVar``, or ``None`` for an ``ArrowType`` (not drawn — see the module docstring)."""
    if isinstance(t, TypeCon):
        return t.name
    if isinstance(t, TypeVar):
        return _POLY_NODE
    return None


def _edge_sources(primitive: Primitive) -> list[str]:
    types: list[Type] = list(primitive.param_types)
    if primitive.variadic_param is not None:
        types.append(primitive.variadic_param)
    ids = {node_id for t in types if (node_id := _node_id_for_type(t)) is not None}
    return sorted(ids) if ids else [_NULLARY_NODE]


def build_library_graph(
    library: Library,
    *,
    constant_sources: tuple[ConstantSource, ...] = ("finite-enumerate",),
) -> LibraryGraph:
    """The type-flow DAG for ``library`` under an assumed ``constant_sources`` policy."""
    primitives = library.primitives
    reachable, _activated = compute_closure(primitives, leaf_seed_names(constant_sources))

    type_names: set[str] = set(reachable)
    uses_poly = False
    uses_nullary = False
    edge_primitives: dict[tuple[str, str], set[str]] = defaultdict(set)
    hole_bearing: list[str] = []

    for primitive in primitives:
        if any(isinstance(t, ArrowType) for t in primitive.param_types):
            hole_bearing.append(primitive.name)
        target = _node_id_for_type(primitive.return_type)
        if target is None:
            continue  # a function-valued return type — not in the current substrate, not drawn
        if target == _POLY_NODE:
            uses_poly = True
        else:
            type_names.add(target)
        for source in _edge_sources(primitive):
            if source == _POLY_NODE:
                uses_poly = True
            elif source == _NULLARY_NODE:
                uses_nullary = True
            else:
                type_names.add(source)
            edge_primitives[(source, target)].add(primitive.name)

    nodes = [
        GraphNode(node_id=name, label=name, reachable=name in reachable)
        for name in sorted(type_names)
    ]
    if uses_poly:
        nodes.append(GraphNode(_POLY_NODE, "any (polymorphic)", reachable=True, kind="synthetic"))
    if uses_nullary:
        nodes.append(GraphNode(_NULLARY_NODE, "no input", reachable=True, kind="synthetic"))

    edges = tuple(
        GraphEdge(source=source, target=target, primitives=tuple(sorted(names)))
        for (source, target), names in sorted(edge_primitives.items())
    )

    flags: tuple[str, ...] = ()
    if hole_bearing:
        flags = (
            "function-typed hole(s) omitted from this data-flow view for: "
            f"{', '.join(sorted(hole_bearing))} — see check-library-coherence's hole-fill check",
        )

    return LibraryGraph(
        library_name=library.name,
        constant_sources=constant_sources,
        nodes=tuple(nodes),
        edges=edges,
        flags=flags,
    )


def _dot_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_dot(graph: LibraryGraph) -> str:
    """Render ``graph`` as Graphviz DOT text (``dot -Tsvg`` or any DOT-compatible renderer)."""
    lines = [
        f"digraph {_dot_quote(graph.library_name)} {{",
        "  rankdir=LR;",
        '  node [fontname="Helvetica"];',
    ]
    for node in graph.nodes:
        shape = "diamond" if node.kind == "synthetic" else "ellipse"
        fill = "#c8e6c9" if node.reachable else "#e0e0e0"
        lines.append(
            f"  {_dot_quote(node.node_id)} [label={_dot_quote(node.label)}, shape={shape}, "
            f'style=filled, fillcolor="{fill}"];'
        )
    for edge in graph.edges:
        label = _dot_quote(", ".join(edge.primitives))
        lines.append(f"  {_dot_quote(edge.source)} -> {_dot_quote(edge.target)} [label={label}];")
    for flag in graph.flags:
        lines.append(f"  // NOTE: {flag}")
    lines.append("}")
    return "\n".join(lines)


def to_mermaid(graph: LibraryGraph) -> str:
    """Render ``graph`` as Mermaid ``flowchart`` text (renders inline on GitHub/most markdown)."""
    slug = {node.node_id: f"n{index}" for index, node in enumerate(graph.nodes)}
    lines = ["flowchart LR"]
    for node in graph.nodes:
        open_, close = ("{{", "}}") if node.kind == "synthetic" else ("[", "]")
        label = node.label.replace('"', "'")
        lines.append(f'  {slug[node.node_id]}{open_}"{label}"{close}')
    for edge in graph.edges:
        label = ", ".join(edge.primitives).replace('"', "'")
        lines.append(f'  {slug[edge.source]} -->|"{label}"| {slug[edge.target]}')
    lines.append("  classDef unreachable fill:#eee,stroke:#999,color:#999,stroke-dasharray: 3 3;")
    for node in graph.nodes:
        if not node.reachable:
            lines.append(f"  class {slug[node.node_id]} unreachable;")
    for flag in graph.flags:
        lines.append(f"  %% NOTE: {flag}")
    return "\n".join(lines)
