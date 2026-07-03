"""Render grids and tasks as images using the canonical ARC color palette.

Seeing the grids is the single highest-leverage thing when building intuition
about ARC, so this is a first-class part of the harness rather than an
afterthought. Rendering uses a non-interactive matplotlib backend so it works
headless (saving to PNG); pass ``show=True`` for an interactive window.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

import matplotlib

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

# The canonical ARC 10-color palette, indexed by color value 0-9.
ARC_COLORS: Final[list[str]] = [
    "#000000",  # 0 black
    "#0074D9",  # 1 blue
    "#FF4136",  # 2 red
    "#2ECC40",  # 3 green
    "#FFDC00",  # 4 yellow
    "#AAAAAA",  # 5 grey
    "#F012BE",  # 6 fuchsia
    "#FF851B",  # 7 orange
    "#7FDBFF",  # 8 cyan
    "#870C25",  # 9 maroon
]


def _cmap() -> matplotlib.colors.ListedColormap:
    return matplotlib.colors.ListedColormap(ARC_COLORS)


def _draw(ax: Axes, grid: Grid, title: str | None = None) -> None:
    from matplotlib.colors import Normalize

    ax.imshow(grid.array, cmap=_cmap(), norm=Normalize(vmin=0, vmax=9))
    ax.set_xticks([x - 0.5 for x in range(1, grid.width)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, grid.height)], minor=True)
    ax.grid(which="minor", color="#333333", linewidth=0.5)
    ax.tick_params(which="both", length=0, labelbottom=False, labelleft=False)
    if title:
        ax.set_title(title, fontsize=9)


def _finish(fig: Figure, save: str | Path | None, show: bool) -> None:
    fig.tight_layout()
    if save is not None:
        fig.savefig(save, dpi=120, bbox_inches="tight")
    if show:  # pragma: no cover - interactive only
        import matplotlib.pyplot as plt

        plt.show()
    import matplotlib.pyplot as plt

    plt.close(fig)


def render_grid(
    grid: Grid,
    *,
    title: str | None = None,
    save: str | Path | None = None,
    show: bool = False,
) -> None:
    """Render a single grid."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3, 3))
    _draw(ax, grid, title)
    _finish(fig, save, show)


def render_task(
    task: Task,
    *,
    save: str | Path | None = None,
    show: bool = False,
) -> None:
    """Render a whole task: train pairs on top, test pairs beneath."""
    import matplotlib.pyplot as plt

    n = len(task.train) + len(task.test)
    fig, axes = plt.subplots(2, n, figsize=(2.2 * n, 4.6), squeeze=False)
    fig.suptitle(task.task_id, fontsize=11)

    col = 0
    for i, ex in enumerate(task.train, start=1):
        _draw(axes[0][col], ex.input, f"train {i} in")
        if ex.output is not None:
            _draw(axes[1][col], ex.output, "out")
        else:  # pragma: no cover
            axes[1][col].axis("off")
        col += 1
    for i, ex in enumerate(task.test, start=1):
        _draw(axes[0][col], ex.input, f"TEST {i} in")
        if ex.output is not None:
            _draw(axes[1][col], ex.output, "out")
        else:
            axes[1][col].axis("off")
            axes[1][col].set_title("out ?", fontsize=9)
        col += 1

    _finish(fig, save, show)
