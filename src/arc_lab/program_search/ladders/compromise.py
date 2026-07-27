"""Compromise Options: the named, uniform concept for "this reduces cost and costs data".

Some settings buy a runnable experiment at the price of a weaker claim. Each one is individually
defensible and each one is easy to forget by the time the number is quoted -- which is how a
measurement made under assistance ends up compared against one that was not. So they are DATA here
rather than lore, each stating three things: what it saves, what it forfeits, and when it is
justified.

**Detected, never declared.** :func:`compromises_in` reads them off the ``Config`` itself, so a run
cannot be under an option without saying so -- the failure mode this exists to prevent is a
forgotten label, and a label you have to remember to set is exactly the thing that gets forgotten.
The read side then banners them wherever the numbers appear (``report.py``), following the
``wake_schedule`` arm-label precedent that already worked.

The default position is NO compromise: ``ladder_default_config`` leaves ``solution_limit`` unset
precisely so one exhaustive run yields three cost quantities at once (``first_solution_index``,
``cheapest_solution_index``, ``considered``) -- the RQ1 cost-to-first vs cost-to-exhaust asymmetry
needs no machinery, only reading the right column.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.execution.model.config import Config

#: The library-name suffix :func:`ladders.probe.prune_library` stamps on an oracle-pruned library.
PRUNED_SUFFIX = ":pruned"


@dataclass(frozen=True, slots=True)
class CompromiseOption:
    """One named cost/data trade. ``severity`` is how much of a claim it costs."""

    code: str
    label: str
    saves: str
    forfeits: str
    when_justified: str
    #: ``"voids-cost"`` -- cost comparisons are meaningless under it; ``"narrows"`` -- some
    #: quantities survive exactly, others do not.
    severity: str


SOLUTION_LIMIT = CompromiseOption(
    code="solution-limit",
    label="early stop at the first solution(s)",
    saves="large, whenever solutions are found well below `depth_limit` -- the run stops paying "
    "instead of enumerating the rest of the budget",
    forfeits="`cheapest_solution_index`, cost-to-exhaust, and a complete `by_primitive` "
    "attribution. **AND the loop-overhead factor** -- added 2026-07-27 after it was found missing "
    "from this list by measurement, not by review: `laddered_marginal` is read off the CHAIN and "
    "`laddered_end_to_end` off the CLIMB, and an early stop truncates the two at different points, "
    "so their ratio stops comparing like with like. Observed range moved 2.16-3.88x -> 0.30-10.52x, "
    "including a member reporting end-to-end BELOW marginal (0.30x), which is impossible for a "
    "quantity defined as re-search overhead. Do not quote loop overhead from a run carrying this "
    "option. RQ1 SURVIVES: `first_solution_index` is exact either way",
    when_justified="a cell whose only question is cost-to-first, or a guarded baseline arm where "
    "exhausting is the thing being avoided (the raw arm runs `solution_limit=1` by design)",
    severity="narrows",
)

PRUNED_LIBRARY = CompromiseOption(
    code="pruned-library",
    label="oracle-pruned library",
    saves="makes an otherwise unrunnable ladder runnable -- measured ~5.3e6x on "
    "`dae9d2b5-halves-union` rung 1",
    forfeits="**all cost interpretation (RQ1 void)**. The library was chosen by reading the "
    "answer, so what it measures is not a search anyone could have run. Learnability survives "
    "(recovery / junk / cascade are about what sleep does with what wake found)",
    when_justified="pricing a floor (the probe's `FloorTax` cell), or sizing a guard. NEVER as a "
    "run whose cost is quoted",
    severity="voids-cost",
)

WAKE_SCHEDULE = CompromiseOption(
    code="wake-schedule",
    label="assisted wake schedule (`skip-solved` / curriculum)",
    saves="climb wall-clock, by not re-searching what is already solved",
    forfeits="end-to-end cost, the loop-overhead factor, and what sleep saw -- all measured under "
    "assistance (design doc 3.7)",
    when_justified="an arm whose question is about learning rather than cost, paired with an "
    "honest `full` cell for any recovery claim",
    severity="narrows",
)

#: The registry, in reporting order (worst first). Machinery-as-data, like `PRESETS`.
COMPROMISE_OPTIONS: tuple[CompromiseOption, ...] = (
    PRUNED_LIBRARY,
    WAKE_SCHEDULE,
    SOLUTION_LIMIT,
)

_BY_CODE = {option.code: option for option in COMPROMISE_OPTIONS}


def compromises_in(config: Config) -> tuple[CompromiseOption, ...]:
    """Which options this config is running under -- read off the config, never declared."""
    found: list[CompromiseOption] = []
    if config.library.name.endswith(PRUNED_SUFFIX):
        found.append(PRUNED_LIBRARY)
    learn = config.learn
    if learn is not None and (
        getattr(learn, "wake_schedule", "full") != "full" or getattr(learn, "curriculum", None)
    ):
        found.append(WAKE_SCHEDULE)
    if config.budget.solution_limit is not None:
        found.append(SOLUTION_LIMIT)
    return tuple(option for option in COMPROMISE_OPTIONS if option in found)


def get(code: str) -> CompromiseOption:
    return _BY_CODE[code]
