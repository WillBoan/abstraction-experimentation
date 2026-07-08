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
from arc_lab.solvers.dsl.substrate.library import Closure, Primitive
from arc_lab.solvers.dsl.substrate.types import (
    ArrowType,
    Type,
    ValueType,
    type_from_serializable,
    type_to_serializable,
)

if TYPE_CHECKING:
    from arc_lab.solvers.dsl.substrate.library import Library, Value


class Program(ABC):
    """A node in a DSL program tree."""

    __slots__ = ()

    # -- node-specific operations (each subclass implements) ------------

    @abstractmethod
    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        """Compute this program's value on an input ``grid``.

        Two separate binding channels (kept distinct on purpose — this is what lets a
        ``build_grid`` program become a learned abstraction cleanly):

        * ``env`` binds *abstraction arguments*: a :class:`Param` (``#j``) reads ``env[index]``,
          fixed once per evaluation at an abstraction call.
        * ``scope`` binds *lambda-bound variables*: a :class:`Var` (De Bruijn ``$i``) reads
          ``scope[-1 - index]`` — a stack a :class:`Lam` extends once per application (per cell,
          for ``build_grid``).

        Both default to empty, so every existing call site is unaffected."""

    @abstractmethod
    def result_type(self, library: Library) -> Type:
        """The type of value this program produces (a base type, arrow, or type variable)."""

    @abstractmethod
    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict (round-trips via :meth:`from_dict`)."""

    @abstractmethod
    def children(self) -> tuple[Program, ...]:
        """The immediate sub-programs (empty for leaves)."""

    # -- derived helpers, shared across node kinds ----------------------

    def evaluate_grid(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Grid:
        """Evaluate a program expected to produce a grid (raise otherwise)."""
        result = self.evaluate(grid, library, env, scope)
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
        if op == "param":
            index, param_type = data["index"], data["value_type"]
            if not isinstance(index, int) or not isinstance(param_type, (str, dict)):
                raise ValueError(f"malformed param node: {data!r}")
            return Param(index=index, value_type=type_from_serializable(param_type))
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
        if op == "var":
            index, var_type = data["index"], data["value_type"]
            if not isinstance(index, int) or not isinstance(var_type, (str, dict)):
                raise ValueError(f"malformed var node: {data!r}")
            return Var(index=index, value_type=type_from_serializable(var_type))
        if op == "lam":
            body = data["body"]
            if not isinstance(body, Mapping):
                raise ValueError(f"malformed lam node: {data!r}")
            return Lam(body=Program.from_dict(body))
        if op == "appfn":
            fn, raw_fn_args = data["fn"], data["args"]
            if not isinstance(fn, Mapping) or not isinstance(raw_fn_args, list):
                raise ValueError(f"malformed appfn node: {data!r}")
            fn_args: list[Program] = []
            for arg in raw_fn_args:
                if not isinstance(arg, Mapping):
                    raise ValueError(f"malformed appfn argument: {arg!r}")
                fn_args.append(Program.from_dict(arg))
            return AppFn(fn=Program.from_dict(fn), args=tuple(fn_args))
        if op == "primref":
            name = data["name"]
            if not isinstance(name, str):
                raise ValueError(f"malformed primref node: {data!r}")
            return PrimRef(name=name)
        raise ValueError(f"unknown program node: {data!r}")


@dataclass(frozen=True, slots=True)
class Input(Program):
    """The program's single free variable: the task input grid."""

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
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
class Param(Program):
    """A positional hole in an abstraction template: the value of argument ``index``.

    A learned abstraction's definition is a *closed* template (no :class:`Input`) whose
    holes are ``Param`` nodes; evaluating it binds ``env[index]`` here. Carries its own
    ``value_type`` (like :class:`Const`) because :meth:`result_type` gets no type environment.
    """

    index: int
    value_type: Type  # a base type, or an arrow (a function-typed hole — the higher-order case)

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        return env[self.index]

    def result_type(self, library: Library) -> Type:
        return self.value_type

    def to_dict(self) -> dict[str, object]:
        return {
            "op": "param",
            "index": self.index,
            "value_type": type_to_serializable(self.value_type),
        }

    def children(self) -> tuple[Program, ...]:
        return ()

    def __str__(self) -> str:
        return f"#{self.index}"  # Stitch's abstraction-var notation (`#j`); cf. Var's `$i`


@dataclass(frozen=True, slots=True)
class Const(Program):
    """A literal scalar value, tagged with its type (e.g. a COLOR or an INT)."""

    value: int
    value_type: ValueType

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
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

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        prim = library.get(self.primitive)
        return prim.impl(*(arg.evaluate(grid, library, env, scope) for arg in self.args))

    def result_type(self, library: Library) -> Type:
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


