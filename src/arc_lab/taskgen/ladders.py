"""Template-driven ladder testbeds: generate a whole ladder's corpus from its rung templates.

The point: a demonstrating task's solution IS its rung's template, so there is no reason to
hand-write one. :func:`template_solution` turns a :class:`Program` into the ``Grid -> Grid``
callable ``make_task`` wants by *evaluating* it, which makes the generated tasks correct by
construction -- a hand-written reimplementation can silently drift from the template it is meant to
demonstrate (and then the ladder demonstrates something other than its own spine).

Each rung's template is evaluated over ``L_{i-1}`` (the oracle chain, :mod:`ladders.chain`), so a
template may call the rung beneath it by name. Adding a new ladder is then a declarative block of
:class:`RungTasks` rather than a new module of bespoke numpy.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from arc_lab.core.grid import Grid
from arc_lab.program_search.ladders.chain import oracle_libraries
from arc_lab.program_search.substrate.library import Library, Value
from arc_lab.program_search.substrate.program import Program

from . import GeneratedTask, Solution, make_task


def template_solution(template: Program, library: Library, args: Sequence[Value] = ()) -> Solution:
    """The ``Grid -> Grid`` solution that *is* ``template``, with its free params bound to ``args``.

    ``Param(0)`` is the input grid and ``Param(1..)`` the free parameters, so the environment is
    ``(grid, *args)``. A Top-Rung reference solution written with ``Input()``/``Const`` ignores the
    environment entirely, so the same helper serves both.
    """

    def solution(grid: Grid) -> Grid:
        return template.evaluate_grid(grid, library, env=(grid, *args))

    return solution


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
        return symmetry_repair_seeds(
            count, rows=rows, cols=cols, variant=variant, palette=palette
        )
    if seed_mode != "stride":
        raise ValueError(f"unknown seed_mode {seed_mode!r}")
    return seed_grids(
        count, rows=rows, cols=cols, variant=variant, palette=palette, background=background
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RungTasks:
    """How to generate one rung's demonstrating tasks.

    ``train_args``/``heldout_args`` hold one argument tuple per task: the rung's **free** parameter
    values (empty for a param-free rung). They are fixed within a task and vary across tasks, which
    is exactly the variation plan the design doc requires of free params -- so the generator
    enforces it structurally rather than by convention.
    """

    name: str  # the rung name == the task label
    #: The program whose evaluation produces the demonstrating tasks.
    template: Program
    #: What sleep should mint, when that differs from what the demos are solved by. They coincide
    #: for a ``full_solution`` rung; a rung whose target is not ``GRID -> GRID`` cannot be a whole
    #: solution, so its demos use a grid-to-grid wrapper that merely CONTAINS the target and the
    #: target is given here (a ``fragment_identical`` rung -- see al4-mask-crop).
    target_template: Program | None = None
    train_args: tuple[tuple[Value, ...], ...] = ((),)
    heldout_args: tuple[tuple[Value, ...], ...] = ((),)
    rows: int = 2
    cols: int = 3
    palette: tuple[int, ...] = (1, 2, 3, 4, 5)
    background: int | None = None
    #: Seed shape: ``"stride"`` dense grids, or ``"symmetry-repair"`` holed grids that need both-axis
    #: repair (:func:`symmetry_repair_seeds`) -- mutually exclusive with ``background``.
    seed_mode: str = "stride"
    train_examples: int = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class TopTasks:
    """The goal layer: reference solutions over ``L_k`` (``Input()``-rooted, not templates)."""

    solutions: tuple[Program, ...]
    heldout_solutions: tuple[Program, ...] = ()
    rows: int = 2
    cols: int = 3
    palette: tuple[int, ...] = (1, 2, 3, 4, 5)
    background: int | None = None
    seed_mode: str = "stride"
    train_examples: int = 2
    label: str = "top"


@dataclass(frozen=True, slots=True, kw_only=True)
class LadderTestbed:
    """A whole ladder's corpus, declaratively: a Floor, the rungs in order, and the goal layer."""

    floor: Library
    rungs: tuple[RungTasks, ...]
    top: TopTasks
    #: Tasks that are NOT rungs: a learnable competence sitting in the corpus off the ladder's
    #: spine. Used by the control ladders (`decoy`, `greedy-trap`) to ask what the loop does with
    #: mintable-but-useless material. Their templates are stated over the FLOOR, since they are not
    #: part of the chain and must be solvable without any rung.
    distractors: tuple[RungTasks, ...] = ()
    note: str = ""
    _variant: int = field(default=0, repr=False)

    def libraries(self) -> tuple[Library, ...]:
        """``L_0 .. L_k``, built from each rung's TARGET template (what sleep should mint) -- never
        from its demo template, which for a fragment rung refers to the rung itself."""
        return oracle_libraries(
            self.floor, [(r.name, r.target_template or r.template) for r in self.rungs]
        )

    def tasks(self) -> tuple[GeneratedTask, ...]:
        """Generate every task: each rung's demos + heldout, then the goal layer's."""
        libs = self.libraries()
        out: list[GeneratedTask] = []
        variant = self._variant
        for level, rung in enumerate(self.rungs, start=1):
            # Evaluate over L_i, not L_{i-1}: a full-solution rung's template is stated over
            # L_{i-1} and evaluates fine against the superset, while a FRAGMENT rung's demo wrapper
            # calls the rung itself and needs L_i. One rule serves both.
            below = libs[level]
            for split, arg_sets in (("train", rung.train_args), ("heldout", rung.heldout_args)):
                for i, args in enumerate(arg_sets):
                    variant += 1
                    grids = _seeds(
                        rung.train_examples + 1,
                        rows=rung.rows,
                        cols=rung.cols,
                        variant=variant,
                        palette=rung.palette,
                        background=rung.background,
                        seed_mode=rung.seed_mode,
                    )
                    suffix = f"{i:02d}" if split == "train" else f"heldout-{i:02d}"
                    out.append(
                        make_task(
                            f"{rung.name}-{suffix}",
                            label=rung.name,
                            split=split,
                            solution=template_solution(rung.template, below, args),
                            train_inputs=grids[: rung.train_examples],
                            test_inputs=grids[rung.train_examples :],
                        )
                    )
        for rung in self.distractors:  # off-spine: evaluated over the Floor, never a Rung
            for split, arg_sets in (("train", rung.train_args), ("heldout", rung.heldout_args)):
                for i, args in enumerate(arg_sets):
                    variant += 1
                    grids = _seeds(
                        rung.train_examples + 1,
                        rows=rung.rows,
                        cols=rung.cols,
                        variant=variant,
                        palette=rung.palette,
                        background=rung.background,
                        seed_mode=rung.seed_mode,
                    )
                    suffix = f"{i:02d}" if split == "train" else f"heldout-{i:02d}"
                    out.append(
                        make_task(
                            f"{rung.name}-{suffix}",
                            label=rung.name,
                            split=split,
                            solution=template_solution(rung.template, libs[0], args),
                            train_inputs=grids[: rung.train_examples],
                            test_inputs=grids[rung.train_examples :],
                        )
                    )
        top, full = self.top, libs[-1]
        for split, sols in (("train", top.solutions), ("heldout", top.heldout_solutions)):
            for i, sol in enumerate(sols):
                variant += 1
                grids = _seeds(
                    top.train_examples + 1,
                    rows=top.rows,
                    cols=top.cols,
                    variant=variant,
                    palette=top.palette,
                    background=top.background,
                    seed_mode=top.seed_mode,
                )
                suffix = f"{i:02d}" if split == "train" else f"heldout-{i:02d}"
                out.append(
                    make_task(
                        f"{top.label}-{suffix}",
                        label=top.label,
                        split=split,
                        solution=template_solution(sol, full),
                        train_inputs=grids[: top.train_examples],
                        test_inputs=grids[top.train_examples :],
                    )
                )
        return tuple(out)
