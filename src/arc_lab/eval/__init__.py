"""Evaluation: ARC scoring rules — paradigm-agnostic (grids in, booleans out).

The old experiment runner (``eval.runner``) is pre-overhaul code that dies with the
``solvers/`` tree; it is deliberately NOT re-exported here, so importing this package
never touches the old tree. The execution layer's driver is
``arc_lab.program_search.execution.execute``.
"""

from arc_lab.eval.scoring import score_task, score_test_input

__all__ = ["score_task", "score_test_input"]
