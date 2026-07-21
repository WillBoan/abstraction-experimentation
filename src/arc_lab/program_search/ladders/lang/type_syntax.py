"""Surface syntax for types and signatures (LADDER-FORMAT.md FLR-8, RNG-2).

One spelling per type, so a signature in a file and the substrate's own signature compare by
equality (spec FLR-7):

- a **constructor** is capitalised -- ``Grid``, ``Color``, ``List[Grid]``, ``Pair[Grid, Grid]``;
- a **type variable** is lowercase -- ``a``;
- an **arrow** is ``(T1, ..., Tn) -> T``;
- a trailing ``...`` marks the variadic parameter of a primitive signature (``overlay`` is
  ``(Color, Grid...) -> Grid``).

Capitalisation is not decoration: it is what distinguishes a nullary constructor from a type
variable without a lookup table that could drift from the substrate's registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.names import check_identifier
from arc_lab.program_search.substrate.types import (
    ArrowType,
    Type,
    TypeVar,
    base_type,
    list_type,
    pair_type,
)

#: Parametric constructors, by substrate name -> arity. Base types are the nullary case and
#: resolve through :func:`base_type`, so they never need listing here.
_CONSTRUCTORS: dict[str, int] = {"list": 1, "pair": 2}

_TOKEN_RE = re.compile(r"->|\.\.\.|[()\[\],:]|[A-Za-z_][A-Za-z_0-9]*|\S")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")


@dataclass(frozen=True, slots=True)
class PrimitiveSignature:
    """A floor primitive's declared signature (spec FLR-1) -- comparable to a ``Primitive``'s."""

    param_types: tuple[Type, ...]
    return_type: Type
    variadic_param: Type | None = None


@dataclass(frozen=True, slots=True)
class DefinitionHeader:
    """A rung definition's left-hand side: ``name(p1: T1, ...) -> T`` (spec RNG-2).

    ``params`` is in declaration order, which *is* param-index order (spec RNG-3).
    """

    name: str
    params: tuple[tuple[str, Type], ...]
    return_type: Type

    @property
    def param_types(self) -> tuple[Type, ...]:
        return tuple(t for _, t in self.params)


def parse_type(text: str) -> Type:
    """Parse a single type; raise :class:`LadderFormatError` on anything else."""
    cursor = _Cursor(text)
    parsed = _type(cursor)
    cursor.expect_end("a type")
    return parsed


def parse_primitive_signature(text: str) -> PrimitiveSignature:
    """Parse a floor ``use`` line's signature -- an arrow, optionally variadic in its last param."""
    cursor = _Cursor(text)
    cursor.expect("(", "a signature starts with `(`")
    params: list[Type] = []
    variadic: Type | None = None
    if cursor.peek() != ")":
        while True:
            parsed = _type(cursor)
            if cursor.peek() == "...":
                cursor.take()
                variadic = parsed
                break  # `...` marks the last parameter
            params.append(parsed)
            if cursor.peek() != ",":
                break
            cursor.take()
    cursor.expect(")", "unclosed parameter list")
    cursor.expect("->", "a signature needs `->` and a return type")
    return_type = _type(cursor)
    cursor.expect_end("a signature")
    return PrimitiveSignature(
        param_types=tuple(params), return_type=return_type, variadic_param=variadic
    )


def parse_definition_header(text: str) -> DefinitionHeader:
    """Parse ``name(p1: T1, ...) -> T`` -- a rung definition's left-hand side (spec RNG-2)."""
    cursor = _Cursor(text)
    name = check_identifier(cursor.take_identifier("an abstraction name"), "abstraction name")
    cursor.expect("(", f"`{name}` needs a parameter list")
    params: list[tuple[str, Type]] = []
    if cursor.peek() != ")":
        while True:
            param_name = check_identifier(
                cursor.take_identifier("a parameter name"), "parameter name"
            )
            cursor.expect(":", f"parameter `{param_name}` needs a `: Type` annotation")
            params.append((param_name, _type(cursor)))
            if cursor.peek() != ",":
                break
            cursor.take()
    cursor.expect(")", "unclosed parameter list")
    cursor.expect("->", f"`{name}` needs `->` and a return type")
    return_type = _type(cursor)
    cursor.expect_end("a definition header")
    seen = [n for n, _ in params]
    duplicates = sorted({n for n in seen if seen.count(n) > 1})
    if duplicates:  # spec RNG-3
        raise LadderFormatError(f"duplicate parameter names in `{name}`: {', '.join(duplicates)}")
    return DefinitionHeader(name=name, params=tuple(params), return_type=return_type)


