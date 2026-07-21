"""``arc-lab ladder-seeds``: deterministic input grids, ready to paste into a `.ladder` file.

A ladder's task inputs are literal grids (docs/abstraction_ladders/LADDER-FORMAT.md TSK-3), which
is what makes a `.ladder` file self-contained -- but hand-picking grids is exactly where a ladder
acquires a literal, constant or identity shortcut. This prints the constructions
:mod:`arc_lab.taskgen.ladders` was built around: varied within a task, varied across tasks, and
asymmetric under both flips.

Output is `.ladder` task lines verbatim:

    arc-lab ladder-seeds --variant 3 --rows 2 --cols 3
        train [[3, 4, 5], [1, 2, 3]]
        train [[5, 1, 2], [4, 5, 1]]
        test  [[2, 3, 4], [5, 1, 2]]

Vary ``--variant`` per task so no two tasks in a ladder share a grid set.
"""

from __future__ import annotations

import json

import typer

from arc_lab.taskgen.ladders import seed_grids, symmetry_repair_seeds


def ladder_seeds_command(
    variant: int = typer.Option(
        ..., help="Separates one task's grids from another's -- use a fresh value per task."
    ),
    rows: int = typer.Option(2, help="Grid height."),
    cols: int = typer.Option(3, help="Grid width."),
    train: int = typer.Option(2, help="How many `train` grids to emit."),
    test: int = typer.Option(1, help="How many `test` grids to emit."),
    palette: str = typer.Option("1,2,3,4,5", help="Comma-separated colours to fill from."),
    background: int | None = typer.Option(
        None,
        help="Frame every grid with this colour and fill only the interior "
        "(mask/crop ladders need it; requires rows and cols >= 3).",
    ),
    mode: str = typer.Option(
        "stride",
        help="`stride` (dense, the default) or `symmetry-repair` (holed grids needing both-axis "
        "repair -- see al13).",
    ),
) -> None:
    colours = tuple(int(part) for part in palette.split(",") if part.strip())
    count = train + test
    try:
        if mode == "symmetry-repair":
            if background is not None:
                raise typer.BadParameter("--background does not apply to symmetry-repair seeds")
            grids = symmetry_repair_seeds(
                count, rows=rows, cols=cols, variant=variant, palette=colours
            )
        elif mode == "stride":
            grids = seed_grids(
                count,
                rows=rows,
                cols=cols,
                variant=variant,
                palette=colours,
                background=background,
            )
        else:
            raise typer.BadParameter(f"unknown --mode {mode!r} (stride | symmetry-repair)")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None

    for index, grid in enumerate(grids):
        keyword = "train" if index < train else "test "
        typer.echo(f"        {keyword} {json.dumps(grid.to_list())}")
