"""`.ladder` source -> document tree (LADDER-FORMAT.md LEX, STR, FLR, CFG, RNG, TSK).

Syntax only. Names are checked for shape, types/signatures are parsed, grid literals become
:class:`Grid`\\ s -- but expressions stay text and nothing here consults the substrate registry or
builds a ``LadderSpec``. That is :mod:`load`'s job, and the split is what lets a malformed file
report *where* it is malformed before any semantic work begins.

Three passes: physical lines -> logical lines (comments stripped, bracket-continued lines joined) ->
a block tree -> the typed document. Every error carries the line it came from.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from arc_lab.core.grid import Grid
from arc_lab.program_search.ladders.lang.errors import LadderFormatError, at_line
from arc_lab.program_search.ladders.lang.names import check_identifier, check_task_id
from arc_lab.program_search.ladders.lang.type_syntax import (
    DefinitionHeader,
    PrimitiveSignature,
    parse_definition_header,
    parse_primitive_signature,
)

#: The file extension a ladder source carries (spec STR-1).
LADDER_SUFFIX = ".ladder"

_LADDER_NAME_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-"


@dataclass(frozen=True, slots=True)
class FloorEntry:
    """One ``use <name>: <signature>`` line (spec FLR-1)."""

    name: str
    signature: PrimitiveSignature
    line: int


@dataclass(frozen=True, slots=True)
class ConfigEntry:
    """One ``dotted.path: value`` line (spec CFG-1)."""

    path: str
    value: object
    line: int


@dataclass(frozen=True, slots=True)
class TaskBlock:
    """One ``task``/``heldout task`` block (spec TSK-1..2); ``solution`` is still text."""

    task_id: str
    heldout: bool
    solution: str
    train_inputs: tuple[Grid, ...]
    test_inputs: tuple[Grid, ...]
    line: int


@dataclass(frozen=True, slots=True)
class RungBlock:
    """One ``rung`` block: its definition (spec RNG-2) plus its task blocks."""

    header: DefinitionHeader
    body: str
    tasks: tuple[TaskBlock, ...]
    line: int

    @property
    def name(self) -> str:
        return self.header.name


@dataclass(frozen=True, slots=True)
class DistractorBlock:
    """One ``distractor <label>`` block: tasks that sit in the corpus OFF the ladder's spine.

    A control ladder (al9's ``decoy``, al11's ``trap``) puts learnable-but-unused competence in the
    corpus to ask what the loop does with it. Its tasks are solved over the Floor alone -- they
    demonstrate no rung, and nothing is minted for them.
    """

    label: str
    tasks: tuple[TaskBlock, ...]
    line: int


@dataclass(frozen=True, slots=True)
class LadderDocument:
    """A parsed `.ladder` source -- the file's content, before any substrate resolution."""

    name: str
    config: tuple[ConfigEntry, ...]
    #: The Floor library's name -- stated, not derived, because a control ladder deliberately
    #: SHARES its parent's floor identity (al9/al11 use al7's, al10/al12 use al2's) and that
    #: sharing is what makes their columns comparable (spec FLR-2).
    floor_name: str
    floor: tuple[FloorEntry, ...]
    rungs: tuple[RungBlock, ...]
    distractors: tuple[DistractorBlock, ...]
    top: tuple[TaskBlock, ...]

    def tasks(self) -> tuple[TaskBlock, ...]:
        """Every task in the file, in emission order: rungs, distractors, then the goal layer."""
        return (
            *(task for rung in self.rungs for task in rung.tasks),
            *(task for block in self.distractors for task in block.tasks),
            *self.top,
        )


def parse_ladder_file(path: Path) -> LadderDocument:
    """Parse ``path``; its stem must equal the ``ladder`` header (spec STR-1/STR-2)."""
    if path.suffix != LADDER_SUFFIX:
        raise LadderFormatError(f"{path.name} is not a {LADDER_SUFFIX} file")
    document = parse_document(path.read_text(encoding="utf-8"))
    if document.name != path.stem:
        raise LadderFormatError(
            f"file {path.name} declares `ladder {document.name}`; the name must match the filename"
        )
    return document