@dataclass(frozen=True, slots=True)
class Var(Program):
    """A lambda-bound variable: the De Bruijn index ``$i`` into the current ``scope``.

    ``$0`` is the innermost (most-recently-bound) variable, ``$1`` the next one out, and so on —
    read from the ``scope`` stack that a :class:`Lam` extends on each application. Deliberately
    distinct from :class:`Param` (``#j``, the abstraction-argument channel): the two binder
    namespaces never collide, which is what lets a ``build_grid`` program be minted as an
    abstraction with the loop variables staying internal. This is Stitch's ``$i``.

    Carries its own ``value_type`` (like :class:`Param`/:class:`Const`) because
    :meth:`result_type` gets no type environment; on the cell floor a bound coordinate is ``INT``.
    """

    index: int
    value_type: Type

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        return scope[-1 - self.index]

    def result_type(self, library: Library) -> Type:
        return self.value_type

    def to_dict(self) -> dict[str, object]:
        return {"op": "var", "index": self.index, "value_type": type_to_serializable(self.value_type)}

    def children(self) -> tuple[Program, ...]:
        return ()

    def __str__(self) -> str:
        return f"${self.index}"  # Stitch's De Bruijn bound-var notation (`$i`); cf. Param's `#j`


@dataclass(frozen=True, slots=True)
class Lam(Program):
    """A unary lambda binder — Stitch's ``(lam …)``.

    Evaluates to a :class:`~...library.Closure` capturing the current environment; applying it
    (e.g. by ``build_grid``, per cell) pushes the argument onto ``scope`` and evaluates ``body``.
    Multi-argument binding is nested ``Lam(Lam(body))`` (Stitch is unary), so for a coordinate
    lambda the outer ``Lam`` binds the row and the inner binds the column, seen from ``body`` as
    ``$1`` and ``$0`` respectively.

    Using an *environment* (closure) semantics — rather than substitution — means De Bruijn
    indices are just looked up in ``scope`` at evaluation time: no index shifting, no capture.
    """

    body: Program

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        return Closure(body=self.body, grid=grid, library=library, env=env, scope=scope)

    def result_type(self, library: Library) -> ValueType:
        return ValueType.FN

    def to_dict(self) -> dict[str, object]:
        return {"op": "lam", "body": self.body.to_dict()}

    def children(self) -> tuple[Program, ...]:
        return (self.body,)

    def __str__(self) -> str:
        return f"lam({self.body})"


@dataclass(frozen=True, slots=True)
class AppFn(Program):
    """Apply a *computed* function value to arguments — the higher-order application node.

    Unlike :class:`Apply` (whose head is a fixed primitive *name*), ``fn`` is a sub-program that
    evaluates to a function value: a :class:`~...library.Closure` (from a :class:`Lam`) or a
    :class:`~...library.Primitive` (from a :class:`PrimRef`). Evaluation reuses exactly the machinery
    ``build_grid`` uses per cell — ``Closure.__call__`` for a lambda (curried), ``impl(*args)`` for a
    primitive — so applying a function value needs no new runtime. Its :meth:`result_type` is the head
    arrow's codomain, which is why :class:`Type`'s arrow types (Phase C) are the prerequisite.
    """

    fn: Program
    args: tuple[Program, ...]

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        fn_value = self.fn.evaluate(grid, library, env, scope)
        arg_values = [arg.evaluate(grid, library, env, scope) for arg in self.args]
        if isinstance(fn_value, Primitive):
            return fn_value.impl(*arg_values)  # a primitive applies all args at once
        result: Value = fn_value
        for arg_value in arg_values:  # a closure is curried: apply one argument at a time
            if not isinstance(result, Closure):
                raise TypeError(f"AppFn applied a non-function value: {type(result).__name__}")
            result = result(arg_value)
        return result

    def result_type(self, library: Library) -> Type:
        fn_type = self.fn.result_type(library)
        if not isinstance(fn_type, ArrowType):
            raise TypeError(f"AppFn head does not have a function type: {fn_type}")
        return fn_type.result

    def to_dict(self) -> dict[str, object]:
        return {"op": "appfn", "fn": self.fn.to_dict(), "args": [arg.to_dict() for arg in self.args]}

    def children(self) -> tuple[Program, ...]:
        return (self.fn, *self.args)

    def __str__(self) -> str:
        return f"{self.fn}({', '.join(str(arg) for arg in self.args)})"


@dataclass(frozen=True, slots=True)
class PrimRef(Program):
    """A primitive as a first-class *function value* — e.g. ``width`` passed to a function-typed hole.

    Evaluates to the named :class:`~...library.Primitive` itself (a callable value that :class:`AppFn`
    applies), and its type is that primitive's arrow ``(param_types) -> return_type``. This is what lets
    a ``GRID -> INT`` perceiver fill a function-typed hole — cleaner than eta-expanding into a ``Lam``
    (no size inflation, variadic-safe, uniform).
    """

    name: str

    def evaluate(
        self,
        grid: Grid,
        library: Library,
        env: tuple[Value, ...] = (),
        scope: tuple[Value, ...] = (),
    ) -> Value:
        return library.get(self.name)

    def result_type(self, library: Library) -> Type:
        prim = library.get(self.name)
        return ArrowType(tuple(prim.param_types), prim.return_type)

    def to_dict(self) -> dict[str, object]:
        return {"op": "primref", "name": self.name}

    def children(self) -> tuple[Program, ...]:
        return ()

    def __str__(self) -> str:
        return f"&{self.name}"  # `&` = a reference to the primitive as a value
