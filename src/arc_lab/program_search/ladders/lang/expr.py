"""Expression elaboration: surface text <-> :class:`Program` (LADDER-FORMAT.md EXP-1..7).

An expression is positional application of named functions over identifiers and int literals --
``map_color(rot180(g), 1, 2)`` -- and elaborates to the ``Apply | Param | Const | Input`` fragment.
Parsing rides on :mod:`ast` (the surface *is* a Python expression subset), but every construct
:mod:`ast` accepts beyond the fragment is rejected here.

Elaboration is also where an expression is **type-checked**. The substrate types programs but does
not verify them (``Apply.result_type`` reports its primitive's return type without inspecting the
arguments), and an int literal has no intrinsic type -- ``Const`` carries one. Both are settled by
the same top-down walk: each argument is elaborated against the (substituted) type of the parameter
position it fills, unifying as it goes, so arity errors, type errors, and literal typing all fall
out of one pass.
"""

from __future__ import annotations

import ast
import itertools
from collections.abc import Sequence

from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.type_syntax import render_type
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.program_search.substrate.types import (
    COLOR,
    GRID,
    INT,
    ArrowType,
    Substitution,
    Type,
    TypeCon,
    TypeVar,
    apply_subst,
    instantiate,
    unify,
)

#: The task input grid, the format's one free variable (spec EXP-3).
INPUT_KEYWORD = "input"

#: The types an int literal may inhabit -- the substrate's int-valued scalars. ``BOOL`` is
#: bool-valued (no surface literal); ``GRID``/``MASK``/``FN`` hold no literal at all. Deliberately
#: stricter than ``Const``, which the substrate lets carry any nullary type.
_LITERAL_TYPES: frozenset[TypeCon] = frozenset({COLOR, INT})


def elaborate_expression(
    text: str,
    *,
    library: Library,
    params: Sequence[tuple[str, Type]] = (),
    allow_input: bool,
) -> Program:
    """Elaborate ``text`` into a typed :class:`Program`.

    ``params`` are the enclosing definition's parameters in index order (spec RNG-3); a name in it
    elaborates to a :class:`Param`. ``allow_input`` gates :data:`INPUT_KEYWORD`: false inside a rung
    template, which must be closed (spec NAM-4), true in a task solution (spec NAM-5).
    """
    stripped = text.strip()
    if not stripped:
        raise LadderFormatError("empty expression")
    try:
        tree = ast.parse(stripped, mode="eval")
    except SyntaxError as exc:
        raise LadderFormatError(f"could not parse expression {stripped!r}: {exc.msg}") from None
    return _Elaborator(library=library, params=params, allow_input=allow_input).run(tree.body)


def render_expression(program: Program, param_names: Sequence[str] = ()) -> str:
    """The canonical surface spelling of ``program`` -- inverse of :func:`elaborate_expression`.

    ``param_names`` supplies the names for :class:`Param` holes, in index order.
    """
    if isinstance(program, Input):
        return INPUT_KEYWORD
    if isinstance(program, Param):
        if program.index >= len(param_names):
            raise LadderFormatError(
                f"no name for parameter #{program.index} (given: {list(param_names)})"
            )
        return param_names[program.index]
    if isinstance(program, Const):
        if isinstance(program.value, bool):
            raise LadderFormatError("boolean constants have no surface syntax")
        return str(program.value)
    if isinstance(program, Apply):
        args = ", ".join(render_expression(arg, param_names) for arg in program.args)
        return f"{program.primitive}({args})"
    raise LadderFormatError(
        f"{type(program).__name__} has no surface syntax (the format covers "
        "Apply | Param | Const | Input)"
    )


