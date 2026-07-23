"""``arc-lab diff-ladder A B``: is one ladder a behaviour-preserving version of another?

Compares two `.ladder` files (or registered names) by their top solutions, picking the validator the
relationship licenses (docs/abstraction_ladders/LADDER-RELATIONSHIPS-2026-07-23.md):

- **Same floor** (a cohort) -- prove it STATICALLY: unfold both to the floor and compare (then
  equational normal forms). No bodies, no grids; works on assumed-primitive drafts (e.g. cfb2ce5a
  ``v1`` vs ``v3`` -> EQUAL, "proved by unfold").
- **Different floor** (an ablation) -- static cannot bridge, so fall to an EXACT observational diff on
  a battery of diverse + edge grids, which needs both sides to have real primitive bodies. When the
  primitives are still assumed, there is nothing to run: INCONCLUSIVE (e.g. ``v1`` vs ``v4``).

Reports the floor relationship, the per-top-task verdict, and HOW it was reached. Exit code: EQUAL=0,
DIFFERENT=1, INCONCLUSIVE=2 (worst-outcome-wins), so it drops into a hook or a try-simplification loop.
"""

from __future__ import annotations

import enum
from pathlib import Path

import typer

from arc_lab.program_search.analysis.equivalence import (
    observationally_equivalent_programs,
    static_equivalent,
)
from arc_lab.program_search.analysis.grids import exact_grids
from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.load import LoadedLadder, resolve
from arc_lab.program_search.ladders.lang.parse import LADDER_SUFFIX, parse_ladder_file
from arc_lab.program_search.ladders.registry import ladder_paths
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program


class _Outcome(enum.Enum):
    """One top-task comparison. The exit code distinguishes a definite difference (DIFFERENT) from
    "could not tell" (INCONCLUSIVE) from equal."""

    EQUAL = 0
    DIFFERENT = 1
    INCONCLUSIVE = 2


#: How a static proof reads in the report.
_PROVEN_BY = {"syntactic": "unfold-and-compare", "equational": "equational normal form"}


def diff_ladder_command(
    ladder_a: str = typer.Argument(..., help="A registered ladder name or a path to a `.ladder` file."),
    ladder_b: str = typer.Argument(..., help="The ladder to compare it against (name or path)."),
) -> None:
    """Report whether ``ladder_a`` and ``ladder_b`` compute the same thing, and how it was decided."""
    try:
        a, b = _resolve(ladder_a), _resolve(ladder_b)
    except LadderFormatError as exc:
        typer.echo(f"LOAD FAILED -- {exc}")
        raise typer.Exit(code=1) from None

    label_a, label_b = _label(ladder_a), _label(ladder_b)
    names_a, names_b = set(a.floor.names()), set(b.floor.names())
    same_floor = names_a == names_b
    typer.echo(
        f"floor: {_floor_relation(names_a, names_b, label_a, label_b)} "
        f"({len(names_a)} vs {len(names_b)} primitives)"
    )

    ids_a = [task.task_id for task in a.document.top]
    ids_b = {task.task_id for task in b.document.top}
    if set(ids_a) != ids_b:
        typer.echo(
            f"top tasks differ ({ids_a} vs {sorted(ids_b)}): not the same target, cannot compare"
        )
        raise typer.Exit(code=_Outcome.INCONCLUSIVE.value)

    outcomes = [_compare_top(task_id, a, b, same_floor=same_floor) for task_id in ids_a]
    if any(outcome is _Outcome.DIFFERENT for outcome in outcomes):
        overall = _Outcome.DIFFERENT
    elif any(outcome is _Outcome.INCONCLUSIVE for outcome in outcomes):
        overall = _Outcome.INCONCLUSIVE
    else:
        overall = _Outcome.EQUAL
    typer.echo(f"\ndiff-ladder: {overall.name}")
    if overall is not _Outcome.EQUAL:
        raise typer.Exit(code=overall.value)


