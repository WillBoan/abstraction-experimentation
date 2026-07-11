"""Per-task result records — the rows of ``results.json``.

``TaskScore`` is the scorer's verdict (``score_task``); ``TaskResult`` wraps it with
run provenance (task id, timing, error isolation). These are *records* (derived
outputs), never hashed into run identity.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskScore:
    """The scorer's verdict for one task: solved iff **every** test input is correct."""

    solved: bool
    per_test: tuple[bool, ...]

    def to_dict(self) -> dict[str, object]:
        return {"solved": self.solved, "per_test": list(self.per_test)}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TaskScore:
        solved, per_test = data.get("solved"), data.get("per_test")
        if not isinstance(solved, bool) or not isinstance(per_test, list):
            raise ValueError(f"malformed TaskScore: {data!r}")
        return cls(solved=solved, per_test=tuple(bool(item) for item in per_test))


@dataclass(frozen=True, slots=True)
class TaskResult:
    """One row of ``results.json``: a task's score plus timing and error isolation.

    ``error`` is set (and ``score`` is all-False) when the task's search or
    prediction raised — one broken task never aborts a run.
    """

    task_id: str
    score: TaskScore
    seconds: float
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "score": self.score.to_dict(),
            "seconds": self.seconds,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TaskResult:
        task_id, score, seconds = data.get("task_id"), data.get("score"), data.get("seconds")
        error = data.get("error")
        if (
            not isinstance(task_id, str)
            or not isinstance(score, Mapping)
            or not isinstance(seconds, (int, float))
            or not (error is None or isinstance(error, str))
        ):
            raise ValueError(f"malformed TaskResult: {data!r}")
        return cls(
            task_id=task_id,
            score=TaskScore.from_dict(score),
            seconds=float(seconds),
            error=error,
        )
