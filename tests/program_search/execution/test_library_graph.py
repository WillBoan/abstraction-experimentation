"""``library_graph``: the type-flow DAG builder and its DOT/Mermaid renderers."""

from __future__ import annotations

from arc_lab.program_search.execution.library_graph import build_library_graph, to_dot, to_mermaid
from arc_lab.program_search.execution.presets import SYMMETRY_LIBRARY
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.build import ADD
from arc_lab.program_search.substrate.primitives.control import AND, EQ, IF
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.higher_order import HOF_LIBRARY
from arc_lab.program_search.substrate.primitives.mask import CROP_TO_MASK, MASK_BY_COLOR
from arc_lab.program_search.substrate.primitives.pairs import FST, PAIR


def test_d4_bundles_all_eight_transforms_onto_one_self_loop() -> None:
    graph = build_library_graph(D4_LIBRARY)
    node_ids = {n.node_id for n in graph.nodes}
    # Every type a constant policy could mint appears, whether or not this library consumes it —
    # `leaf_seed_names` is a documented over-approximation (D4 has no int/color/bool primitive
    # either). The addressing types joined that set, so they show up here for the same reason.
    assert node_ids == {"grid", "int", "color", "bool", "coord", "offset"}
    (edge,) = graph.edges
    assert edge.source == "grid" and edge.target == "grid"
    assert set(edge.primitives) == set(D4_LIBRARY.names())
    assert all(n.reachable for n in graph.nodes)
    assert graph.flags == ()


def test_mask_intro_elim_and_set_algebra_are_distinct_edges() -> None:
    library = Library(
        name="mask-test", primitives=(*D4_LIBRARY.primitives, MASK_BY_COLOR, CROP_TO_MASK)
    )
    graph = build_library_graph(library)
    edge_map = {(e.source, e.target): e.primitives for e in graph.edges}
    assert edge_map[("color", "mask")] == ("mask_by_color",)
    assert edge_map[("grid", "mask")] == ("mask_by_color",)
    assert edge_map[("mask", "grid")] == ("crop_to_mask",)


def test_dead_types_are_marked_unreachable_but_edges_still_drawn() -> None:
    """Without constant_sources, overlay/tile's Color/Int source is unreachable — the node is
    flagged, but the edge is still drawn (it's a structural relationship, not a liveness claim)."""
    graph = build_library_graph(SYMMETRY_LIBRARY, constant_sources=())
    nodes = {n.node_id: n for n in graph.nodes}
    assert not nodes["color"].reachable
    assert not nodes["int"].reachable
    assert nodes["grid"].reachable
    edge_sources = {e.source for e in graph.edges}
    assert "color" in edge_sources
    assert "int" in edge_sources


def test_polymorphic_typevar_primitives_route_through_the_synthetic_any_node() -> None:
    library = Library(name="poly", primitives=(ADD, EQ, AND, IF, PAIR, FST))
    graph = build_library_graph(library)
    poly_nodes = [n for n in graph.nodes if n.kind == "synthetic"]
    assert [n.node_id for n in poly_nodes] == ["any"]
    edge_map = {(e.source, e.target): e.primitives for e in graph.edges}
    assert "eq" in edge_map[("any", "bool")]
    assert "fst" in edge_map[("pair", "any")]
    assert "if" in edge_map[("any", "any")]
    assert "if" in edge_map[("bool", "any")]
    # grid never appears in any edge — nothing in this bundle touches it.
    assert not any(e.source == "grid" or e.target == "grid" for e in graph.edges)


def test_function_typed_holes_are_omitted_from_edges_and_flagged() -> None:
    graph = build_library_graph(HOF_LIBRARY)
    assert not any("map" in e.primitives and e.source not in {"list"} for e in graph.edges)
    assert len(graph.flags) == 1
    assert "map" in graph.flags[0]
    # map's list[a] -> list[b] sibling param still contributes a plain list -> list edge.
    edge_map = {(e.source, e.target): e.primitives for e in graph.edges}
    assert "map" in edge_map[("list", "list")]


def test_to_dot_is_well_formed_and_quotes_labels() -> None:
    graph = build_library_graph(D4_LIBRARY)
    text = to_dot(graph)
    assert text.startswith('digraph "d4" {')
    assert text.rstrip().endswith("}")
    assert '"grid" -> "grid"' in text


def test_to_mermaid_uses_slugged_ids_and_classdef_for_unreachable() -> None:
    graph = build_library_graph(SYMMETRY_LIBRARY, constant_sources=())
    text = to_mermaid(graph)
    assert text.startswith("flowchart LR")
    assert "classDef unreachable" in text
    assert "class " in text  # at least one node classed unreachable


def test_every_node_referenced_by_an_edge_is_declared() -> None:
    """A rendering sanity net: DOT/Mermaid would silently draw a phantom node otherwise."""
    for library in (D4_LIBRARY, SYMMETRY_LIBRARY, HOF_LIBRARY):
        graph = build_library_graph(library)
        node_ids = {n.node_id for n in graph.nodes}
        for edge in graph.edges:
            assert edge.source in node_ids
            assert edge.target in node_ids
