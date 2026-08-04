"""The --set / config-file override surface: precedence, dotted paths, fail-loud errors."""

from __future__ import annotations

import pytest

from arc_lab.program_search.execution.model import Config, LearnSpec, RunSpec
from arc_lab.program_search.execution.overrides import apply_overrides, parse_set_values
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)


def test_precedence_later_layers_win() -> None:
    base = PRESETS["synth"]  # named preset (defaults already inside)
    file_layer = apply_overrides(base, {"budget.depth_limit": 3, "attempts_per_test": 1})
    cli_layer = apply_overrides(file_layer, {"budget.depth_limit": 4})
    assert base.budget.depth_limit == 2  # presets stay frozen
    assert file_layer.budget.depth_limit == 3
    assert cli_layer.budget.depth_limit == 4  # CLI --set beats the config file
    assert cli_layer.attempts_per_test == 1  # untouched file-layer overrides survive


def test_nested_engine_field_and_library_by_name() -> None:
    config = apply_overrides(PRESETS["beam"], {"search_engine.beam_width": 64, "library": "d4"})
    assert isinstance(config.search_engine, BeamBottomUpSearchEngine)
    assert config.search_engine.beam_width == 64
    assert config.library.name == "d4"


def test_tuple_coercion() -> None:
    config = apply_overrides(
        PRESETS["synth"], {"search_engine.constant_sources": ["harvest-from-instance"]}
    )
    assert isinstance(config.search_engine, BottomUpSearchEngine)
    assert config.search_engine.constant_sources == ("harvest-from-instance",)


def test_learn_paths_work_on_a_learn_config_and_fail_on_search() -> None:
    learn_config = PRESETS["d4"].with_(
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=5)
    )
    assert apply_overrides(learn_config, {"learn.iterations": 3}).learn.iterations == 3  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="learn"):
        apply_overrides(PRESETS["d4"], {"learn.iterations": 3})


def test_unknown_field_and_type_mismatch_fail_loudly() -> None:
    with pytest.raises(ValueError, match=r"unknown field 'depht'.*depth_limit"):
        apply_overrides(PRESETS["d4"], {"budget.depht": 4})
    with pytest.raises(ValueError, match="type mismatch"):
        apply_overrides(PRESETS["d4"], {"budget.depth_limit": "deep"})
    with pytest.raises(ValueError, match="unknown library"):
        apply_overrides(PRESETS["d4"], {"library": "nope"})


def test_stop_limits_are_settable_and_validated() -> None:
    """``_coerce`` cannot type-check a field whose current value is ``None`` (it compares against
    ``type(current)``), so ``Budget.__post_init__`` is what makes a bad ``--set`` fail loudly here
    rather than silently installing a string into the run identity."""
    updated = apply_overrides(PRESETS["d4"], {"budget.considered_limit": 5000})
    assert updated.budget.considered_limit == 5000
    updated = apply_overrides(PRESETS["d4"], {"budget.solution_limit_mode": "immediate"})
    assert updated.budget.solution_limit_mode == "immediate"

    with pytest.raises(ValueError, match="considered_limit"):
        apply_overrides(PRESETS["d4"], {"budget.considered_limit": "garbage"})
    with pytest.raises(ValueError, match="considered_limit"):
        apply_overrides(PRESETS["d4"], {"budget.considered_limit": 0})
    with pytest.raises(ValueError, match="solution_limit_mode"):
        apply_overrides(PRESETS["d4"], {"budget.solution_limit_mode": "eventually"})


def test_an_optional_field_can_be_cleared_back_to_none() -> None:
    """``--set path=null`` clears an optional field -- the only way to express an arm that REMOVES
    a compromise (measured 2026-08-04: the ladder members carrying ``solution_limit: 1`` could not
    be re-run exhaustively at all, because ``_coerce`` sees only the field's CURRENT value, so one
    holding ``1`` looked like a plain ``int``). The declared type is what decides, so a required
    field still refuses."""
    pinned = apply_overrides(PRESETS["d4"], {"budget.solution_limit": 1})
    assert pinned.budget.solution_limit == 1

    cleared = apply_overrides(pinned, {"budget.solution_limit": None})
    assert cleared.budget.solution_limit is None
    # Clearing is a real config change, so the cleared config is not the pinned one (and, being
    # part of `Config`, carries its own `RunSpec` identity -- pinned by the test below).
    assert cleared != pinned

    with pytest.raises(ValueError, match=r"budget.depth_limit.*not an optional field"):
        apply_overrides(PRESETS["d4"], {"budget.depth_limit": None})


def test_parse_set_values() -> None:
    parsed = parse_set_values(["budget.depth_limit=3", "library=d4", "flag=true"])
    assert parsed == {"budget.depth_limit": 3, "library": "d4", "flag": True}
    with pytest.raises(ValueError, match="malformed --set"):
        parse_set_values(["no-equals-sign"])


def test_overridden_config_gets_its_own_run_identity() -> None:
    from arc_lab.core.dataset import Corpus
    from arc_lab.core.grid import Grid
    from arc_lab.core.task import Example, Task

    grid = Grid.from_list([[1, 2], [3, 4]])
    corpus = Corpus.of("c", [Task(task_id="t", train=(Example(input=grid, output=grid),), test=())])
    base = RunSpec(config=PRESETS["d4"], corpus=corpus)
    tweaked = RunSpec(
        config=apply_overrides(PRESETS["d4"], {"budget.depth_limit": 2}), corpus=corpus
    )
    assert base.run_id != tweaked.run_id


def test_component_fields_are_set_by_their_serde_kind() -> None:
    """A machinery component is named by the same ``kind`` string ``to_data`` emits, so ``--set``
    and a `.ladder` config block use the registry's vocabulary (LADDER-FORMAT.md CFG-6)."""
    from arc_lab.program_search.ladders.registry import make_ladder

    def proposer_name(config: Config) -> str:
        assert config.learn is not None
        engine = config.learn.learn_engine
        assert isinstance(engine, GreedyMDLLearnEngine)
        return type(engine.proposer).__name__

    config = make_ladder("al1-mirror").reference_config
    assert proposer_name(config) == "AntiunifyPairs"
    swapped = apply_overrides(config, {"learn.learn_engine.proposer": "FrequentSubtree"})
    assert proposer_name(swapped) == "FrequentSubtree"
    assert type(apply_overrides(config, {"cost": "ProgramSize"}).cost).__name__ == "ProgramSize"


def test_component_override_rejects_the_wrong_interface_and_unknown_kinds() -> None:
    from arc_lab.program_search.ladders.registry import make_ladder

    config = make_ladder("al1-mirror").reference_config
    with pytest.raises(ValueError, match="is not a AbstractionProposer"):
        apply_overrides(config, {"learn.learn_engine.proposer": "BottomUpSearchEngine"})
    with pytest.raises(ValueError, match="unknown component 'Nope'"):
        apply_overrides(config, {"learn.learn_engine.proposer": "Nope"})
