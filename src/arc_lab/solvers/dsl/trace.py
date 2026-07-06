"""Cross-cutting trace context for the search logging.

The per-candidate DEBUG trace is emitted deep inside the strategies, which have no
notion of *which* task is being solved. Rather than thread a task id through every
``find``/``consider`` call, we bind it once at the solver boundary
(:meth:`ProgramSearchSolver.predict`) into a :class:`~contextvars.ContextVar` and
copy it onto every log record with a :class:`logging.Filter`. Installing the filter
adds ``%(task_id)s`` to each line, so the otherwise task-blind trace becomes
greppable by task (``grep 007bbfb7 trace.log``).

Kept deliberately dependency-free and self-contained; if the trace grows into a
structured event stream, ``structlog``'s bound-context loggers would subsume this
(see the TODO in ``cli.py``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

#: The task currently being solved, or ``"-"`` outside any solve.
_current_task_id: ContextVar[str] = ContextVar("arc_lab_task_id", default="-")


@contextmanager
def task_context(task_id: str) -> Iterator[None]:
    """Bind ``task_id`` to the trace context for the duration of the block."""
    token = _current_task_id.set(task_id)
    try:
        yield
    finally:
        _current_task_id.reset(token)


class TaskIdFilter(logging.Filter):
    """Copy the current task id onto every record as ``%(task_id)s``.

    Attach to the *handler* (not a logger) so it also stamps records that
    propagate up from the ``arc_lab.solvers.dsl`` subtree.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Assign via __dict__ so mypy/ruff don't flag a dynamic LogRecord attribute.
        record.__dict__.setdefault("task_id", _current_task_id.get())
        return True
