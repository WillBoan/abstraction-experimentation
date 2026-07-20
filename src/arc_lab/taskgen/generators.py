"""Named testbed generators for ``arc-lab taskgen <name>``.

Each generator deterministically writes one committed testbed (task content is stable
across runs — see ``tests/taskgen/test_taskgen.py``). Generators are registered here as the old
E-suite's environments are recalibrated onto the new engine (their `StudySpec`s live in
``program_search/execution/studies.py``); a study and its generator share a name.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.program_search.ladders.registry import (
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
)

from . import GeneratedTask, make_task, write_testbed


def _small_grids() -> list[Grid]:
    """A deterministic pool of varied small grids (square / non-square)."""
    rows_pool = [
        [[1, 2], [3, 4]],
        [[1, 2, 3], [4, 5, 6]],
        [[5, 0], [0, 5], [1, 2]],
        [[2, 0, 1], [3, 4, 5]],
        [[7, 8], [9, 1]],
        [[1, 1, 2], [2, 3, 3]],
        [[4, 5], [6, 7], [8, 9]],
        [[0, 1, 2, 3]],
        [[3], [2], [1]],
        [[9, 8, 7], [6, 5, 4], [3, 2, 1]],
        [[1, 0], [0, 1]],
        [[2, 2, 2], [1, 1, 1]],
    ]
    return [Grid.from_list(rows) for rows in rows_pool]


def e1_rot90_tasks() -> tuple[GeneratedTask, ...]:
    """E1's testbed: 12 rot90 tasks over varied small grids, 8 train / 4 held-out."""
    tasks: list[GeneratedTask] = []
    for i, grid in enumerate(_small_grids()):
        tasks.append(
            make_task(
                f"rot90-{i:02d}",
                label="rot90",
                split="train" if i < 8 else "heldout",
                solution=lambda g: Grid(np.rot90(g.array, 1)),
                train_inputs=[grid],
                test_inputs=[grid],
            )
        )
    return tuple(tasks)


def generate_e1_rot90(out_root: Path) -> Path:
    return write_testbed(
        "e1-rot90",
        e1_rot90_tasks(),
        out_root=out_root,
        note="E1 smoke: re-derive rot90 from the D4 generators {flip_h, transpose}.",
    )


def _accent_grid(bg: int, accent_a: int, accent_b: int) -> Grid:
    """A 3x3 grid: background ``bg`` filling 7 cells, two singleton accent cells.

    The 7-1-1 majority makes ``most_common_color`` unambiguous (no tie-break needed).
    """
    return Grid.from_list(
        [
            [accent_a, bg, bg],
            [bg, bg, bg],
            [bg, bg, accent_b],
        ]
    )


#: Backgrounds shared by every recolor_bg task -- reused *within* each task so the
#: search cannot solve via one literal COLOR constant (see `perceive_transform_tasks`).
_RECOLOR_BG_BACKGROUNDS = (3, 4, 6)


def _most_common_color(grid: Grid) -> int:
    """Reference most-common-color (ties -> lowest value): a plain numpy computation,
    independent of the `most_common_color` DSL primitive it stands in for."""
    return int(np.bincount(grid.array.ravel(), minlength=10).argmax())


def _recolor_bg_solution(target: int) -> Callable[[Grid], Grid]:
    """recolor_bg(g, target): replace `g`'s most common color with `target`."""

    def solution(grid: Grid) -> Grid:
        arr = grid.array
        arr[arr == _most_common_color(grid)] = target
        return Grid(arr)

    return solution


