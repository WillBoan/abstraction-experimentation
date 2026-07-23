"""Expression elaboration: surface text <-> :class:`Program` (LADDER-FORMAT.md EXP-1..7).

The surface is a subset of Python expressions, so :mod:`ast` does the parsing and this module does
everything else. It covers all nine substrate node kinds, and the unifying idea is that almost none
of them need syntax of their own -- each is a Python form resolved by **the type of the position it
sits in**, exactly as an int literal already takes its type from its argument slot:

===========================  ==========================  =========================================
Surface                      Python form                 Elaborates to
===========================  ==========================  =========================================
``input``                    ``Name``                    ``Input``
``1`` / ``-1``               ``Constant`` / ``UnaryOp``  ``Const`` (Color or Int position)
``true`` / ``false``         ``Name``                    ``Const`` (Bool position)
``g`` (a rung parameter)     ``Name``                    ``Param``
``r`` (a lambda binder)      ``Name``                    ``Var`` (De Bruijn, innermost = 0)
``flip_h`` (bare)            ``Name``                    ``PrimRef`` (arrow-typed position)
``flip_h(g)``                ``Call``                    ``Apply``
``f(g)`` (``f`` a value)     ``Call``                    ``AppFn``
``a if c else b``            ``IfExp``                   ``If`` (short-circuit, like Python's)
``lambda r, c: body``        ``Lambda``                  curried ``Lam`` chain
===========================  ==========================  =========================================

Elaboration is also where an expression is **type-checked**: the substrate types programs but does
not verify them, and a literal has no intrinsic type. One top-down walk settles both -- each
argument is elaborated against the (substituted) type of the parameter position it fills, unifying
as it goes -- so arity errors, type errors, literal typing, and the resolutions in the table above
all fall out together.
"""

from __future__ import annotations

import ast
import itertools
from collections.abc import Sequence

