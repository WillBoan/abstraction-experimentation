"""The `Budget`: the resource caps that bound a bottom-up search and guarantee termination.

`depth_limit` is the **inclusive cap on compositional depth** (leaf = 0): a program of depth
`d` is reachable iff `d <= depth_limit` — equivalently, the engine runs generations
`0..depth_limit`, generation 0 being the leaf seeding. It **strictly decreases** each time
enumeration recurses into a lambda body (:meth:`Budget.descend`), which alone guarantees lambda
synthesis terminates. `max_arity` caps variadic-primitive fan-out; `max_pool` caps the
per-round frontier. Neither cap needs to shrink on recursion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Budget:
    """The `Budget`: the resource caps that bound a bottom-up search and guarantee termination."""

    depth_limit: int
    max_arity: int
    max_pool: int

    # TODO: Add a `stop_after_solutions: int | None = None` field

    @property
    def exhausted(self) -> bool:
        """True when not even the leaf generation may run (`depth_limit` spent below zero)."""
        return self.depth_limit < 0

    def descend(self) -> Budget:
        """The budget for a nested lambda-body search: one less depth (the termination guarantee)."""
        return Budget(self.depth_limit - 1, self.max_arity, self.max_pool)
