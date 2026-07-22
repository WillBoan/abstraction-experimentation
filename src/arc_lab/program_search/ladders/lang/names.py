"""Name rules: what may be spelled where (LADDER-FORMAT.md LEX-6, NAM-1, NAM-2).

Code identifiers (primitive, abstraction and parameter names) are checked against three things --
identifier shape, Python keywords, and the format's own reserved words -- because expressions
elaborate through :mod:`ast`: a name Python cannot parse as an identifier, or reads as a keyword,
would fail with a parser error far from its cause.
"""

from __future__ import annotations

import keyword
import re

from arc_lab.program_search.ladders.lang.errors import LadderFormatError

#: The format's structural keywords (spec LEX-6) -- never a code identifier or a task id.
RESERVED_WORDS: frozenset[str] = frozenset(
    {
        "ladder",
        "floor",
        "config",
        "rung",
        "top",
        "task",
        "heldout",
        "use",
        "solution",
        "train",
        "test",
        "input",
        "true",
        "false",
    }
)

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_TASK_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


def check_identifier(name: str, what: str) -> str:
    """``name`` if it is a legal code identifier (spec NAM-1); raise otherwise."""
    if not _IDENTIFIER_RE.match(name):
        raise LadderFormatError(
            f"{what} {name!r} is not a valid identifier (letters, digits and `_`, not starting "
            "with a digit)"
        )
    if keyword.iskeyword(name) or keyword.issoftkeyword(name):
        raise LadderFormatError(f"{what} {name!r} is a Python keyword; choose another name")
    if name in RESERVED_WORDS:
        raise LadderFormatError(
            f"{what} {name!r} is a reserved word of the format; choose another name"
        )
    return name


def check_task_id(task_id: str) -> str:
    """``task_id`` if it matches the task-id shape (spec NAM-2); raise otherwise."""
    if not _TASK_ID_RE.match(task_id):
        raise LadderFormatError(
            f"task id {task_id!r} must be lowercase alphanumeric with `_`/`-`, "
            "starting with a letter or digit"
        )
    return task_id
