"""Seed grids for hand-authoring a `.ladder` file.

An **authoring aid**, not part of any pipeline: a ladder's task inputs are literal grids in its
`.ladder` source (docs/abstraction_ladders/LADDER-FORMAT.md), and these are the deterministic
constructions that make *good* ones -- grids that vary within a task and across tasks, so no
literal, constant or identity shortcut can coincide with the intended solution. Reach for them via
``arc-lab ladder-seeds``, paste the output into the file, and the lint's variation checks
(``distinct-train-inputs`` / ``outputs-vary`` / ``not-identity``) become a formality rather than a
hazard.

Until 2026-07-21 these fed a ``LadderTestbed`` generator per ladder; the `.ladder` loader replaced
that, and the reasoning in these docstrings is the part worth keeping.
"""

from __future__ import annotations

from collections.abc import Sequence

from arc_lab.core.grid import Grid


def seed_grids(
    count: int,
    *,
    rows: int,
    cols: int,
    variant: int,
    palette: Sequence[int] = (1, 2, 3, 4, 5),
    background: int | None = None,
) -> tuple[Grid, ...]:
    """``count`` deterministic, mutually distinct grids -- no RNG (reproducibility is load-bearing).

    Cells are filled from ``palette`` by a per-grid stride, which makes each grid asymmetric under
    both flips (adjacent cells differ) and makes the set vary in content, so neither a literal
    constant program nor an identity/flip shortcut can coincide on every example. ``variant``
    separates one task's grids from another's.

    ``background``, when given, frames every grid with a one-cell border of that colour and fills
    only the interior from ``palette``. Mask/crop ladders need this: the border guarantees a
    non-empty margin (so cropping to content is not a no-op) and a strict majority background (so
    ``most_common_color`` is unambiguous), while the interior stays multi-coloured (so the mask of
    the *cropped* grid is non-empty in turn). Requires ``rows``/``cols`` >= 3.
    """
    if not palette:
        raise ValueError("palette must be non-empty")
    if background is not None and (rows < 3 or cols < 3):
        raise ValueError("a background frame needs rows and cols >= 3")
    content = [c for c in palette if c != background] or list(palette)
    grids: list[Grid] = []
    for k in range(count):
        stride = 1 + (variant + k) % max(1, len(content) - 1)
        start = (variant * 3 + k * 5) % len(content)
        rows_out: list[list[int]] = []
        for r in range(rows):
            row: list[int] = []
            for c in range(cols):
                if background is not None and (r == 0 or c == 0 or r == rows - 1 or c == cols - 1):
                    row.append(background)
                else:
                    row.append(content[(start + stride * (r * cols + c)) % len(content)])
            rows_out.append(row)
        grids.append(Grid.from_list(rows_out))
    return tuple(grids)


def symmetry_repair_seeds(
    count: int,
    *,
    rows: int,
    cols: int,
    variant: int,
    palette: Sequence[int] = (1, 2, 3, 4, 5),
) -> tuple[Grid, ...]:
    """``count`` distinct holed grids for the symmetry-**repair** ladders (al13), where a rung
    reconstructs missing cells (colour 0) from a mirror rather than transforming the grid.

    ``seed_grids`` produces *dense* grids, so a repair rung applied to one has nothing to repair and
    the whole ladder collapses (measured: al13's ``sym_both`` was a no-op on stride seeds, so the
    top was reachable with the H-repair rung alone). These seeds instead carry a deliberate hole
    pattern that *requires both axes* to fill:

    - the answer is a 4-fold-symmetric grid ``T`` (``T[r][c] == T[r][c'] == T[r'][c]``, the mirrors
      via ``c'=cols-1-c``/``r'=rows-1-r``);
    - a corner cell ``(0,0)`` is blanked together with its H-mirror ``(0,c')`` and V-mirror
      ``(r',0)``, its diagonal ``(r',c')`` kept -- so the H-repair alone cannot fill ``(0,0)`` (its
      H-mirror is also blank), and only ``overlay`` from the V-mirror of the *already-H-repaired*
      grid recovers it. One extra blank ``(1,0)`` gives the H-repair rung genuine work of its own.

    The shape is deliberately non-square so ``transpose`` (a floor primitive) changes the shape and
    cannot feed ``overlay`` as a shortcut -- ``transpose`` is only reachable at the Top, where the
    goal genuinely transposes the repaired grid.
    """
    if rows < 3 or cols < 3:
        raise ValueError("symmetry-repair seeds need rows and cols >= 3")
    content = [c for c in palette if c != 0] or list(palette)
    n = len(content)
    grids: list[Grid] = []
    for k in range(count):
        # A per-grid stride over the fundamental domain (as in ``seed_grids``) so consecutive cells
        # differ and the set varies across tasks, not just within one.
        stride = 1 + (variant + k) % max(1, n - 1)
        start = (variant * 3 + k * 5) % n
        # 4-fold-symmetric target T: fill the top-left fundamental domain, mirror it out.
        half_r, half_c = (rows + 1) // 2, (cols + 1) // 2
        fund = [
            [content[(start + stride * (r * half_c + c)) % n] for c in range(half_c)]
            for r in range(half_r)
        ]
        target = [
            [fund[min(r, rows - 1 - r)][min(c, cols - 1 - c)] for c in range(cols)]
            for r in range(rows)
        ]
        holed = [row[:] for row in target]
        for r, c in ((0, 0), (0, cols - 1), (rows - 1, 0), (1, 0)):
            holed[r][c] = 0
        grids.append(Grid.from_list(holed))
    return tuple(grids)


def _seeds(
    count: int,
    *,
    rows: int,
    cols: int,
    variant: int,
    palette: Sequence[int],
    background: int | None,
    seed_mode: str,
) -> tuple[Grid, ...]:
    """Dispatch to the seed generator named by ``seed_mode`` (shared by rungs and the goal layer)."""
    if seed_mode == "symmetry-repair":
        return symmetry_repair_seeds(count, rows=rows, cols=cols, variant=variant, palette=palette)
    if seed_mode != "stride":
        raise ValueError(f"unknown seed_mode {seed_mode!r}")
    return seed_grids(
        count, rows=rows, cols=cols, variant=variant, palette=palette, background=background
    )
