"""``arc-lab check-library-coherence <library>`` — a static, no-execution vocabulary diagnostic."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.bundle_sheet import library_from_names
from arc_lab.program_search.execution.check_coherence import check_library_coherence
from arc_lab.program_search.execution.presets import resolve_library
from arc_lab.program_search.search.leaves import ConstantSource

_KNOWN_CONSTANT_SOURCES: tuple[ConstantSource, ...] = (
    "finite-enumerate",
    "harvest-from-instance",
    "parameterize",
)


def check_library_coherence_command(
    library: str | None = typer.Argument(
        None,
        help="Library/preset/bundle name (see `arc-lab configs`) — omit if using --primitives.",
    ),
    primitives: str | None = typer.Option(
        None,
        "--primitives",
        help="Comma-separated base primitive names — an ad hoc bundle, no registration needed.",
    ),
    name: str = typer.Option(
        "adhoc", "--name", help="Display name for an ad hoc --primitives bundle."
    ),
    constant_sources: list[str] = typer.Option(
        ["finite-enumerate"],
        "--constant-sources",
        help="ConstantSource(s) assumed available (finite-enumerate / harvest-from-instance).",
    ),
) -> None:
    """Check type-closure, goal-directedness, and hole-fill sufficiency for a bundle."""
    if (library is None) == (primitives is None):
        raise typer.BadParameter("pass exactly one of LIBRARY or --primitives")
    for source in constant_sources:
        if source not in _KNOWN_CONSTANT_SOURCES:
            raise typer.BadParameter(
                f"unknown constant source {source!r}; known: {', '.join(_KNOWN_CONSTANT_SOURCES)}"
            )

    try:
        if primitives is not None:
            names = [p.strip() for p in primitives.split(",") if p.strip()]
            lib = library_from_names(names, library_name=name)
        else:
            assert library is not None  # the exactly-one-of check above guarantees this
            lib = resolve_library(library)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    sources = tuple(source for source in _KNOWN_CONSTANT_SOURCES if source in constant_sources)
    report = check_library_coherence(lib, constant_sources=sources)

    typer.echo(
        f"{report.library_name} ({len(lib.primitives)} primitives, "
        f"constant_sources={list(report.constant_sources)}): "
        f"{'COHERENT' if report.is_coherent else 'INCOHERENT'}"
    )
    typer.echo(f"  reachable types: {', '.join(report.reachable_types)}")
    typer.echo(f"  goal-directed (produces grid): {report.goal_directed}")
    if report.dead_primitives:
        typer.echo(f"  dead primitives (never applicable): {', '.join(report.dead_primitives)}")
    for finding in report.findings:
        marker = "!" if finding.severity == "error" else "?"
        typer.echo(f"  {marker} [{finding.check}] {finding.primitive}: {finding.message}")
