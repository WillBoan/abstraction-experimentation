"""Datasets — named collections of tasks loaded from the vendored ARC repos.

The ARC-AGI-1 and ARC-AGI-2 corpora live under ``data/`` as git submodules. This
module maps friendly names (``arc1-train``, ``arc2-eval``, ...) to their on-disk
locations and loads them into :class:`Dataset` objects.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from arc_lab.core.task import Task, load_tasks

# Repo root: this file is <root>/src/arc_lab/core/dataset.py
_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_DATA_ROOT: Final = _REPO_ROOT / "data"
#: Synthetic learning testbeds (generated + committed) live here, not under data/.
_TESTBED_ROOT: Final = _REPO_ROOT / "testbeds"

# Friendly name -> path relative to the data root.
DATASETS: Final[dict[str, str]] = {
    "arc1-train": "arc-agi-1/data/training",
    "arc1-eval": "arc-agi-1/data/evaluation",
    "arc2-train": "arc-agi-2/data/training",
    "arc2-eval": "arc-agi-2/data/evaluation",
}


def dataset_path(name: str) -> Path:
    """Resolve a friendly dataset name to an absolute directory path."""
    try:
        rel = DATASETS[name]
    except KeyError:
        known = ", ".join(sorted(DATASETS))
        raise KeyError(f"unknown dataset {name!r}; known datasets: {known}") from None
    return _DATA_ROOT / rel


@dataclass(frozen=True, slots=True)
class Dataset:
    """An ordered, named collection of :class:`Task` objects."""

    name: str
    tasks: tuple[Task, ...]

    def __len__(self) -> int:
        return len(self.tasks)

    def __iter__(self) -> Iterator[Task]:
        return iter(self.tasks)

    def __getitem__(self, index: int) -> Task:
        return self.tasks[index]

    def get(self, task_id: str) -> Task:
        """Fetch a single task by id, or raise ``KeyError``."""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(f"task {task_id!r} not found in dataset {self.name!r}")


def load_dataset(name: str, *, limit: int | None = None) -> Dataset:
    """Load a named dataset; ``limit`` truncates to the first *n* tasks."""
    path = dataset_path(name)
    if not path.is_dir():
        raise FileNotFoundError(
            f"dataset directory missing: {path}\n"
            "Did you initialise the submodules?  git submodule update --init --recursive"
        )
    tasks = load_tasks(path)
    if limit is not None:
        tasks = tasks[:limit]
    return Dataset(name=name, tasks=tasks)


def load_testbed(name: str) -> Dataset:
    """Load a generated synthetic testbed from ``testbeds/<name>/tasks/``.

    Testbeds are ARC-format task directories, so they load exactly like a real dataset;
    the sibling ``manifest.json`` records how they were generated (see ``learn/taskgen.py``).
    """
    path = _TESTBED_ROOT / name / "tasks"
    if not path.is_dir():
        raise FileNotFoundError(f"testbed {name!r} not found at {path}; generate it first")
    return Dataset(name=name, tasks=load_tasks(path))


def split_dataset(
    dataset: Dataset, *, name_a: str | None = None, name_b: str | None = None
) -> tuple[Dataset, Dataset]:
    """Deterministic disjoint parity split (even / odd index) into two named halves.

    Distinct names matter: the name feeds ``RunCoordinates`` (and the ``run_id`` hash),
    so the two halves' run artifacts never collide. Used for held-out transfer.
    """
    return (
        Dataset(name=name_a or f"{dataset.name}:A", tasks=dataset.tasks[0::2]),
        Dataset(name=name_b or f"{dataset.name}:B", tasks=dataset.tasks[1::2]),
    )
