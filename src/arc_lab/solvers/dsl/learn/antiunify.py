"""Proposing abstraction candidates by antiunification (least-general-generalization).

The *sleep* step of the loop mines the solved corpus for recurring structure. Two
programs' antiunification is their most-specific common template: shared structure is
kept, differing positions become fresh :class:`~...program.Param` holes. Remaining
``Input()`` nodes are then lifted to a shared grid ``Param`` so the template is **closed**
(reusable, not bolted to the task input). A recurring *identical* program is the simplest
case — it antiunifies with itself, so lifting its input already yields a candidate.

This v1 has **no variable-sharing**: distinct differing positions get distinct holes even
when they hold the same subterm. That's sound for identical-program recurrence (E1/E2) but
over-generalises when correctness needs a shared variable (E3 `swap_cells`) — the
`LGG variable-sharing` upgrade is TODO. Rewriting folds any matching *subtree* (not just the
program root), so a recurring idiom compresses even inside larger, otherwise-distinct programs.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterator

from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Apply, Input, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import ValueType


class _BoundVarEscapeError(Exception):
    """Antiunification would lift a bound ``$i`` out of its binder -- unsound; abort this pair."""


class AbstractionProposer(ABC):
    """Propose candidate closed templates mined from the solved programs."""

    @abstractmethod
    def propose(self, programs: list[Program], library: Library) -> list[Program]:
        """Candidate templates (closed, Param-holed), best-effort deduplicated."""


class AntiunifyPairs(AbstractionProposer):
    """Antiunify recurring identical programs and distinct pairs into closed templates.

    ``bound_var_safe`` (default ``False`` — the historical behaviour): when a pairwise
    antiunification would hole a differing subterm that contains a lambda-bound ``$i``, that is a
    **scope violation** (lifting a per-cell bound var into a per-call abstraction arg), so with the
    flag set that pairwise candidate is dropped. Off, the loop happily mints such unsound
    abstractions and — since they "compress" by covering several members — governance prefers them
    (the E6 finding). E1-E4 never hit this (they hole ``Const``s, not ``Var``s), so the flag is inert
    there; it only bites on ``build_grid`` corpora with multiple distinct programs (E6 vs E7).

    - TODO(alternatives): frequent-subtree mining; version-space / e-graph compression
    (the DreamCoder-grade proposer) — what a `mirror_index`-style cross-member idiom would need.
    - TODO(variable-sharing): reuse one Param when the same
    differing subterm recurs across positions — required for E3 `swap_cells`.
    """

    def __init__(self, *, bound_var_safe: bool = False) -> None:
        self.bound_var_safe = bound_var_safe

    def propose(self, programs: list[Program], library: Library) -> list[Program]:
        candidates: dict[Program, None] = {}  # ordered set (dedup by structure)
        counts = Counter(programs)
        # A program that recurs verbatim is itself an abstraction once its input is lifted.
        for program, n in counts.items():
            if n >= 2:
                self._offer(_close_template(program), candidates)
        # Distinct programs generalise via pairwise antiunification (with variable-sharing).
        for a, b in itertools.combinations(counts, 2):
            try:
                generalised = _antiunify(a, b, library, {}, itertools.count(), self.bound_var_safe)
            except _BoundVarEscapeError:
                continue  # would hoist a bound var out of its binder — skip this pair
            self._offer(_close_template(generalised), candidates)
        return list(candidates)

    @staticmethod
    def _offer(template: Program, candidates: dict[Program, None]) -> None:
        if _is_useful(template):
            candidates.setdefault(template, None)


def _contains_var(program: Program) -> bool:
    """Whether a subterm references a lambda-bound variable (``$i``) — i.e. is not closed."""
    return any(isinstance(node, Var) for node in program.walk())


def _antiunify(
    p: Program,
    q: Program,
    library: Library,
    memo: dict[tuple[Program, Program], Param],
    counter: Iterator[int],
    bound_var_safe: bool = False,
) -> Program:
    """Most-specific common generalisation of ``p`` and ``q``, with variable-sharing.

    ``memo`` maps a *differing* subterm pair ``(p_sub, q_sub)`` to the hole standing for it,
    so the same difference recurring at several positions reuses **one** ``Param`` — the
    least-general-generalization semantics needed for e.g. `swap_cells`, where one coordinate
    feeds both a ``read`` and a ``set_cell``. With ``bound_var_safe``, holing a differing subterm
    that references a bound ``$i`` raises :class:`_BoundVarEscapeError` (you cannot lift a bound var out
    of its binder — see :class:`AntiunifyPairs`).
    """
    if p == q:
        return p
    if isinstance(p, Param):  # already maximally general at this position
        return p
    if isinstance(q, Param):
        return q
    if (
        isinstance(p, Apply)
        and isinstance(q, Apply)
        and p.primitive == q.primitive
        and len(p.args) == len(q.args)
    ):
        return Apply(
            p.primitive,
            tuple(
                _antiunify(pa, qa, library, memo, counter, bound_var_safe)
                for pa, qa in zip(p.args, q.args, strict=True)
            ),
        )
    if isinstance(p, Lam) and isinstance(q, Lam):  # generalise under the binder; scope is shared
        return Lam(_antiunify(p.body, q.body, library, memo, counter, bound_var_safe))
    if bound_var_safe and (_contains_var(p) or _contains_var(q)):
        raise _BoundVarEscapeError  # cannot lift a per-cell bound var into a per-call abstraction arg
    key = (p, q)
    if key not in memo:
        memo[key] = Param(next(counter), p.result_type(library))
    return memo[key]


def _close_template(program: Program) -> Program:
    """Lift ``Input()`` to a shared grid ``Param`` and renumber all params contiguously.

    First-occurrence (pre-order) determines argument order; all ``Input()`` collapse to one
    grid param (same value), so a template stays closed and minimal-arity.
    """
    index_of: dict[object, int] = {}

    def rebuild(node: Program) -> Program:
        if isinstance(node, Input):
            return Param(index_of.setdefault(("input",), len(index_of)), ValueType.GRID)
        if isinstance(node, Param):
            return Param(index_of.setdefault(("param", node.index), len(index_of)), node.value_type)
        if isinstance(node, Apply):
            return Apply(node.primitive, tuple(rebuild(arg) for arg in node.args))
        if isinstance(node, Lam):  # descend so an Input inside a lambda body is lifted too
            return Lam(rebuild(node.body))
        return node  # Const / Var: an invariant leaf, kept concrete

    return rebuild(program)


def _is_useful(template: Program) -> bool:
    """A useful template has real structure (an Apply) and at least one hole (a Param)."""
    nodes = list(template.walk())
    return any(isinstance(n, Apply) for n in nodes) and any(isinstance(n, Param) for n in nodes)


def match(template: Program, program: Program) -> tuple[Program, ...] | None:
    """If ``program`` is an instance of ``template``, the argument bindings (by index); else None.

    A shared param bound to two different subterms fails the match (keeps rewriting sound).
    """
    bindings: dict[int, Program] = {}
    if not _match_into(template, program, bindings):
        return None
    if set(bindings) != set(range(len(bindings))):
        return None
    return tuple(bindings[i] for i in range(len(bindings)))


def _match_into(template: Program, program: Program, bindings: dict[int, Program]) -> bool:
    if isinstance(template, Param):
        existing = bindings.get(template.index)
        if existing is not None:
            return existing == program
        bindings[template.index] = program
        return True
    if isinstance(template, Apply) and isinstance(program, Apply):
        if template.primitive != program.primitive or len(template.args) != len(program.args):
            return False
        return all(
            _match_into(t, p, bindings) for t, p in zip(template.args, program.args, strict=True)
        )
    if isinstance(template, Lam) and isinstance(program, Lam):
        return _match_into(template.body, program.body, bindings)
    return template == program


def rewrite_with(program: Program, name: str, template: Program) -> Program:
    """Fold every subtree that is an instance of ``template`` into a call to ``name``.

    Matches top-down: a subtree matching ``template`` collapses to ``Apply(name, args)``, and its
    bound arguments are themselves rewritten so *nested* occurrences fold too; a non-matching
    ``Apply`` is rebuilt with its children rewritten; leaves are returned unchanged. This is a
    strict superset of root-only matching — it reduces to the old behaviour when only the root
    matches — and it is what makes compression bite on heterogeneous corpora, where a shared
    idiom recurs *inside* larger, otherwise-distinct programs rather than as a whole program.

    Terminates because ``name`` never appears in ``template``, so a folded call can never re-match.
    """
    args = match(template, program)
    if args is not None:
        return Apply(name, tuple(rewrite_with(arg, name, template) for arg in args))
    if isinstance(program, Apply):
        return Apply(
            program.primitive, tuple(rewrite_with(arg, name, template) for arg in program.args)
        )
    return program
