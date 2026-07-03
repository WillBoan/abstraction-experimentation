"""Trivial baseline solvers — the scoring floor.

:class:`IdentitySolver` returns each test input unchanged. It solves almost
nothing, but it proves the harness end-to-end and gives every other solver a
number to beat.
"""

from __future__ import annotations

from arc_lab.core.task import Task
from arc_lab.solvers.base import Prediction, Solver


class IdentitySolver(Solver):
    """Predict the input grid unchanged as the output."""

    name = "identity"

    def predict(self, task: Task) -> Prediction:
        return [[example.input] for example in task.test]