from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.names import check_identifier
from arc_lab.program_search.ladders.lang.type_syntax import render_type
from arc_lab.program_search.search.search_engine import BRANCHING_ENTRY
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    Const,
    If,
    Input,
    Lam,
    Param,
    PrimRef,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import (
    BOOL,
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

#: Boolean literals. Lowercase deliberately: Python's capitalised ``True`` parses as a ``Constant``
#: and these parse as plain ``Name``s, so there is exactly one spelling and no clash.
TRUE_KEYWORD, FALSE_KEYWORD = "true", "false"

#: The types an int literal may inhabit -- the substrate's int-valued scalars. ``GRID``/``MASK``/
#: ``FN`` hold no literal at all. Deliberately stricter than ``Const``, which the substrate lets
#: carry any nullary type.
_INT_LITERAL_TYPES: frozenset[TypeCon] = frozenset({COLOR, INT})


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
    program, _ = elaborate_typed(text, library=library, params=params, allow_input=allow_input)
    return program


def elaborate_typed(
    text: str,
    *,
    library: Library,
    params: Sequence[tuple[str, Type]] = (),
    allow_input: bool,
) -> tuple[Program, Type]:
    """:func:`elaborate_expression`, plus the RESOLVED type of the whole expression.

    The substrate cannot recover that type from the program alone (``Program.result_type`` does
    not unify), so a caller that needs it -- checking a rung body against its declared return
    type, and minting the abstraction -- must take it from elaboration.
    """
    stripped = text.strip()
    if not stripped:
        raise LadderFormatError("empty expression")
    try:
        tree = ast.parse(stripped, mode="eval")
    except SyntaxError as exc:
        raise LadderFormatError(f"could not parse expression {stripped!r}: {exc.msg}") from None
    return _Elaborator(library=library, params=params, allow_input=allow_input).run_typed(tree.body)


def render_expression(program: Program, param_names: Sequence[str] = ()) -> str:
    """The canonical surface spelling of ``program`` -- inverse of :func:`elaborate_expression`.

    ``param_names`` supplies the names for :class:`Param` holes, in index order; lambda binders are
    named ``v0``, ``v1``, ... by their depth, so nested lambdas never collide.
    """
    return _render(program, tuple(param_names), ())


class _Elaborator:
    """One expression's elaboration: scopes, fresh-type-variable counter, and substitution."""

    def __init__(
        self, *, library: Library, params: Sequence[tuple[str, Type]], allow_input: bool
    ) -> None:
        self.library = library
        self.params = {name: (index, t) for index, (name, t) in enumerate(params)}
        self.allow_input = allow_input
        self.counter: itertools.count[int] = itertools.count()
        self.subst: Substitution = {}
        #: Lambda binders, OUTERMOST first. A name's De Bruijn index counts from the other end.
        self.binders: list[tuple[str, Type]] = []

    def run_typed(self, node: ast.expr) -> tuple[Program, Type]:
        program, value_type = self.elaborate(node, None)
        # A binder's type is captured when it is bound, which can be BEFORE the body pins the
        # type variable it came from (`map`'s hole is `(a) -> b`, and only the body says what `a`
        # is). Resolving once at the end is what keeps a stored program monomorphic.
        return _resolve_types(program, self.subst), apply_subst(self.subst, value_type)

    def elaborate(self, node: ast.expr, expected: Type | None) -> tuple[Program, Type]:
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.Name):
            return self._name(node, expected)
        if isinstance(node, ast.Constant):
            return self._constant(node, expected)
        if isinstance(node, ast.UnaryOp):
            return self._negative(node, expected)
        if isinstance(node, ast.IfExp):
            return self._conditional(node, expected)
        if isinstance(node, ast.Lambda):
            return self._lambda(node, expected)
        raise LadderFormatError(
            f"{_describe(node)} is not part of the format (an expression is application over "
            "identifiers, literals, conditionals and lambdas)"
        )

    # -- leaves ---------------------------------------------------------------------

    def _name(self, node: ast.Name, expected: Type | None) -> tuple[Program, Type]:
        name = node.id
        if name == INPUT_KEYWORD:
            if not self.allow_input:
                raise LadderFormatError(
                    f"`{INPUT_KEYWORD}` is not in scope: a rung template is closed over its "
                    "parameters (spec NAM-4)"
                )
            return Input(), GRID
        if name in (TRUE_KEYWORD, FALSE_KEYWORD):
            return self._boolean(name == TRUE_KEYWORD, expected)
        binder = self._binder(name)
        if binder is not None:
            index, value_type = binder
            return Var(index, value_type), value_type
        entry = self.params.get(name)
        if entry is not None:
            index, value_type = entry
            return Param(index, value_type), value_type
        if name in self.library:
            # A primitive used as a VALUE, not applied -- legal exactly where a function is wanted.
            resolved = None if expected is None else apply_subst(self.subst, expected)
            if isinstance(resolved, ArrowType):
                prim = self.library.get(name)
                return PrimRef(name), self._arrow_of(prim)
            raise LadderFormatError(
                f"`{name}` is a function; write `{name}(...)` to apply it, or pass it bare only "
                "where a function-typed argument is expected"
            )
        raise LadderFormatError(f"unknown name `{name}`; {self._scope_hint()}")

    def _constant(self, node: ast.Constant, expected: Type | None) -> tuple[Program, Type]:
        value = node.value
        if isinstance(value, bool):
            raise LadderFormatError(
                f"write `{str(value).lower()}`, not `{value}`: boolean literals are lowercase"
            )
        if not isinstance(value, int):
            raise LadderFormatError(f"unsupported literal {value!r}: the format has int literals")
        return self._integer(value, expected)

    def _negative(self, node: ast.UnaryOp, expected: Type | None) -> tuple[Program, Type]:
        operand = node.operand
        if not isinstance(node.op, ast.USub) or not isinstance(operand, ast.Constant):
            raise LadderFormatError(f"{_describe(node)} is not part of the format")
        if isinstance(operand.value, bool) or not isinstance(operand.value, int):
            raise LadderFormatError(f"unsupported literal -{operand.value!r}")
        return self._integer(-operand.value, expected)

    def _integer(self, value: int, expected: Type | None) -> tuple[Program, Type]:
        resolved = self._literal_type(value, expected)
        if resolved not in _INT_LITERAL_TYPES:
            allowed = ", ".join(sorted(render_type(t) for t in _INT_LITERAL_TYPES))
            raise LadderFormatError(
                f"the literal {value} cannot fill a `{render_type(resolved)}` position "
                f"(an int literal is {allowed})"
            )
        return Const(value, resolved), resolved

    def _boolean(self, value: bool, expected: Type | None) -> tuple[Program, Type]:
        resolved = self._literal_type(value, expected)
        if resolved != BOOL:
            raise LadderFormatError(
                f"`{str(value).lower()}` cannot fill a `{render_type(resolved)}` position"
            )
        return Const(value, BOOL), BOOL

    def _literal_type(self, value: object, expected: Type | None) -> TypeCon:
        """The nullary type a literal in this position takes, or a load error (spec EXP-5)."""
        if expected is None:
            raise LadderFormatError(
                f"cannot type the literal {value}: a literal only appears in a typed argument "
                "position (spec EXP-5)"
            )
        resolved = apply_subst(self.subst, expected)
        if isinstance(resolved, TypeVar):
            raise LadderFormatError(
                f"cannot type the literal {value}: the argument position is polymorphic "
                f"({render_type(resolved)}) (spec EXP-5)"
            )
        if not isinstance(resolved, TypeCon) or resolved.args:
            raise LadderFormatError(
                f"the literal {value} cannot fill a `{render_type(resolved)}` position"
            )
        return resolved

    # -- composites -----------------------------------------------------------------

    def _call(self, node: ast.Call) -> tuple[Program, Type]:
        head = node.func
        name = head.id if isinstance(head, ast.Name) else "<expression>"
        if node.keywords:
            raise LadderFormatError(f"`{name}` must be called with positional arguments only")
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise LadderFormatError(f"`{name}` cannot be called with `*` arguments")
        if isinstance(head, ast.Name) and head.id == INPUT_KEYWORD:
            raise LadderFormatError(f"`{INPUT_KEYWORD}` is the task input grid, not a function")
        # A library primitive is applied directly (`Apply`); anything else must evaluate to a
        # function VALUE, which is the higher-order application node (`AppFn`).
        if isinstance(head, ast.Name) and head.id in self.library:
            return self._apply(head.id, node.args)
        if (
            isinstance(head, ast.Name)
            and head.id not in self.params
            and self._binder(head.id) is None
        ):  # not a primitive and not a value in scope -- name the right thing
            raise LadderFormatError(f"unknown function `{head.id}`; {self._scope_hint()}")
        return self._apply_value(head, node.args)

    def _apply(self, name: str, arg_nodes: list[ast.expr]) -> tuple[Program, Type]:
        prim = self.library.get(name)
        fixed, variadic, return_type = self._instantiate(prim)
        self._check_arity(name, len(arg_nodes), len(fixed), variadic is not None)
        args: list[Program] = []
        for index, arg_node in enumerate(arg_nodes):
            slot = fixed[index] if index < len(fixed) else variadic
            assert slot is not None  # arity check above guarantees a variadic slot exists
            args.append(self._argument(arg_node, slot, f"argument {index + 1} of `{name}`"))
        return Apply(name, tuple(args)), apply_subst(self.subst, return_type)

    def _apply_value(self, head: ast.expr, arg_nodes: list[ast.expr]) -> tuple[Program, Type]:
        """Apply a computed function value -- a parameter, a binder, a lambda, or a `PrimRef`."""
        fn, fn_type = self.elaborate(head, None)
        resolved = apply_subst(self.subst, fn_type)
        if not isinstance(resolved, ArrowType):
            raise LadderFormatError(
                f"`{_spell(head)}` is not a function ({render_type(resolved)}), so it cannot be "
                "applied"
            )
        if len(resolved.params) != len(arg_nodes):
            raise LadderFormatError(
                f"`{_spell(head)}` takes {len(resolved.params)} argument(s), got {len(arg_nodes)}"
                + (
                    "; a curried function is applied one stage at a time, as `f(a)(b)`"
                    if isinstance(resolved.result, ArrowType)
                    else ""
                )
            )
        args = [
            self._argument(arg_node, slot, f"argument {index + 1} of `{_spell(head)}`")
            for index, (arg_node, slot) in enumerate(zip(arg_nodes, resolved.params, strict=True))
        ]
        return AppFn(fn, tuple(args)), apply_subst(self.subst, resolved.result)

    def _conditional(self, node: ast.IfExp, expected: Type | None) -> tuple[Program, Type]:
        """``a if c else b`` -> :class:`If` -- short-circuit in Python and in the substrate.

        Branching is the one node kind with no ``Apply`` to name a primitive, yet the engine only
        enumerates branches when the ``if`` summoner is in the library (``_branch_candidates``); a
        branch written over a floor that omits it is writable but unreachable at any budget. That is
        a coherence failure, not an unsoundness -- the ladder cannot mean anything for search -- so
        it is a load error here, beside every other "unknown vocabulary" one, rather than a lint
        finding. The floor is a subset of every ``L_i``, and only the floor can carry ``if``, so
        checking the elaboration scope is exactly checking the floor.
        """
        if BRANCHING_ENTRY not in self.library:
            raise LadderFormatError(
                f"a conditional needs the `{BRANCHING_ENTRY}` summoner in the floor, which this "
                "scope does not declare: search could never reach the branch"
            )
        cond = self._argument(node.test, BOOL, "an `if` condition")
        then, then_type = self.elaborate(node.body, expected)
        orelse = self._argument(node.orelse, then_type, "the `else` branch")
        return If(cond=cond, then=then, orelse=orelse), apply_subst(self.subst, then_type)

    def _lambda(self, node: ast.Lambda, expected: Type | None) -> tuple[Program, Type]:
        """``lambda r, c: body`` -> a curried :class:`Lam` chain, binder types from ``expected``.

        Python lambdas cannot carry annotations, and they do not need to: the function-typed
        position the lambda fills already states each binder's type. One arrow is peeled per
        binder, which serves both the single-argument holes (``map``'s ``(a) -> b``) and the
        curried ones (``build_grid``'s ``(int) -> (int) -> color``).
        """
        spec = node.args
        if spec.vararg or spec.kwarg or spec.defaults or spec.kwonlyargs or spec.posonlyargs:
            raise LadderFormatError("a lambda takes plain positional binders only")
        if not spec.args:
            raise LadderFormatError("a lambda needs at least one binder")
        if expected is None:
            raise LadderFormatError(
                "cannot type this lambda: it only appears in a function-typed argument position"
            )
        remaining = apply_subst(self.subst, expected)
        added = 0
        try:
            for argument in spec.args:
                name = check_identifier(argument.arg, "lambda binder")
                if not isinstance(remaining, ArrowType) or len(remaining.params) != 1:
                    raise LadderFormatError(
                        f"binder `{name}` has no function type to take it from "
                        f"(the position is {render_type(remaining)})"
                    )
                if name in self.params or self._binder(name) is not None:
                    raise LadderFormatError(
                        f"lambda binder `{name}` shadows a parameter or an enclosing binder"
                    )
                self.binders.append((name, remaining.params[0]))
                added += 1
                remaining = remaining.result
            body, _ = self.elaborate(node.body, remaining)
            bound = [value_type for _, value_type in self.binders[len(self.binders) - added :]]
        finally:
            del self.binders[len(self.binders) - added :]
        program: Program = body
        for value_type in reversed(bound):  # the OUTERMOST Lam binds the first binder
            program = Lam(param_type=value_type, body=program)
        return program, apply_subst(self.subst, expected)

    # -- helpers --------------------------------------------------------------------

    def _argument(self, node: ast.expr, slot: Type, where: str) -> Program:
        """Elaborate ``node`` against the type of the position it fills, unifying as we go."""
        expected = apply_subst(self.subst, slot)
        program, actual = self.elaborate(node, expected)
        unified = unify(actual, expected, self.subst)
        if unified is None:
            raise LadderFormatError(
                f"{where} is {render_type(actual)}, expected {render_type(expected)}"
            )
        self.subst = unified
        return program

    def _binder(self, name: str) -> tuple[int, Type] | None:
        """A lambda binder's De Bruijn index and type -- innermost is 0 (the substrate's ``$0``)."""
        for position in range(len(self.binders) - 1, -1, -1):
            if self.binders[position][0] == name:
                return len(self.binders) - 1 - position, self.binders[position][1]
        return None

    def _arrow_of(self, prim: Primitive) -> ArrowType:
        """A primitive's type as a first-class function value, with fresh type variables."""
        fresh = instantiate(ArrowType(tuple(prim.param_types), prim.return_type), self.counter)
        assert isinstance(fresh, ArrowType)
        return fresh

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
        names = [name for name, _ in self.binders] + sorted(self.params)
        names += sorted(self.library.names())
        if self.allow_input:
            names.append(INPUT_KEYWORD)
        return "in scope: " + ", ".join(names)


