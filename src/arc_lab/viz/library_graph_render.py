"""Render a :class:`LibraryGraph` as a saved image -- no external tool required.

Complements the DOT/Mermaid text renderers (``execution/library_graph.py``) with a self-contained
path: a small pure-matplotlib layered layout (nodes ranked left-to-right by longest path from the
graph's roots, mirroring the DOT renderer's ``rankdir=LR``), saved straight to a file. No
graphviz/mermaid-cli install, no preview-extension flakiness, no transparent-background surprises
-- the figure background is set explicitly, same headless-save convention as ``render.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from arc_lab.program_search.execution.library_graph import GraphEdge, GraphNode, LibraryGraph

if TYPE_CHECKING:
    from matplotlib.axes import Axes

_REACHABLE_FILL = "#c8e6c9"
_UNREACHABLE_FILL = "#e0e0e0"
_SYNTHETIC_FILL = "#bbdefb"
_BACKGROUND = "#ffffff"
_NODE_WIDTH = 1.7
_NODE_HEIGHT = 0.6
_COLUMN_SPACING = 3.4
_ROW_SPACING = 1.6


def _reachable_from(adjacency: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = list(adjacency[start])
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node])
    return seen


def _strongly_connected_components(
    node_ids: list[str], edges: list[tuple[str, str]]
) -> dict[str, int]:
    """Node -> SCC id, by mutual reachability -- these graphs are tiny (a handful of type
    constructors), so an O(n^2) grouping is plenty; no need for Tarjan here."""
    adjacency: dict[str, set[str]] = {node: set() for node in node_ids}
    for source, target in edges:
        adjacency[source].add(target)
    reach = {node: _reachable_from(adjacency, node) for node in node_ids}

    scc_id: dict[str, int] = {}
    next_id = 0
    for node in node_ids:
        if node in scc_id:
            continue
        scc_id[node] = next_id
        for other in node_ids:
            if other != node and other in reach[node] and node in reach[other]:
                scc_id[other] = next_id
        next_id += 1
    return scc_id


def _ranks_over(node_ids: list[str], graph_edges: tuple[GraphEdge, ...]) -> dict[str, int]:
    """Longest-path rank per node in ``node_ids`` -- a left-to-right layering, mirroring the DOT
    renderer's ``rankdir=LR``. A real (non-self-loop) cycle -- e.g. ``mask`` <-> ``grid`` via
    ``mask_by_color``/``crop_to_mask`` -- would make a naive longest-path relaxation blow up
    (cascading increments around the cycle, never converging cleanly), so cyclic nodes are first
    collapsed into one strongly-connected component and ranked as a single column; the condensed
    graph is then acyclic by construction, so plain relaxation is exact and terminates cleanly."""
    node_id_set = set(node_ids)
    edges = [
        (edge.source, edge.target)
        for edge in graph_edges
        if edge.source != edge.target and edge.source in node_id_set and edge.target in node_id_set
    ]
    scc_id = _strongly_connected_components(node_ids, edges)

    condensed_edges = {
        (scc_id[source], scc_id[target])
        for source, target in edges
        if scc_id[source] != scc_id[target]
    }
    scc_ids = sorted(set(scc_id.values()))
    scc_rank = dict.fromkeys(scc_ids, 0)
    for _ in range(len(scc_ids) + 1):
        changed = False
        for source_id, target_id in condensed_edges:
            if scc_rank[target_id] < scc_rank[source_id] + 1:
                scc_rank[target_id] = scc_rank[source_id] + 1
                changed = True
        if not changed:
            break
    return {node: scc_rank[scc_id[node]] for node in node_ids}


@dataclass(frozen=True, slots=True)
class _NodeLayout:
    x: float
    y: float
    #: +1/-1: which side a self-loop bulges to. Alternated by row *within a column* so two
    #: vertically-stacked, mutually-connected nodes (e.g. ``mask``<->``grid``, collapsed into the
    #: same column by the SCC handling above) don't both reach into the corridor between them.
    loop_side: int


def _layout(graph: LibraryGraph) -> dict[str, _NodeLayout]:
    # Nodes with no edge at all (a seeded leaf type nothing in the library touches -- e.g. `bool`
    # for a pure geometric library like `d4`) are laid out separately from the rank/column system:
    # mixed into a column with a self-loop-bearing node, an edge-less node's "empty" space is
    # exactly where the self-loop wants to bulge into, colliding with it. Keeping them in their
    # own dedicated row sidesteps that regardless of how the rest of the graph is shaped.
    touched = {n for edge in graph.edges for n in (edge.source, edge.target)}
    connected = [node.node_id for node in graph.nodes if node.node_id in touched]
    isolated = sorted(node.node_id for node in graph.nodes if node.node_id not in touched)

    rank = _ranks_over(connected, graph.edges)
    columns: dict[int, list[str]] = {}
    for node_id in connected:
        columns.setdefault(rank[node_id], []).append(node_id)
    layout: dict[str, _NodeLayout] = {}
    min_y = 0.0
    for column, node_ids in columns.items():
        node_ids.sort()
        offset = (len(node_ids) - 1) / 2
        for row, node_id in enumerate(node_ids):
            y = (offset - row) * _ROW_SPACING
            min_y = min(min_y, y)
            layout[node_id] = _NodeLayout(
                x=column * _COLUMN_SPACING, y=y, loop_side=1 if row % 2 == 0 else -1
            )

    isolated_row_y = min_y - _ROW_SPACING * 1.6
    isolated_offset = (len(isolated) - 1) / 2
    for col, node_id in enumerate(isolated):
        layout[node_id] = _NodeLayout(
            x=(col - isolated_offset) * _COLUMN_SPACING * 0.75, y=isolated_row_y, loop_side=1
        )
    return layout


def _box_offset(ux: float, uy: float) -> float:
    """Distance from a node's center to its box boundary along direction ``(ux, uy)`` -- the
    node's rectangle approximated as an inscribed ellipse (half-width ``_NODE_WIDTH/2``,
    half-height ``_NODE_HEIGHT/2``). Using a flat ``_NODE_WIDTH/2`` offset regardless of angle
    (an earlier version of this function did) overshoots badly for a near-vertical edge -- e.g.
    two nodes one row apart in the same SCC column -- inverting the arrow into a tiny malformed
    glyph once the offset from both ends exceeds the actual gap between them."""
    half_width, half_height = _NODE_WIDTH / 2, _NODE_HEIGHT / 2
    denom = math.hypot(ux / half_width, uy / half_height)
    return 1.0 / denom if denom else half_width


def _fill_color(node: GraphNode) -> str:
    if node.kind == "synthetic":
        return _SYNTHETIC_FILL
    return _REACHABLE_FILL if node.reachable else _UNREACHABLE_FILL


def _draw_node(ax: Axes, node: GraphNode, layout: _NodeLayout) -> None:
    from matplotlib.patches import FancyBboxPatch

    x, y = layout.x, layout.y
    box = FancyBboxPatch(
        (x - _NODE_WIDTH / 2, y - _NODE_HEIGHT / 2),
        _NODE_WIDTH,
        _NODE_HEIGHT,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2,
        edgecolor="#333333",
        facecolor=_fill_color(node),
        zorder=3,
    )
    ax.add_patch(box)
    ax.text(x, y, node.label, ha="center", va="center", fontsize=9, zorder=4)


def _label(ax: Axes, x: float, y: float, text: str) -> None:
    # A background box behind every edge label is what actually fixes "text overlaps" --
    # crossing lines stay legible because the label sits on its own opaque patch.
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=7.5,
        zorder=5,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88, "pad": 1.2},
    )


def _draw_self_loop(ax: Axes, layout: _NodeLayout, text: str) -> None:
    from matplotlib.patches import FancyArrowPatch

    x, y = layout.x, layout.y
    edge_y = y + layout.loop_side * _NODE_HEIGHT / 2
    label_y = y + layout.loop_side * (_NODE_HEIGHT / 2 + 0.6)
    rad = -1.6 if layout.loop_side > 0 else 1.6
    loop = FancyArrowPatch(
        (x - 0.35, edge_y),
        (x + 0.35, edge_y),
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.0,
        color="#555555",
        zorder=2,
    )
    ax.add_patch(loop)
    _label(ax, x, label_y, text)


def _draw_edge(ax: Axes, edge: GraphEdge, layout: dict[str, _NodeLayout]) -> None:
    from matplotlib.patches import FancyArrowPatch

    label = ", ".join(edge.primitives)
    if edge.source == edge.target:
        _draw_self_loop(ax, layout[edge.source], label)
        return
    x0, y0 = layout[edge.source].x, layout[edge.source].y
    x1, y1 = layout[edge.target].x, layout[edge.target].y
    dx, dy = x1 - x0, y1 - y0
    edge_length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / edge_length, dy / edge_length

    # The bulge side must be keyed off the *pair* (alphabetically low -> high), not this edge's
    # own source->target direction -- that direction flips between an A->B and a B->A edge, which
    # would otherwise cancel out against `rad`'s flip and land both labels on the same side (the
    # bug that made the mask<->grid pair unreadable: both edges' offsets landed on top of each
    # other instead of opposite sides).
    lo, hi = sorted((edge.source, edge.target))
    lo_x, lo_y = layout[lo].x, layout[lo].y
    hi_x, hi_y = layout[hi].x, layout[hi].y
    pair_length = math.hypot(hi_x - lo_x, hi_y - lo_y) or 1.0
    perp_x = -(hi_y - lo_y) / pair_length
    perp_y = (hi_x - lo_x) / pair_length
    rad = 0.3 if edge.source < edge.target else -0.3

    # Symmetric: the offset magnitude only depends on the line's angle, not which end -- both
    # nodes are the same size and shape.
    offset = _box_offset(ux, uy)
    start = (x0 + ux * offset, y0 + uy * offset)
    end = (x1 - ux * offset, y1 - uy * offset)
    arrow = FancyArrowPatch(
        start,
        end,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.0,
        color="#555555",
        zorder=2,
    )
    ax.add_patch(arrow)
    # Label placed off to the arc's bulge side, at a *fixed* minimum offset (not scaled by edge
    # length, or a short edge -- e.g. two nodes collapsed into the same SCC column, like
    # mask<->grid -- would place an A->B and a B->A label too close to stay legible), AND shifted
    # along the line itself (not just perpendicular to it): edge labels here are often wider than
    # the node spacing, so separating on one axis alone isn't enough once the text is that long.
    along_t = 0.1 if rad > 0 else 0.9
    mid_x = start[0] + (end[0] - start[0]) * along_t
    mid_y = start[1] + (end[1] - start[1]) * along_t
    bulge = math.copysign(max(abs(rad) * pair_length * 0.5, 1.3), rad)
    _label(ax, mid_x + perp_x * bulge, mid_y + perp_y * bulge, label)


def render_library_graph(
    graph: LibraryGraph,
    out_path: str | Path,
    *,
    show: bool = False,
) -> None:
    """Render ``graph`` to ``out_path`` (format inferred from the suffix -- ``.png``/``.svg``/...)."""
    import matplotlib.pyplot as plt

    layout = _layout(graph)
    xs = [node.x for node in layout.values()] or [0.0]
    ys = [node.y for node in layout.values()] or [0.0]

    width = max(6.0, (max(xs) - min(xs)) + 3.0)
    height = max(4.0, (max(ys) - min(ys)) + 3.0)
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor(_BACKGROUND)
    ax.set_facecolor(_BACKGROUND)

    for edge in graph.edges:
        _draw_edge(ax, edge, layout)
    for node in graph.nodes:
        _draw_node(ax, node, layout[node.node_id])

    ax.set_xlim(min(xs) - _NODE_WIDTH, max(xs) + _NODE_WIDTH)
    ax.set_ylim(min(ys) - _NODE_HEIGHT * 2, max(ys) + _NODE_HEIGHT * 2 + 0.6)
    ax.set_title(
        f"{graph.library_name}  (constant_sources={list(graph.constant_sources)})", fontsize=11
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    if show:  # pragma: no cover - interactive only
        plt.show()
    plt.close(fig)
