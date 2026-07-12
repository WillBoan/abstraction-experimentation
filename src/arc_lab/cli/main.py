"""The ``arc-lab`` entry point: app assembly + the logging callback.

Thin by design (EXECUTION.md): one module per command, arg-parse + dispatch only —
all behavior lives in ``program_search/execution/``. The old solver-driving CLI
survives as ``arc_lab.cli_legacy`` until the old tree's deletion pass.
"""

from __future__ import annotations

import logging
import os
import sys

import typer

from . import (
    analyze_run,
    configs,
    datasets,
    estimate,
    learn,
    run_study,
    runs,
    search,
    show,
    taskgen,
)

app = typer.Typer(add_completion=False, help="ARC-AGI experimentation sandbox.")

#: Logger subtree the search / learn / execution stack traces under.
_TRACE_LOGGER = "arc_lab.program_search"
_LOG_FORMAT = "%(name)s %(levelname)s %(message)s"


def _configure_logging(verbosity: int) -> None:
    """Enable tracing on stderr; ``ARC_LAB_LOG`` overrides the ``-v`` count.

    Off by default (no handler installed, so tracing costs nothing). ``-v`` shows INFO
    run/iteration summaries; ``-vv`` the DEBUG per-candidate trace. Only the
    ``arc_lab.program_search`` subtree is lowered, so third-party loggers stay quiet.
    """
    env = os.environ.get("ARC_LAB_LOG")
    if env:
        level = logging.getLevelNamesMapping().get(env.upper(), logging.INFO)
    elif verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        return
    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT, stream=sys.stderr)
    logging.getLogger(_TRACE_LOGGER).setLevel(level)


@app.callback()
def main(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="-v: INFO summaries, -vv: DEBUG per-candidate trace (or set ARC_LAB_LOG).",
    ),
) -> None:
    """ARC-AGI experimentation sandbox."""
    _configure_logging(verbose)


app.command(name="search")(search.search)
app.command(name="estimate")(estimate.estimate)
app.command(name="learn")(learn.learn)
app.command(name="run-study")(run_study.run_study_command)
app.command(name="analyze-run")(analyze_run.analyze_run_command)
app.command(name="taskgen")(taskgen.taskgen)
app.command(name="runs")(runs.list_runs)
app.command(name="configs")(configs.list_configs)
app.command(name="datasets")(datasets.list_datasets)
app.command(name="show")(show.show)


if __name__ == "__main__":  # pragma: no cover
    app()
