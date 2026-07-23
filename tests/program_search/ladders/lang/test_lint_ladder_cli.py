"""`arc-lab lint-ladder` exit codes: a draft must never read as a sound ladder.

The command distinguishes three outcomes by exit code, so a hook or script can tell a
verified-sound ladder from one that merely loaded:

    0  clean    -- loaded and every lint check passed
    1  failed   -- a lint check failed, or the file could not load
    2  incomplete -- a draft: type-checked, but soundness unverified
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.cli.lint_ladder import _lint_one, _Outcome

_DRAFTS = Path(__file__).resolve().parents[4] / "src/arc_lab/program_search/ladders/drafts"


def test_a_clean_ladder_is_clean() -> None:
    assert _lint_one("al1-mirror", quiet=True, draft=False) is _Outcome.CLEAN


def test_a_ladder_that_fails_lint_reports_failed() -> None:
    assert _lint_one("al14-cell-row-grid", quiet=True, draft=False) is _Outcome.FAILED


def test_a_draft_is_incomplete_not_clean() -> None:
    """The load-bearing distinction: exit 2, not 0 -- a draft loaded but proved nothing about
    soundness, so a script must not treat it as a pass."""
    draft = _DRAFTS / "cfb2ce5a-1-basic.ladder"
    assert _lint_one(str(draft), quiet=True, draft=True) is _Outcome.INCOMPLETE


def test_a_draft_without_draft_mode_fails_to_load() -> None:
    """Its proposed primitives do not resolve, so plain load is a hard failure -- the flag is the
    deliberate opt-in to trusting declared signatures."""
    draft = _DRAFTS / "cfb2ce5a-1-basic.ladder"
    assert _lint_one(str(draft), quiet=True, draft=False) is _Outcome.FAILED
