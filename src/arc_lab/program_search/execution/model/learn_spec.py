"""``LearnSpec``: sleep machinery + wake-sleep loop params — ALL in run identity.

The loop params live here (not on ``LearnEngine``) because they are activity-level
choices that must move the ``run_id``: ``iterations=3`` vs ``=5`` are different runs.
Sleep's *internal* governance (MDL threshold, proposer choice) lives on the concrete
``LearnEngine`` and is hashed via the engine's own serialisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias, get_args

from arc_lab.program_search.learn.learn_engine import LearnEngine

#: Which tasks a wake searches (design doc §3.7 — the schedule is an ARM LABEL, not a neutral
#: optimization; see the field docstring for what each mode does to measured costs):
#:
#: - ``full`` — every wake searches every task. The only mode whose end-to-end cost and
#:   whose "what sleep sees" are the loop's honest, unassisted measurements.
#: - ``skip-solved`` — solutions carry across wakes and solved tasks are not re-searched.
#:   Cheap screening; end-to-end cost is NOT full-wake comparable, and sleep sees carried
#:   solutions expressed in the OLD library rather than re-found in the grown one.
#: - ``curriculum`` — iteration ``i`` wakes only ``curriculum[i]``'s task ids (the
#:   oracle-schedule arm: the schedule itself encodes ladder knowledge the loop is being
#:   graded on discovering). Iterations past the last group fall back to the full corpus.
#:   Implies carrying, like ``skip-solved``.
WakeSchedule: TypeAlias = Literal["full", "skip-solved", "curriculum"]

_WAKE_SCHEDULES: tuple[str, ...] = get_args(WakeSchedule)


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
    #: Governs the ``full`` schedule only — the non-``full`` schedules imply carrying
    #: (``skip-solved`` IS carrying; a curriculum without carrying would hand sleep only the
    #: current group's solutions).
    reset_programs_each_wake: bool = True
    #: Telemetry only — scoring after each wake never feeds back into learning.
    score_each_wake: bool = False
    #: Which tasks each wake searches — an ARM LABEL in run identity: any non-``full`` value
    #: means the run's end-to-end cost, loop-overhead factor, and sleep-input claims are
    #: measured under assistance and must not be compared against full-wake cells.
    wake_schedule: WakeSchedule = "full"
    #: The ``curriculum`` schedule's groups: iteration ``i`` wakes exactly ``curriculum[i]``'s
    #: task ids (later iterations: full corpus). Required iff ``wake_schedule="curriculum"`` —
    #: an explicit value, never inferred from task metadata, so the executor stays blind to
    #: ladder structure and the schedule is plainly visible in the run identity.
    curriculum: tuple[tuple[str, ...], ...] | None = None

    def __post_init__(self) -> None:
        if self.wake_schedule not in _WAKE_SCHEDULES:
            raise ValueError(
                f"wake_schedule must be one of {_WAKE_SCHEDULES}, got {self.wake_schedule!r}"
            )
        if (self.wake_schedule == "curriculum") != (self.curriculum is not None):
            raise ValueError(
                "curriculum groups are required exactly when wake_schedule='curriculum' "
                f"(got wake_schedule={self.wake_schedule!r}, curriculum={self.curriculum!r})"
            )