def render_type(t: Type) -> str:
    """The canonical surface spelling of ``t`` -- inverse of :func:`parse_type`."""
    if isinstance(t, TypeVar):
        return t.name
    if isinstance(t, ArrowType):
        params = ", ".join(render_type(p) for p in t.params)
        return f"({params}) -> {render_type(t.result)}"
    head = t.name.capitalize()
    if not t.args:
        return head
    return f"{head}[{', '.join(render_type(a) for a in t.args)}]"


def render_primitive_signature(signature: PrimitiveSignature) -> str:
    """The canonical surface spelling of a floor signature -- inverse of the parser."""
    parts = [render_type(t) for t in signature.param_types]
    if signature.variadic_param is not None:
        parts.append(f"{render_type(signature.variadic_param)}...")
    return f"({', '.join(parts)}) -> {render_type(signature.return_type)}"


class _Cursor:
    """A token cursor over a type/signature fragment (whitespace is not a token)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = _TOKEN_RE.findall(text)
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            raise LadderFormatError(f"unexpected end of {self.text.strip()!r}")
        self.pos += 1
        return token

    def expect(self, token: str, why: str) -> None:
        if self.peek() != token:
            found = self.peek()
            seen = "end of input" if found is None else repr(found)
            raise LadderFormatError(f"expected `{token}` but found {seen}: {why}")
        self.pos += 1

    def expect_end(self, what: str) -> None:
        if self.peek() is not None:
            raise LadderFormatError(f"trailing {self.peek()!r} after {what}: {self.text.strip()!r}")

    def take_identifier(self, what: str) -> str:
        token = self.take()
        if not _IDENTIFIER_RE.match(token):
            raise LadderFormatError(f"expected {what}, found {token!r}")
        return token


def _type(cursor: _Cursor) -> Type:
    if cursor.peek() == "(":
        cursor.take()
        params: list[Type] = []
        if cursor.peek() != ")":
            params.append(_type(cursor))
            while cursor.peek() == ",":
                cursor.take()
                params.append(_type(cursor))
        cursor.expect(")", "unclosed parameter list in a function type")
        cursor.expect("->", "a function type needs `->` and a result type")
        return ArrowType(tuple(params), _type(cursor))
    return _atom(cursor)


def _atom(cursor: _Cursor) -> Type:
    name = cursor.take_identifier("a type")
    if name[0].islower():
        lowered = name
        if lowered in _CONSTRUCTORS or _is_base_type(lowered):
            raise LadderFormatError(
                f"type names are capitalised: write `{lowered.capitalize()}`, not `{name}` "
                "(a lowercase name is a type variable)"
            )
        return TypeVar(name)
    lowered = name.lower()
    if name != lowered.capitalize():
        raise LadderFormatError(
            f"unknown type {name!r}: a constructor is capitalised (`{lowered.capitalize()}`) "
            "and a type variable is lowercase"
        )
    args: list[Type] = []
    if cursor.peek() == "[":
        cursor.take()
        args.append(_type(cursor))
        while cursor.peek() == ",":
            cursor.take()
            args.append(_type(cursor))
        cursor.expect("]", f"unclosed type arguments for `{name}`")
    arity = _CONSTRUCTORS.get(lowered)
    if arity is None:
        if args:
            raise LadderFormatError(f"`{name}` takes no type arguments")
        try:
            return base_type(lowered)
        except ValueError as exc:
            raise LadderFormatError(f"unknown type `{name}` ({exc})") from None
    if len(args) != arity:
        raise LadderFormatError(f"`{name}` takes {arity} type argument(s), got {len(args)}")
    return list_type(args[0]) if lowered == "list" else pair_type(args[0], args[1])


def _is_base_type(name: str) -> bool:
    try:
        base_type(name)
    except ValueError:
        return False
    return True


def signature_of(
    param_types: tuple[Type, ...], return_type: Type, variadic_param: Type | None
) -> PrimitiveSignature:
    """A :class:`PrimitiveSignature` from a ``Primitive``'s three type fields (spec FLR-7)."""
    return PrimitiveSignature(
        param_types=param_types, return_type=return_type, variadic_param=variadic_param
    )
