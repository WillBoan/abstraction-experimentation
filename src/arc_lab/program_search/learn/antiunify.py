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

Two proposers implement :class:`AbstractionProposer`: :class:`AntiunifyPairs` generalises *whole
programs*; :class:`FrequentSubtree` mines recurring *proper subtrees* — the cross-member idiom
(`mirror_index`) whole-program antiunification can't surface (E7). They are complementary.

``If`` (the short-circuit branching node) is an ordinary 3-child constructor throughout:
antiunify pointwise, match pointwise, rewrite through, mine ``If``-rooted subtrees — so sleep
can invent *branching* abstractions with no special-casing.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from arc_lab.program_search.learn.telemetry import SleepCounters
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    If,
    Input,
    Lam,
    Param,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import GRID, Type, TypeCon


class _BoundVarEscapeError(Exception):
    """Antiunification would lift a bound ``$i`` out of its binder -- unsound; abort this pair."""


class AbstractionProposer(ABC):
    """Propose candidate closed templates mined from the solved programs.

    Proposers are frozen dataclasses: they sit on a ``LearnEngine`` inside the run
    identity, so their parameters must hash via the component serde.
    """

    @abstractmethod
    def propose(
        self,
        programs: list[Program],
        library: Library,
        *,
        counters: SleepCounters | None = None,
    ) -> list[Program]:
        """Candidate templates (closed, Param-holed), best-effort deduplicated.

        ``counters`` (if given) accumulates sleep-cost telemetry — antiunify-pair attempts — as a
        side effect; it never changes *what* is proposed."""


@dataclass(frozen=True, slots=True, kw_only=True)
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

    bound_var_safe: bool = False

    def propose(
        self,
        programs: list[Program],
        library: Library,
        *,
        counters: SleepCounters | None = None,
    ) -> list[Program]:
        candidates: dict[Program, None] = {}  # ordered set (dedup by structure)
        counts = Counter(programs)
        # A program that recurs verbatim is itself an abstraction once its input is lifted.
        for program, n in counts.items():
            if n >= 2:
                self._offer(_close_template(program), candidates)
        # Distinct programs generalise via pairwise antiunification (with variable-sharing).
        for a, b in itertools.combinations(counts, 2):
            if counters is not None:
                counters.antiunify_pair_count += 1
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


@dataclass(frozen=True, slots=True, kw_only=True)
class FrequentSubtree(AbstractionProposer):
    """Naive frequent-subtree mining: closed templates from recurring *proper subtrees*.

    Where :class:`AntiunifyPairs` generalises *whole programs* pairwise, this mines the shared
    *sub-idioms* that recur *inside* larger, otherwise-distinct programs — the cross-member
    coordinate idiom ``mirror_index = sub(sub(#0, #1), 1)`` that whole-program antiunification
    structurally cannot surface (the E7 finding). A focused, deterministic miner built on the same
    LGG helpers — *not* the DreamCoder-grade version-space / e-graph engine (that stays Stitch's
    job: adopt at scale, per ``MACHINERY-STRATEGY``'s "not yet").

    **Soundness — the mirror image of** ``AntiunifyPairs.bound_var_safe``. This mines only
    **Lam-free** proper subtrees, so every ``Var`` (``$i``) inside a mined subtree ``T`` is bound by
    a ``Lam`` *outside* ``T``. Holing a differing subterm that contains such a ``$i`` is then sound:
    the folded call sits in ``T``'s original place — still under that binder — so the ``$i`` is
    passed as an *argument*, not lifted out of its scope. (``AntiunifyPairs`` must *refuse* this
    because its abstraction is applied at the program root, outside the λ — the E6 break.) A
    candidate that would keep a *free* ``$i`` (a ``Var`` invariant across occurrences, so never
    holed) is dropped — minted, its ``$i`` would have no binder. ``min_frequency`` (default 2) keeps
    only genuinely recurring idioms, not incidental pairwise generalisations.

    **Limitation — the compression/reusability divergence (flagged).** Governed by greedy MDL over
    the *train corpus*, this naive miner offers the *largest* compressor, which here is a specialised
    ``COLOR`` read-body idiom (``read(#0, #1, sub(sub(width(#0), #2), 1))``) — sound, but dead weight
    to a coordinate search (uncomposable), so re-solve DL *worsens* and there is no speedup. The
    reusable factor (``mirror_index``) is a smaller subterm the read-bodies *share*, but it compresses
    less, so greedy skips it; and once the read-bodies absorb it into their *definitions*, corpus-only
    iteration can't recover it (that needs library refactoring). The scoped subclasses below are
    **stopgaps**; the full map of approaches lives in ``MACHINERY.md``.
    """

    min_frequency: int = 2

    def propose(
        self,
        programs: list[Program],
        library: Library,
        *,
        counters: SleepCounters | None = None,
    ) -> list[Program]:
        # Lam-free proper subtrees (each program's own root excluded) that carry real structure.
        # ``If``-rooted subtrees are minable like ``Apply``-rooted ones (branching idioms recur too).
        subtrees: list[Program] = [
            node
            for program in programs
            for node in list(program.walk())[1:]
            if isinstance(node, (Apply, If)) and not _contains_lam(node)
        ]
        templates: dict[Program, None] = {}  # ordered set (dedup by structure)
        counts = Counter(subtrees)
        # A subtree that recurs verbatim is a template once its Input is lifted.
        for subtree, n in counts.items():
            if n >= 2:
                self._offer(_close_template(subtree), templates, subtrees, library)
        # Distinct subtrees generalise via antiunification — differing leaves (Vars too) become holes.
        for a, b in itertools.combinations(counts, 2):
            if counters is not None:
                counters.antiunify_pair_count += 1
            generalised = _antiunify(a, b, library, {}, itertools.count())
            self._offer(_close_template(generalised), templates, subtrees, library)
        return list(templates)

    def _offer(
        self,
        template: Program,
        templates: dict[Program, None],
        subtrees: list[Program],
        library: Library,
    ) -> None:
        if not _is_useful(template):
            return
        if _contains_var(template):
            return  # a free bound-var would escape its binder once minted — unsound
        if not self._accept(template, library):
            return  # a scoping subclass rejected this candidate's type/signature
        if sum(match(template, s) is not None for s in subtrees) < self.min_frequency:
            return  # not a *frequent* idiom, just an incidental generalisation
        templates.setdefault(template, None)

    def _accept(self, template: Program, library: Library) -> bool:
        """Whether to keep a useful, closed, frequent candidate. Base: keep all — the divergence."""
        return True


