"""Compromise Options: named cost/data trades, DETECTED rather than declared.

The failure they exist to prevent is a forgotten label -- a number measured under assistance quoted
next to one that was not. A label you have to remember to set is exactly the one that gets
forgotten, so these tests pin that the detection reads the config itself.
"""

from __future__ import annotations

import dataclasses

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.ladders.compromise import (
    COMPROMISE_OPTIONS,
    PRUNED_LIBRARY,
    SOLUTION_LIMIT,
    compromises_in,
)
from arc_lab.program_search.ladders.probe import prune_library
from arc_lab.program_search.ladders.registry import make_ladder


def _config() -> Config:
    return make_ladder("al21-dag-siblings").reference_config


def test_an_honest_run_is_under_no_option() -> None:
    """The default position. `ladder_default_config` leaves `solution_limit` unset on purpose, so
    one exhaustive run yields cost-to-first AND cost-to-exhaust AND full attribution."""
    assert compromises_in(_config()) == ()


def test_an_oracle_pruned_library_is_detected_and_voids_cost() -> None:
    """The severe one: the library was chosen by reading the answer, so the measured spend is a
    fact about a search nobody could have run."""
    spec = make_ladder("al21-dag-siblings")
    config = _config()
    pruned = config.with_(library=prune_library(config.library, spec.rungs[0].template))

    assert compromises_in(pruned) == (PRUNED_LIBRARY,)
    assert PRUNED_LIBRARY.severity == "voids-cost"


def test_an_early_stop_is_detected_and_narrows_rather_than_voids() -> None:
    """`solution_limit` costs cost-to-exhaust but NOT RQ1: `first_solution_index` is exact either
    way, which is why the raw arm can run under it and still prove a ratio."""
    config = _config()
    stopped = config.with_(budget=dataclasses.replace(config.budget, solution_limit=1))

    assert compromises_in(stopped) == (SOLUTION_LIMIT,)
    assert SOLUTION_LIMIT.severity == "narrows"


def test_options_are_reported_worst_first() -> None:
    """Reporting order is severity order, so the claim-voiding one can never be buried under a
    narrowing one in a banner."""
    config = _config()
    both = config.with_(
        library=prune_library(config.library, make_ladder("al21-dag-siblings").rungs[0].template),
        budget=dataclasses.replace(config.budget, solution_limit=1),
    )
    detected = compromises_in(both)
    assert [o.code for o in detected] == ["pruned-library", "solution-limit"]
    assert detected[0].severity == "voids-cost"


def test_every_registered_option_states_all_three_things() -> None:
    """The registry's contract: saves, forfeits, and when it is justified. An entry missing one of
    those is lore wearing a dataclass."""
    for option in COMPROMISE_OPTIONS:
        assert option.saves.strip()
        assert option.forfeits.strip()
        assert option.when_justified.strip()
        assert option.severity in {"voids-cost", "narrows"}
