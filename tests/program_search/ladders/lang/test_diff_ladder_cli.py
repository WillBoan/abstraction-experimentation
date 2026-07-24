"""`arc-lab diff-ladder` outcomes: the relationship picks the validator.

Three outcomes, distinguished by exit code so a hook or a try-a-simplification loop can branch:

    0  equal        -- proved statically, or no counterexample observationally
    1  different    -- a definite split, with a counterexample
    2  inconclusive -- could not tell (no static bridge across floors, and no bodies to run)
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.cli.diff_ladder import _compare_top, _Outcome, _resolve

_DRAFTS = Path(__file__).resolve().parents[4] / "src/arc_lab/program_search/ladders/drafts"


def _draft(name: str) -> str:
    return str(_DRAFTS / f"{name}.ladder")


def test_same_floor_refactor_is_proved_equal_without_bodies() -> None:
    """The headline case: cfb2ce5a v1 and v3 restructure the same computation over an identical,
    entirely ASSUMED floor -- so the static layer settles it and no primitive needs implementing."""
    a, b = _resolve(_draft("cfb2ce5a-1-basic")), _resolve(_draft("cfb2ce5a-3-parameterized"))
    assert set(a.floor.names()) == set(b.floor.names())
    assert _compare_top("cfb2ce5a", a, b, same_floor=True) is _Outcome.EQUAL


def test_floor_change_over_assumed_primitives_is_inconclusive_not_equal() -> None:
    """v4 moves to a fold-based floor. Static cannot bridge two vocabularies and the assumed
    primitives leave nothing to run -- so the honest answer is INCONCLUSIVE, never a false EQUAL."""
    a, b = _resolve(_draft("cfb2ce5a-1-basic")), _resolve(_draft("cfb2ce5a-4-fold"))
    assert set(a.floor.names()) != set(b.floor.names())
    assert _compare_top("cfb2ce5a", a, b, same_floor=False) is _Outcome.INCONCLUSIVE


def test_a_registered_ladder_compares_equal_to_itself() -> None:
    loaded = _resolve("al1-mirror")
    assert _compare_top("top-00", loaded, loaded, same_floor=True) is _Outcome.EQUAL


def test_resolve_accepts_both_a_registered_name_and_a_path() -> None:
    by_name = _resolve("al1-mirror")
    by_path = _resolve(_draft("cfb2ce5a-4-fold"))
    assert not by_name.assumed  # a real ladder resolves with every primitive implemented
    assert by_path.assumed  # a draft reports its assumed vocabulary instead of failing
    # v1's floor is implemented now (`substrate/primitives/cfb2ce5a_reference.py`), so it resolves like a real
    # ladder -- being a *draft* is about lacking a testbed, not about assumed primitives.
    assert not _resolve(_draft("cfb2ce5a-1-basic")).assumed
