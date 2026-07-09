"""Config presets wire the expected (library x search x cost), and params are data.

These presets replaced the config-as-subclass solvers; the regression locks
(``tests/test_integration.py``) pin their *behaviour*, while this file pins their *wiring*.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.dsl.config import PRESETS, Config
from arc_lab.solvers.dsl.search.composite import CompositeSearch
from arc_lab.solvers.dsl.search.cost import ProgramSize
from arc_lab.solvers.dsl.search.enumerate import BeamSearch, Enumerate
from arc_lab.solvers.dsl.solver import ProgramSearchSolver

#: name -> (library name, search class)
_EXPECTED = {
    "dsl": ("d4", "SingleApply"),
    "dsl-sym": ("d4+combinators", "CompositeSearch"),
    "dsl-synth": ("atomic", "Enumerate"),
    "dsl-beam": ("atomic", "BeamSearch"),
}


def test_presets_wire_expected_library_and_search() -> None:
    for name, (lib_name, search_type) in _EXPECTED.items():
        solver = ProgramSearchSolver.from_config(PRESETS[name])
        assert solver.name == name
        assert solver.library.name == lib_name
        assert type(solver.search).__name__ == search_type
        assert isinstance(solver.cost, ProgramSize)


def test_enumerate_and_beam_params_match() -> None:
    synth = ProgramSearchSolver.from_config(PRESETS["dsl-synth"])
    assert isinstance(synth.search, Enumerate)
    assert synth.search.max_depth == 2

    beam = ProgramSearchSolver.from_config(PRESETS["dsl-beam"])
    assert isinstance(beam.search, BeamSearch)
    assert beam.search.beam_width == 16
    assert beam.search.max_depth == 2


def test_composite_wires_three_leaf_strategies() -> None:
    built = ProgramSearchSolver.from_config(PRESETS["dsl-sym"])
    assert isinstance(built.search, CompositeSearch)
    assert [type(s).__name__ for s in built.search.strategies] == [
        "SingleApply",
        "OverlaySearch",
        "TileSearch",
    ]


def test_with_param_overrides_search_param() -> None:
    tightened = PRESETS["dsl-synth"].with_param(max_depth=1)
    solver = ProgramSearchSolver.from_config(tightened)
    assert isinstance(solver.search, Enumerate)
    assert solver.search.max_depth == 1
    # The original preset is unchanged (Config is frozen; with_param returns a copy).
    assert PRESETS["dsl-synth"].search.max_depth == 2


def test_config_round_trips_through_dict() -> None:
    # RunSpec holds a live Config and reconstructs it from results.json via Config.from_dict.
    for cfg in PRESETS.values():
        assert Config.from_dict(cfg.to_dict()) == cfg
    tightened = PRESETS["dsl-synth"].with_param(max_depth=1)
    assert Config.from_dict(tightened.to_dict()) == tightened


def test_config_is_hashable() -> None:
    # A run's identity (Phase 11) hangs off this: equal configs hash equal.
    assert hash(PRESETS["dsl-synth"]) == hash(PRESETS["dsl-synth"].with_param(max_depth=2))
    assert PRESETS["dsl-synth"] == PRESETS["dsl-synth"].with_param(max_depth=2)


def test_dsl_preset_solves_a_flip_task() -> None:
    # Equivalence smoke: the dsl preset solves the canonical whole-grid flip.
    grid_in = Grid.from_list([[1, 2], [3, 4]])
    grid_out = Grid.from_list([[2, 1], [4, 3]])
    task = Task(
        task_id="flip", train=(Example(grid_in, grid_out),), test=(Example(grid_in, grid_out),)
    )
    solver = ProgramSearchSolver.from_config(PRESETS["dsl"])
    solved, _ = score_task(task, solver.predict(task))
    assert solved is True
