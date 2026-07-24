"""The cfb2ce5a drafts, now that their floor has bodies: do they solve the real ARC task?

A reference implementation cannot be validated against a docstring the same author wrote. The one
external check that means anything is the task's own ground truth — so this drives each draft's top
solution over every train example *and* the held-out test, against `arc1-eval`.

It also closes the loop on ``diff-ladder``: v1 and v3 were proved equal STATICALLY, with no bodies at
all. Their agreeing on real grids is that proof cashed out, and a standing check that the static layer
is not quietly lying.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.core.dataset import load_dataset
from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.program_search.ladders.lang.load import resolve
from arc_lab.program_search.ladders.lang.parse import parse_ladder_file

_DRAFTS = Path(__file__).resolve().parents[3] / "src/arc_lab/program_search/ladders/drafts"
_DRAFT_NAMES = ("cfb2ce5a-1-basic", "cfb2ce5a-3-parameterized")


def _cfb2ce5a() -> Task:
    try:
        corpus = load_dataset("arc1-eval")
    except FileNotFoundError:  # submodules absent: skip cleanly (CLAUDE.md)
        pytest.skip("arc1-eval dataset not available (git submodule update --init)")
    for task in corpus.tasks:
        if task.task_id == "cfb2ce5a":
            return task
    pytest.skip("cfb2ce5a not present in arc1-eval")


@pytest.mark.parametrize("name", _DRAFT_NAMES)
def test_a_draft_resolves_with_no_assumed_primitives(name: str) -> None:
    # `resolve` without `assume_missing` is the real bar: every floor name must be a live primitive.
    # Before `primitives/cfb2ce5a_reference.py` these drafts could only load as sketches.
    loaded = resolve(parse_ladder_file(_DRAFTS / f"{name}.ladder"))
    assert not loaded.assumed


@pytest.mark.parametrize("name", _DRAFT_NAMES)
def test_a_draft_solves_cfb2ce5a_including_the_held_out_test(name: str) -> None:
    task = _cfb2ce5a()
    loaded = resolve(parse_ladder_file(_DRAFTS / f"{name}.ladder"))
    program, library = loaded.solutions["cfb2ce5a"], loaded.libraries[-1]
    examples = [*task.train, *task.test]
    assert len(examples) == 4  # 3 train + 1 test; a corpus change that alters this should surface
    for example in examples:
        assert program.evaluate(example.input, library) == example.output


def test_the_two_drafts_agree_on_the_real_grids_as_the_static_proof_predicted() -> None:
    # `diff-ladder` proves v1 == v3 by unfold-and-compare, with no bodies. This is the cash-out.
    task = _cfb2ce5a()
    outputs: list[list[Grid]] = []
    for name in _DRAFT_NAMES:
        loaded = resolve(parse_ladder_file(_DRAFTS / f"{name}.ladder"))
        program, library = loaded.solutions["cfb2ce5a"], loaded.libraries[-1]
        results = [program.evaluate(ex.input, library) for ex in [*task.train, *task.test]]
        outputs.append([r for r in results if isinstance(r, Grid)])
    assert outputs[0] == outputs[1]
