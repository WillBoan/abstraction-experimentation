"""The --set / config-file override surface: precedence, dotted paths, fail-loud errors."""

from __future__ import annotations

import pytest

from arc_lab.program_search.execution.model import LearnSpec, RunSpec
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