def perceive_transform_tasks() -> tuple[GeneratedTask, ...]:
    """perceive->transform testbed: recolor_bg(g,c) = map_color(g, most_common_color(g), c).

    Each task fixes ONE target color across its 3 train examples but varies the
    background *within* the task (same 3 backgrounds every task) -- no single literal
    COLOR constant solves all of a task's examples at once, so the search is forced
    through the perceiving composition `map_color(g, most_common_color(g), c)`. Target
    color then varies *across* tasks, which is what gives antiunify the differing
    literal that becomes recolor_bg's free parameter. Train targets {0,2,5,7,9}, held-out
    (unseen) targets {1,8} -- disjoint from the shared backgrounds {3,4,6}.
    """
    grids = [_accent_grid(bg, 1, 2) for bg in _RECOLOR_BG_BACKGROUNDS]
    tasks: list[GeneratedTask] = []
    for split, targets in (("train", (0, 2, 5, 7, 9)), ("heldout", (1, 8))):
        for target in targets:
            tasks.append(
                make_task(
                    f"recolor-bg-{target}",
                    label="recolor_bg",
                    split=split,
                    solution=_recolor_bg_solution(target),
                    train_inputs=grids,
                    test_inputs=[grids[0]],
                )
            )
    return tuple(tasks)


def generate_perceive_transform(out_root: Path) -> Path:
    return write_testbed(
        "perceive-transform",
        perceive_transform_tasks(),
        out_root=out_root,
        note=(
            "perceive->transform: recolor_bg(g,c) = map_color(g, most_common_color(g), c), "
            "derived from {map_color, most_common_color} via within-task background "
            "variation + cross-task target-color variation."
        ),
    )


_LAYERED_ROT180_TRAIN_GRIDS = (
    Grid.from_list([[1, 2, 3], [4, 5, 6]]),
    Grid.from_list([[7, 0], [8, 9], [1, 2]]),
    Grid.from_list([[3, 4, 5], [6, 7, 8]]),
    Grid.from_list([[9, 1], [2, 3], [4, 5]]),
)
_LAYERED_ROT180_HELDOUT_GRID = Grid.from_list([[6, 7], [8, 9], [0, 1]])

_LAYERED_RECOLOR_FLIPPED_TRAIN_PAIRS = ((1, 2), (3, 4), (5, 6), (7, 0))
_LAYERED_RECOLOR_FLIPPED_HELDOUT_PAIR = (8, 9)


def _rot180_reference(grid: Grid) -> Grid:
    return Grid(grid.array[::-1, ::-1])


def _grid_containing(color: int) -> Grid:
    """A 2x3 asymmetric grid guaranteed to contain `color` (top-left cell)."""
    others = [(color + offset) % 10 for offset in range(1, 6)]
    return Grid.from_list([[color, others[0], others[1]], [others[2], others[3], others[4]]])


def _recolor_flipped_solution(a: int, b: int) -> Callable[[Grid], Grid]:
    """recolor_flipped(g, a, b) = map_color(rot180(g), a, b)."""

    def solution(grid: Grid) -> Grid:
        arr = grid.array[::-1, ::-1].copy()
        arr[arr == a] = b
        return Grid(arr)

    return solution


def layered_abstraction_tasks() -> tuple[GeneratedTask, ...]:
    """layered abstraction testbed: L1 `rot180 = flip_h(flip_v(g))`; L2
    `recolor_flipped(g,a,b) = map_color(rot180(g),a,b)` built ON the learned L1.

    Every task's own WAKE budget (`depth_limit=2`, two applications) reaches rot180
    tasks directly but not recolor_flipped ones (three applications); only once abs0
    (rot180) is minted does recolor_flipped collapse to two applications and become
    reachable at that SAME budget -- so the second generation's WAKE genuinely needs
    the grown library, not just a post-hoc corpus rewrite. `a`/`b` are fixed within
    each recolor_flipped task and vary across tasks (each param used once -- no
    var-sharing needed here, unlike perceive-transform).
    """
    tasks: list[GeneratedTask] = []
    for i, grid in enumerate(_LAYERED_ROT180_TRAIN_GRIDS):
        tasks.append(
            make_task(
                f"rot180-{i:02d}",
                label="rot180",
                split="train",
                solution=_rot180_reference,
                train_inputs=[grid],
                test_inputs=[grid],
            )
        )
    tasks.append(
        make_task(
            "rot180-heldout",
            label="rot180",
            split="heldout",
            solution=_rot180_reference,
            train_inputs=[_LAYERED_ROT180_HELDOUT_GRID],
            test_inputs=[_LAYERED_ROT180_HELDOUT_GRID],
        )
    )
    for a, b in _LAYERED_RECOLOR_FLIPPED_TRAIN_PAIRS:
        grid = _grid_containing(a)
        tasks.append(
            make_task(
                f"recolor-flipped-{a}-{b}",
                label="recolor_flipped",
                split="train",
                solution=_recolor_flipped_solution(a, b),
                train_inputs=[grid],
                test_inputs=[grid],
            )
        )
    a, b = _LAYERED_RECOLOR_FLIPPED_HELDOUT_PAIR
    heldout_grid = _grid_containing(a)
    tasks.append(
        make_task(
            f"recolor-flipped-{a}-{b}",
            label="recolor_flipped",
            split="heldout",
            solution=_recolor_flipped_solution(a, b),
            train_inputs=[heldout_grid],
            test_inputs=[heldout_grid],
        )
    )
    return tuple(tasks)


