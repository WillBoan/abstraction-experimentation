"""``arc-lab probe-ladder``: drive one ladder's rungs through the real engine, one cell at a time.

The design-time inner loop between lint and the certificate. Unlike ``run-ladder`` (a full climb
plus the oracle chain, gated on a certificate and writing the ladder's artifacts), this searches
ONE rung cell at a time and prints what search actually retained -- so a collapsed rung, a task
collision or a wrong mint is visible while the `.ladder` file is still being written.

Each cell IS a recorded run (2026-07-26), so re-probing an unchanged rung is a cache hit rather
than a fresh enumeration and a crash mid-sweep resumes. They are namespaced as probe cells and
hidden from ``arc-lab runs`` unless you ask (`--probes`): scratch, not results.

**The probe convicts; only the certificate acquits.** An INCONCLUSIVE cell is a non-result by
design -- raising ``--guard`` buys a longer search, never a verdict. Lint first: it settles
statically, in ~1s, everything it can see, including the breadth census that usually explains an
expensive cell before it is run.

Exits non-zero when any probed rung fails, so it works in a script or a hook.
"""

from __future__ import annotations

import dataclasses

import typer

from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.load import draft_spec
from arc_lab.program_search.ladders.probe import probe_ladder, probe_rung, render_probes
from arc_lab.program_search.ladders.registry import load_ladder


def probe_ladder_command(
    name: str = typer.Argument(..., help="Ladder name (its `.ladder` filename stem)."),
    level: int = typer.Option(
        None, "--level", "-l", help="Probe only this rung level (1..k); omit for every rung."
    ),
    guard: int = typer.Option(
        None,
        "--guard",
        help="Override the compute guard for this probe. RAISING IT CANNOT PRODUCE AN "
        "ACQUITTAL -- an INCONCLUSIVE cell is a non-result by design, and a bigger guard buys a "
        "longer wait, not a verdict. Lower it for a fast smoke probe; only `run-ladder` acquits.",
    ),
) -> None:
    try:
        spec = draft_spec(load_ladder(name))
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except LadderFormatError as exc:
        typer.echo(f"{name}: LOAD FAILED -- {exc}")
        raise typer.Exit(code=1) from exc

    budget = spec.reference_config.budget
    if guard is not None:
        # `considered_limit` is `None` for an unguarded budget, which no raise can exceed.
        current = budget.considered_limit
        if current is not None and guard > current:
            typer.echo(
                f"note: guard raised {current:,} -> {guard:,}. This buys a longer "
                "search, NOT a stronger verdict -- the probe convicts, only the certificate "
                "acquits. If a cell is INCONCLUSIVE, run `run-ladder` rather than escalating here.",
                err=True,
            )
        budget = dataclasses.replace(budget, considered_limit=guard)
    if level is not None and not 1 <= level <= len(spec.rungs):
        raise typer.BadParameter(f"level must be 1..{len(spec.rungs)} for {name}")

    probes = (
        (probe_rung(spec, level, budget=budget),)
        if level is not None
        else probe_ladder(spec, budget=budget)
    )
    typer.echo(render_probes(probes))
    failed = [probe for probe in probes if not probe.ok]
    typer.echo(f"\n{len(probes) - len(failed)}/{len(probes)} rungs probe clean")
    if failed:
        raise typer.Exit(code=1)
