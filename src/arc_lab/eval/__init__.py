"""Evaluation: ARC scoring rules — paradigm-agnostic (grids in, booleans out).

Scoring rules only — this package holds no driver. The execution layer's driver is
``arc_lab.program_search.execution.execute``. (The pre-overhaul ``eval.runner`` was
deleted with the ``solvers/`` tree on 2026-07-15.)
"""

from arc_lab.eval.scoring import score_task, score_test_input

__all__ = ["score_task", "score_test_input"]
