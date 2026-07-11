"""Content hashing (core/hashing.py) and Corpus.content_hash — the basis of run identity."""

from __future__ import annotations

import pytest

from arc_lab.core.annotation import Synthetic, TaskMeta
from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.hashing import ID_LENGTH, canonical_json, content_id
from arc_lab.core.task import Example, Task

# -- canonical_json / content_id --------------------------------------------


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_is_tight() -> None:
    assert canonical_json({"a": [1, 2]}) == '{"a":[1,2]}'


def test_canonical_json_rejects_non_json() -> None:
    with pytest.raises(TypeError):
        canonical_json({"a": {1, 2}})  # a set must never hash by repr


def test_content_id_is_stable_and_sized() -> None:
    first = content_id({"x": [1, 2, 3]})
    second = content_id({"x": [1, 2, 3]})
    assert first == second
    assert len(first) == ID_LENGTH
    assert content_id({"x": [1, 2, 3]}, length=8) == first[:8]


def test_content_id_distinguishes_values() -> None:
    assert content_id({"x": 1}) != content_id({"x": 2})


# -- Corpus.content_hash ------------------------------------------------------


def _grid(value: int) -> Grid:
    return Grid.from_list([[value, 0], [0, value]])


def _task(task_id: str, value: int) -> Task:
    example = Example(input=_grid(value), output=_grid(value))
    return Task(task_id=task_id, train=(example,), test=(example,))


def test_same_content_same_hash_even_across_names() -> None:
    tasks = [_task("t1", 1), _task("t2", 2)]
    assert Corpus.of("a", tasks).content_hash() == Corpus.of("b", tasks).content_hash()


def test_content_change_moves_hash() -> None:
    base = Corpus.of("c", [_task("t1", 1)])
    changed_grid = Corpus.of("c", [_task("t1", 2)])
    changed_id = Corpus.of("c", [_task("renamed", 1)])
    assert base.content_hash() != changed_grid.content_hash()
    assert base.content_hash() != changed_id.content_hash()


def test_entry_order_is_identity() -> None:
    t1, t2 = _task("t1", 1), _task("t2", 2)
    assert Corpus.of("c", [t1, t2]).content_hash() != Corpus.of("c", [t2, t1]).content_hash()


def test_meta_is_identity() -> None:
    task = _task("t1", 1)
    plain = Corpus.of("c", [task])
    annotated = Corpus.of("c", [task], meta=TaskMeta(provenance=Synthetic(generator="gen")))
    assert plain.content_hash() != annotated.content_hash()


def test_missing_test_output_hashes() -> None:
    example = Example(input=_grid(1), output=None)
    task = Task(task_id="t", train=(example,), test=(example,))
    corpus = Corpus.of("c", [task])
    assert len(corpus.content_hash()) == ID_LENGTH