class _Elaborator:
    """One expression's elaboration: scope, fresh-type-variable counter, and substitution."""

    def __init__(
        self, *, library: Library, params: Sequence[tuple[str, Type]], allow_input: bool
    ) -> None:
        self.library = library
        self.params = {name: (index, t) for index, (name, t) in enumerate(params)}
        self.allow_input = allow_input
        self.counter: itertools.count[int] = itertools.count()
        self.subst: Substitution = {}

    def run(self, node: ast.expr) -> Program:
        program, _ = self.elaborate(node, None)
        return program

    def elaborate(self, node: ast.expr, expected: Type | None) -> tuple[Program, Type]:
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.Name):
            return self._name(node)
        if isinstance(node, ast.Constant):
            return self._constant(node, expected)
        raise LadderFormatError(
            f"{_describe(node)} is not part of the format (an expression is positional "
            "application of named functions over identifiers and int literals)"
        )

    # -- node kinds -----------------------------------------------------------------

    def _call(self, node: ast.Call) -> tuple[Program, Type]:
        if not isinstance(node.func, ast.Name):
            raise LadderFormatError("only a named primitive or abstraction can be applied")
        name = node.func.id
        if node.keywords:
            raise LadderFormatError(f"`{name}` must be called with positional arguments only")
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise LadderFormatError(f"`{name}` cannot be called with `*` arguments")
        if name in self.params:
            raise LadderFormatError(f"`{name}` is a parameter, not a function")
        if name == INPUT_KEYWORD:
            raise LadderFormatError(f"`{INPUT_KEYWORD}` is the task input grid, not a function")
        if name not in self.library:
            raise LadderFormatError(f"unknown function `{name}`; {self._scope_hint()}")
        prim = self.library.get(name)
        fixed, variadic, return_type = self._instantiate(prim)
        self._check_arity(name, len(node.args), len(fixed), variadic is not None)

        args: list[Program] = []
        for index, arg_node in enumerate(node.args):
            slot = fixed[index] if index < len(fixed) else variadic
            assert slot is not None  # arity check above guarantees a variadic slot exists
            expected = apply_subst(self.subst, slot)
            program, actual = self.elaborate(arg_node, expected)
            unified = unify(actual, expected, self.subst)
            if unified is None:
                raise LadderFormatError(
                    f"argument {index + 1} of `{name}` is {render_type(actual)}, "
                    f"expected {render_type(expected)}"
                )
            self.subst = unified
            args.append(program)
        return Apply(name, tuple(args)), apply_subst(self.subst, return_type)

    def _name(self, node: ast.Name) -> tuple[Program, Type]:
        if node.id == INPUT_KEYWORD:
            if not self.allow_input:
                raise LadderFormatError(
                    f"`{INPUT_KEYWORD}` is not in scope: a rung template is closed over its "
                    "parameters (spec NAM-4)"
                )
            return Input(), GRID
        entry = self.params.get(node.id)
        if entry is not None:
            index, value_type = entry
            return Param(index, value_type), value_type
        if node.id in self.library:
            raise LadderFormatError(
                f"`{node.id}` is a function; write `{node.id}(...)` to apply it"
            )
        raise LadderFormatError(f"unknown name `{node.id}`; {self._scope_hint()}")

    def _constant(self, node: ast.Constant, expected: Type | None) -> tuple[Program, Type]:
        value = node.value
        if isinstance(value, bool) or not isinstance(value, int):
            raise LadderFormatError(f"unsupported literal {value!r}: the format has int literals")
        if expected is None:
            raise LadderFormatError(
                f"cannot type the literal {value}: an int literal only appears in a typed "
                "argument position (spec EXP-5)"
            )
        resolved = apply_subst(self.subst, expected)
        if isinstance(resolved, TypeVar):
            raise LadderFormatError(
                f"cannot type the literal {value}: the argument position is polymorphic "
                f"({render_type(resolved)}) (spec EXP-5)"
            )
        if not isinstance(resolved, TypeCon) or resolved not in _LITERAL_TYPES:
            allowed = ", ".join(sorted(render_type(t) for t in _LITERAL_TYPES))
            raise LadderFormatError(
                f"the literal {value} cannot fill a `{render_type(resolved)}` position "
                f"(an int literal is {allowed})"
            )
        return Const(value, resolved), resolved

    # -- helpers --------------------------------------------------------------------

    def _instantiate(self, prim: Primitive) -> tuple[tuple[Type, ...], Type | None, Type]:
        """``prim``'s signature with fresh type variables: (fixed params, variadic param, result).

        Instantiated as ONE arrow so a polymorphic primitive's variables stay linked across its
        parameters, its variadic tail, and its result.
        """
        tail = () if prim.variadic_param is None else (prim.variadic_param,)
        fresh = instantiate(ArrowType((*prim.param_types, *tail), prim.return_type), self.counter)
        assert isinstance(fresh, ArrowType)
        if prim.variadic_param is None:
            return fresh.params, None, fresh.result
        return fresh.params[:-1], fresh.params[-1], fresh.result

    def _check_arity(self, name: str, given: int, fixed: int, variadic: bool) -> None:
        if variadic:
            if given < fixed:
                raise LadderFormatError(f"`{name}` takes at least {fixed} argument(s), got {given}")
            return
        if given != fixed:
            raise LadderFormatError(f"`{name}` takes {fixed} argument(s), got {given}")

    def _scope_hint(self) -> str:
        names = sorted(self.params) + sorted(self.library.names())
        if self.allow_input:
            names.append(INPUT_KEYWORD)
        return "in scope: " + ", ".join(names)


def _describe(node: ast.expr) -> str:
    """A human name for an out-of-fragment construct (spec EXP-1)."""
    descriptions: dict[type[ast.expr], str] = {
        ast.Attribute: "attribute access",
        ast.BinOp: "an arithmetic operator",
        ast.BoolOp: "a boolean operator",
        ast.Compare: "a comparison",
        ast.Dict: "a dict literal",
        ast.DictComp: "a comprehension",
        ast.GeneratorExp: "a comprehension",
        ast.IfExp: "a conditional expression",
        ast.Lambda: "a lambda",
        ast.List: "a list literal",
        ast.ListComp: "a comprehension",
        ast.Set: "a set literal",
        ast.SetComp: "a comprehension",
        ast.Starred: "a `*` argument",
        ast.Subscript: "subscripting",
        ast.Tuple: "a tuple literal",
        ast.UnaryOp: "a unary operator (including a negative literal)",
    }
    return descriptions.get(type(node), f"`{type(node).__name__}`")
