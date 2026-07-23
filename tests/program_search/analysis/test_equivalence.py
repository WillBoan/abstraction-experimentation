"""Program equivalence: the static (no-bodies) and observational (exact) layers.

The load-bearing case is :func:`test_static_proves_a_same_floor_refactor_without_bodies` — cfb2ce5a
v1 and v3 are a restructuring of one another over an ALL-ASSUMED floor, and unfold-and-compare proves
them equal with zero primitive implementations. That is the property the whole validator rests on.
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.core.grid import Grid
from arc_lab.program_search.analysis.equivalence import (
    observationally_equivalent_functions,
    observationally_equivalent_programs,
    static_equivalent,
)
from arc_lab.program_search.analysis.grids import edge_grids, exact_grids
from arc_lab.program_search.ladders.lang.load import LoadedLadder, resolve
from arc_lab.program_search.ladders.lang.parse import parse_ladder_file
from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Apply, Input, Program
from arc_lab.program_search.substrate.types import COLOR, GRID

_DRAFTS = Path(__file__).resolve().parents[3] / "src/arc_lab/program_search/ladders/drafts"


def _draft(name: str) -> LoadedLadder:
    return resolve(parse_ladder_file(_DRAFTS / f"{name}.ladder"), assume_missing=True)


def _top(loaded: LoadedLadder) -> tuple[Program, Library, Library]:
    """A ladder's first top solution, the library it is stated over, and its floor."""
    task_id = loaded.document.top[0].task_id
    return loaded.solutions[task_id], loaded.libraries[-1], loaded.floor


def test_static_proves_a_same_floor_refactor_without_bodies() -> None:
    # cfb2ce5a v1 and v3 decompose the same computation differently over an identical, entirely
    # ASSUMED floor. Unfolding both to that floor yields the same term, so they are equal for any
    # implementation of those primitives -- proven with no bodies, no grids, no OOD question.
    sol_a, lib_a, floor = _top(_draft("cfb2ce5a-1-basic"))
    sol_b, lib_b, _ = _top(_draft("cfb2ce5a-3-parameterized"))
    verdict = static_equivalent(sol_a, lib_a, sol_b, lib_b, floor)
    assert verdict.equivalent
    assert verdict.proven_by == "syntactic"


def test_static_does_not_prove_a_genuinely_different_program() -> None:
    # A conservative "not proven", never a false EQUAL: swapping the top solution for a different
    # program leaves the unfolded terms unequal and the normal forms unable to bridge them.
    sol_a, lib_a, floor = _top(_draft("cfb2ce5a-1-basic"))
    mutated = Apply("flip_h", (Input(),))
    verdict = static_equivalent(sol_a, lib_a, mutated, lib_a, floor)
    assert not verdict.equivalent
    assert verdict.proven_by is None


def test_observational_agrees_with_itself_and_splits_on_a_real_difference() -> None:
    # Over REAL primitives (al1's floor), a program is observationally equal to itself, and a
    # genuinely different program is refuted with a concrete counterexample grid.
    loaded = load_ladder("al1-mirror")
    library = loaded.libraries[-1]
    grids = exact_grids({(3, 3), (2, 4)})
    same = Apply("flip_h", (Input(),))
    other = Apply("flip_v", (Input(),))
    agree = observationally_equivalent_programs(same, library, same, library, grids)
    assert agree.equivalent and agree.counterexample is None and agree.cases_tested == len(grids)
    split = observationally_equivalent_programs(same, library, other, library, grids)
    assert not split.equivalent
    assert isinstance(split.counterexample, Grid)  # a reproducible witness, not just a bool


def test_observational_functions_is_exact_and_order_sensitive() -> None:
    # The decomposition-validation path: same signature, probed over grids x the COLOR battery,
    # compared EXACTLY -- no argument permutation (unlike behavioral.matches_target).
    def keep_two(grid: Grid, first: int, second: int) -> Grid:
        array = grid.array
        array[(array != first) & (array != second)] = 0
        return Grid(array)

    def keep_first_only(grid: Grid, first: int, _second: int) -> Grid:
        array = grid.array
        array[array != first] = 0
        return Grid(array)

    types = (GRID, COLOR, COLOR)
    reference = Primitive(name="keep_two", param_types=types, return_type=GRID, impl=keep_two)
    twin = Primitive(name="keep_two_again", param_types=types, return_type=GRID, impl=keep_two)
    wrong = Primitive(name="keep_first", param_types=types, return_type=GRID, impl=keep_first_only)

    grids = edge_grids({(3, 3)})
    assert observationally_equivalent_functions(reference, twin, grids).equivalent
    split = observationally_equivalent_functions(reference, wrong, grids)
    assert not split.equivalent
    assert split.counterexample is not None  # the offending (grid, color, color) tuple


def test_exact_grid_battery_is_deterministic_and_covers_the_edges() -> None:
    # Determinism matters: a verdict must be reproducible and a counterexample stable.
    assert exact_grids({(3, 3)}) == exact_grids({(3, 3)})
    battery = edge_grids({(2, 2)})
    assert Grid.from_list([[0]]) in battery  # the minimal grid is always probed
    assert any(len(set(grid.to_list()[0])) == 1 for grid in battery)  # a uniform row
    assert any(0 not in {c for row in grid.to_list() for c in row} for grid in battery)  # 0 absent
