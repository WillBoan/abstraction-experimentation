"""The sleep interface — Sync point C of EXECUTION.md.

``LearnEngine.run`` is one *sleep*: it consumes the whole corpus's wake solutions at
once (cross-task compression needs the corpus in view) and returns the grown library.
The wake-sleep *loop* around it (iterations, early-stop, reset policy) is not here —
those are ``LearnSpec`` params in the run identity (``execution/model/learn_spec.py``);
sleep's internal governance (MDL threshold, proposer choice) belongs on concrete
subclasses of this ABC.

This file seeds the minimal agreed interface; concrete engines land with the learn
overhaul.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from arc_lab.program_search.substrate.library import Library
    from arc_lab.program_search.substrate.program import Program

#: One wake's harvest: task_id -> the (train-consistent) programs found for that task.
WakeSolutions: TypeAlias = "Mapping[str, tuple[Program, ...]]"


class LearnEngine(ABC):
    """Sleep: grow the library from a whole corpus's wake solutions."""

    @abstractmethod
    def run(self, library: Library, solutions: WakeSolutions) -> Library:
        """One sleep step: propose + govern abstractions, return the grown library."""