def _compare_top(task_id: str, a: LoadedLadder, b: LoadedLadder, *, same_floor: bool) -> _Outcome:
    """Compare the two ladders' solution for one top task, print the verdict + how, return it."""
    sol_a, lib_a = a.solutions[task_id], a.libraries[-1]
    sol_b, lib_b = b.solutions[task_id], b.libraries[-1]
    has_bodies = not a.assumed and not b.assumed

    if same_floor:
        static = static_equivalent(sol_a, lib_a, sol_b, lib_b, a.floor)
        if static.equivalent:
            how = _PROVEN_BY.get(static.proven_by or "", static.proven_by or "?")
            typer.echo(f"{task_id}: EQUAL -- proved by {how} (static, no bodies needed)")
            return _Outcome.EQUAL
        if not has_bodies:
            typer.echo(
                f"{task_id}: INCONCLUSIVE -- static could not prove equal, and assumed primitives "
                "block the observational check (implement them to decide)"
            )
            return _Outcome.INCONCLUSIVE
        return _observe(task_id, a, sol_a, lib_a, sol_b, lib_b, static_note="static could not prove")

    # Different floor: no static bridge. Observe if both sides have bodies, else inconclusive.
    if not has_bodies:
        typer.echo(
            f"{task_id}: INCONCLUSIVE -- different floor (no static bridge) and assumed primitives "
            "(nothing to run)"
        )
        return _Outcome.INCONCLUSIVE
    return _observe(task_id, a, sol_a, lib_a, sol_b, lib_b, static_note="different floor")


def _observe(
    task_id: str,
    a: LoadedLadder,
    sol_a: Program,
    lib_a: Library,
    sol_b: Program,
    lib_b: Library,
    *,
    static_note: str,
) -> _Outcome:
    """Run the EXACT observational diff over an edge-grid battery at the top task's shapes."""
    shapes = {
        (grid.height, grid.width) for task in a.document.top for grid in task.train_inputs
    }
    grids = exact_grids(shapes)
    verdict = observationally_equivalent_programs(sol_a, lib_a, sol_b, lib_b, grids)
    if verdict.equivalent:
        typer.echo(
            f"{task_id}: EQUAL -- no counterexample at {verdict.cases_tested} grids "
            f"({static_note}, so observational)"
        )
        return _Outcome.EQUAL
    typer.echo(
        f"{task_id}: DIFFERENT -- split on a grid ({static_note}); "
        f"counterexample input:\n{_render(verdict.counterexample)}"
    )
    return _Outcome.DIFFERENT


def _resolve(target: str) -> LoadedLadder:
    """Load ``target`` as a path if it looks like one, else as a registered name.

    ``assume_missing=True`` is harmless for a fully-real ladder (nothing is missing, ``assumed`` stays
    empty) and is what lets a still-assumed draft load at all -- so both kinds resolve uniformly and
    ``loaded.assumed`` reports whether bodies exist.
    """
    path = Path(target)
    if path.suffix == LADDER_SUFFIX or path.exists():
        if not path.is_file():
            raise typer.BadParameter(f"{target}: no such `.ladder` file")
        return resolve(parse_ladder_file(path), assume_missing=True)
    try:
        return resolve(parse_ladder_file(ladder_paths()[target]), assume_missing=True)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _floor_relation(names_a: set[str], names_b: set[str], label_a: str, label_b: str) -> str:
    if names_a == names_b:
        return "identical"
    if names_a < names_b:
        return f"{label_a} floor ⊆ {label_b}"
    if names_b < names_a:
        return f"{label_b} floor ⊆ {label_a}"
    return "disjoint / overlapping"


def _label(target: str) -> str:
    return Path(target).stem if target.endswith(LADDER_SUFFIX) else target


def _render(grid: object) -> str:
    to_text = getattr(grid, "to_text", None)
    return to_text() if callable(to_text) else repr(grid)
