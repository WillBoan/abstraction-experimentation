"""Bounded equational rewriting: normal forms and shallow-equivalent detection.

The rewrite lint's engine. Two pieces, one theory (``analysis/equations.py``):

- :func:`normal_form` — directed, terminating normalization of a first-order floor term
  (leftmost-innermost over the curated reductions, interleaved with D4-chain canonicalization).
  The result is a COMPARISON KEY, not a runnable program: the interchange law's shape
  side-condition means two terms with equal normal forms are only *candidates* for equality,
  which is why every witness must be behaviorally confirmed by the caller.
- :func:`shallow_equivalent` — bounded typed enumeration of candidate terms over a *skip
  library* (floor + the rungs strictly below the skipped one), each unfolded to the floor and
  normalized; a candidate whose normal form equals the target's is a witness that the target is
  reachable at that depth despite the depth sandwich. Refolding rung definitions is realized by
  the candidates CALLING the rungs, then being unfolded for comparison — no fold-direction
  rewriting needed.

Deliberate incompleteness (all silent-pass — a ``None``/no-witness answer proves nothing):
no associativity law; candidate leaves are only the target's own ``Param``/``Input`` nodes
(no constants); variadic and polymorphic primitives are skipped as candidate heads; ``Lam``/
``Var``/``AppFn``-bearing terms are not normalized; every cap (``RewriteLimits``) returns the
no-witness answer. The caps are test-driven: the al3/al7 batch locks fail if they are too small.

Determinism: iteration follows library order and insertion order everywhere; no hashing of
task-derived sets into results.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.analysis.equations import (
    BASE_EQUATIONS,
    D4_NAMES,
    Equation,
    canonical_d4_word,
    d4_compose,
)
from arc_lab.program_search.learn.antiunify import match
from arc_lab.program_search.search.search_engine import BRANCHING_ENTRY
from arc_lab.program_search.substrate.abstraction import (
    rebuild,
    substitute_params,
    unfold_program,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    Const,
    Input,
    Lam,
    Param,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import GRID, ArrowType, Type, TypeCon, TypeVar


@dataclass(frozen=True, slots=True)
class RewriteLimits:
    """The engine's hard caps. A cap hit is a silent pass, never an error."""

    max_terms: int = 4000  # candidate pool cap (distinct normal forms)
    max_nodes: int = 5000  # unfolded / normal-form size cap (node occurrences)
    max_steps: int = 20_000  # total rewrite steps per normalization budget


_DEFAULT_LIMITS = RewriteLimits()


@dataclass(frozen=True, slots=True)
class ShallowWitness:
    """A term over the skip library, equal (up to confirmation) to the target, at this depth."""

    term: Program
    depth: int


class _CapHitError(Exception):
    pass


def normal_form(program: Program, floor: Library, limits: RewriteLimits) -> Program | None:
    """The program's normal form under the active reductions, or ``None`` on a cap or on
    ``Lam``/``Var``/``AppFn`` content (first-order terms only; ``Param``/``Input`` are opaque
    leaves)."""
    if _size_capped(program, limits.max_nodes) is None:
        return None
    equations = _active_equations(floor)
    d4_active = any(name in floor for name in D4_NAMES)
    steps = [limits.max_steps]
    try:
        result = _normalize(program, equations, d4_active, steps)
    except (_CapHitError, _FirstOrderOnlyError):
        return None
    if _size_capped(result, limits.max_nodes) is None:
        return None
    return result