def parse_document(text: str) -> LadderDocument:
    """Parse `.ladder` source text into a :class:`LadderDocument`."""
    nodes = _build_tree(_logical_lines(text))
    if not nodes:
        raise LadderFormatError("empty ladder file")
    name = _ladder_header(nodes[0])
    sections = nodes[1:]
    if len(sections) < 3:
        raise LadderFormatError(
            "a ladder needs `config`, `floor`, at least one `rung`, and `top` (spec STR-4)",
            line=nodes[0].line,
        )
    if sections[0].header != "config" or sections[0].children is None:
        raise LadderFormatError(
            "expected a `config { ... }` section here (spec STR-4)", line=sections[0].line
        )
    config = tuple(_config_entry(child) for child in _block(sections[0]))
    floor_name = _floor_name(sections[1])
    floor = tuple(_floor_entry(child) for child in _block(sections[1]))
    rungs: list[RungBlock] = []
    distractors: list[DistractorBlock] = []
    for node in sections[2:-1]:
        if node.children is None:
            raise LadderFormatError(f"expected a section, got {node.header!r}", line=node.line)
        if node.header == "rung":
            if distractors:  # spec STR-4: every rung precedes every distractor
                raise LadderFormatError(
                    "`rung` sections come before `distractor` sections", line=node.line
                )
            rungs.append(_rung_block(node))
        elif node.header.split()[:1] == ["distractor"]:
            distractors.append(_distractor_block(node))
        else:
            raise LadderFormatError(
                "expected a `rung { ... }` or `distractor <label> { ... }` section (spec STR-4)",
                line=node.line,
            )
    last = sections[-1]
    if last.header != "top" or last.children is None:
        raise LadderFormatError("a ladder ends with a `top { ... }` section", line=last.line)
    if not rungs:
        raise LadderFormatError("a ladder needs at least one `rung` section", line=last.line)
    return LadderDocument(
        name=name,
        config=config,
        floor_name=floor_name,
        floor=floor,
        rungs=tuple(rungs),
        distractors=tuple(distractors),
        top=tuple(_task_block(child) for child in _block(last)),
    )


# -- sections -----------------------------------------------------------------------


def _ladder_header(node: _Node) -> str:
    if node.children is not None or not node.header.startswith("ladder"):
        raise LadderFormatError("a ladder file starts with `ladder <name>`", line=node.line)
    parts = node.header.split()
    if len(parts) != 2:
        raise LadderFormatError("the `ladder` header takes exactly one name", line=node.line)
    name = parts[1]
    if not name or any(c not in _LADDER_NAME_CHARS for c in name) or name[0] == "-":
        raise LadderFormatError(
            f"ladder name {name!r} must be kebab-case (spec STR-3)", line=node.line
        )
    return name


def _floor_name(node: _Node) -> str:
    """The ``floor <library-name> {`` header's library name (spec FLR-2)."""
    parts = node.header.split()
    if parts[:1] != ["floor"] or node.children is None:
        raise LadderFormatError(
            "expected a `floor <library-name> { ... }` section here (spec STR-4)", line=node.line
        )
    if len(parts) != 2:
        raise LadderFormatError(
            "the `floor` section header carries its library name, e.g. `floor al1-L0 {`",
            line=node.line,
        )
    return parts[1]


def _config_entry(node: _Node) -> ConfigEntry:
    if node.children is not None:
        raise LadderFormatError("the `config` section holds `path: value` lines", line=node.line)
    path, separator, raw = node.header.partition(":")
    path = path.strip()
    if not separator or not path:
        raise LadderFormatError(f"malformed config line {node.header!r}", line=node.line)
    for part in path.split("."):
        if not part.isidentifier():
            raise LadderFormatError(f"malformed config path {path!r}", line=node.line)
    try:
        value = ast.literal_eval(raw.strip())
    except (ValueError, SyntaxError):
        raise LadderFormatError(
            f"config value for {path!r} must be a literal (int, float, string, bool, list, None), "
            f"got {raw.strip()!r}",
            line=node.line,
        ) from None
    return ConfigEntry(path=path, value=value, line=node.line)


