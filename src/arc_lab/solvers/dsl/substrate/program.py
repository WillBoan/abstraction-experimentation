"""Programs as data: a typed AST with virtual-dispatch operations.

A program is not a Python closure but an inspectable tree:

* :class:`Input` — the single free variable, the task's input grid;
* :class:`Const` — a literal scalar value (a color, a tiling dimension, …);
* :class:`Apply` — apply a named primitive to sub-programs.

Operations are provided by **virtual dispatch**: each node kind implements
:meth:`~Program.evaluate`, :meth:`~Program.result_type`, :meth:`~Program.to_dict`,
:meth:`~Program.children`, and ``__str__``. Structural helpers (:meth:`~Program.size`,
:meth:`~Program.depth`, :meth:`~Program.walk`, :meth:`~Program.evaluate_grid`) are
derived once on the base from those. Adding a node kind therefore *must* implement
the operations (the abstract methods enforce it), which is the exhaustiveness the
old union alias gave us — kept, now with method ergonomics.

Because a program is data, it can be enumerated, evaluated, compared, hashed,
serialised, and — later — abstracted over (frequently-used sub-trees become new
library primitives, the signal :meth:`~Program.walk` will surface).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.types import ValueType

if TYPE_CHECKING:
    from arc_lab.solvers.dsl.substrate.library import Library, Value


class Program(ABC):
    """A node in a DSL program tree."""

    __slots__ = ()

    # -- node-specific operations (each subclass implements) ------------

    @abstractmethod
    def evaluate(self, grid: Grid, library: Library) -> Value:
        """Compute this program's value on an input ``grid``."""

    @abstractmethod
    def result_type(self, library: Library) -> ValueType:
        """The type of value this program produces."""

    @abstractmethod
    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict (round-trips via :meth:`from_dict`)."""

    @abstractmethod
    def children(self) -> tuple[Program, ...]:
        """The immediate sub-programs (empty for leaves)."""

    # -- derived helpers, shared across node kinds ----------------------

    def evaluate_grid(self, grid: Grid, library: Library) -> Grid:
        """Evaluate a program expected to produce a grid (raise otherwise)."""
        result = self.evaluate(grid, library)
        if not isinstance(result, Grid):
            raise TypeError(f"program evaluated to {type(result).__name__}, expected a grid")
        return result

    def size(self) -> int:
        """Total number of nodes in the tree."""
        return 1 + sum(child.size() for child in self.children())

    def depth(self) -> int:
        """Length of the longest root-to-leaf path (a leaf has depth 1)."""
        return 1 + max((child.depth() for child in self.children()), default=0)

    def walk(self) -> Iterator[Program]:
        """Yield every node in the tree, this node first, then its descendants."""
        yield self
        for child in self.children():
            yield from child.walk()

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> Program:
        """Reconstruct a program from :meth:`to_dict` output."""
        op = data.get("op")
        if op == "input":
            return Input()
        if op == "const":
            value, value_type = data["value"], data["value_type"]
            if not isinstance(value, int) or not isinstance(value_type, str):
                raise ValueError(f"malformed const node: {data!r}")
            return Const(value=value, value_type=ValueType(value_type))
        if op == "apply":
            primitive, raw_args = data["primitive"], data["args"]
            if not isinstance(primitive, str) or not isinstance(raw_args, list):
                raise ValueError(f"malformed apply node: {data!r}")
            args: list[Program] = []
            for arg in raw_args:
                if not isinstance(arg, Mapping):
                    raise ValueError(f"malformed program argument: {arg!r}")
                args.append(Program.from_dict(arg))
            return Apply(primitive=primitive, args=tuple(args))
        raise ValueError(f"unknown program node: {data!r}")


@dataclass(frozen=True, slots=True)
class Input(Program):
    """The program's single free variable: the task input grid."""

    def evaluate(self, grid: Grid, library: Library) -> Value:
        return grid

    def result_type(self, library: Library) -> ValueType:
        return ValueType.GRID

    def to_dict(self) -> dict[str, object]:
        return {"op": "input"}

    def children(self) -> tuple[Program, ...]:
        return ()

    def __str__(self) -> str:
        return "input"


@dataclass(frozen=True, slots=True)
class Const(Program):
    """A literal scalar value, tagged with its type (e.g. a COLOR or an INT)."""

    value: int
    value_type: ValueType

    def evaluate(self, grid: Grid, library: Library) -> Value:
        return self.value

    def result_type(self, library: Library) -> ValueType:
        return self.value_type

    def to_dict(self) -> dict[str, object]:
        return {"op": "const", "value": self.value, "value_type": self.value_type.value}

    def children(self) -> tuple[Program, ...]:
        return ()

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Apply(Program):
    """Apply a named library primitive to argument sub-programs."""

    primitive: str
    args: tuple[Program, ...]

    def evaluate(self, grid: Grid, library: Library) -> Value:
        prim = library.get(self.primitive)
        return prim.impl(*(arg.evaluate(grid, library) for arg in self.args))

    def result_type(self, library: Library) -> ValueType:
        return library.get(self.primitive).return_type

    def to_dict(self) -> dict[str, object]:
        return {
            "op": "apply",
            "primitive": self.primitive,
            "args": [arg.to_dict() for arg in self.args],
        }

    def children(self) -> tuple[Program, ...]:
        return self.args

    def __str__(self) -> str:
        return f"{self.primitive}({', '.join(str(arg) for arg in self.args)})"
