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


# -- Abstraction Ladder testbeds: generated from the `.ladder` sources -------------
# A ladder's `.ladder` file is its single source of truth (docs/abstraction_ladders/
# LADDER-FORMAT.md): the same file drives its LadderSpec and, here, its committed testbed. Task
# outputs come from EVALUATING each task's declared solution, so a demonstrating task cannot drift
# from the spine it demonstrates.


def _ladder_testbed_writer(name: str) -> Callable[[Path], Path]:
    def generate(out_root: Path) -> Path:
        from arc_lab.program_search.ladders.lang.load import ladder_tasks
        from arc_lab.program_search.ladders.registry import load_ladder

        loaded = load_ladder(name)
        return write_testbed(
            name,
            ladder_tasks(loaded),
            out_root=out_root,
            note=f"Generated from {name}.ladder",
        )

    return generate


def _ladder_generators() -> dict[str, Callable[[Path], Path]]:
    from arc_lab.program_search.ladders.registry import ladder_paths

    return {name: _ladder_testbed_writer(name) for name in ladder_paths()}


#: Generator registry for the CLI (`arc-lab taskgen <name>`).
GENERATORS: dict[str, Callable[[Path], Path]] = {
    "e1-rot90": generate_e1_rot90,
    "perceive-transform": generate_perceive_transform,
    "layered-abstraction": generate_layered_abstraction,
    "grain-contrast": generate_grain_contrast,
    **_ladder_generators(),
}


def generate(name: str, out_root: Path) -> Path:
    """Run the named generator, writing its testbed under ``out_root``."""
    try:
        generator = GENERATORS[name]
    except KeyError:
        known = ", ".join(sorted(GENERATORS))
        raise KeyError(f"unknown generator {name!r}; known: {known}") from None
    return generator(out_root)