# -- rendering ----------------------------------------------------------------------


def _render(program: Program, param_names: tuple[str, ...], binders: tuple[str, ...]) -> str:
    if isinstance(program, Input):
        return INPUT_KEYWORD
    if isinstance(program, Param):
        if program.index >= len(param_names):
            raise LadderFormatError(
                f"no name for parameter #{program.index} (given: {list(param_names)})"
            )
        return param_names[program.index]
    if isinstance(program, Var):
        if program.index >= len(binders):
            raise LadderFormatError(f"unbound lambda variable ${program.index}")
        return binders[len(binders) - 1 - program.index]
    if isinstance(program, Const):
        if isinstance(program.value, bool):
            return TRUE_KEYWORD if program.value else FALSE_KEYWORD
        return str(program.value)
    if isinstance(program, PrimRef):
        return program.name
    if isinstance(program, Apply):
        args = ", ".join(_render(arg, param_names, binders) for arg in program.args)
        return f"{program.primitive}({args})"
    if isinstance(program, AppFn):
        args = ", ".join(_render(arg, param_names, binders) for arg in program.args)
        return f"{_render(program.fn, param_names, binders)}({args})"
    if isinstance(program, If):
        return (
            f"{_render(program.then, param_names, binders)} "
            f"if {_render(program.cond, param_names, binders)} "
            f"else {_render(program.orelse, param_names, binders)}"
        )
    if isinstance(program, Lam):
        names: list[str] = []
        body: Program = program
        while isinstance(body, Lam):  # a curried chain is ONE surface lambda
            names.append(f"v{len(binders) + len(names)}")
            body = body.body
        inner = (*binders, *names)
        return f"lambda {', '.join(names)}: {_render(body, param_names, inner)}"
    raise LadderFormatError(f"{type(program).__name__} has no surface syntax")


