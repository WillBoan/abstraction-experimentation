"""Deterministic grid batteries — shared by the rung probe and the equivalence checker.

- :func:`discriminating_grids` — three position-separating colour layouts per shape (moved here from
  ``ladders/probe.py`` so the probe and :mod:`analysis.equivalence` share one RNG-free generator).
- :func:`edge_grids` — the deliberate corner cases an EXACT-equivalence check wants. For exact
  equivalence a split on ANY grid is a real difference, so out-of-distribution grids help rather than
  hurt: 1x1, uniform colour, colour-0-absent, and an all-ten-colours staircase.
- :func:`exact_grids` — their deduped union, the default battery for exact observational equivalence.

Everything is deterministic (no RNG), so a verdict is reproducible and a counterexample is stable.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid


def discriminating_grids(shapes: set[tuple[int, int]]) -> tuple[Grid, ...]:
    """Three position-separating colour patterns per shape -- deterministic, no RNG.

    The colour at each cell varies with its position under three different layouts, so a program that
    reads the wrong cell is separated from one that reads the right cell even when they agree on a
    corpus whose own grids happen to make the two positions equal (al14's collision).
    """
    grids: list[Grid] = []
    for height, width in sorted(shapes):
        patterns = (
            [[(r * width + c) % 10 for c in range(width)] for r in range(height)],
            [[(c * height + r) % 10 for c in range(width)] for r in range(height)],
            [[(r * 7 + c * 3) % 10 for c in range(width)] for r in range(height)],
        )
        grids.extend(Grid.from_list(rows) for rows in patterns)
    return tuple(grids)


def edge_grids(shapes: set[tuple[int, int]]) -> tuple[Grid, ...]:
    """Deliberate corner cases for EXACT refutation, at ``shapes`` (plus the minimal 1x1).

    Uniform grids (each of a few colours), a colour-0-absent grid, and an all-ten staircase -- the
    inputs most likely to separate two programs that agree on ordinary grids (a background-colour
    assumption, a missing-colour edge, a wrap-around).
    """
    seen: dict[Grid, None] = {}
    for height, width in sorted(shapes | {(1, 1)}):
        for color in (0, 1, 9):  # uniform: background and two nonzero colours
            seen.setdefault(Grid.from_list([[color] * width for _ in range(height)]), None)
        # colours 1..9 only, so colour 0 (the usual background) is entirely absent
        seen.setdefault(
            Grid.from_list([[((r * width + c) % 9) + 1 for c in range(width)] for r in range(height)]),
            None,
        )
        # every colour 0..9 present wherever the shape is large enough to hold them
        seen.setdefault(
            Grid.from_list([[(r * width + c) % 10 for c in range(width)] for r in range(height)]),
            None,
        )
    return tuple(seen)


def exact_grids(shapes: set[tuple[int, int]]) -> tuple[Grid, ...]:
    """The default EXACT-equivalence battery: discriminating layouts + edge cases, deduped."""
    seen: dict[Grid, None] = {}
    for grid in (*discriminating_grids(shapes), *edge_grids(shapes)):
        seen.setdefault(grid, None)
    return tuple(seen)
