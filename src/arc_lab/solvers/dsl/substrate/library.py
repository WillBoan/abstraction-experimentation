"""Primitives and libraries — the vocabulary a program-search solver draws on.

A :class:`Primitive` is a *named, typed* operation. Its implementation is still an
ordinary Python function (programs always bottom out in real code), but crucially
programs reference it *by name* rather than embedding an opaque closure — so a
program stays inspectable data.

A :class:`Library` is a first-class, extensible collection of primitives. Keeping
it a value (rather than a module-level dict) is what will let a future learning
loop *grow* the vocabulary: search discovers useful sub-programs, and
:meth:`Library.extended` folds them back in as new named primitives.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.types import ValueType

#: A value flowing through a program: a grid, or a scalar (a color or a small int).
#: Widens further as new value types are introduced.
Value = Grid | int

#: A primitive implementation: takes value arguments, returns a value.
PrimitiveImpl = Callable[..., Value]


@dataclass(frozen=True, slots=True)
class Primitive:
    """A named, typed operation usable as a node in a program.

    A primitive has ``len(param_types)`` fixed leading parameters; if
    ``variadic_param`` is set, it additionally accepts any number of trailing
    arguments of that type (e.g. overlay combines a variable number of grids).
    """

    name: str
    param_types: tuple[ValueType, ...]
    return_type: ValueType
    impl: PrimitiveImpl
    variadic_param: ValueType | None = None

    @property
    def arity(self) -> int:
        return len(self.param_types)

    @property
    def is_variadic(self) -> bool:
        return self.variadic_param is not None


@dataclass(frozen=True, slots=True)
class Library:
    """An ordered, named, extensible collection of primitives."""

    name: str
    primitives: tuple[Primitive, ...]
    version: int = 1

    def __post_init__(self) -> None:
        names = [p.name for p in self.primitives]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate primitive names in library {self.name!r}: {names}")

    def get(self, name: str) -> Primitive:
        for prim in self.primitives:
            if prim.name == name:
                return prim
        raise KeyError(f"primitive {name!r} not in library {self.name!r}")

    def names(self) -> tuple[str, ...]:
        return tuple(prim.name for prim in self.primitives)

    def unary_grid_primitives(self) -> Iterator[Primitive]:
        """Fixed-arity ``(GRID,) -> GRID`` primitives, in library order (no combinators)."""
        for prim in self.primitives:
            if (
                prim.param_types == (ValueType.GRID,)
                and prim.return_type == ValueType.GRID
                and not prim.is_variadic
            ):
                yield prim

    def extended(self, *, name: str, extra: tuple[Primitive, ...]) -> Library:
        """Return a new library with ``extra`` primitives appended (for learning)."""
        return Library(name=name, primitives=self.primitives + extra, version=self.version + 1)
