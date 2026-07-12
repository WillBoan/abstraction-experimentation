"""Named testbed generators for ``arc-lab taskgen <name>``.

Each generator deterministically writes one committed testbed (task content is stable
across runs — see ``tests/test_taskgen.py``). Generators are registered here as the old
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


#: Generator registry for the CLI (`arc-lab taskgen <name>`).
GENERATORS: dict[str, Callable[[Path], Path]] = {
    "e1-rot90": generate_e1_rot90,
}


def generate(name: str, out_root: Path) -> Path:
    """Run the named generator, writing its testbed under ``out_root``."""
    try:
        generator = GENERATORS[name]
    except KeyError:
        known = ", ".join(sorted(GENERATORS))
        raise KeyError(f"unknown generator {name!r}; known: {known}") from None
    return generator(out_root)
