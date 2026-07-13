"""``arc-lab learn <config> --corpus <train> [--eval-corpus <eval>]`` — SEARCH + LEARN."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.run_search_learn import run_search_learn
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine

from ._config import resolve_config_arg
from ._corpora import load_corpus
from ._trace import build_trace_spec


def learn(
    config: str = typer.Argument(..., help="Config preset name or a JSON config file."),
    corpus: str = typer.Option(..., help="Train corpus: dataset, testbed, or testbed:split."),
    eval_corpus: str | None = typer.Option(
        None, help="Optional eval corpus — never touched by the loop; grades transfer."
    ),
    iterations: int = typer.Option(5, help="Max wake-sleep cycles (early-stops on convergence)."),
    set_: list[str] = typer.Option(
        [],
        "--set",
        help="Override a Config field by dotted path (applies AFTER the LearnSpec "
        "is attached, so `learn.iterations=3`-style paths work too).",
    ),
    sample: list[str] = typer.Option(
        [],
        "--sample",
        help="Reservoir sample spec 'k:mode' (mode: first_k, cheapest_k), repeatable. "
        "Default: a small first_k sampler. Applies to every wake and derived SEARCH run.",
    ),
    track_all: bool = typer.Option(
        False,
        "--track-all",
        help="Capture every considered candidate to capture/iter-<n>/<task>.jsonl per wake.",
    ),
    capture_max: int = typer.Option(
        100_000, "--capture-max", help="Cap on captured candidates per task with --track-all."
    ),
    force_recapture: bool = typer.Option(
        False,
        "--force-recapture",
        help="Re-execute already-completed runs to (re)populate tracing artifacts.",
    ),
) -> None:
    """Run the wake-sleep loop, then the derived SEARCH runs (2-3 recorded runs)."""
    preset = resolve_config_arg(config, [])
    learn_config = preset.with_(
        learn=preset.learn
        if preset.learn is not None
        else LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=iterations,
        )
    )
    if set_:
        from arc_lab.program_search.execution.overrides import apply_overrides, parse_set_values

        try:
            learn_config = apply_overrides(learn_config, parse_set_values(set_))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    train = load_corpus(corpus)
    evaluation = load_corpus(eval_corpus) if eval_corpus is not None else None
    trace_spec = build_trace_spec(sample, track_all, capture_max)
    typer.echo(f"learning with {config} on {train.name} ({len(train)} tasks)...")
    result = run_search_learn(
        learn_config,
        train,
        evaluation,
        runs_root=None,
        trace=trace_spec,
        force_recapture=force_recapture,
    )

    learned = result.learn.results()
    typer.echo(
        f"learn run {result.learn.run_id}: iterations={learned.get('iterations_run')} "
        f"converged={learned.get('converged')} added={learned.get('added')} "
        f"library_size={learned.get('library_size')}"
    )
    usefulness = result.train_usefulness.results()
    typer.echo(
        f"train-usefulness run {result.train_usefulness.run_id}: "
        f"solved {usefulness.get('solved')}/{usefulness.get('task_count')}"
    )
    if result.transfer is not None:
        transfer = result.transfer.results()
        typer.echo(
            f"transfer run {result.transfer.run_id}: "
            f"solved {transfer.get('solved')}/{transfer.get('task_count')}"
        )
