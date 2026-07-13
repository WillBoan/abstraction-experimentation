"""Corpus surface: the solver-facing view yields pure Tasks; meta rides alongside."""

from __future__ import annotations

from arc_lab.core.annotation import Real, Split, Synthetic, TaskMeta
from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task


def _task(task_id: str) -> Task:
    grid = Grid.from_list([[1]])
    return Task(task_id=task_id, train=(Example(grid, grid),), test=(Example(grid, grid),))


def test_of_attaches_shared_meta_and_exposes_pure_tasks() -> None:
    corpus = Corpus.of("real", [_task("a"), _task("b")], meta=TaskMeta(Real("real")))
    assert len(corpus) == 2
    assert [t.task_id for t in corpus] == ["a", "b"]  # __iter__ yields Task
    assert all(isinstance(t, Task) for t in corpus.tasks)
    assert corpus.get("a").task_id == "a"  # get() yields the pure Task
    assert corpus.get_annotated("a").meta == TaskMeta(Real("real"))


def test_get_annotated_missing_raises() -> None:
    corpus = Corpus.of("c", [_task("a")])
    try:
        corpus.get_annotated("missing")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected KeyError")


def test_split_style_partition_preserves_meta() -> None:
    from arc_lab.core.dataset import split_dataset

    entries = Corpus(
        name="c",
        entries=(
            Corpus.of("c", [_task("a")], meta=TaskMeta(Synthetic("g"), split=Split.TRAIN)).entries[
                0
            ],
            Corpus.of(
                "c", [_task("b")], meta=TaskMeta(Synthetic("g"), split=Split.HELDOUT)
            ).entries[0],
        ),
    )
    a, b = split_dataset(entries)
    assert a.get_annotated("a").meta is not None
    assert a.get_annotated("a").meta.split is Split.TRAIN  # type: ignore[union-attr]
    assert b.get_annotated("b").meta.split is Split.HELDOUT  # type: ignore[union-attr]
