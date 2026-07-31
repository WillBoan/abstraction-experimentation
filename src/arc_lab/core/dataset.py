"""Corpora — named collections of tasks loaded from the vendored ARC repos.

The ARC-AGI-1 and ARC-AGI-2 corpora live under ``data/`` as git submodules. This
module maps friendly names (``arc1-train``, ``arc2-eval``, ...) to their on-disk
locations and loads them into :class:`Corpus` objects.

A :class:`Corpus` stores :class:`AnnotatedTask` entries (each a pure :class:`Task` plus
solver-invisible :class:`TaskMeta`), but its iteration / indexing / ``tasks`` surface
yields the pure ``Task`` — so solvers and the eval harness never see metadata (blindness).
Meta-aware code reads ``entries``.

Two loaders, one return type: :func:`load_dataset` for the vendored ARC corpora and
:func:`load_testbed` for the generated synthetic ones, both yielding a :class:`Corpus`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from arc_lab.core.annotation import AnnotatedTask, Real, Split, Synthetic, TaskMeta
from arc_lab.core.hashing import content_id
from arc_lab.core.task import Example, Task, load_tasks

# Repo root: this file is <root>/src/arc_lab/core/dataset.py
_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_DATA_ROOT: Final = _REPO_ROOT / "data"
#: Synthetic learning testbeds (generated + committed) live here, not under data/.
_TESTBED_ROOT: Final = _REPO_ROOT / "testbeds"

# Friendly name -> path relative to the data root.
ARC_DATASETS: Final[dict[str, str]] = {
    "arc1-train": "arc-agi-1/data/training",
    "arc1-eval": "arc-agi-1/data/evaluation",
    "arc2-train": "arc-agi-2/data/training",
    "arc2-eval": "arc-agi-2/data/evaluation",
}


def dataset_path(name: str) -> Path:
    """Resolve a friendly dataset name to an absolute directory path."""
    try:
        rel = ARC_DATASETS[name]
    except KeyError:
        known = ", ".join(sorted(ARC_DATASETS))
        raise KeyError(f"unknown dataset {name!r}; known datasets: {known}") from None
    return _DATA_ROOT / rel


@dataclass(frozen=True, slots=True)
class Corpus:
    """An ordered, named collection of tasks (real and/or synthetic).

    Stores :class:`AnnotatedTask` entries; the solver-facing surface (``__iter__``,
    ``__getitem__``, ``get``, ``tasks``) yields the pure :class:`Task`. Meta-aware code
    reads ``entries`` / ``get_annotated``.
    """

    name: str
    entries: tuple[AnnotatedTask, ...]

    @classmethod
    def of(
        cls,
        name: str,
        tasks: Iterable[Task],
        *,
        meta: TaskMeta | None = None,
    ) -> Corpus:
        """Build a corpus from plain tasks, attaching the same ``meta`` to each."""
        return cls(name=name, entries=tuple(AnnotatedTask(task, meta) for task in tasks))

    @property
    def tasks(self) -> tuple[Task, ...]:
        """The pure tasks — what solvers and the eval harness see."""
        return tuple(entry.task for entry in self.entries)

    def content_hash(self) -> str:
        """A content-addressed id over the corpus's *entries* — the corpus half of a ``run_id``.

        Hashes task ids, every example grid, and each entry's meta. The corpus ``name`` is
        deliberately **excluded**: identity is content-addressed, so identical content under two
        names is the same corpus for run-caching purposes (the name is provenance — recorded in
        ``runspec.json``, never hashed). Entry *order* is included: a corpus is an ordered
        collection, and order can affect a run's trace.
        """

        def example_data(example: Example) -> dict[str, object]:
            return {
                "input": example.input.to_list(),
                "output": example.output.to_list() if example.output is not None else None,
            }

        def entry_data(entry: AnnotatedTask) -> dict[str, object]:
            return {
                "task_id": entry.task.task_id,
                "train": [example_data(ex) for ex in entry.task.train],
                "test": [example_data(ex) for ex in entry.task.test],
                "meta": entry.meta.to_dict() if entry.meta is not None else None,
            }

        return content_id([entry_data(entry) for entry in self.entries])

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[Task]:
        return (entry.task for entry in self.entries)

    def __getitem__(self, index: int) -> Task:
        return self.entries[index].task

    def get(self, task_id: str) -> Task:
        """Fetch a single task by id, or raise ``KeyError``."""
        return self.get_annotated(task_id).task

    def get_annotated(self, task_id: str) -> AnnotatedTask:
        """Fetch a single annotated entry by id, or raise ``KeyError``."""
        for entry in self.entries:
            if entry.task.task_id == task_id:
                return entry
        raise KeyError(f"task {task_id!r} not found in corpus {self.name!r}")


def load_dataset(name: str, *, limit: int | None = None) -> Corpus:
    """Load a named ARC corpus (``arc1-train``, ...) from the vendored datasets under ``data/``.

    Named for its *source* — the ARC datasets — and paired with :func:`load_testbed`, which
    loads the synthetic ones. Both return a :class:`Corpus`; ``limit`` truncates to the first
    *n* tasks. To resolve a name across both sources (plus ``:split`` suffixes), the CLI's
    ``_corpora.load_corpus`` is the dispatcher over this pair.
    """
    path = dataset_path(name)
    if not path.is_dir():
        raise FileNotFoundError(
            f"dataset directory missing: {path}\n"
            "Did you initialise the submodules?  git submodule update --init --recursive"
        )
    tasks = load_tasks(path)
    if limit is not None:
        tasks = tasks[:limit]
    return Corpus.of(name, tasks, meta=TaskMeta(provenance=Real(name)))


def load_testbed(name: str) -> Corpus:
    """Load a generated synthetic testbed from ``testbeds/<name>/tasks/``.

    Testbeds are ARC-format task directories, so they load exactly like a real dataset;
    the sibling ``manifest.json`` records each task's ground-truth label and split, which
    become the (solver-invisible) :class:`TaskMeta`.
    """
    root = _TESTBED_ROOT / name
    path = root / "tasks"
    if not path.is_dir():
        raise FileNotFoundError(f"testbed {name!r} not found at {path}; generate it first")
    manifest = _read_testbed_manifest(root / "manifest.json")
    entries = tuple(
        AnnotatedTask(task, _synthetic_meta(name, manifest.get(task.task_id, {})))
        for task in load_tasks(path)
    )
    return Corpus(name=name, entries=entries)


def _read_testbed_manifest(path: Path) -> dict[str, dict[str, str]]:
    """Map ``task_id -> {label, split}`` from a testbed manifest (empty if absent)."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("tasks", []) if isinstance(data, dict) else []
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("task_id"), str):
            out[row["task_id"]] = {k: str(v) for k, v in row.items() if k != "task_id"}
    return out


def _synthetic_meta(generator: str, row: dict[str, str]) -> TaskMeta:
    split_raw = row.get("split")
    split = Split(split_raw) if split_raw in ("train", "heldout") else None
    return TaskMeta(provenance=Synthetic(generator), split=split, label=row.get("label"))


def split_corpus(
    corpus: Corpus, *, name_a: str | None = None, name_b: str | None = None
) -> tuple[Corpus, Corpus]:
    """Deterministic disjoint parity split (even / odd index) into two named halves.

    Distinct names matter: the name feeds ``RunCoordinates`` (and the ``run_id`` hash),
    so the two halves' run artifacts never collide. Used for held-out transfer. Entries
    keep their metadata across the split.
    """
    return (
        Corpus(name=name_a or f"{corpus.name}:A", entries=corpus.entries[0::2]),
        Corpus(name=name_b or f"{corpus.name}:B", entries=corpus.entries[1::2]),
    )
