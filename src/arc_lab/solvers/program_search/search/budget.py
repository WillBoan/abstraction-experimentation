"""The ``Budget``: the resource caps that bound a bottom-up search and guarantee termination.

``max_depth`` is the number of composition rounds and — crucially — **strictly decreases** each time
enumeration recurses into a lambda body (:meth:`Budget.descend`), which alone guarantees lambda
synthesis terminates. ``max_arity`` caps variadic-primitive fan-out; ``max_pool`` caps the per-round
frontier. Neither cap needs to shrink on recursion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Budget:
    """Search resource caps: composition depth, variadic arity, and frontier size."""

    max_depth: int
    max_arity: int
    max_pool: int

    @property
    def exhausted(self) -> bool:
        """True when no further composition rounds remain (``max_depth`` spent)."""
        return self.max_depth <= 0

    def descend(self) -> Budget:
        """The budget for a nested lambda-body search: one less depth (the termination guarantee)."""
        return Budget(self.max_depth - 1, self.max_arity, self.max_pool)
