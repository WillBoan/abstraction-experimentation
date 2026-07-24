"""The committed check register is a projection of ``CHECK_PLAN``, not a parallel list.

A check whose metadata changes -- or a new check added to the plan -- must be regenerated into
``docs/abstraction_ladders/LINT-CHECKS.md`` or this fails, so the two cannot drift.
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.program_search.ladders.checks import CHECK_PLAN
from arc_lab.program_search.ladders.checks.register import REGISTER_PATH, render_register

REPO = Path(__file__).resolve().parents[3]


def test_the_committed_register_matches_the_plan() -> None:
    committed = (REPO / REGISTER_PATH).read_text()
    assert committed == render_register(), (
        "LINT-CHECKS.md is stale -- regenerate with "
        f"`uv run arc-lab lint-checks --out {REGISTER_PATH}`"
    )


def test_the_register_covers_every_check() -> None:
    text = render_register()
    for index, check in enumerate(CHECK_PLAN, start=1):
        assert f"{index}. `{check.code}`" in text, f"{check.code} missing from the run order"
        assert f"| `{check.code}`" in text, f"{check.code} missing from its family table"
        assert check.summary in text, f"{check.code} summary missing"
