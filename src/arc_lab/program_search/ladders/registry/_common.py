"""Shared plumbing for ladder registry modules: testbed -> :class:`LadderSpec`.

Every ladder resolves its rungs' demonstrations and its Top Rung's task ids the same way -- by the
rung-name labels the generator wrote onto the testbed manifest. :func:`spec_from_testbed` does that
once, so a ladder module only has to state its Floor, its templates, and its reference config.

A rung's **target** template (what sleep should mint) is deliberately separate from the **demo**
template the generator used to build its tasks: they coincide for a ``full_solution`` rung, but a
rung whose target is not ``GRID -> GRID`` (so no task can have it as a whole solution) is
demonstrated by a grid-to-grid wrapper that merely *contains* it -- a ``fragment_identical`` rung.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from arc_lab.core.dataset import load_testbed
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.execution.studies import split_by_meta
from arc_lab.program_search.ladders.spec import (
    Demonstration,
    DemonstrationKind,
    LadderSpec,
    Rung,
    TopRung,
)
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.substrate.program import Program

#: One bridging rung, as a registry module states it: (name, target template, demonstration kind).
RungDef: TypeAlias = tuple[str, Program, DemonstrationKind]


def spec_from_testbed(
    testbed_name: str,
    *,
    reference_config: Config,
    rungs: Sequence[RungDef],
    top_solutions: Sequence[Program],
    budgets: Sequence[Budget] = (),
    top_label: str = "top",
) -> LadderSpec:
    """Build a :class:`LadderSpec` from a committed testbed, resolving tasks by their rung labels."""
    train, heldout = split_by_meta(load_testbed(testbed_name))

    def labelled(label: str) -> tuple[str, ...]:
        return tuple(
            entry.task.task_id
            for entry in train.entries
            if entry.meta is not None and entry.meta.label == label
        )

    return LadderSpec(
        reference_config=reference_config,
        rungs=tuple(
            Rung(
                level=level,
                target_abstraction=TargetAbstraction(name=name, template=template),
                demonstrations=tuple(
                    Demonstration(task_id=task_id, kind=kind) for task_id in labelled(name)
                ),
            )
            for level, (name, template, kind) in enumerate(rungs, start=1)
        ),
        top=TopRung(task_ids=labelled(top_label), reference_solutions=tuple(top_solutions)),
        train_corpus=train,
        heldout_corpus=heldout,
        budgets=tuple(budgets) or (reference_config.budget,),
    )