def generate_layered_abstraction(out_root: Path) -> Path:
    return write_testbed(
        "layered-abstraction",
        layered_abstraction_tasks(),
        out_root=out_root,
        note=(
            "layered abstraction: L1 rot180 = flip_h(flip_v(g)); L2 "
            "recolor_flipped(g,a,b) = map_color(rot180(g),a,b), built on the learned L1."
        ),
    )


def _pattern_grid(size: int, offset: int) -> Grid:
    """A deterministic ``size`` x ``size`` grid varying by ``offset`` (no RNG, per CLAUDE.md).

    Coefficients ``(1, 2)`` are load-bearing: coefficients that sum to a multiple of the modulus
    (e.g. the first draft's ``(3, 7)``) make ``transpose`` *algebraically identical* to ``rot180``
    for this row/col-linear formula, at every size and offset — a real accidental-symmetry bug,
    not just a style choice. Verified collision-free against all 7 other D4 members (both 3x3 and
    10x10, offsets 0-9) before use.
    """
    return Grid(
        np.array(
            [[(row * 1 + col * 2 + offset) % 10 for col in range(size)] for row in range(size)],
            dtype=np.int8,
        )
    )


def _rot180_grain_task(size: int, task_id: str) -> GeneratedTask:
    """A fixed ``size`` x ``size`` rot180 task, 4 varied train examples (rules out a per-cell
    hardcoded-literal-output shortcut — EXPERIMENT_QUEUE.md's `fundamental-floor grain contrast`)
    + 1 held-out-content test example."""
    train = [_pattern_grid(size, offset) for offset in (0, 1, 2, 3)]
    test = [_pattern_grid(size, 4)]
    return make_task(
        task_id,
        label="rot180",
        split="train",
        solution=_rot180_reference,
        train_inputs=train,
        test_inputs=test,
    )


def grain_contrast_tasks() -> tuple[GeneratedTask, ...]:
    """`fundamental-floor grain contrast`: rot180 on a fixed 3x3 and a fixed 10x10 grid, read
    across the floor ladder (`MINIMAL_COMPLETE_FLOOR` -> `UNIVERSAL_FLOOR` -> `GEOM`)."""
    return (
        _rot180_grain_task(3, "grain-rot180-3x3"),
        _rot180_grain_task(10, "grain-rot180-10x10"),
    )


def generate_grain_contrast(out_root: Path) -> Path:
    return write_testbed(
        "grain-contrast",
        grain_contrast_tasks(),
        out_root=out_root,
        note=(
            "fundamental-floor grain contrast: rot180 on a fixed 3x3 and a fixed 10x10 grid, "
            "4 varied train examples each."
        ),
    )


# -- al1-mirror: the first Abstraction Ladder testbed --------------------------------


def _mirror_recolor_solution(a: int, b: int) -> Callable[[Grid], Grid]:
    """mirror_recolor(g, a, b) = map_color(rot180(g), a, b) -- rung 2, built on rot180."""

    def solution(grid: Grid) -> Grid:
        arr = grid.array[::-1, ::-1].copy()
        arr[arr == a] = b
        return Grid(arr)

    return solution


