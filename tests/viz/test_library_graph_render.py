"""``library_graph_render``: the layout math (rank/SCC/box-offset) and the image smoke test.

Layout correctness matters here more than usual for a "just draw a picture" module: a naive
longest-path rank computation blows up on a real type-graph cycle (``mask`` <-> ``grid``), and a
flat node-boundary offset inverts into a malformed arrow on a near-vertical edge -- both were
real, visually-confirmed bugs this module now guards against structurally, not just by eyeballing
a render.
"""

from __future__ import annotations

import math
from pathlib import Path

from arc_lab.program_search.execution.library_graph import GraphEdge, build_library_graph
from arc_lab.program_search.execution.presets import LIBRARIES
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.viz.library_graph_render import (
    _NODE_HEIGHT,
    _NODE_WIDTH,
    _box_offset,
    _layout,
    _ranks_over,
    render_library_graph,
)


def test_ranks_over_a_two_cycle_stays_bounded() -> None:
    """The ``mask`` <-> ``grid`` cycle (``mask_by_color``: grid->mask, ``crop_to_mask``:
    mask->grid) previously made a naive longest-path relaxation cascade to rank ~12-13 within a
    single outer iteration; the SCC-collapsed version keeps every rank small and finite."""
    graph = build_library_graph(LIBRARIES["mask"])
    node_ids = [n.node_id for n in graph.nodes]
    ranks = _ranks_over(node_ids, graph.edges)
    assert all(0 <= r <= len(node_ids) for r in ranks.values())
    # grid and mask are mutually reachable (a real cycle) -- they must land in the same column.
    assert ranks["grid"] == ranks["mask"]


def test_ranks_over_a_three_way_cycle_through_a_shared_hub() -> None:
    """``hof``: grid<->int (via width/height + from_cells) and grid<->list (via cells +
    from_cells) share the ``grid`` hub -- transitively, all three are mutually reachable and
    must collapse to one column, not blow up or split incorrectly."""
    graph = build_library_graph(LIBRARIES["hof"])
    node_ids = [n.node_id for n in graph.nodes]
    ranks = _ranks_over(node_ids, graph.edges)
    assert ranks["grid"] == ranks["int"] == ranks["list"]
    assert all(0 <= r <= len(node_ids) for r in ranks.values())


def test_ranks_over_acyclic_chain_increases_monotonically() -> None:
    edges = (
        GraphEdge(source="a", target="b", primitives=("f",)),
        GraphEdge(source="b", target="c", primitives=("g",)),
    )
    ranks = _ranks_over(["a", "b", "c"], edges)
    assert ranks["a"] < ranks["b"] < ranks["c"]


def test_isolated_nodes_are_excluded_from_the_ranked_layout() -> None:
    """``bool``/``int`` touch no primitive in ``d4`` at all -- ``_layout`` must place them off to
    the side rather than interleaved into the column that holds the self-loop-bearing ``grid``
    (the crowding bug: an isolated node's "empty" space is where a self-loop wants to bulge)."""
    graph = build_library_graph(D4_LIBRARY)
    layout = _layout(graph)
    grid_y = layout["grid"].y
    for isolated in ("bool", "int"):
        assert layout[isolated].y < grid_y - _NODE_HEIGHT


def test_box_offset_matches_half_width_and_half_height_on_axes() -> None:
    assert math.isclose(_box_offset(1.0, 0.0), _NODE_WIDTH / 2)
    assert math.isclose(_box_offset(0.0, 1.0), _NODE_HEIGHT / 2)


def test_box_offset_never_exceeds_half_width() -> None:
    """The inscribed-ellipse offset must never overshoot the box's own half-width, whatever the
    angle -- that overshoot was exactly what inverted an edge between vertically-adjacent nodes
    into a malformed arrow (offset from both ends summing to more than the row gap)."""
    for angle_deg in range(0, 360, 15):
        angle = math.radians(angle_deg)
        offset = _box_offset(math.cos(angle), math.sin(angle))
        assert offset <= _NODE_WIDTH / 2 + 1e-9


def test_render_library_graph_writes_a_nonempty_file(tmp_path: Path) -> None:
    graph = build_library_graph(LIBRARIES["mask"])
    out_path = tmp_path / "mask.png"
    render_library_graph(graph, out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_render_library_graph_handles_an_edgeless_library(tmp_path: Path) -> None:
    """No primitives at all -- every node isolated, zero edges -- must still render, not crash."""
    empty = build_library_graph(Library(name="empty", primitives=()))
    out_path = tmp_path / "empty.png"
    render_library_graph(empty, out_path)
    assert out_path.exists()
