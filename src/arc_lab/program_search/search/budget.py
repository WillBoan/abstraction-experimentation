"""The `Budget`: the resource caps that bound a bottom-up search and guarantee termination.

`depth_limit` is the **inclusive cap on compositional depth** (leaf = 0): a program of depth
`d` is reachable iff `d <= depth_limit` — equivalently, the engine runs generations
`0..depth_limit`, generation 0 being the leaf seeding. It **strictly decreases** each time
enumeration recurses into a lambda body (:meth:`Budget.descend`), which alone guarantees lambda
synthesis terminates. `max_arity` caps variadic-primitive fan-out; `max_pool` caps the
per-round frontier. Neither cap needs to shrink on recursion.

`considered_limit` and `solution_limit` are the two **stop limits**: unlike the caps above, which
shape the space, these end the search outright. Three properties are easy to get wrong:

- **Per task, not per corpus.** Each task's search gets a fresh allowance (`execute.py` builds one
  `SearchTracker` per task). A per-corpus limit would make a task's allowance depend on corpus
  iteration order — non-determinism, in a system whose caching rests on content hashes.
- **Counted at absorption, and run-global.** `considered_limit` counts candidates *considered* —
  incremented when a candidate is evaluated, not when it is built — so it includes lambda-synthesis
  sub-search candidates, which share the run's one tracker while belonging to no generation.
- **`immediate` discards, it does not drain.** Candidates already built but not yet absorbed (the
  buffered function candidates, the `If` branch candidates) are dropped, so `considered` lands on
  exactly `considered_limit`. Draining them would overshoot and destroy the exactness that makes a
  censored baseline a usable denominator.

Each limit's `*_mode` picks between stopping the instant it trips and finishing the current
generation first. The defaults differ deliberately: exactness is the point of `considered_limit`,
whereas `solution_limit` defaults to `generation-end` so the retained solution is the cheapest of
its generation rather than merely the first found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

#: When a stop limit takes effect: the instant it trips, or at the end of the current generation.
StopMode = Literal["immediate", "generation-end"]

_STOP_MODES: tuple[str, ...] = get_args(StopMode)


@dataclass(frozen=True, slots=True)
class Budget:
    """The `Budget`: the resource caps that bound a bottom-up search and guarantee termination."""

    depth_limit: int
    max_arity: int
    max_pool: int
    #: Stop once this many candidates have been considered; `None` disables. See the module
    #: docstring — counted at absorption, run-global, per task.
    considered_limit: int | None = None
    considered_limit_mode: StopMode = "immediate"
    #: Stop once this many goal-matching candidates have been absorbed; `None` disables. Counts
    #: goal-matches pre-dedup, so it is not a count of distinct behaviours.
    solution_limit: int | None = None
    solution_limit_mode: StopMode = "generation-end"

    def __post_init__(self) -> None:
        # `execution/overrides.py` cannot type-check a `--set` against a field whose current value
        # is `None`, so validating here is what makes `--set budget.considered_limit=garbage` fail.
        for name in ("considered_limit", "solution_limit"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or value < 1):
                raise ValueError(f"{name} must be a positive int or None, got {value!r}")
        for name in ("considered_limit_mode", "solution_limit_mode"):
            value = getattr(self, name)
            if value not in _STOP_MODES:
                known = ", ".join(_STOP_MODES)
                raise ValueError(f"{name} must be one of {known}, got {value!r}")

    @property
    def exhausted(self) -> bool:
        """True when not even the leaf generation may run (`depth_limit` spent below zero)."""
        return self.depth_limit < 0

    def descend(self) -> Budget:
        """The budget for a nested lambda-body search: one less depth (the termination guarantee).

        Every other field carries over verbatim — the stop limits are run-global, so a sub-search
        must not be handed a fresh allowance. (Constructed positionally: a new field added above
        without a matching argument here would silently revert to its default in every sub-search.)
        """
        return Budget(
            self.depth_limit - 1,
            self.max_arity,
            self.max_pool,
            self.considered_limit,
            self.considered_limit_mode,
            self.solution_limit,
            self.solution_limit_mode,
        )
