"""Extraction: the goal test that reads solutions off a built pool (§5.8 of ARCHITECTURE.md).

``_enumerate`` builds the full pool with no goal or target; extraction is the separate, thin step run
against it. A program *solves* the task iff it has the goal type and its signature equals ``target``
(the training outputs). Because ``target`` is a total signature and ``⊥ ≠ v``, ``sig == target``
already implies totality on the training contexts — no separate check. Consistency-with-training *is*
``sig == target``; ``constraints`` holds only the *extra* inductive-bias filters on the survivors.
"""

from __future__ import annotations

from arc_lab.core.task import Task

from ..substrate.library import Library
from ..substrate.program import Program
from ..substrate.types import Type
from .constraints import Constraint
from .pool import Pool
from .signature import Signature


def extract(
    pool: Pool,
    goal_type: Type,
    target: Signature,
    constraints: tuple[Constraint, ...],
    task: Task,
    library: Library,
) -> tuple[Program, ...]:
    """The goal-type programs whose signature equals `target` and pass every constraint, ranked.

    Ranked by an explicit key — cached cost, then program size, then serialization — so equal costs
    fall to a deterministic tiebreak and `Program`s are never compared directly (which would
    raise).

    Costs are read straight from the pooled entries (cached once at insertion, §5.7); nothing
    is re-evaluated here.
    """
    solutions = [
        entry
        for entry in pool.items_of_type(goal_type)
        if entry.sig == target
        and all(constraint.holds(entry.program, task, library) for constraint in constraints)
    ]
    solutions.sort(key=lambda entry: (entry.cost, entry.program.size(), str(entry.program)))
    return tuple(entry.program for entry in solutions)
