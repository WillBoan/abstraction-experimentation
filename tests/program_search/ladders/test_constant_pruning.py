"""Value-level constant pruning: the other half of an optimally-pruned cell.

Library pruning drops whole TYPES for free (``leaves._type_in_use`` gates minting on whether any
primitive mentions the type), and on some rungs that is the entire story. On others it does nothing
at all, because the type survives and the whole typed battery comes with it — so a cell offering
only library pruning reports "this rung is expensive" where the truth is "its constant battery is".
These tests pin that both prunings exist and that neither subsumes the other.

They also pin the thing that made the field cheap to add: it is omitted from the serialised form
when unset, so **no existing ``run_id`` moved**.
"""

from __future__ import annotations

from arc_lab.program_search.execution.model.serde import to_data
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.ladders.probe import constant_allowlist_for, prune_library
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine


def test_adding_the_field_moved_no_run_id() -> None:
    """``constant_allowlist=None`` must serialise to NOTHING.

    This is what let an oracle knob be added to a search engine without invalidating every cached
    run and every committed artifact in the repo. It is sound only because ``None`` means "no
    restriction" — the engine mints exactly what it minted before the field existed — so a run
    under it IS the recorded run, not merely one like it.
    """
    engine = PRESETS["synth"].search_engine
    assert isinstance(engine, BottomUpSearchEngine)
    assert engine.constant_allowlist is None
    assert "constant_allowlist" not in to_data(engine)

    # ...and it appears the moment it means something, so a pruned cell is a DIFFERENT run.
    import dataclasses

    restricted = dataclasses.replace(engine, constant_allowlist=("int=1",))
    assert to_data(restricted)["constant_allowlist"] == ["int=1"]
    assert to_data(restricted) != to_data(engine)


def test_the_allowlist_is_the_values_the_program_uses() -> None:
    """Read off the answer — an oracle, which is why it may only price a floor, never run one."""
    spec = make_ladder("dae9d2b5-halves-union")
    west, east = spec.rungs  # west takes no constant; east indexes with 1

    assert constant_allowlist_for(west.template) == ()
    assert constant_allowlist_for(east.template) == ("int=1",)


def test_library_pruning_and_value_pruning_do_not_subsume_each_other() -> None:
    """The measurement that motivated the field.

    On `al14-cell-row-grid`'s `move_cell_up`, pruning the LIBRARY to the primitives the program
    references leaves round-1 width completely unchanged — every primitive it uses survives, so the
    INT/COLOR batteries come with them. Only value pruning moves it. A floor-tax cell built on
    library pruning alone would report a ratio of 1.0x on this rung and call it `clean`.
    """
    by_name = {entry.name: entry for entry in make_ladder("al14-cell-row-grid").lint().breadth}
    cell = by_name["move_cell_up"]

    assert cell.b1_primitive_pruned == cell.b1_full  # library pruning buys NOTHING here
    assert cell.b1_constant_pruned < cell.b1_full  # value pruning is the whole story
    assert cell.b1_min == cell.b1_constant_pruned

    # ...and the converse case, where library pruning is the whole story.
    west = {e.name: e for e in make_ladder("dae9d2b5-halves-union").lint().breadth}["west"]
    assert west.b1_primitive_pruned < west.b1_full


def test_pruning_a_library_drops_the_types_no_survivor_mentions() -> None:
    """Why the two prunings overlap at all: the coarse gate is real, it is just not sufficient."""
    spec = make_ladder("dae9d2b5-halves-union")
    floor = spec.floor()
    west = spec.rungs[0]

    pruned = prune_library(floor, west.template)
    assert "map_color" in floor.names() and "map_color" not in pruned.names()
    # `map_color`/`overlay` are the only COLOR-taking primitives, so the whole battery goes with
    # them -- which is why `west`'s irreducible width is 1 rather than 11.
    assert not any("color" in str(p.param_types).lower() for p in pruned.primitives)
