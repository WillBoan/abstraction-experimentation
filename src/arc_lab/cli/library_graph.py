"""``arc-lab library-graph <library>`` -- a type-flow diagram for a bundle of primitives.

Defaults to a rendered PNG saved straight to a file -- no external renderer needed. ``--format
dot``/``mermaid`` still emit the interoperable text forms (for piping to Graphviz or embedding in
a markdown doc) if you want those instead.
"""

from __future__ import annotations

from pathlib import Path

import typer

from arc_lab.program_search.execution.library_graph import (
    build_library_graph,
    to_dot,
    to_mermaid,
)
from arc_lab.program_search.execution.presets import resolve_library
from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.viz.library_graph_render import render_library_graph

_KNOWN_CONSTANT_SOURCES: tuple[ConstantSource, ...] = (
    "finite-enumerate",
    "harvest-from-instance",
    "parameterize",
)
_TEXT_RENDERERS = {"dot": to_dot, "mermaid": to_mermaid}
_IMAGE_FORMATS = {"png", "svg"}
_KNOWN_FORMATS = {*_TEXT_RENDERERS, *_IMAGE_FORMATS}


def library_graph_command(
    library: str = typer.Argument(..., help="Library name (see `arc-lab configs`) or preset name."),
    format_: str = typer.Option(
        "png", "--format", "-f", help="png | svg (rendered image, saved to a file) | dot | mermaid."
    ),
    constant_sources: list[str] = typer.Option(
        ["finite-enumerate"],
        "--constant-sources",
        help="ConstantSource(s) assumed available (finite-enumerate / harvest-from-instance).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path. Defaults to <library>-graph.<format> for png/svg.",
    ),
) -> None:
    """Emit a type-flow diagram for a library: nodes are types, edges are the primitives that
    connect them (bundled -- one edge per (source, target) type pair, not per primitive)."""
    if format_ not in _KNOWN_FORMATS:
        raise typer.BadParameter(
            f"unknown format {format_!r}; known: {', '.join(sorted(_KNOWN_FORMATS))}"
        )
    for source in constant_sources:
        if source not in _KNOWN_CONSTANT_SOURCES:
            raise typer.BadParameter(
                f"unknown constant source {source!r}; known: {', '.join(_KNOWN_CONSTANT_SOURCES)}"
            )
    try:
        lib = resolve_library(library)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    sources = tuple(source for source in _KNOWN_CONSTANT_SOURCES if source in constant_sources)
    graph = build_library_graph(lib, constant_sources=sources)

    if format_ in _IMAGE_FORMATS:
        out_path = output if output is not None else Path(f"{library}-graph.{format_}")
        render_library_graph(graph, out_path)
        typer.echo(
            f"wrote {graph.library_name} graph ({len(graph.nodes)} nodes, "
            f"{len(graph.edges)} edges) to {out_path}"
        )
    else:
        text = _TEXT_RENDERERS[format_](graph)
        if output is not None:
            output.write_text(text + "\n", encoding="utf-8")
            typer.echo(
                f"wrote {format_} graph ({len(graph.nodes)} nodes, {len(graph.edges)} edges) "
                f"to {output}"
            )
        else:
            typer.echo(text)
    for flag in graph.flags:
        typer.echo(f"# {flag}", err=True)