def _floor_entry(node: _Node) -> FloorEntry:
    if node.children is not None:
        raise LadderFormatError(
            "the `floor` section holds `use <name>: <signature>` lines", line=node.line
        )
    keyword, _, rest = node.header.partition(" ")
    if keyword != "use" or not rest.strip():
        raise LadderFormatError(
            f"a floor line is `use <name>: <signature>`, got {node.header!r}", line=node.line
        )
    name, separator, signature = rest.partition(":")
    if not separator:
        raise LadderFormatError(
            f"floor primitive {name.strip()!r} needs a `: <signature>` (spec FLR-6)",
            line=node.line,
        )
    try:
        return FloorEntry(
            name=check_identifier(name.strip(), "primitive name"),
            signature=parse_primitive_signature(signature.strip()),
            line=node.line,
        )
    except LadderFormatError as exc:
        raise at_line(exc, node.line) from None


def _rung_block(node: _Node) -> RungBlock:
    children = _block(node)
    if not children:
        raise LadderFormatError("a `rung` section starts with its definition", line=node.line)
    definition, tasks = children[0], children[1:]
    if definition.children is not None or "=" not in definition.header:
        raise LadderFormatError(
            "a `rung` section starts with `name(p: T, ...) -> T = <expression>` (spec RNG-2)",
            line=definition.line,
        )
    left, _, body = definition.header.partition("=")
    if not body.strip():
        raise LadderFormatError("the rung definition has no body", line=definition.line)
    try:
        header = parse_definition_header(left.strip())
    except LadderFormatError as exc:
        raise at_line(exc, definition.line) from None
    return RungBlock(
        header=header,
        body=body.strip(),
        tasks=tuple(_task_block(child) for child in tasks),
        line=node.line,
    )


def _distractor_block(node: _Node) -> DistractorBlock:
    """One ``distractor <label> { ... }`` section (spec DST)."""
    parts = node.header.split()
    if len(parts) != 2:
        raise LadderFormatError(
            "a distractor section is `distractor <label> { ... }`", line=node.line
        )
    try:
        label = check_identifier(parts[1], "distractor label")
    except LadderFormatError as exc:
        raise at_line(exc, node.line) from None
    tasks = tuple(_task_block(child) for child in _block(node))
    if not tasks:
        raise LadderFormatError(f"distractor {label!r} has no tasks", line=node.line)
    return DistractorBlock(label=label, tasks=tasks, line=node.line)


def _task_block(node: _Node) -> TaskBlock:
    if node.children is None:
        raise LadderFormatError(
            f"expected a `task <id> {{ ... }}` block, got {node.header!r}", line=node.line
        )
    parts = node.header.split()
    heldout = parts[:1] == ["heldout"]
    if heldout:
        parts = parts[1:]
    if len(parts) != 2 or parts[0] != "task":
        raise LadderFormatError(
            f"a task block header is `task <id>` or `heldout task <id>`, got {node.header!r}",
            line=node.line,
        )
    try:
        task_id = check_task_id(parts[1])
    except LadderFormatError as exc:
        raise at_line(exc, node.line) from None

    solution: str | None = None
    train: list[Grid] = []
    test: list[Grid] = []
    for child in node.children:
        if child.children is not None:
            raise LadderFormatError(f"unexpected block inside task {task_id!r}", line=child.line)
        keyword, _, rest = child.header.partition(" ")
        if keyword == "solution:" or (keyword == "solution" and rest.startswith(":")):
            if solution is not None:
                raise LadderFormatError(f"task {task_id!r} has two solutions", line=child.line)
            if train or test:
                raise LadderFormatError(
                    f"task {task_id!r}: `solution` comes before its grids (spec TSK-2)",
                    line=child.line,
                )
            solution = rest.removeprefix(":").strip()
            if not solution:
                raise LadderFormatError(f"task {task_id!r} has an empty solution", line=child.line)
        elif keyword in ("train", "test"):
            if solution is None:
                raise LadderFormatError(
                    f"task {task_id!r}: `solution` comes first (spec TSK-2)", line=child.line
                )
            if keyword == "train" and test:
                raise LadderFormatError(
                    f"task {task_id!r}: `train` grids come before `test` grids (spec TSK-2)",
                    line=child.line,
                )
            (train if keyword == "train" else test).append(_grid(rest, task_id, child.line))
        else:
            raise LadderFormatError(
                f"unknown field {child.header!r} in task {task_id!r} "
                "(a task has `solution:`, `train` and `test`)",
                line=child.line,
            )
    if solution is None:
        raise LadderFormatError(f"task {task_id!r} has no `solution`", line=node.line)
    if not train or not test:
        raise LadderFormatError(
            f"task {task_id!r} needs at least one `train` and one `test` grid (spec TSK-2)",
            line=node.line,
        )
    return TaskBlock(
        task_id=task_id,
        heldout=heldout,
        solution=solution,
        train_inputs=tuple(train),
        test_inputs=tuple(test),
        line=node.line,
    )


