"""Programs as data: a small typed AST, an interpreter, and (de)serialisation.

This is the hinge of the whole DSL direction. A program is not a Python closure
but an inspectable tree:

* :class:`Input` — the single free variable, the task's input grid;
* :class:`Const` — a literal scalar value (a color, a tiling dimension, …);
* :class:`Apply` — apply a named primitive to sub-programs.

Because a program is data, it can be enumerated, evaluated, compared, hashed,
serialised, and — later — abstracted over (frequently-used sub-trees become new
library primitives). That last property is what makes "learn which compositions
are useful" possible; it is impossible if a program is an opaque lambda.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, assert_never

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.types import ValueType

if TYPE_CHECKING:
    from arc_lab.core.task import Task
    from arc_lab.solvers.dsl.substrate.library import Library, Value


@dataclass(frozen=True, slots=True)
class Input:
    """The program's single free variable: the task input grid."""


@dataclass(frozen=True, slots=True)
class Const:
    """A literal scalar value, tagged with its type (e.g. a COLOR or an INT)."""

    value: int
    value_type: ValueType


@dataclass(frozen=True, slots=True)
class Apply:
    """Apply a library primitive (by name) to argument sub-programs."""

    primitive: str
    args: tuple[Program, ...]


#: A program is one of these node types. (Grows as new node kinds are added.)
Program: TypeAlias = Input | Const | Apply


def evaluate(program: Program, grid: Grid, library: Library) -> Value:
    """Evaluate ``program`` on an input ``grid`` using ``library``'s primitives."""
    match program:
        case Input():
            return grid
        case Const(value, _):
            return value
        case Apply(primitive, args):
            prim = library.get(primitive)
            values = tuple(evaluate(arg, grid, library) for arg in args)
            return prim.impl(*values)
    assert_never(program)  # pragma: no cover - exhaustive match above


def evaluate_grid(program: Program, grid: Grid, library: Library) -> Grid:
    """Evaluate a program that is expected to produce a grid (raise otherwise)."""
    result = evaluate(program, grid, library)
    if not isinstance(result, Grid):
        raise TypeError(f"program evaluated to {type(result).__name__}, expected a grid")
    return result


def is_consistent(program: Program, task: Task, library: Library) -> bool:
    """True if ``program`` reproduces the output of *every* training example."""
    for example in task.train:
        if example.output is None:
            return False
        if evaluate_grid(program, example.input, library) != example.output:
            return False
    return True


def program_to_dict(program: Program) -> dict[str, object]:
    """Serialise a program to a plain JSON-compatible dict."""
    match program:
        case Input():
            return {
                "op": "input",
            }
        case Const(value, value_type):
            return {
                "op": "const",
                "value": value,
                "value_type": value_type.value,
            }
        case Apply(primitive, args):
            return {
                "op": "apply",
                "primitive": primitive,
                "args": [program_to_dict(arg) for arg in args],
            }
    assert_never(program)  # pragma: no cover - exhaustive match above


def program_from_dict(data: Mapping[str, object]) -> Program:
    """Reconstruct a program from :func:`program_to_dict` output."""
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
            args.append(program_from_dict(arg))
        return Apply(primitive=primitive, args=tuple(args))
    raise ValueError(f"unknown program node: {data!r}")
