"""``LearnSpec``: sleep machinery + wake-sleep loop params — ALL in run identity.

The loop params live here (not on ``LearnEngine``) because they are activity-level
choices that must move the ``run_id``: ``iterations=3`` vs ``=5`` are different runs.
Sleep's *internal* governance (MDL threshold, proposer choice) lives on the concrete
``LearnEngine`` and is hashed via the engine's own serialisation.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.learn.learn_engine import LearnEngine


@dataclass(frozen=True, slots=True, kw_only=True)
class LearnSpec:
    """The LEARN half of a :class:`Config`: one sleep engine + the loop around it."""

    learn_engine: LearnEngine
    #: Max wake-sleep cycles — a cap, not a mandate (see ``early_stop``).
    iterations: int
    #: Stop when sleep converges (library unchanged / no MDL gain).
    early_stop: bool = True
    #: Fresh search each wake: sleep must see solutions re-expressed in the grown
    #: library, and search-effort is a measured signal (EXECUTION.md, property 5).
    reset_programs_each_wake: bool = True
    #: Telemetry only — scoring after each wake never feeds back into learning.
    score_each_wake: bool = False
