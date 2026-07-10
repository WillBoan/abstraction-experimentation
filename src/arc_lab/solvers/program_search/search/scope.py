"""The scope Γ: the typed De Bruijn binders in force at a point in an (open) term.

Empty at the top level; extended by one binder each time enumeration descends under a ``Lam`` (a
``build_grid`` cell body, a synthesized lambda). De Bruijn indexing: ``Var(0)`` is the *innermost*
binder — the last one pushed — so binder types are stored innermost-**last**, mirroring the runtime
``scope`` stack a ``Lam`` builds (``scope[-1 - index]``). For ``build_grid``'s curried
``Lam(Lam(body))`` (row then col), the scope is therefore ``(row, col)`` — ``Var(0)`` = col,
``Var(1)`` = row (§3 of ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..substrate.types import Type


@dataclass(frozen=True, slots=True)
class Scope:
    """The ordered binder types in scope; ``binders[-1]`` is De Bruijn index 0 (the innermost)."""

    binders: tuple[Type, ...] = ()

    def __len__(self) -> int:
        return len(self.binders)

    def extend(self, binder: Type) -> Scope:
        """A new scope with ``binder`` as the innermost variable (De Bruijn 0)."""
        return Scope((*self.binders, binder))

    def type_of(self, index: int) -> Type:
        """The type of ``Var(index)`` — 0 is the innermost binder, counting outward."""
        return self.binders[-1 - index]
