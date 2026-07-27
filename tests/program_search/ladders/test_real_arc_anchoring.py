"""Real-ARC-anchored ladders: does the top solution actually solve the task it names?

A `.ladder` file DERIVES its task outputs by evaluating the declared solution (LADDER-FORMAT DRV-3),
so a ladder can be perfectly self-consistent while computing something that is not the ARC task at
all. The only external check that means anything is the task's own ground truth.

This is the general form of the check `test_cfb2ce5a_cohort.py` makes for that one task: a registry
ladder anchored on a real ARC task must reproduce it on every train example AND its held-out test.
"""

from __future__ import annotations

import pytest

from arc_lab.core.dataset import load_dataset
from arc_lab.core.task import Task
from arc_lab.program_search.ladders.registry import ladder_paths, load_ladder

#: ladder name -> (corpus, the top task id, which is the real ARC task id). A synthetic ladder
#: (al1-al20) has no row and is not checked.
_ANCHORED: dict[str, tuple[str, str]] = {
    "dae9d2b5-halves-union": ("arc1-train", "dae9d2b5"),
    # The granularity pair over the Grid-valued half-split floor: same task, same top, two cut
    # densities. Both must reproduce the real task, or the pair compares two different things.
    "dae9d2b5-split-recolor": ("arc1-train", "dae9d2b5"),
    "dae9d2b5-split-halves": ("arc1-train", "dae9d2b5"),
    # The `lean` arms differ from their parents only in `max_pool`, so they must still solve the
    # real task -- a budget calibration that changed WHAT is computed would be worthless.
    "dae9d2b5-split-recolor-lean": ("arc1-train", "dae9d2b5"),
    "dae9d2b5-split-halves-lean": ("arc1-train", "dae9d2b5"),
}


def _arc_task(corpus_name: str, task_id: str) -> Task:
    try:
        corpus = load_dataset(corpus_name)
    except FileNotFoundError:  # submodules absent: skip cleanly (CLAUDE.md)
        pytest.skip(f"{corpus_name} not available (git submodule update --init --recursive)")
    for entry in corpus.entries:
        if entry.task.task_id == task_id:
            return entry.task
    pytest.skip(f"{task_id} not present in {corpus_name}")


def test_every_anchored_ladder_is_registered() -> None:
    """The map above must name ladders that exist -- otherwise a rename silently stops checking."""
    assert set(_ANCHORED) <= set(ladder_paths())


@pytest.mark.parametrize("name", sorted(_ANCHORED))
def test_an_anchored_ladder_solves_its_real_task(name: str) -> None:
    corpus_name, task_id = _ANCHORED[name]
    task = _arc_task(corpus_name, task_id)
    loaded = load_ladder(name)
    program, library = loaded.solutions[task_id], loaded.libraries[-1]
    examples = [*task.train, *task.test]
    assert examples, f"{task_id} has no examples"
    for index, example in enumerate(examples):
        assert program.evaluate(example.input, library) == example.output, (
            f"{name}: top solution disagrees with {task_id} ground truth at example {index}"
        )
