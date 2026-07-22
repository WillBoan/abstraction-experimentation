"""``forecast_cost``: the calibrated per-round prediction (vs ``estimate_cost``'s worst-case bound)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from arc_lab.core.dataset import Corpus
from arc_lab.core.task import Task
from arc_lab.program_search.execution.estimate_cost import estimate_cost
from arc_lab.program_search.execution.forecast_cost import (
    forecast_cost,
    survival_from,
)
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.search.search_result import SearchResult


def _cell(ladder: str, level: int) -> tuple[Config, Task]:
    """One rung cell: the ladder's config with the library it actually searches under."""
    spec = make_ladder(ladder)
    library = spec.oracle_library(level - 1)
    task = next(
        e.task
        for e in spec.train_corpus.entries
        if e.task.task_id == spec.rungs[level - 1].demonstrations[0].task_id
    )
    return replace(spec.reference_config, library=library), task


def _run(config: Config, task: Task) -> SearchResult:
    return config.search_engine.run(
        train_examples=task.train,
        library=config.library,
        constraints=config.constraints,
        cost=config.cost,
        budget=config.budget,
    )


def test_forecast_is_exact_on_a_monomorphic_floor_given_the_real_survival() -> None:
    # al2's floor is two unary GRID primitives and no constants: with the survival rates the run
    # itself measured, the model's per-round `composed` must reproduce the funnel EXACTLY --
    # typed census x new-layer restriction is the engine's own composition rule, not an estimate.
    config, task = _cell("al2-rot90-calibration", 1)
    result = _run(config, task)
    actual = [g["composed"] for g in result.stats.generations]
    forecast = forecast_cost(config, task, survival=survival_from(result.stats))
    assert [r.composed for r in forecast.rounds] == actual


def test_the_new_layer_restriction_is_modelled() -> None:
    # Without it, round 2 over a 3-entry pool would be 2 x 3 = 6 for two unary primitives; the
    # engine only composes tuples using an argument from the previous round, so it is 2 x (3-1).
    config, task = _cell("al2-rot90-calibration", 1)
    result = _run(config, task)
    forecast = forecast_cost(config, task, survival=survival_from(result.stats))
    pool_before_round_2 = sum(forecast.rounds[2].census.values())
    assert forecast.rounds[2].composed < 2 * pool_before_round_2


def test_typing_the_pool_beats_the_untyped_ceiling_by_orders_of_magnitude() -> None:
    # al14's cell floor is where an untyped pool**arity bound diverges from reality: set_cell is
    # arity 4, so the ceiling is pool**4 while the truth is |grid| x |int| x |int| x |color|.
    config, task = _cell("al14-cell-row-grid", 1)
    forecast = forecast_cost(config, task)
    ceiling = estimate_cost(RunSpec(config=config, corpus=Corpus.of("t", [task])))
    assert forecast.total_considered * 1000 < ceiling.total_considered_ceiling


def test_the_dominant_factor_is_attributed_per_round() -> None:
    # The point of the typed census: it names WHICH product term is eating the budget.
    config, task = _cell("al14-cell-row-grid", 1)
    forecast = forecast_cost(config, task)
    dominant = forecast.dominant_round
    assert dominant is not None
    assert "set_cell" in dominant.dominant
    assert "int(" in dominant.dominant and "grid(" in dominant.dominant


def test_survival_from_reads_the_funnel() -> None:
    config, task = _cell("al1-mirror", 1)
    rates = survival_from(_run(config, task).stats)
    assert rates and all(0.0 <= rate <= 1.0 for rate in rates)


def test_a_survival_profile_is_carried_forward_past_the_rounds_it_covers() -> None:
    # The calibration mode: measure two cheap rounds, project deeper ones with the last rate.
    config, task = _cell("al1-mirror", 1)
    deep = forecast_cost(config, task, survival=(1.0, 0.5), depth_limit=4)
    assert len(deep.rounds) == 5
    assert all(r.composed > 0 for r in deep.rounds)


def test_a_learn_config_is_flagged_as_wake_zero_only() -> None:
    config, task = _cell("al1-mirror", 1)
    assert any("wake iteration 0" in flag for flag in forecast_cost(config, task).flags)


class _NotAnEngine:
    """Stands in for a future non-bottom-up engine: modelling one would be a guess."""


def test_a_non_bottom_up_engine_is_refused_rather_than_guessed() -> None:
    # The guard is a RUNTIME one, so the test has to get past the type checker to exercise it:
    # `--strict` already rejects a non-SearchEngine here, which is the point of the ignore.
    config, task = _cell("al1-mirror", 1)
    with pytest.raises(NotImplementedError):
        forecast_cost(
            replace(config, search_engine=_NotAnEngine()),  # type: ignore[arg-type]
            task,
        )


def test_saturation_is_flagged_rather_than_reported_as_a_cheap_deep_round() -> None:
    # Past the round where `max_pool` freezes the modelled census, the new-layer restriction makes
    # every deeper round exactly zero -- which reads as "depth 6 is free" unless it is labelled.
    # The 2026-07-22 frontier sweep measured the real gap at that point: ~0.15x, i.e. the engine
    # composes nearly 7x what the model does, because it truncates cheapest-first.
    config, task = _cell("al1-mirror", 1)
    forecast = forecast_cost(config, task, depth_limit=6)
    saturated_at = forecast.saturated_at
    assert saturated_at is not None
    assert all(r.composed == 0 and r.saturated for r in forecast.rounds[saturated_at:])
    assert all(not r.saturated for r in forecast.rounds[:saturated_at])
    assert any("LOWER BOUND" in flag for flag in forecast.flags)


def test_a_pool_that_does_not_bind_is_not_flagged_as_saturated() -> None:
    # The negative that makes the flag mean something: same cell, same depth, pool freed.
    config, task = _cell("al1-mirror", 1)
    freed = replace(config, budget=replace(config.budget, max_pool=50_000))
    forecast = forecast_cost(freed, task, depth_limit=4)
    assert forecast.saturated_at is None
    assert not any("SATURATED" in flag for flag in forecast.flags)
