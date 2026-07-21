"""Evaluation-backed lint checks over a ladder's STATED solutions.

These run inside ``LadderSpec.lint()`` but live apart from it (the spec passes plain data in, so
there is no import cycle). They keep lint *search-free* while giving up evaluation-freeness: each
check evaluates the stated solutions' subterms on the tasks' own train inputs — deterministic,
cheap, no engine search, no run identity.

The law behind ``constancy_findings``: the enumerator dedupes candidates by signature (behavior on
the train examples) and keeps the cheapest representative of each class — so a COMPOSITE subterm
whose value is constant across a task's train examples is strictly beaten by its literal whenever
that value is in the configured constant domain. The depth that computing the value was meant to
contribute never exists (the al14 literal collapse, made static). A merely-constant subterm whose
value is NOT mintable still contributes fictional depth, hence the warn tier.

``conditional_findings`` is the same law's branching corollary: an ``If`` whose condition is
constant across a task's train examples has the taken branch's signature, so search keeps the
branch alone and the conditional collapses.

All checks run on solutions UNFOLDED to the floor — collapse lives in the floor's term space
(al14's ``sub(1, 1)`` only appears after unfolding). Solutions are closed and Input-rooted;
subterms containing ``Param``/``Var``/``Lam`` (or anything that fails to evaluate) are skipped,
never flagged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from arc_lab.core.grid import Grid
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.search.leaves import ConstantSource, policy_constants
from arc_lab.program_search.substrate.library import Library
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
from arc_lab.program_search.substrate.types import BOOL, COLOR, INT, Type

#: Sentinel for "this subterm (or a child) does not evaluate on this grid" — poisons ancestors.
_ERROR = object()

#: The scalar result types the constancy check flags. GRID-valued constants are deliberately
#: excluded in v1: a train-constant grid subterm is suspicious too, but flagging it needs a
#: noise-controlled story (background grids, seeds) that scalars don't.
_SCALAR_TYPES = (INT, COLOR, BOOL)


def constancy_findings(
    stated: Sequence[tuple[str, Program]],
    train_inputs: Mapping[str, tuple[Grid, ...]],
    library: Library,
    constant_sources: tuple[ConstantSource, ...],
) -> tuple[LintFinding, ...]:
    """One ``constant-subterm[<task_id>]`` finding per stated task (pass or fail).

    Error when a composite scalar subterm is train-constant AND its (type, value) is in the
    ladder's own configured constant domain (the beating literal exists in this ladder's search);
    warn when merely train-constant. Tasks with fewer than 2 train examples are skipped (everything
    is trivially constant there — the ``min-2-train-examples`` advisory owns that defect).
    """
    findings: list[LintFinding] = []
    for task_id, solution in stated:
        grids = train_inputs.get(task_id, ())
        if len(grids) < 2:
            continue
        domain = {
            (constant.value_type, constant.value)
            for constant, _ in policy_constants(grids, constant_sources, library)
            if isinstance(constant, Const)
        }
        memos = [_subterm_values(solution, grid, library) for grid in grids]
        beaten: dict[str, object] = {}
        fictional: dict[str, object] = {}
        for node in _distinct_composites(solution):
            result_type = _scalar_result_type(node, library)
            if result_type is None:
                continue
            values = [memo.get(id(node), _ERROR) for memo in memos]
            if any(value is _ERROR for value in values):
                continue
            if any(value != values[0] for value in values[1:]):
                continue
            target = beaten if (result_type, values[0]) in domain else fictional
            target.setdefault(_spell(node), values[0])
        if beaten:
            findings.append(
                LintFinding(
                    check=f"constant-subterm[{task_id}]",
                    ok=False,
                    detail="train-constant subterms beaten by an enumerated literal: "
                    f"{_offenders(beaten)}",
                    severity="error",
                )
            )
        elif fictional:
            findings.append(
                LintFinding(
                    check=f"constant-subterm[{task_id}]",
                    ok=False,
                    detail="train-constant subterms (fictional depth; value not mintable here): "
                    f"{_offenders(fictional)}",
                    severity="warn",
                )
            )
        else:
            findings.append(
                LintFinding(check=f"constant-subterm[{task_id}]", ok=True, detail="")
            )
    return tuple(findings)


def conditional_findings(
    stated: Sequence[tuple[str, Program]],
    train_inputs: Mapping[str, tuple[Grid, ...]],
    library: Library,
) -> tuple[LintFinding, ...]:
    """One ``if-condition-varies[<task_id>]`` finding per stated task that CONTAINS an ``If``.

    Error unless every ``If``'s condition takes both truth values across the task's train
    examples. Tasks without branching emit nothing (the check is dormant until a conditional
    floor exists); conditions that fail to evaluate are skipped, never flagged.
    """
    findings: list[LintFinding] = []
    for task_id, solution in stated:
        conditionals = [node for node in _distinct_composites(solution) if isinstance(node, If)]
        grids = train_inputs.get(task_id, ())
        if not conditionals or len(grids) < 2:
            continue
        memos = [_subterm_values(solution, grid, library) for grid in grids]
        constant: dict[str, object] = {}
        for node in conditionals:
            values = [memo.get(id(node.cond), _ERROR) for memo in memos]
            observed = {value for value in values if isinstance(value, bool)}
            if any(value is _ERROR for value in values) or len(observed) == 2:
                continue
            constant.setdefault(_spell(node.cond), next(iter(observed), "?"))
        if constant:
            findings.append(
                LintFinding(
                    check=f"if-condition-varies[{task_id}]",
                    ok=False,
                    detail="conditions constant across train examples (the If collapses to the "
                    f"taken branch): {_offenders(constant)}",
                    severity="error",
                )
            )
        else:
            findings.append(
                LintFinding(check=f"if-condition-varies[{task_id}]", ok=True, detail="")
            )
    return tuple(findings)


def _subterm_values(root: Program, grid: Grid, library: Library) -> dict[int, object]:
    """Every subterm's value on one input grid, keyed by ``id(node)`` (or the error sentinel).

    Bottom-up with an ``id()``-memo: heavily-shared trees (``substitute_params`` reuses subtree
    objects, so an unfolded solution's millions of occurrences are a few hundred distinct nodes)
    cost one evaluation per distinct node object, never one per occurrence. ``If`` keeps the
    engine's short-circuit semantics: its value needs only the taken branch, though both branches
    are still visited so their own subterms get values.
    """
    memo: dict[int, object] = {}

    def go(node: Program) -> object:
        key = id(node)
        if key not in memo:
            memo[key] = _evaluate_node(node, go, grid, library)
        return memo[key]

    go(root)
    return memo


def _evaluate_node(
    node: Program, go: Callable[[Program], object], grid: Grid, library: Library
) -> object:
    if isinstance(node, Input):
        return grid
    if isinstance(node, Const):
        return node.value
    if isinstance(node, Param | Var | Lam | PrimRef):
        return _ERROR  # not standalone-evaluable (open term or function value)
    if isinstance(node, If):
        condition = go(node.cond)
        then, orelse = go(node.then), go(node.orelse)
        if not isinstance(condition, bool):
            return _ERROR
        return then if condition else orelse
    if isinstance(node, Apply):
        args = [go(arg) for arg in node.args]
        if any(arg is _ERROR for arg in args) or node.primitive not in library:
            return _ERROR
        try:
            return library.get(node.primitive).impl(*args)
        except Exception:  # partial primitives error freely off their domain
            return _ERROR
    # AppFn: its fn child is a function value the memo's value domain can't carry — evaluate the
    # whole node directly (rare; v1 floors are first-order).
    for child in node.children():
        go(child)
    try:
        return node.evaluate(grid, library)
    except Exception:
        return _ERROR


def _distinct_composites(root: Program) -> list[Program]:
    """The distinct (by identity) ``Apply``/``If``/``AppFn`` subterms, deterministic order.

    Walks children of already-seen shared subtrees only once, so an unfolded solution with
    millions of occurrences but few distinct nodes stays cheap.
    """
    seen: set[int] = set()
    ordered: list[Program] = []

    def visit(node: Program) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, Apply | If | AppFn):
            ordered.append(node)
        for child in node.children():
            visit(child)

    visit(root)
    return ordered


def _scalar_result_type(node: Program, library: Library) -> Type | None:
    """The node's result type if it is one of the flagged scalar types, else ``None``."""
    try:
        result_type = node.result_type(library)
    except Exception:
        return None
    return result_type if result_type in _SCALAR_TYPES else None


#: A finding detail names subterms of UNFOLDED solutions, which can be megabytes deep (al14's
#: unfolded top is ~3.4M nodes) — spellings are hard-capped so details stay readable and bounded.
_SPELL_LIMIT = 120


def _spell(node: Program) -> str:
    """A readable, bounded spelling for a finding detail — surface syntax where possible."""
    try:
        from arc_lab.program_search.ladders.lang.expr import render_expression

        spelling = render_expression(node)
    except Exception:
        spelling = str(node)
    if len(spelling) > _SPELL_LIMIT:
        return f"{spelling[:_SPELL_LIMIT]}..."
    return spelling


def _offenders(named: Mapping[str, object], limit: int = 5) -> str:
    """Up to ``limit`` ``spelling=value`` pairs, sorted for lock stability, with an overflow note."""
    pairs = [f"{spelling}={named[spelling]!r}" for spelling in sorted(named)]
    shown = ", ".join(pairs[:limit])
    overflow = len(pairs) - limit
    return f"{shown} (+{overflow} more)" if overflow > 0 else shown