def shallow_equivalent(
    target: Program,
    library: Library,
    floor: Library,
    depth_limit: int,
    limits: RewriteLimits = _DEFAULT_LIMITS,
) -> ShallowWitness | None:
    """A term over ``library`` within ``depth_limit`` whose floor normal form equals the
    target's, or ``None`` (not found OR capped — a silent pass either way).

    ``target`` must be FULLY UNFOLDED to the floor by the caller: its original statement may
    reference rungs the skip ``library`` deliberately lacks, so only the caller (holding the
    full oracle library) can expand it. Its leaves — the distinct ``Param``s and ``Input`` it
    mentions — are the candidate leaves, so a witness computes the same function of the same
    holes.
    """
    target_nf = normal_form(target, floor, limits)
    if target_nf is None:
        return None
    target_size = _size_capped(target_nf, limits.max_nodes)
    if target_size is None:
        return None

    leaves = _target_leaves(target)
    if not leaves:
        return None
    pool: dict[Type, list[tuple[Program, int]]] = {}  # per type: (term, depth), insertion order
    seen: dict[Program, int] = {}  # normal form -> depth of first (minimal-depth) carrier
    total = 0
    for leaf, leaf_type in leaves:
        leaf_nf = normal_form(leaf, floor, limits)
        if leaf_nf is None:
            continue
        if leaf_nf == target_nf:
            return ShallowWitness(term=leaf, depth=0)
        if leaf_nf not in seen:
            seen[leaf_nf] = 0
            pool.setdefault(leaf_type, []).append((leaf, 0))
            total += 1

    heads = [
        primitive
        for primitive in library.primitives
        if primitive.name != BRANCHING_ENTRY
        and not primitive.is_variadic
        and not _polymorphic(primitive.param_types, primitive.return_type)
    ]
    for depth in range(1, depth_limit + 1):
        new_entries: list[tuple[Type, Program, Program]] = []  # (type, term, normal form)
        for primitive in heads:
            for args in _argument_tuples(primitive.param_types, pool, depth - 1):
                candidate = Apply(primitive.name, args)
                candidate_nf = normal_form(unfold_program(candidate, library), floor, limits)
                if candidate_nf is None or candidate_nf in seen:
                    continue
                candidate_size = _size_capped(candidate_nf, limits.max_nodes)
                if candidate_size is None or candidate_size > target_size:
                    continue  # size-monotone floors: an oversized normal form can never shrink back
                if candidate_nf == target_nf:
                    return ShallowWitness(term=candidate, depth=depth)
                seen[candidate_nf] = depth
                new_entries.append((primitive.return_type, candidate, candidate_nf))
                total += 1
                if total >= limits.max_terms:
                    return None  # capped: a silent pass
        for return_type, term, _ in new_entries:
            pool.setdefault(return_type, []).append((term, depth))
    return None


# -- normalization ------------------------------------------------------------------


class _FirstOrderOnlyError(Exception):
    pass


def _normalize(
    node: Program, equations: tuple[Equation, ...], d4_active: bool, steps: list[int]
) -> Program:
    if isinstance(node, Lam | Var | AppFn):
        raise _FirstOrderOnlyError
    children = node.children()
    if children:
        normalized = tuple(_normalize(child, equations, d4_active, steps) for child in children)
        node = rebuild(node, normalized)
    while True:
        rewritten = _rewrite_root(node, equations, d4_active)
        if rewritten is None:
            return node
        steps[0] -= 1
        if steps[0] <= 0:
            raise _CapHitError
        # A root rewrite splices already-normalized pieces under new constructors, which can
        # expose fresh redexes below (a flip pushed through a concat) — re-normalize the result.
        node = _normalize_children_then_root(rewritten, equations, d4_active, steps)


def _normalize_children_then_root(
    node: Program, equations: tuple[Equation, ...], d4_active: bool, steps: list[int]
) -> Program:
    children = node.children()
    if not children:
        return node
    normalized = tuple(_normalize(child, equations, d4_active, steps) for child in children)
    return rebuild(node, normalized)