def _al1_top_solution(a: int, b: int, c: int, d: int) -> Callable[[Grid], Grid]:
    """top(g) = map_color(mirror_recolor(g, a, b), c, d) -- mirror_recolor then a SECOND, independent
    recolor. Uses mirror_recolor as a fragment and, unlike a D4 wrapper (which would collapse via the
    group law, e.g. flip_v(rot180)=flip_h), does not algebraically shorten -- two distinct recolors
    plus a rotation need all four floor applications, so the top is genuinely intractable raw."""

    def solution(grid: Grid) -> Grid:
        arr = grid.array[::-1, ::-1].copy()  # rot180
        arr[arr == a] = b  # mirror_recolor's recolor
        arr[arr == c] = d  # the outer map_color's recolor (distinct colors: no merge)
        return Grid(arr)

    return solution


def _al1_grids(color: int) -> list[Grid]:
    """Three distinct 2x3 grids, each asymmetric under rot180 and containing ``color`` (so a
    recolor of that color is active -- keeping the intended composition the cheapest solution)."""
    patterns = [
        [[color, (color + 1) % 10, (color + 2) % 10], [(color + 3) % 10, (color + 4) % 10, color]],
        [[(color + 2) % 10, color, (color + 5) % 10], [color, (color + 3) % 10, (color + 6) % 10]],
        [[(color + 7) % 10, (color + 6) % 10, color], [(color + 1) % 10, color, (color + 2) % 10]],
    ]
    return [Grid.from_list(rows) for rows in patterns]


def al1_mirror_tasks() -> tuple[GeneratedTask, ...]:
    """Abstraction Ladder #1: L0 {flip_h, flip_v, map_color} -> rot180 -> mirror_recolor -> top.

    At the reference budget (depth_limit=2) rot180 is reachable raw (2 applications) but
    mirror_recolor (3) and the top (4) are not -- they collapse only once the rung below is
    minted, so the wake-sleep loop must climb. Every task carries 2 train examples + 1 test;
    (a,b) are fixed within a mirror_recolor/top task and vary across them so AntiunifyPairs mints
    the general two-parameter form. See docs/abstraction_ladders/ABSTRACTION-LADDERS-2026-07-16.md.
    """
    tasks: list[GeneratedTask] = []
    # rung 1: rot180 -- pure GRID->GRID, so no literal shortcut; 2 train + 1 heldout.
    for i in range(2):
        grids = _al1_grids(1 + i)
        tasks.append(
            make_task(
                f"rot180-{i:02d}",
                label="rot180",
                split="train",
                solution=_rot180_reference,
                train_inputs=grids[:2],
                test_inputs=grids[2:],
            )
        )
    held = _al1_grids(5)
    tasks.append(
        make_task(
            "rot180-heldout",
            label="rot180",
            split="heldout",
            solution=_rot180_reference,
            train_inputs=held[:2],
            test_inputs=held[2:],
        )
    )
    # rung 2: mirror_recolor -- (a,b) vary across tasks; unreachable at L0, minted after rot180.
    for a, b in ((1, 2), (3, 4)):
        grids = _al1_grids(a)
        tasks.append(
            make_task(
                f"mirror-recolor-{a}-{b}",
                label="mirror_recolor",
                split="train",
                solution=_mirror_recolor_solution(a, b),
                train_inputs=grids[:2],
                test_inputs=grids[2:],
            )
        )
    grids = _al1_grids(2)
    tasks.append(
        make_task(
            "mirror-recolor-2-3",
            label="mirror_recolor",
            split="heldout",
            solution=_mirror_recolor_solution(2, 3),
            train_inputs=grids[:2],
            test_inputs=grids[2:],
        )
    )
    # top: map_color(mirror_recolor(g,1,2),3,4) -- reachable only once both rungs are minted; the
    # second independent recolor prevents the D4 group-law collapse a single-flip wrapper would have.
    grids = _al1_grids(1)  # contains colors 1 and 3
    tasks.append(
        make_task(
            "top-00",
            label="top",
            split="train",
            solution=_al1_top_solution(1, 2, 3, 4),
            train_inputs=grids[:2],
            test_inputs=grids[2:],
        )
    )
    grids = _al1_grids(5)  # contains colors 5 and 7 (unseen)
    tasks.append(
        make_task(
            "top-heldout",
            label="top",
            split="heldout",
            solution=_al1_top_solution(5, 6, 7, 8),
            train_inputs=grids[:2],
            test_inputs=grids[2:],
        )
    )
    return tuple(tasks)


