"""``arc-lab lint-checks``: print (or write) the generated ladder-lint check register.

Reads nothing but ``CHECK_PLAN`` -- each check declares its own code, family, stage, severity and
summary -- so the register is a projection of the code, never a parallel list to keep in step.
``--out`` writes the committed copy that ``test_check_register.py`` pins.
"""

from __future__ import annotations

from pathlib import Path

import typer

from arc_lab.program_search.ladders.checks.register import render_register


def lint_checks_command(
    out: Path = typer.Option(
        None,
        "--out",
        help="Write the register here instead of printing it (the committed copy lives at "
        "docs/abstraction_ladders/LINT-CHECKS.md).",
    ),
) -> None:
    """Print (or write) the generated ladder-lint check register.

    A projection of ``CHECK_PLAN``, never a parallel list to keep in step.
    """
    text = render_register()
    if out is None:
        typer.echo(text, nl=False)
        return
    out.write_text(text)
    typer.echo(f"wrote {out}")
