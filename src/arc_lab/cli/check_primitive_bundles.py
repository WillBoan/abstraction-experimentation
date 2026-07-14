"""``arc-lab check-primitive-bundles`` — batch coherence check over the candidate bundle sheet
(``execution/bundle_sheet.py``): one summary line per bundle, ``-v`` for full findings."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.bundle_sheet import BUNDLES, resolve_bundle
from arc_lab.program_search.execution.check_coherence import check_library_coherence


def check_primitive_bundles_command(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Also print each bundle's individual findings."
    ),
) -> None:
    """Run ``check_library_coherence`` over every bundle in the candidate sheet."""
    for name in sorted(BUNDLES):
        library, constant_sources = resolve_bundle(name)
        report = check_library_coherence(library, constant_sources=constant_sources)
        errors = sum(1 for f in report.findings if f.severity == "error")
        warnings = sum(1 for f in report.findings if f.severity == "warning")
        status = "COHERENT" if report.is_coherent else "INCOHERENT"
        typer.echo(
            f"{name:20s} {len(library.primitives):2d} prims  {status:10s} "
            f"errors={errors} warnings={warnings}"
        )
        if verbose:
            for finding in report.findings:
                marker = "!" if finding.severity == "error" else "?"
                typer.echo(f"    {marker} [{finding.check}] {finding.primitive}: {finding.message}")
