"""The Ladder registry: named :class:`LadderSpec` builders for ``arc-lab run-ladder <name>``.

Each ladder (or family of related ladders) is a builder module here; ``LADDERS`` aggregates them.
Mirrors ``execution/studies.py::STUDIES`` -- a zero-arg factory per name, resolved by
:func:`make_ladder`. Per-ladder *artifacts* (rendered tables, notes) live under
``docs/abstraction_ladders/ladders/<name>/``, not here.
"""

from __future__ import annotations

from collections.abc import Callable

from arc_lab.program_search.ladders.registry import (
    al1_mirror,
    al2_rot90,
    al3_quad,
    al4_mask_crop,
    al5_perceiver,
    al6_mirror_tall,
    al7_fast_tower,
    al8_lean_perceiver,
    al9_decoy,
    al10_skippable,
    al11_greedy_trap,
    al12_unlearnable,
    al13_symmetry_repair,
    al14_cell_row_grid,
    al15_shift_frame,
    al16_layout_nest,
)
from arc_lab.program_search.ladders.spec import LadderSpec

#: LadderSpec builder registry for the CLI (`arc-lab run-ladder <name>`).
LADDERS: dict[str, Callable[[], LadderSpec]] = {
    "al1-mirror": al1_mirror.build,
    "al2-rot90-calibration": al2_rot90.build,
    "al3-quad-symmetrize": al3_quad.build,
    "al4-mask-crop": al4_mask_crop.build,
    "al5-perceiver-chain": al5_perceiver.build,
    "al6-mirror-tall": al6_mirror_tall.build,
    "al7-fast-tower": al7_fast_tower.build,
    "al8-lean-perceiver": al8_lean_perceiver.build,
    "al9-decoy": al9_decoy.build,
    "al10-skippable": al10_skippable.build,
    "al11-greedy-trap": al11_greedy_trap.build,
    "al12-unlearnable": al12_unlearnable.build,
    "al13-symmetry-repair": al13_symmetry_repair.build,
    "al14-cell-row-grid": al14_cell_row_grid.build,
    "al15-shift-frame": al15_shift_frame.build,
    "al16-layout-nest": al16_layout_nest.build,
}


def make_ladder(name: str) -> LadderSpec:
    """Resolve a ladder name to a freshly built :class:`LadderSpec`."""
    try:
        return LADDERS[name]()
    except KeyError:
        known = ", ".join(sorted(LADDERS))
        raise KeyError(f"unknown ladder {name!r}; known: {known}") from None