@dataclass(frozen=True, slots=True, kw_only=True)
class TypeScopedFrequentSubtree(FrequentSubtree):
    """Type-scoped invention with a **declared** result type — a STOPGAP.

    Keeps only candidates whose result type equals ``result_type`` (e.g. ``INT`` for the coordinate
    grammar — a nullary ``TypeCon``), so the reusable idiom (``mirror_index``) survives instead of the
    ``COLOR`` read-bodies.

    **Flags.** The type is *hand-declared* — a proxy that presumes you already know the answer
    ("cheating"). And it is *anti-open-ended*: the proposer can only ever invent abstractions of this
    one type, foreclosing new-type / layered vocabulary growth. **Superseded by**
    :class:`SearchScopedFrequentSubtree`, which derives the constraint from the search (not declared)
    and filters the full signature (not just the result type). The open-ended fix is library
    refactoring — see ``MACHINERY.md``.
    """

    result_type: TypeCon

    def _accept(self, template: Program, library: Library) -> bool:
        return template.result_type(library) == self.result_type


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchScopedFrequentSubtree(FrequentSubtree):
    """Signature-scoped invention with the composable signature **derived from the search** — STOPGAP.

    Keeps only candidates whose *closed signature* the consuming search can actually reuse: pass the
    search's own composition rule.

    - Non-cheating (nothing is hand-declared)
    - Precise (filters the full ``(param_types, return_type)`` signature, so it also drops
      ``(GRID, INT) -> INT`` candidates a bare result-type filter would admit).

    **Flag — still anti-open-ended.** It can only invent what the current search *already* composes,
    so it can't grow non-composable / higher-level / new-type vocabulary (the read-body idioms, ``GRID``
    members, learned intermediate types). The general, open-ended fix is **library refactoring**
    (compress the *library*, not just the corpus) — see ``MACHINERY.md``; adopt Stitch at scale.

    Note: ``composes`` is a callable, so this proposer does not serialise via the component
    serde — it is a programmatic/experimental scoping tool, not a preset ingredient.
    """

    composes: Callable[[tuple[Type, ...], Type], bool]

    def _accept(self, template: Program, library: Library) -> bool:
        param_types, return_type = _template_signature(template, library)
        return self.composes(param_types, return_type)


def _contains_var(program: Program) -> bool:
    """Whether a subterm references a lambda-bound variable (``$i``) — i.e. is not closed."""
    return any(isinstance(node, Var) for node in program.walk())


def _contains_lam(program: Program) -> bool:
    """Whether a subtree contains a lambda binder — i.e. binds its own ``$i`` internally."""
    return any(isinstance(node, Lam) for node in program.walk())