def _resolve_types(program: Program, subst: Substitution) -> Program:
    """Apply the final substitution to every type a node carries (``Lam`` binders, ``Var``s)."""
    if not subst:
        return program
    if isinstance(program, Lam):
        return Lam(
            param_type=apply_subst(subst, program.param_type),
            body=_resolve_types(program.body, subst),
        )
    if isinstance(program, Var):
        return Var(index=program.index, value_type=apply_subst(subst, program.value_type))
    if isinstance(program, Apply):
        return Apply(program.primitive, tuple(_resolve_types(a, subst) for a in program.args))
    if isinstance(program, AppFn):
        return AppFn(
            fn=_resolve_types(program.fn, subst),
            args=tuple(_resolve_types(a, subst) for a in program.args),
        )
    if isinstance(program, If):
        return If(
            cond=_resolve_types(program.cond, subst),
            then=_resolve_types(program.then, subst),
            orelse=_resolve_types(program.orelse, subst),
        )
    return program


def _spell(node: ast.expr) -> str:
    """How the source wrote an expression, for an error message."""
    return node.id if isinstance(node, ast.Name) else ast.unparse(node)


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
        ast.List: "a list literal",
        ast.ListComp: "a comprehension",
        ast.Set: "a set literal",
        ast.SetComp: "a comprehension",
        ast.Starred: "a `*` argument",
        ast.Subscript: "subscripting",
        ast.Tuple: "a tuple literal",
        ast.UnaryOp: "a unary operator (only `-` before an int literal is allowed)",
    }
    return descriptions.get(type(node), f"`{type(node).__name__}`")
