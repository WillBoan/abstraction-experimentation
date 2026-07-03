"""End-to-end tests against the vendored ARC datasets.

These require the git submodules to be initialised; they skip cleanly if not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.core.dataset import dataset_path, load_dataset
from arc_lab.eval.runner import run
from arc_lab.solvers import make_solver
from arc_lab.viz import render_task

pytestmark = pytest.mark.skipif(
    not dataset_path("arc1-train").is_dir(),
    reason="ARC submodules not initialised (git submodule update --init --recursive)",
)


def test_load_real_dataset() -> None:
    ds = load_dataset("arc1-train", limit=5)
    assert len(ds) == 5
    assert all(len(task.train) >= 1 for task in ds)


def test_run_dsl_on_slice() -> None:
    ds = load_dataset("arc1-train", limit=20)
    report = run(make_solver("dsl"), ds)
    assert report.total == 20
    assert report.errored == 0
    assert 0.0 <= report.accuracy <= 1.0


def test_render_task_to_png(tmp_path: Path) -> None:
    ds = load_dataset("arc1-train", limit=1)
    out = tmp_path / "task.png"
    render_task(ds[0], save=out)
    assert out.exists() and out.stat().st_size > 0