def generate_al1_mirror(out_root: Path) -> Path:
    return write_testbed(
        "al1-mirror",
        al1_mirror_tasks(),
        out_root=out_root,
        note=(
            "Abstraction Ladder #1: L0{flip_h,flip_v,map_color} -> rot180 -> "
            "mirror_recolor(g,a,b)=map_color(rot180(g),a,b) -> "
            "top=map_color(mirror_recolor(g,1,2),3,4)."
        ),
    )


# -- al2..al6: template-driven Abstraction Ladder testbeds ---------------------------
# Each ladder's corpus is generated from its own rung templates (see taskgen/ladders.py), so the
# demonstrating tasks cannot drift from the spine they demonstrate. The templates live with the
# LadderSpec in program_search/ladders/registry/, keeping ONE source of truth per ladder.


def _ladder_testbed_writer(name: str, module: object) -> Callable[[Path], Path]:
    def generate(out_root: Path) -> Path:
        testbed = module.testbed()  # type: ignore[attr-defined]
        return write_testbed(name, testbed.tasks(), out_root=out_root, note=testbed.note)

    return generate


generate_al2_rot90 = _ladder_testbed_writer("al2-rot90-calibration", al2_rot90)
generate_al3_quad = _ladder_testbed_writer("al3-quad-symmetrize", al3_quad)
generate_al4_mask_crop = _ladder_testbed_writer("al4-mask-crop", al4_mask_crop)
generate_al5_perceiver = _ladder_testbed_writer("al5-perceiver-chain", al5_perceiver)
generate_al6_mirror_tall = _ladder_testbed_writer("al6-mirror-tall", al6_mirror_tall)
generate_al7_fast_tower = _ladder_testbed_writer("al7-fast-tower", al7_fast_tower)
generate_al8_lean_perceiver = _ladder_testbed_writer("al8-lean-perceiver", al8_lean_perceiver)
generate_al9_decoy = _ladder_testbed_writer("al9-decoy", al9_decoy)
generate_al10_skippable = _ladder_testbed_writer("al10-skippable", al10_skippable)
generate_al11_greedy_trap = _ladder_testbed_writer("al11-greedy-trap", al11_greedy_trap)
generate_al12_unlearnable = _ladder_testbed_writer("al12-unlearnable", al12_unlearnable)
generate_al13_symmetry_repair = _ladder_testbed_writer("al13-symmetry-repair", al13_symmetry_repair)
generate_al14_cell_row_grid = _ladder_testbed_writer("al14-cell-row-grid", al14_cell_row_grid)


#: Generator registry for the CLI (`arc-lab taskgen <name>`).
GENERATORS: dict[str, Callable[[Path], Path]] = {
    "e1-rot90": generate_e1_rot90,
    "perceive-transform": generate_perceive_transform,
    "layered-abstraction": generate_layered_abstraction,
    "grain-contrast": generate_grain_contrast,
    "al1-mirror": generate_al1_mirror,
    "al2-rot90-calibration": generate_al2_rot90,
    "al3-quad-symmetrize": generate_al3_quad,
    "al4-mask-crop": generate_al4_mask_crop,
    "al5-perceiver-chain": generate_al5_perceiver,
    "al6-mirror-tall": generate_al6_mirror_tall,
    "al7-fast-tower": generate_al7_fast_tower,
    "al8-lean-perceiver": generate_al8_lean_perceiver,
    "al9-decoy": generate_al9_decoy,
    "al10-skippable": generate_al10_skippable,
    "al11-greedy-trap": generate_al11_greedy_trap,
    "al12-unlearnable": generate_al12_unlearnable,
    "al13-symmetry-repair": generate_al13_symmetry_repair,
    "al14-cell-row-grid": generate_al14_cell_row_grid,
}


def generate(name: str, out_root: Path) -> Path:
    """Run the named generator, writing its testbed under ``out_root``."""
    try:
        generator = GENERATORS[name]
    except KeyError:
        known = ", ".join(sorted(GENERATORS))
        raise KeyError(f"unknown generator {name!r}; known: {known}") from None
    return generator(out_root)
