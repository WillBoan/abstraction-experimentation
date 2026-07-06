"""Guard: module-level type aliases must be annotated with ``TypeAlias``.

The project targets Python 3.11, so the 3.12 ``type X = ...`` statement is off the
table. A bare ``X = int | str`` *works*, but tools (and IDEs) can't tell it apart
from an ordinary constant, so it renders as a plain variable and warns when used in
a type position. Spelling it ``X: TypeAlias = int | str`` fixes that — and ruff has
no rule that enforces it on ``.py`` source (``PYI026`` only fires in ``.pyi`` stubs),
so this test is the enforcement.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "arc_lab"

# Subscript bases that mark the RHS as a type expression (``list[...]`` etc.), as
# opposed to ordinary indexing (``TABLE[0]``).
_TYPE_CONSTRUCTORS = frozenset(
    {
        "list",
        "dict",
        "tuple",
        "set",
        "frozenset",
        "Callable",
        "Sequence",
        "Mapping",
        "Iterable",
        "Iterator",
        "Optional",
        "Union",
    }
)


def _is_generic(node: ast.expr) -> bool:
    """A subscripted generic — ``list[...]``, ``Callable[...]`` — vs. plain indexing."""
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in _TYPE_CONSTRUCTORS
    )


def _is_union_operand(node: ast.expr) -> bool:
    """A type-ish operand of a ``|`` union: a name, generic, forward-ref str, or None."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_union_operand(node.left) and _is_union_operand(node.right)
    if isinstance(node, ast.Name) or _is_generic(node):
        return True
    return isinstance(node, ast.Constant) and (node.value is None or isinstance(node.value, str))


def _is_alias_rhs(node: ast.expr) -> bool:
    """Whether an assignment's RHS is a type alias needing a ``TypeAlias`` annotation.

    Deliberately conservative: only the two shapes real aliases take — a subscripted
    generic (``list[...]``) and a ``|`` union of type-ish operands. A bare string or
    name RHS (``__version__ = "0.1.0"``, ``DEFAULT_MODEL = "..."``) is *not* an alias,
    and bit-or over attributes (``re.IGNORECASE | re.DOTALL``) is never mistaken for one.
    """
    if _is_generic(node):
        return True
    return (
        isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) and _is_union_operand(node)
    )


def _module_level_statements(tree: ast.Module) -> list[ast.stmt]:
    """Top-level statements, descending into ``if TYPE_CHECKING:`` blocks only."""
    statements: list[ast.stmt] = []
    for stmt in tree.body:
        statements.append(stmt)
        if isinstance(stmt, ast.If):
            statements.extend(stmt.body)
            statements.extend(stmt.orelse)
    return statements


def _unannotated_aliases(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    offenders: list[tuple[int, str]] = []
    for stmt in _module_level_statements(tree):
        # ``x: TypeAlias = ...`` is an AnnAssign and is never flagged — the point.
        if not isinstance(stmt, ast.Assign) or not _is_alias_rhs(stmt.value):
            continue
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                offenders.append((stmt.lineno, target.id))
    return offenders


def test_type_aliases_are_annotated() -> None:
    violations = [
        f"{path.relative_to(_SRC.parent.parent)}:{lineno}  {name}"
        for path in sorted(_SRC.rglob("*.py"))
        for lineno, name in _unannotated_aliases(path)
    ]
    assert not violations, (
        "Module-level type aliases must be annotated `: TypeAlias` (Python 3.11 "
        "can't use the 3.12 `type` statement). Offenders:\n  " + "\n  ".join(violations)
    )
