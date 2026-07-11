"""Tasks and examples — the ARC unit of a single puzzle.

A task is a handful of ``train`` input/output demonstrations plus one or more
``test`` inputs whose outputs a solver must infer. In the public datasets the
test outputs are included (so we can score locally); on a hidden set they would
be absent, which is why :class:`Example.output` is optional.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from arc_lab.core.grid import Grid


@dataclass(frozen=True, slots=True)
class Example:
    """A single input grid paired with its (optional) output grid."""

    input: Grid
    output: Grid | None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Example:
        out = d.get("output")
        return cls(
            input=Grid.from_list(d["input"]),
            output=Grid.from_list(out) if out is not None else None,
        )


#: A task's train examples — the ONLY task data the search stack receives
#: (``SearchEngine.run`` / ``Cost.of`` / ``Constraint.holds`` / ``BodySampler``), so
#: blindness to test examples is structural, not a promise (EXECUTION.md, Sync B).
TrainExamples: TypeAlias = tuple[Example, ...]


@dataclass(frozen=True, slots=True)
class Task:
    """One ARC task: its demonstrations and its held-out test inputs."""

    task_id: str
    train: tuple[Example, ...]
    test: tuple[Example, ...]

    @classmethod
    def from_dict(cls, task_id: str, d: Mapping[str, Any]) -> Task:
        return cls(
            task_id=task_id,
            train=tuple(Example.from_dict(e) for e in d["train"]),
            test=tuple(Example.from_dict(e) for e in d["test"]),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> Task:
        p = Path(path)
        with p.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(p.stem, data)

    @property
    def test_outputs(self) -> tuple[Grid, ...] | None:
        """The ground-truth test outputs, or ``None`` if any are missing."""
        outs = [e.output for e in self.test]
        if any(o is None for o in outs):
            return None
        return tuple(o for o in outs if o is not None)

    def __len__(self) -> int:
        return len(self.test)


def load_tasks(directory: str | Path) -> tuple[Task, ...]:
    """Load every ``*.json`` task in a directory, sorted by task id."""
    d = Path(directory)
    if not d.is_dir():
        raise FileNotFoundError(f"not a directory: {d}")
    paths = sorted(d.glob("*.json"), key=lambda p: p.stem)
    if not paths:
        raise FileNotFoundError(f"no task JSON files found in {d}")
    return tuple(Task.from_json_file(p) for p in paths)
