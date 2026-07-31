"""``arc-lab run-ladder``: execute a registered Ladder and print/write its report.

Thin wrapper (all behavior lives in ``program_search/ladders/``): resolve a name from the
registry, render + lint the spec, execute the climb + oracle chain + off-chain run, print the
report JSON. ``--artifacts <dir>`` writes the committed per-ladder docs artifacts (``spec.md``,
``results.md``, ``report.json``) into the ladder's ``docs/abstraction_ladders/ladders/<name>/``
folder. Mirrors ``run-study``.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report, render_report_markdown
from arc_lab.program_search.ladders.run import run_ladder


def run_ladder_command(
    name: str = typer.Argument(..., help="Registered ladder name (ladders/registry)."),
    out: Path | None = typer.Option(None, help="Also write the report JSON to this path."),
    artifacts: Path | None = typer.Option(
        None,
        help="Write the committed docs artifacts (spec.md, results.md, report.json) "
        "into this directory (the ladder's docs/abstraction_ladders/ladders/<name>/ folder).",
    ),
    climb_rejected: bool = typer.Option(
        False,
        "--climb-rejected",
        help="Run the climb stage even if the certificate rejects -- for control arms whose "
        "measurement IS the climb under a rejected structure, never for ordinary ladders.",
    ),
    raw_arm_k: int = typer.Option(
        10,
        "--raw-arm-k",
        help="RQ1 claim strength: the raw arm's guard is K x the measured laddered cost. If the "
        "arm censors, the amortization ratio is proven >= K; if it solves, the ratio is measured.",
    ),
) -> None:
    """Execute a registered Ladder end-to-end and print (or write) its certificate report.

    Renders and lints the spec, then runs the climb, the oracle chain and the off-chain arm.
    """
    try:
        spec = make_ladder(name)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(spec.render())
    if not spec.lint().ok:
        typer.echo("WARNING: ladder lint has errors (see the render above); running anyway.")
    typer.echo(f"running ladder {name} (chain + certificate first; climb only if admitted)...")
    result = run_ladder(spec, runs_root=None, climb_rejected=climb_rejected, raw_arm_k=raw_arm_k)
    if result.certificate.admitted:
        typer.echo("certificate: ADMITTED -- climb executed.")
    elif result.climbed:
        typer.echo("certificate: NOT ADMITTED -- climb forced by --climb-rejected.")
    else:
        typer.echo(
            "certificate: NOT ADMITTED -- climb skipped (no learning paid; "
            "pass --climb-rejected to force)."
        )
    report = create_ladder_report(result)
    payload = json.dumps(report, indent=2, sort_keys=True)
    if out is not None:
        out.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote {out}")
    if artifacts is not None:
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "spec.md").write_text(spec.render() + "\n", encoding="utf-8")
        (artifacts / "results.md").write_text(
            render_report_markdown(report) + "\n", encoding="utf-8"
        )
        (artifacts / "report.json").write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote {artifacts}/{{spec.md, results.md, report.json}}")
    else:
        typer.echo(payload)
