"""``arc-lab probe-ladder``: drive one ladder's rungs through the real engine, without a run.

The design-time inner loop between lint and the certificate. Unlike ``run-ladder`` (a full climb
plus the oracle chain, recorded and cached), this searches ONE rung cell at a time in process,
records nothing, and prints what search actually retained -- so a collapsed rung, a task collision
or a wrong mint is visible while the `.ladder` file is still being written.

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
    considered_limit: int = typer.Option(
        None,
        "--considered-limit",
        help="Override the reference budget's compute guard for this probe (a censored probe is "
        "inconclusive, so raise it when a cell censors).",
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
    if considered_limit is not None:
        budget = dataclasses.replace(budget, considered_limit=considered_limit)
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
