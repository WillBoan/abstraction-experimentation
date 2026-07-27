"""Advisories (A): shape observations that are not defects.

Everything here is a WARN by construction. Each names something that is legitimate on purpose in
some ladders and accidental in others -- a pure telescope, a lambda-bearing template, a floor
broader than the spine -- so the check reports the fact and leaves the verdict to the author.
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.search.search_engine import BRANCHING_ENTRY
from arc_lab.program_search.substrate.program import Apply, If, PrimRef, Program


class NotAllTelescope(LadderCheck):
    """Does any rung recombine (fan-in > 1), or is the whole ladder a pure telescope?"""

    code = "not-all-telescope"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "At least one rung recombines rather than piping a single lower-rung call."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        yield self.finding(
            any(shape.fan_in > 1 for shape in ctx.rung_shapes),
            "every rung has fan-in 1 (a pure telescope)",
        )


class NoLambdaInTemplates(LadderCheck):
    """The depth checks are EXACT for a lambda-bearing template (they are stated in
    ``min_depth_limit``, which accounts for the descended body budget). What stays advisory is the
    thing no depth function can express: a higher-order call nested under a wrapper can have its
    lambda body filtered out by example propagation, making it unreachable at ANY budget (measured
    2026-07-22 -- see ``analysis/depth.py``)."""

    code = "no-lambda-in-templates"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "No rung template contains a lambda (whose reachability depth cannot certify)."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        if not any(shape.involves_lambda for shape in ctx.rung_shapes):
            return  # nothing to say: this advisory speaks only when a Lam is present
        yield self.finding(
            False,  # reached only when a template does carry a Lam
            "a rung template contains a Lam: depth claims hold, but a higher-order call that "
            "is not at the root of its solution may be unreachable at any depth_limit",
        )


class FloorFullyExercised(LadderCheck):
    """Every floor primitive should be exercised by something the ladder states.

    A warning, not an error: a floor is sometimes deliberately broader than the spine (al4 ships a
    realistic mask algebra). But an *accidental* dead primitive is not free -- it widens the round-0
    leaf set for every task, inflating the very vocabulary tax the batch is trying to attribute.
    """

    code = "floor-fully-exercised"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "Every floor primitive is used by some rung, demonstration, distractor or top."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        exercised = _exercised_primitives(
            [*ctx.unfolded_templates, *(sol for _, sol in ctx.unfolded_stated)]
        )
        idle = [p.name for p in ctx.spec.floor().primitives if p.name not in exercised]
        yield self.finding(
            not idle,
            f"floor primitives no rung, demonstration, distractor or top solution uses: {idle}",
        )


#: The budget at which carrying an unneeded primitive stops being cheap. Cost goes as
#: ``(primitives x constants)^depth`` (LADDER-PROCESS-2026-07-26 section 1), so an extra primitive
#: is a base term: at depth 2 a UNARY or BINARY one is a rounding error, at depth 3+ it compounds.
#: Calibration: ``dae9d2b5-halves-union`` carried ``overlay``/``map_color`` -- both needed only by
#: the top -- at two levels running depth 3, measuring 21,149,854 considered against 4 pruned.
DEPTH_WHERE_BREADTH_COMPOUNDS = 3

#: The argument count at which a carried primitive is expensive at ANY depth. A primitive taking
#: ``n`` pool-typed arguments contributes a degree-``n`` term in the pool size, so a ternary (or
#: variadic-to-ternary) one is quadratic in the grid pool within a SINGLE round -- the depth
#: exponent never enters. The 2026-07-25 design rule ("prefer unary/binary primitives over
#: ternary") stated for ``paint_through_mask``; ``overlay: (Color, Grid...) -> Grid`` at
#: ``max_arity`` 3 is the same shape.
#:
#: Calibration, and the reason this exists: ``dae9d2b5-split-recolor`` runs EVERY level at depth 2
#: and this check first read it clean -- while ``overlay``, needed only by the top, took 98.8% of a
#: 230,497-considered cell whose optimally-pruned cost is 4. Depth alone was a false negative on
#: the very ladder the check was built for.
ARITY_EXPENSIVE_AT_ANY_DEPTH = 3


class PrimitiveNecessity(LadderCheck):
    """Which floor primitive does each level's search have to carry, and at what budget?

    The floor is one library for the whole climb, so a primitive only the TOP needs is nonetheless
    in the pool at every level below it -- composed, and (through ``leaves._type_in_use``) minting
    its types' whole constant battery -- for every rung that never mentions it. That is invisible to
    every other check: the ladder is sound, every rung is affordable, and the bill lands on levels
    whose own programs are innocent.

    The map this prints is the middle step of the tractability triage (LADDER-PROCESS section 4):
    attribution names the expensive primitive, this names **which piece of the ladder necessitates
    it**, and the response is to restructure so that piece searches shallower -- or to drop the
    primitive. On ``dae9d2b5-halves-union`` it reads, statically and in about a second, exactly what
    cost hours to find by measurement: ``overlay`` and ``map_color`` needed at ``L_2`` (the top),
    carried from ``L_0`` at depth 3.

    Distinct from ``floor-fully-exercised``, which asks whether a primitive is used by the ladder at
    ALL. This one asks *when* -- a primitive can be exercised, necessary, and still carried three
    levels below the first search that needs it.

    **Two independent reasons a carry is not cheap**, one per side of the cost law: a deep carried
    level (the exponent) and a high-arity primitive (the base -- superlinear in the pool inside a
    single round, so depth never enters). The second was added after the first version read
    ``dae9d2b5-split-recolor`` clean at an all-depth-2 schedule while ``overlay`` took 98.8% of it.

    A warning, never an error, and it fires on about half the batch: carrying a primitive early is
    usually unavoidable, since the top has to be expressible over the floor and there is no
    per-level floor. It is a MAP, to be read against attribution when something is expensive --
    not a defect list.
    """

    code = "primitive-necessity"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "Floor primitives carried below the level that needs them, where the carry is costly."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        carried = carried_primitives(ctx)
        yield self.finding(
            not carried,
            "floor primitives carried below the level that first needs them, where the carry is "
            "not cheap: " + "; ".join(carried),
        )


def carried_primitives(ctx: CheckContext) -> tuple[str, ...]:
    """One ``"name: needed at L_j (who), carried from L_i -- reason"`` per flagged primitive.

    A primitive is CARRIED at every level strictly below the first whose search must compose it.
    Carrying is flagged when it is not cheap, which happens two ways -- and they are independent,
    because they sit on opposite sides of ``(primitives x constants)^depth``:

    - **the exponent** -- a carried level runs at :data:`DEPTH_WHERE_BREADTH_COMPOUNDS` or deeper,
      so the extra base term compounds;
    - **the base** -- the primitive takes :data:`ARITY_EXPENSIVE_AT_ANY_DEPTH` or more arguments
      (variadic counted at the budget's ``max_arity``), making it a degree-``n`` term in the pool
      inside a single round. That is expensive at depth 2 as readily as at depth 5.

    A primitive needed at ``L_0`` is never flagged (nothing is below it), and one no search
    composes at all is left to ``floor-fully-exercised``.
    """
    needed_at = _first_need_level(ctx)
    max_arity = ctx.spec.reference_config.budget.max_arity
    flagged: list[str] = []
    for primitive in ctx.spec.floor().primitives:
        need = needed_at.get(primitive.name)
        if need is None or need == 0:
            continue
        arity = max_arity if primitive.variadic_param is not None else len(primitive.param_types)
        deep = [
            level for level in range(need) if ctx.limit_at(level) >= DEPTH_WHERE_BREADTH_COMPOUNDS
        ]
        reasons = []
        if deep:
            reasons.append(f"depth {max(ctx.limit_at(level) for level in deep)}")
        if arity >= ARITY_EXPENSIVE_AT_ANY_DEPTH:
            reasons.append(f"arity {arity}, superlinear in the pool at any depth")
        if not reasons:
            continue
        flagged.append(
            f"{primitive.name}: needed at L_{need} ({_level_name(ctx, need)}), carried from "
            f"L_0 -- {'; '.join(reasons)}"
        )
    return tuple(flagged)


def _first_need_level(ctx: CheckContext) -> dict[str, int]:
    """Per primitive name, the LOWEST level whose search has to compose it.

    Read off the search-side programs, folded exactly as the search will see them: level ``j``
    looks for rung ``j+1``'s demonstration targets over ``L_j`` (so a lower rung it calls stays
    folded -- that call is a minted abstraction by then, not a composition), and ``L_k`` looks for
    the top's reference solutions. A primitive reachable only INSIDE an already-minted rung is
    therefore correctly not counted: the search never has to build it again.
    """
    first: dict[str, int] = {}
    for level, targets in enumerate(_search_targets_by_level(ctx)):
        for name in _exercised_primitives(list(targets)):
            first.setdefault(name, level)
    return first


def _search_targets_by_level(ctx: CheckContext) -> tuple[tuple[Program, ...], ...]:
    """The programs each level's search must find, ``L_0 .. L_k`` -- the same reading
    ``depth_schedule`` derives each level's budget from, so the two always agree on what a level is
    for. A draft rung with no demonstrations falls back to its template, as elsewhere."""
    levels = [
        tuple(target for _, target in ctx.demo_targets[rung.name]) or (rung.template,)
        for rung in ctx.rungs
    ]
    levels.append(tuple(ctx.spec.top.reference_solutions))
    return tuple(levels)


def _level_name(ctx: CheckContext, level: int) -> str:
    """What sits at ``level``: the rung whose demonstrations it searches for, or the top."""
    return "top" if level >= ctx.k else ctx.rungs[level].name


def _exercised_primitives(roots: list[Program]) -> set[str]:
    """Every primitive name the given programs use, branching included.

    Distinct-id traversal: shared subtrees of a deep unfold are visited once, so al14's millions of
    node occurrences cost a few hundred visits. An ``If`` credits the floor's ``if`` summoner --
    branching is summoned, never applied, so without this a conditional floor would read as dead
    vocabulary.
    """
    exercised: set[str] = set()
    visited: set[int] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, Apply):
            exercised.add(node.primitive)
        elif isinstance(node, PrimRef):
            exercised.add(node.name)  # used as a first-class function value
        elif isinstance(node, If):
            exercised.add(BRANCHING_ENTRY)
        stack.extend(node.children())
    return exercised
