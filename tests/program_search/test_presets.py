"""The preset / study / generator registries: serde identity, resolution, E1 wiring."""

from __future__ import annotations

import pytest

from arc_lab.program_search.execution.model import Config
from arc_lab.program_search.execution.presets import PRESETS, resolve_config
from arc_lab.program_search.execution.studies import STUDIES, make_study
from arc_lab.taskgen.generators import GENERATORS, generate


def test_every_preset_round_trips_the_run_identity_serde() -> None:
    for name, config in PRESETS.items():
        assert Config.from_dict(config.to_dict()) == config, f"preset {name!r}"
        assert config.learn is None, f"preset {name!r} must be a SEARCH config"


def test_unknown_names_fail_loudly() -> None:
    with pytest.raises(KeyError, match="unknown config preset"):
        resolve_config("nope")
    with pytest.raises(KeyError, match="unknown study"):
        make_study("nope")
    with pytest.raises(KeyError, match="unknown generator"):
        generate("nope", out_root=None)  # type: ignore[arg-type]  # raises before use


def test_e1_study_builds_from_the_committed_testbed() -> None:
    spec = make_study("e1-rot90")
    assert len(spec.train_corpus) == 8
    assert len(spec.eval_corpus) == 4
    assert spec.base_config.learn is not None
    assert [t.name for t in spec.target_abstractions] == ["rot90"]
    # the target's generators are IN the starting library; the target itself is not
    assert "flip_h" in spec.base_config.library
    assert "rot90" not in spec.base_config.library


def test_registries_share_names_where_a_study_has_a_generator() -> None:
    assert set(STUDIES) <= set(GENERATORS)
