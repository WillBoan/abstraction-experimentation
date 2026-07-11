"""A ``Context``: one point at which a program is evaluated to read one entry of its signature.

It bundles the two evaluation inputs — the task input grid and the runtime ``scope`` stack (the
values bound to the enclosing De Bruijn variables). At the top level the scope binding is empty
(``Context(input)``); inside a ``build_grid`` cell body it is ``(row, col)`` (§3 scope ordering).
The same type is used *everywhere* a program is evaluated — including function-value sampling — so a
lambda body that reads ``Input()`` always has its grid.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.grid import Grid

from ..substrate.library import Value


@dataclass(frozen=True, slots=True)
class Context:
    """An evaluation point: an input grid and the scope-variable bindings in force there."""

    input_grid: Grid
    scope_binding: tuple[Value, ...] = ()