def _template_signature(template: Program, library: Library) -> tuple[tuple[Type, ...], Type]:
    """The closed template's ``(param_types, return_type)`` — its signature as a would-be abstraction."""
    by_index: dict[int, Type] = {}
    for node in template.walk():
        if isinstance(node, Param):
            by_index[node.index] = node.value_type
    param_types = tuple(by_index[i] for i in range(len(by_index)))
    return param_types, template.result_type(library)


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
    if isinstance(p, If) and isinstance(q, If):  # an ordinary 3-child constructor
        return If(
            cond=_antiunify(p.cond, q.cond, library, memo, counter, bound_var_safe),
            then=_antiunify(p.then, q.then, library, memo, counter, bound_var_safe),
            orelse=_antiunify(p.orelse, q.orelse, library, memo, counter, bound_var_safe),
        )
    if (
        isinstance(p, Lam) and isinstance(q, Lam) and p.param_type == q.param_type
    ):  # generalise under a same-typed binder; scope is shared
        return Lam(
            param_type=p.param_type,
            body=_antiunify(p.body, q.body, library, memo, counter, bound_var_safe),
        )
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
            return Param(index_of.setdefault(("input",), len(index_of)), GRID)
        if isinstance(node, Param):
            return Param(index_of.setdefault(("param", node.index), len(index_of)), node.value_type)
        if isinstance(node, Apply):
            return Apply(node.primitive, tuple(rebuild(arg) for arg in node.args))
        if isinstance(node, If):  # descend all three children
            return If(cond=rebuild(node.cond), then=rebuild(node.then), orelse=rebuild(node.orelse))
        if isinstance(node, Lam):  # descend so an Input inside a lambda body is lifted too
            return Lam(param_type=node.param_type, body=rebuild(node.body))
        if isinstance(node, AppFn):  # descend the higher-order application (head + args)
            return AppFn(rebuild(node.fn), tuple(rebuild(arg) for arg in node.args))
        return node  # Const / Var / PrimRef: an invariant leaf, kept concrete

    return rebuild(program)


def _is_useful(template: Program) -> bool:
    """A useful template has real structure (an application or a branch) and at least one hole.

    Real structure is a first-order :class:`Apply`, a higher-order :class:`AppFn` (a
    ``twice``-style abstraction is all ``AppFn`` and no ``Apply``, but is no less real), or an
    :class:`If` (a branching idiom is a construction in its own right).
    """
    nodes = list(template.walk())
    return any(isinstance(n, (Apply, AppFn, If)) for n in nodes) and any(
        isinstance(n, Param) for n in nodes
    )


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
    if isinstance(template, If) and isinstance(program, If):
        return (
            _match_into(template.cond, program.cond, bindings)
            and _match_into(template.then, program.then, bindings)
            and _match_into(template.orelse, program.orelse, bindings)
        )
    if isinstance(template, Lam) and isinstance(program, Lam):
        return template.param_type == program.param_type and _match_into(
            template.body, program.body, bindings
        )
    return template == program


def rewrite_with(program: Program, name: str, template: Program) -> Program:
    """Fold every subtree that is an instance of ``template`` into a call to ``name``.

    Matches top-down: a subtree matching ``template`` collapses to ``Apply(name, args)``, and its
    bound arguments are themselves rewritten so *nested* occurrences fold too; a non-matching
    ``Apply`` is rebuilt with its children rewritten, an ``If`` with all three children rewritten,
    and a ``Lam`` with its **body** rewritten (so an idiom folds even *inside* a coordinate lambda —
    the mirror_index case); leaves are returned unchanged. This is a strict superset of root-only
    matching — it reduces to the old behaviour when only the root matches — and it is what makes
    compression bite on heterogeneous corpora, where a shared idiom recurs *inside* larger,
    otherwise-distinct programs.

    Terminates because ``name`` never appears in ``template``, so a folded call can never re-match.
    """
    args = match(template, program)
    if args is not None:
        return Apply(name, tuple(rewrite_with(arg, name, template) for arg in args))
    if isinstance(program, Apply):
        return Apply(
            program.primitive, tuple(rewrite_with(arg, name, template) for arg in program.args)
        )
    if isinstance(program, If):
        return If(
            cond=rewrite_with(program.cond, name, template),
            then=rewrite_with(program.then, name, template),
            orelse=rewrite_with(program.orelse, name, template),
        )
    if isinstance(program, Lam):  # descend into the lambda body — an idiom can recur under a binder
        return Lam(param_type=program.param_type, body=rewrite_with(program.body, name, template))
    return program
