"""Ground-truth anchor for `a740d043` -- a SECOND task family (crop-and-recolour).

LADDER-PROCESS section 2 makes hand-authored anchoring the first hard gate and requires it pinned as
a test: everything downstream derives from the term, so it must not be allowed to rot. This pins the
term BEFORE any ladder exists for it -- unlike `test_real_arc_anchoring.py`, which is keyed by
ladder name and can only cover tasks that already have one.

Why this task matters to the batch: every existing real-task ladder is two-halves geometry
(split + combine) with fixed colour constants. This one CROPS to perceived content and routes the
background colour through a PERCEIVER (`most_common_color`), so it exercises a different shape and
a different kind of parameter.
"""

from __future__ import annotations

import pytest

from arc_lab.core.dataset import load_dataset
from arc_lab.core.task import Task
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR

TASK_ID = "a740d043"

_G = Input()
_BG = Apply("most_common_color", (_G,))

#: The honest term: the background colour is PERCEIVED, not a literal. A `map_color(..., 1, 0)`
#: form also passes on this corpus because every example happens to have background 1 -- exactly the
#: constant-subterm trap `constancy` exists to catch, so the perceiver form is the anchor.
SOLUTION: Program = Apply("map_color", (Apply("crop_to_content", (_G,)), _BG, Const(0, COLOR)))

#: The same competence with `crop_to_content` and `nonbg_mask` WITHHELD -- the route a ladder floor
#: would take, and the reason this task can host a ladder at all (`d_raw` 4 rather than 2).
SOLUTION_UNFOLDED: Program = Apply(
    "map_color",
    (
        Apply(
            "crop_to_mask",
            (_G, Apply("mask_complement", (Apply("mask_by_color", (_G, _BG)),))),
        ),
        _BG,
        Const(0, COLOR),
    ),
)


def _task() -> Task:
    for entry in load_dataset("arc1-train").entries:
        if entry.task.task_id == TASK_ID:
            return entry.task
    pytest.skip(f"{TASK_ID} not present in arc1-train")


@pytest.mark.parametrize("term", [SOLUTION, SOLUTION_UNFOLDED], ids=["gifted", "unfolded"])
def test_the_anchor_solves_every_example_including_heldout(term: Program) -> None:
    library = Library(name="registry", primitives=tuple(BASE_PRIMITIVES.values()))
    task = _task()
    examples = [*task.train, *task.test]
    assert examples, f"{TASK_ID} has no examples"
    for index, example in enumerate(examples):
        assert term.evaluate(example.input, library) == example.output, (
            f"{TASK_ID}: anchor disagrees with ground truth at example {index}"
        )


def test_the_two_anchors_agree_so_the_withheld_route_is_the_same_competence() -> None:
    """The unfolded form is what a floor withholding `crop_to_content`/`nonbg_mask` must search
    for; if it computed something else, the ladder's `d_raw` would describe a different function."""
    library = Library(name="registry", primitives=tuple(BASE_PRIMITIVES.values()))
    task = _task()
    for example in [*task.train, *task.test]:
        assert SOLUTION.evaluate(example.input, library) == SOLUTION_UNFOLDED.evaluate(
            example.input, library
        )
