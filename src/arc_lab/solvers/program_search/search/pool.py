from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..substrate.program import Program
from ..substrate.types import Type
from .signature import Signature


@dataclass(slots=True)
class Pool:
    _by_type_sig: dict[Type, dict[Signature, tuple[Program, float]]] = field(default_factory=dict)

    def add_dedup(
        self,
        vtype: Type,
        signature: Signature,
        program: Program,
        cost_value: float,
    ) -> bool:
        """
        Add a program to the pool if it is cheaper than any existing one for that type/signature.

        Returns
        -------
        bool
            True if the program was added to the pool, False if it was deduplicated.
        """
        sig_map = self._by_type_sig.setdefault(vtype, {})
        if signature not in sig_map or cost_value < sig_map[signature][1]:
            sig_map[signature] = (program, cost_value)
            return True
        return False

    def of_type(self, vtype: Type) -> Iterable[Program]:
        """
        Get all programs of a given type in the pool.

        Feeds `SearchEngine._compose_candidate_programs`.

        Returns
        -------
        Iterable[Program]
            An iterable of programs of the specified type.
        """
        return (prog for prog, _ in self._by_type_sig.get(vtype, {}).values())

    def items_of_type(self, vtype: Type) -> Iterable[tuple[Signature, Program, float]]:
        """Get the (signature, program, cost) entries of a given type in the pool.

        Exposes the cached signature and cost so the engine can run the goal test
        (does a signature equal the target?) and rank without re-evaluating.

        Returns
        -------
        Iterable[tuple[Signature, Program, float]]
            The stored entries for the given type.
        """
        return (
            (signature, program, cost_value)
            for signature, (program, cost_value) in self._by_type_sig.get(vtype, {}).items()
        )

    def _entries(self) -> Iterable[tuple[Type, Signature, Program, float]]:
        """Get all entries in the pool, with type, signature, program, and cost."""
        return (
            (vtype, signature, program, cost_value)
            for vtype, sig_map in self._by_type_sig.items()
            for signature, (program, cost_value) in sig_map.items()
        )

    def cheapest(self, n: int) -> Pool:
        """Return a new pool holding the globally-cheapest ``n`` entries, re-bucketed by type.

        Ties break by insertion order, keeping the cut deterministic.

        Returns
        -------
        Pool
            A new pool with at most ``n`` entries.
        """
        entries = sorted(
            self._entries(),
            key=lambda entry: entry[3],
        )
        kept: dict[Type, dict[Signature, tuple[Program, float]]] = {}
        for vtype, signature, program, cost_value in entries[:n]:
            kept.setdefault(vtype, {})[signature] = (program, cost_value)
        return Pool(_by_type_sig=kept)

    def ranked(self) -> tuple[Program, ...]:
        """Every program in the pool, cheapest first (by cached cost).

        This ranks the *whole pool* across all types.

        Returns
        -------
        tuple[Program, ...]
            All pooled programs, ordered by ascending cost.
        """
        entries = sorted(
            self._entries(),
            key=lambda entry: entry[3],
        )
        return tuple(program for _, _, program, _ in entries)

    def size(self) -> int:
        """The total number of programs held across all types."""
        return sum(len(sig_map) for sig_map in self._by_type_sig.values())
