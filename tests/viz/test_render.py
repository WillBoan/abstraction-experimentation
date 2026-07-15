"""``render_task`` smoke test against a real dataset task. Ported from the pre-overhaul
``tests/test_integration.py`` — ``render_task`` is live (used by ``arc-lab show``) but had no
direct test in the new-world tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.core.dataset import load_dataset
from arc_lab.viz import render_task

pytestmark = pytest.mark.slow


def test_render_task_to_png(tmp_path: Path) -> None:
    try:
        ds = load_dataset("arc1-train", limit=1)
    except FileNotFoundError:  # submodules absent: skip cleanly (CLAUDE.md)
        pytest.skip("arc1-train dataset not available (git submodule update --init)")
    out = tmp_path / "task.png"
    render_task(ds[0], save=out)
    assert out.exists() and out.stat().st_size > 0