def _rewrite_root(
    node: Program, equations: tuple[Equation, ...], d4_active: bool
) -> Program | None:
    if d4_active and isinstance(node, Apply) and node.primitive in D4_NAMES:
        inner = node.args[0] if len(node.args) == 1 else None
        if isinstance(inner, Apply) and inner.primitive in D4_NAMES and len(inner.args) == 1:
            word = canonical_d4_word(d4_compose(node.primitive, inner.primitive))
            operand = inner.args[0]
            for name in reversed(word):
                operand = Apply(name, (operand,))
            return operand
        if node.primitive == "identity":
            return inner
    for equation in equations:
        bindings = match(equation.lhs, node)
        if bindings is not None:
            return substitute_params(equation.rhs, bindings)
    return None


def _active_equations(floor: Library) -> tuple[Equation, ...]:
    """The curated laws whose every primitive the floor actually carries."""
    return tuple(
        equation
        for equation in BASE_EQUATIONS
        if all(
            name in floor
            for program in (equation.lhs, equation.rhs)
            for name in _primitive_names(program)
        )
    )


def _primitive_names(program: Program) -> set[str]:
    return {node.primitive for node in program.walk() if isinstance(node, Apply)}


# -- candidate enumeration helpers --------------------------------------------------


def _target_leaves(target: Program) -> list[tuple[Program, Type]]:
    """The target's distinct ``Param``/``Input``/``Const`` leaves, first-seen order.

    ``Const`` counts for the same reason the others do: a witness has to compute the same function
    of the same holes, and a literal the target already names is available to any search that
    enumerates constants at all. Leaving it out silently un-convicts every target stated with its
    parameters BOUND -- a rung template carries ``#1`` where its demonstration carries ``3``, so
    the equational skip path is identical but only the template form can be re-expressed.
    """
    leaves: list[tuple[Program, Type]] = []
    seen: set[Program] = set()
    for node in target.walk():
        if isinstance(node, Param) and node not in seen:
            seen.add(node)
            leaves.append((node, node.value_type))
        elif isinstance(node, Input) and node not in seen:
            seen.add(node)
            leaves.append((node, GRID))
        elif isinstance(node, Const) and node not in seen:
            seen.add(node)
            leaves.append((node, node.value_type))
    return leaves


def _argument_tuples(
    param_types: tuple[Type, ...],
    pool: dict[Type, list[tuple[Program, int]]],
    frontier_depth: int,
) -> list[tuple[Program, ...]]:
    """Cartesian argument tuples from the pool where the deepest argument is exactly
    ``frontier_depth`` — the composed term's depth is then ``frontier_depth + 1``, so each
    candidate is enumerated at its minimal depth exactly once."""
    per_slot: list[list[tuple[Program, int]]] = []
    for param_type in param_types:
        entries = pool.get(param_type, [])
        if not entries:
            return []
        per_slot.append(entries)
    tuples: list[tuple[Program, ...]] = []

    def fill(index: int, chosen: tuple[Program, ...], deepest: int) -> None:
        if index == len(per_slot):
            if deepest == frontier_depth:
                tuples.append(chosen)
            return
        for term, depth in per_slot[index]:
            if depth > frontier_depth:
                continue
            fill(index + 1, (*chosen, term), max(deepest, depth))

    fill(0, (), 0)
    return tuples


def _polymorphic(param_types: tuple[Type, ...], return_type: Type) -> bool:
    def has_var(t: Type) -> bool:
        if isinstance(t, TypeVar):
            return True
        if isinstance(t, ArrowType):
            return has_var(t.result) or any(has_var(p) for p in t.params)
        if isinstance(t, TypeCon):
            return any(has_var(a) for a in t.args)
        return False

    return any(has_var(t) for t in (*param_types, return_type))


def _size_capped(program: Program, cap: int) -> int | None:
    """Node-occurrence count, or ``None`` once it exceeds ``cap`` (early abort — safe on the
    multi-megabyte unfolds shared subtrees produce)."""
    count = 0
    stack = [program]
    while stack:
        node = stack.pop()
        count += 1
        if count > cap:
            return None
        stack.extend(node.children())
    return count
