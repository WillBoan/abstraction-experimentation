"""Offline analysis of program search: metrics and the durable run artifact.

This layer *introspects* a program-search solver — the programs it finds, the search
effort it spends — to measure abstraction formation, rather than just solve-count. It
sits beside the solver-agnostic ``eval`` harness (never inside the narrow
``Solver.predict`` contract), because compression and search-effort are DSL concepts an
LLM or neural solver would not share.

* :mod:`compression` — two-part MDL of a solved corpus (the governance objective).
* :mod:`artifact` / :mod:`runner` — the ``run`` artifact: a deterministic, content-hashed,
  resumable record of one solver x dataset x library.
"""

from arc_lab.solvers.dsl.analysis.artifact import RunCoordinates, TaskRecord
from arc_lab.solvers.dsl.analysis.compression import (
    CompressionMetric,
    DescriptionLength,
    TwoPartMDL,
    compression_ratio,
    speedup_ratio,
)
from arc_lab.solvers.dsl.analysis.runner import RunSummary, analyze

__all__ = [
    "CompressionMetric",
    "DescriptionLength",
    "RunCoordinates",
    "RunSummary",
    "TaskRecord",
    "TwoPartMDL",
    "analyze",
    "compression_ratio",
    "speedup_ratio",
]
