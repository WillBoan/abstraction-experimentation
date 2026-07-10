"""Primitives and libraries — the vocabulary a program-search solver draws on.

:class:`Primitive`:

- A *named, typed* operation.
- Its implementation is still an ordinary Python function (programs always bottom
  out in real code).
- But crucially, programs reference it *by name* rather than embedding an opaque
  closure — so a program stays inspectable data.

:class:`Library`:

- A first-class, extensible collection of primitives.
- Keeping it a value (rather than a module-level dict) is what will let a future
  learning loop *grow* the vocabulary:
  - search discovers useful sub-programs
  - :meth:`Library.extended` folds them back in as new named primitives
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from arc_lab.core.grid import Grid
from arc_lab.solvers.program_search.substrate.types import GRID, Type, type_to_serializable

if TYPE_CHECKING:
    from arc_lab.solvers.program_search.substrate.program import Program


@dataclass(frozen=True, slots=True)
class Closure:
    """A function value: a :class:`~...program.Lam`'s body captured with its environment.

    Produced when a ``Lam`` node is evaluated; consumed by higher-order primitives
    (``build_grid`` today; ``map``/``fold`` later) that apply it. This is a *runtime*
    value only — never part of a program AST and never serialised (unlike the ``Lam``
    node, which is frozen, inspectable data) — so programs stay frozen, hashable, and
    deterministic, and closures never enter the observational-equivalence pools.

    Applying it pushes ``arg`` onto the De Bruijn ``scope`` (so the body's ``$0`` sees the
    most-recently-bound variable) and evaluates the body. ``env`` (the abstraction-argument
    channel, read by ``Param``) is carried through unchanged — the two binder namespaces
    (``$i`` bound vars vs. ``#j`` abstraction vars) stay separate.
    """

    body: Program
    grid: Grid
    library: Library
    env: tuple[Value, ...]
    scope: tuple[Value, ...]

    def __call__(self, arg: Value) -> Value:
        return self.body.evaluate(self.grid, self.library, self.env, (*self.scope, arg))


#: A value flowing through a program: a grid, a scalar (color / small int / bool), a *function value*
#: (a lambda's :class:`Closure` or a :class:`Primitive` referenced first-class via a ``PrimRef``,
#: applied by ``AppFn``), or a *container* — a ``tuple`` of values, the runtime form of a ``list[a]``
#: (homogeneous sequence) or a ``pair[a, b]`` (2-tuple). The type is carried by the program, not the
#: value, so ``list`` and ``pair`` share the native ``tuple`` representation.
Value: TypeAlias = "Grid | int | bool | Closure | Primitive | tuple[Value, ...]"

#: A primitive implementation: takes value arguments, returns a value.
PrimitiveImpl: TypeAlias = Callable[..., Value]


@dataclass(frozen=True, slots=True)
class Primitive:
    """A named, typed operation usable as a node in a program.

    - A primitive has ``len(param_types)`` fixed leading parameters.
    - If ``variadic_param`` is set, it additionally accepts any number of trailing
      arguments of that type (e.g. overlay combines a variable number of grids).

    Args:
        name: The name of the primitive.
        param_types: A tuple of value types for the fixed leading parameters.
        return_type: The value type of the result.
        impl: The implementation of the primitive.
        variadic_param: The value type of any additional trailing parameters, if variadic.
    """

    name: str
    param_types: tuple[Type, ...]  # a base type, or an arrow (a function-typed parameter)
    return_type: Type
    impl: PrimitiveImpl
    variadic_param: Type | None = None
    #: For a *learned* abstraction: its defining template (a closed :class:`Program`
    #: with :class:`~arc_lab.solvers.program_search.substrate.program.Param` holes). ``None`` for a
    #: hand-coded primitive. ``impl`` evaluates this template; carrying it here keeps a
    #: learned entry inspectable data, not an opaque closure.
    template: Program | None = None

    @property
    def arity(self) -> int:
        return len(self.param_types)

    @property
    def is_variadic(self) -> bool:
        return self.variadic_param is not None

    @property
    def is_unary(self) -> bool:
        """True if this is a fixed-arity unary primitive (one argument)."""
        return self.arity == 1 and not self.is_variadic

    @property
    def is_unary_grid_primitive(self) -> bool:
        """True if this is a fixed-arity ``(GRID,) -> GRID`` primitive."""
        return self.param_types == (GRID,) and self.return_type == GRID and not self.is_variadic

    def to_dict(self) -> dict[str, object]:
        """Serialise the primitive's *signature* (name + types), not its Python impl.

        The impl is code, looked up by name from the substrate; what identifies a
        primitive for an artifact is its typed interface. A future *learned* primitive
        would additionally carry its defining sub-program here.
        """
        data: dict[str, object] = {
            "name": self.name,
            "param_types": [type_to_serializable(t) for t in self.param_types],
            "return_type": type_to_serializable(self.return_type),
            "variadic_param": (
                None if self.variadic_param is None else type_to_serializable(self.variadic_param)
            ),
        }
        if self.template is not None:
            data["template"] = self.template.to_dict()
        return data


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

    def __getitem__(self, name: str) -> Primitive:
        return self.get(name)

    def __contains__(self, name: str) -> bool:
        return any(prim.name == name for prim in self.primitives)

    def names(self) -> tuple[str, ...]:
        return tuple(prim.name for prim in self.primitives)

    def to_dict(self) -> dict[str, object]:
        """Serialise the library's identity: name, version, and primitive signatures.

        This is the ``floor`` coordinate recorded in a run artifact — enough to say
        *which vocabulary* a run used (and to detect when it changes), without the
        (unserialisable) primitive implementations.
        """
        return {
            "name": self.name,
            "version": self.version,
            "primitives": [prim.to_dict() for prim in self.primitives],
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> Library:
        """Reconstruct a live library from its serialised form.

        Base primitives are resolved *by name* against the substrate registry (their ``impl`` is
        code, dropped by :meth:`Primitive.to_dict`); learned abstractions are rebuilt from their
        ``template`` via :func:`~arc_lab.solvers.program_search.substrate.abstraction.make_abstraction`,
        replayed in serialised order — which is dependency order, since abstractions are appended
        and reference only earlier primitives.
        """
        from arc_lab.solvers.program_search.substrate.abstraction import make_abstraction
        from arc_lab.solvers.program_search.substrate.program import Program
        from arc_lab.solvers.program_search.substrate.registry import resolve_primitive

        name = str(data["name"])
        version_raw = data.get("version")
        version = version_raw if isinstance(version_raw, int) else 1
        prim_dicts = data["primitives"]
        if not isinstance(prim_dicts, list):
            raise ValueError("malformed library: 'primitives' must be a list")

        built: list[Primitive] = []
        for entry in prim_dicts:
            if not isinstance(entry, Mapping):
                raise ValueError(f"malformed primitive entry: {entry!r}")
            prim_name = str(entry["name"])
            template_raw = entry.get("template")
            if template_raw is None:
                built.append(resolve_primitive(prim_name))
            elif isinstance(template_raw, Mapping):
                lower = Library(name=name, primitives=tuple(built), version=version)
                built.append(make_abstraction(prim_name, Program.from_dict(template_raw), lower))
            else:
                raise ValueError(f"malformed template for primitive {prim_name!r}")
        return Library(name=name, primitives=tuple(built), version=version)

    def unary_grid_primitives(self) -> Iterator[Primitive]:
        """Fixed-arity ``(GRID,) -> GRID`` primitives, in library order (no combinators)."""
        for prim in self.primitives:
            if prim.is_unary_grid_primitive:
                yield prim

    def extended(
        self,
        *,
        name: str,
        extra: tuple[Primitive, ...],
    ) -> Library:
        """Return a new library with ``extra`` primitives appended (for learning)."""
        return Library(
            name=name,
            primitives=self.primitives + extra,
            version=self.version + 1,
        )