def _grid(text: str, task_id: str, line: int) -> Grid:
    try:
        rows = ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        raise LadderFormatError(
            f"task {task_id!r}: {text.strip()!r} is not a grid literal", line=line
        ) from None
    if not isinstance(rows, list):
        raise LadderFormatError(
            f"task {task_id!r}: a grid is a list of rows, got {text.strip()!r}", line=line
        )
    try:  # shape/value validation is the substrate's (spec TSK-3)
        return Grid.from_list(rows)
    except (ValueError, TypeError) as exc:
        raise LadderFormatError(f"task {task_id!r}: malformed grid ({exc})", line=line) from None


# -- lexical ------------------------------------------------------------------------


@dataclass(slots=True)
class _Node:
    """A statement (``children is None``) or a block and its contents."""

    header: str
    line: int
    children: list[_Node] | None = field(default=None)


def _block(node: _Node) -> list[_Node]:
    assert node.children is not None
    return node.children


def _build_tree(statements: list[tuple[str, int]]) -> list[_Node]:
    """Nest the statements by their braces (spec LEX-5)."""
    root: list[_Node] = []
    stack: list[list[_Node]] = [root]
    open_lines: list[int] = []
    for text, line in statements:
        if text == "}":
            if not open_lines:
                raise LadderFormatError("unexpected `}`", line=line)
            stack.pop()
            open_lines.pop()
        elif text.endswith("{"):
            node = _Node(header=text[:-1].strip(), line=line, children=[])
            stack[-1].append(node)
            stack.append(node.children if node.children is not None else [])
            open_lines.append(line)
        elif "{" in text or "}" in text:
            raise LadderFormatError(
                "a block opens with `{` at the end of its header line and closes with `}` on its "
                "own line (spec LEX-5)",
                line=line,
            )
        else:
            stack[-1].append(_Node(header=text, line=line))
    if open_lines:
        raise LadderFormatError("unclosed block", line=open_lines[-1])
    return root


def _logical_lines(text: str) -> list[tuple[str, int]]:
    """Comment-stripped statements with their starting line, joined across bracket continuations."""
    statements: list[tuple[str, int]] = []
    buffer: list[str] = []
    depth = 0
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped, delta = _scan(raw)
        if not stripped and not buffer:
            continue
        if not buffer:
            start = number
        buffer.append(stripped)
        depth += delta
        if depth <= 0:
            joined = " ".join(part for part in buffer if part)
            if joined:
                statements.append((joined, start))
            buffer = []
            depth = 0
    if buffer:
        raise LadderFormatError("unbalanced `(` or `[` at end of file", line=start)
    return statements


def _scan(raw: str) -> tuple[str, int]:
    """One physical line, comment removed, plus its net ``(``/``[`` depth change.

    Quotes are respected, so a ``#`` or a bracket inside a string value stays literal.
    """
    out: list[str] = []
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(raw):
        char = raw[index]
        if quote is not None:
            out.append(char)
            if char == "\\" and index + 1 < len(raw):
                out.append(raw[index + 1])
                index += 2
                continue
            if char == quote:
                quote = None
        elif char == "#":  # spec LEX-2
            break
        elif char in "\"'":
            quote = char
            out.append(char)
        else:
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            out.append(char)
        index += 1
    return "".join(out).strip(), depth
