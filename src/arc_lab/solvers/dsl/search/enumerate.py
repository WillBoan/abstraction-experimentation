"""Typed bottom-up enumeration of composed programs.

This is the general program-synthesis engine the whole DSL direction is built
toward. It grows programs from the leaves up, one composition round at a time:

* **Types prune the space.** A primitive's arguments are drawn only from pools of
    programs whose types unify with the parameter slot, so ill-typed compositions are
    never formed. This is what keeps an atomic vocabulary tractable even once the
    floor includes first-order polymorphism (``eq`` / ``if``).
* **Observational equivalence collapses it further.** Two programs that produce
  identical results on every training input are interchangeable; we keep only the
  *smallest* representative of each behaviour (a later, smaller-node-count equivalent
  replaces an earlier one). The number of distinct *behaviours* is far smaller than
  the number of syntactic programs, and this dedup is the same signal a future
  library-learning step will mine for reusable abstractions.

Constant leaves (colors, integers) are drawn from the task itself, so the search
never enumerates values that could not possibly appear. Variadic primitives (the
combinators) are left to their own bespoke searches; enumeration composes the
fixed-arity, atomic vocabulary.
"""

from __future__ import annotations

import logging
from typing import TypeAlias

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.search.cost import Cost
from arc_lab.solvers.dsl.search.type_directed import (
    TypedProgram,
    candidate_applications,
    signature_matches_type,
)
from arc_lab.solvers.dsl.substrate.library import Closure, Library, Primitive, Value
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, PrimRef, Program, Var
from arc_lab.solvers.dsl.substrate.types import (
    BOOL,
    COLOR,
    GRID,
    INT,
    ArrowType,
    Type,
)

logger = logging.getLogger(__name__)

Signature: TypeAlias = tuple[Value, ...]


def _format_value(value: Value) -> str:
    """Compact rendering of a single behaviour value (grids never materialise)."""
    if isinstance(value, Grid):
        return f"grid{value.height}x{value.width}#{hash(value) & 0xFFFFFF:06x}"
    return str(value)


def _format_signature(sig: Signature) -> str:
    """Compact rendering of a program's behaviour signature across training inputs."""
    return "(" + ", ".join(_format_value(v) for v in sig) + ")"


#: Function synthesis: a dummy grid for evaluating Input-free lambda bodies, small per-type batteries
#: for probing a candidate function's behaviour, and how deep to compose synthesized function bodies.
_SYNTH_GRID: Grid = Grid.from_list([[0]])
#: The grid battery must vary in *height, width, and cell content independently*, so that behaviorally
#: distinct perceivers stay distinct: a battery where every grid shares a height makes ``height``
#: indistinguishable from a constant, silently collapsing them in the behavioral dedup. Heights here are
#: {2, 3, 1} and widths {2, 3, 4} — pairwise distinct, so width/height/transpose/const all separate.
_SYNTH_GRIDS: tuple[Grid, ...] = (
    Grid.from_list([[1, 2], [3, 4]]),  # 2x2
    Grid.from_list([[5, 6, 7], [8, 9, 0]]),  # 2x3 (varies width)
    Grid.from_list([[1], [2], [3]]),  # 3x1 (varies height and width)
    Grid.from_list([[2, 0, 3, 1]]),  # 1x4 (a distinct height and width again)
)
_FUNCTION_SYNTHESIS_DEPTH = 3


def _apply_unary(fn: Value, arg: Value) -> Value:
    """Apply a unary function value (a :class:`Primitive` from a PrimRef, a :class:`Closure` from a Lam)."""
    if isinstance(fn, Primitive):
        return fn.impl(arg)
    if isinstance(fn, Closure):
        return fn(arg)
    raise TypeError(f"not a unary function value: {type(fn).__name__}")


class Enumerate(Search):
    """Bottom-up, type-directed enumeration up to a bounded composition depth."""

    def __init__(
        self,
        *,
        max_depth: int = 2,
        max_pool: int = 600,
        max_grid_args: int = 16,
        coord_ints: bool = False,
        higher_order: bool = False,
        synthesize_functions: bool = False,
    ) -> None:
        # Enumerate enforces consistency implicitly (a program is kept only if its
        # behaviour signature equals the training outputs), so it does not take or
        # apply Constraint objects; the default keeps the base contract satisfied.
        super().__init__()
        self.max_depth = max_depth
        self.max_pool = max_pool
        # Cap on how many grid programs feed a composition round. Distinct grid
        # *behaviours* are few; this bounds the map_color(grid, color, color)
        # blow-up (grids x colors^2) without losing the simple, early programs.
        self.max_grid_args = max_grid_args
        # Mine coordinate INT leaves (0..max grid dimension) for cell-level primitives
        # (read/set_cell). Off by default so the existing INT-consuming vocabularies
        # (scale) are unaffected — keeping the dsl-synth lock intact.
        self.coord_ints = coord_ints
        # Higher-order composition: fill a function-typed (arrow) argument from a pool of library
        # primitives referenced as first-class values (PrimRefs), pruned by arrow-type unification.
        # Off by default, so first-order libraries (no arrow params) enumerate byte-identically.
        self.higher_order = higher_order
        # Additionally synthesize *new* function values — Lam bodies composed bottom-up from the
        # library — for the function pool, deduped by function-behavioral signature (so a composite
        # like the rot180-function, absent as a primitive, becomes fillable). Requires higher_order.
        self.synthesize_functions = synthesize_functions

    def find(self, task: Task, library: Library) -> SearchResult:
        debug = logger.isEnabledFor(logging.DEBUG)
        inputs = [ex.input for ex in task.train]
        outputs = [ex.output for ex in task.train]
        if any(out is None for out in outputs):
            stats = SearchStats(strategy="Enumerate", considered=0, returned=0)
            logger.info(stats.summary())
            return SearchResult(programs=(), stats=stats)
        target: Signature = tuple(out for out in outputs if out is not None)

        # pools[type][behaviour-signature] = smallest program with that behaviour.
        pools: dict[Type, dict[Signature, Program]] = {}

        # Per-search tallies for the INFO summary (cheap; maintained unconditionally).
        counts = {"considered": 0, "kept": 0, "dup": 0, "err": 0, "mistyped": 0}

        # TODO(trace-volume, optional): the four `logger.debug` sites below are the
        # firehose (~600 lines/task today, and it grows with max_depth and library
        # size). If it becomes unwieldy, split them onto child loggers
        # (`{__name__}.accept` / `.reject`) so you can keep accepts and mute the
        # dedup stream independently, e.g. set `...enumerate.reject` to WARNING while
        # the parent stays at DEBUG. Not worth the indirection until the volume
        # actually gets in the way — the `if debug:` guard already makes it free when off.
        def consider(program: Program, expected: Type) -> None:
            counts["considered"] += 1
            try:
                sig: Signature = tuple(program.evaluate(inp, library) for inp in inputs)
            except Exception as exc:
                counts["err"] += 1
                if debug:
                    logger.debug("enumerate reject (eval error) %s: %s", program, exc)
                return
            if not signature_matches_type(sig, expected):
                counts["mistyped"] += 1
                if debug:
                    logger.debug("enumerate reject (mistyped as %s) %s", expected, program)
                return
            bucket = pools.setdefault(expected, {})
            existing = bucket.get(sig)
            if existing is None:
                counts["kept"] += 1
                if debug:
                    logger.debug(
                        "enumerate accept [%s] %s sig=%s",
                        expected,
                        program,
                        _format_signature(sig),
                    )
                bucket[sig] = program
            elif program.size() < existing.size():
                # Same behaviour, fewer nodes: keep the *smallest* witness per behaviour, not
                # merely the first considered. Discovery order tracks size loosely (later rounds
                # are deeper) but not exactly — within a round a multi-arity primitive can form a
                # larger equivalent before a smaller one, and library order decides which lands
                # first. Keeping the smaller one hands the sleep step minimal programs, removing
                # the latent bloat root cause. The *set* of reachable behaviours is unchanged —
                # only the representative shrinks — so which tasks solve is invariant.
                counts["dup"] += 1
                if debug:
                    logger.debug("enumerate replace (smaller than %s) %s", existing, program)
                bucket[sig] = program
            else:
                counts["dup"] += 1
                if debug:
                    logger.debug("enumerate reject (dup of %s) %s", existing, program)

        # Leaves: the input grid, and task-relevant color/int constants.
        consider(Input(), GRID)
        colors, ints = _leaf_constants(task, coord_ints=self.coord_ints)
        for color in colors:
            consider(Const(color, COLOR), COLOR)
        for value in ints:
            consider(Const(value, INT), INT)
        for value in (False, True):
            consider(Const(value, BOOL), BOOL)

        fixed = [prim for prim in library.primitives if not prim.is_variadic]
        function_pool = self._function_pool(library) if self.higher_order else []

        # TODO(checkpointing, deferred): the run artifact checkpoints at *task* grain
        # (streaming trace + resume, see analysis/runner.py), which is the right grain
        # while a single task's search is fast. If a lower primitive floor ever makes one
        # task's enumeration take minutes, add *intra-task* checkpointing here — serialise
        # the frozen pools between rounds so an interrupted search resumes mid-task. Not
        # worth the coupling to engine internals until that cost is actually observed.
        for _ in range(self.max_depth):
            if target in pools.get(GRID, {}):
                break
            # Freeze the current pools so this round composes only prior programs.
            # The grid frontier is capped (the overridable F1 frontier policy) to bound the count.
            frozen = {vtype: list(bucket.values()) for vtype, bucket in pools.items()}
            frozen[GRID] = self._grid_frontier(frozen.get(GRID, []), task, library)
            value_candidates: list[TypedProgram] = [
                (program, result_type)
                for result_type, programs in frozen.items()
                for program in programs
            ]
            for prim in fixed:
                for combo, result_type in candidate_applications(
                    prim,
                    value_candidates=value_candidates,
                    function_candidates=function_pool,
                ):
                    consider(Apply(prim.name, combo), result_type)
            if sum(len(b) for b in pools.values()) > self.max_pool:
                break

        found = pools.get(GRID, {}).get(target)
        programs: tuple[Program, ...] = (found,) if found is not None else ()
        stats = SearchStats(
            strategy="Enumerate",
            considered=counts["considered"],
            returned=len(programs),
            extra={
                "kept": counts["kept"],
                "deduped": counts["dup"],
                "errored": counts["err"],
                "mistyped": counts["mistyped"],
                "pool_grid": len(pools.get(GRID, {})),
                "pool_color": len(pools.get(COLOR, {})),
                "pool_int": len(pools.get(INT, {})),
                "pool_bool": len(pools.get(BOOL, {})),
            },
        )
        logger.info(stats.summary())
        return SearchResult(programs=programs, stats=stats)

    def _grid_frontier(
        self, candidates: list[Program], task: Task, library: Library
    ) -> list[Program]:
        """The grid programs that feed the next composition round — the frontier policy.

        The default is a blind insertion-order cut (``max_grid_args``): it keeps the
        earliest-found — and, post keep-smallest, smallest — grids. ``task``/``library`` are
        unused here but are the inputs a *cost*-ranked policy needs, so a subclass
        (:class:`BeamSearch`) can override this one seam without touching the search loop.
        """
        return candidates[: self.max_grid_args]

    def _function_pool(self, library: Library) -> list[tuple[Program, ArrowType]]:
        """Function *values* for filling function-typed holes (enabled by ``higher_order``): every
        library primitive as a first-class :class:`PrimRef`, plus — when ``synthesize_functions`` —
        *new* function values composed as :class:`Lam` bodies, all deduped by a function-behavioral
        signature so a composite (e.g. the rot180-function, absent as a primitive) becomes fillable
        while a redundant ``lam(rot90($0))`` collapses into ``&rot90``.
        """
        pool: list[tuple[Program, ArrowType]] = [
            (PrimRef(prim.name), ArrowType(tuple(prim.param_types), prim.return_type))
            for prim in library.primitives
            if not prim.is_variadic
        ]
        if self.synthesize_functions:
            pool += self._synthesized_functions(library)
        return self._dedup_functions(pool, library)

    def _synthesized_functions(self, library: Library) -> list[tuple[Program, ArrowType]]:
        """``Lam`` function values composed bottom-up, one per unary arrow a library primitive wants."""
        result: list[tuple[Program, ArrowType]] = []
        for domain, codomain in self._needed_arrows(library):
            for body in self._lam_bodies(domain, codomain, library):
                result.append((Lam(body), ArrowType((domain,), codomain)))
        return result

    def _needed_arrows(self, library: Library) -> list[tuple[Type, Type]]:
        """The distinct unary ``(domain, codomain)`` arrows that appear as a primitive's parameter.

        Returned in library order via an insertion-ordered dict, not a ``set`` — a ``set`` of
        ``BaseType``-bearing tuples iterates in ``PYTHONHASHSEED``-dependent order, which would make the
        synthesized function pool's order vary run-to-run (the substrate is deterministic by design).
        """
        arrows: dict[tuple[Type, Type], None] = {}
        for prim in library.primitives:
            for param in prim.param_types:
                if isinstance(param, ArrowType) and len(param.params) == 1:
                    arrows[(param.params[0], param.result)] = None
        return list(arrows)

    def _lam_bodies(self, domain: Type, codomain: Type, library: Library) -> list[Program]:
        """Bodies of type ``codomain`` over ``{Var(0, domain)}`` + first-order primitives (bottom-up,
        deduped by the body's behaviour as the bound var ranges over a battery)."""
        battery = self._domain_battery(domain)
        if not battery:
            return []
        pools: dict[Type, dict[tuple[object, ...], Program]] = {}

        def keep(body: Program, body_type: Type) -> None:
            sig = self._body_sig(body, battery, library)
            if sig is None:
                return
            bucket = pools.setdefault(body_type, {})
            if sig not in bucket or body.size() < bucket[sig].size():
                bucket[sig] = body

        keep(Var(0, domain), domain)
        fixed = [
            prim
            for prim in library.primitives
            if not prim.is_variadic and all(not isinstance(t, ArrowType) for t in prim.param_types)
        ]
        for _ in range(_FUNCTION_SYNTHESIS_DEPTH):
            frozen = {t: list(b.values()) for t, b in pools.items()}
            value_candidates: list[TypedProgram] = [
                (program, result_type)
                for result_type, programs in frozen.items()
                for program in programs
            ]
            for prim in fixed:
                for combo, result_type in candidate_applications(
                    prim,
                    value_candidates=value_candidates,
                ):
                    keep(Apply(prim.name, combo), result_type)
            # Bound the synthesis the same way the main loop bounds enumeration: an arithmetic-rich
            # library (mul growing integers) could otherwise balloon the depth-N product unchecked.
            if sum(len(b) for b in pools.values()) > self.max_pool:
                break
        return list(pools.get(codomain, {}).values())

    def _dedup_functions(
        self, pool: list[tuple[Program, ArrowType]], library: Library
    ) -> list[tuple[Program, ArrowType]]:
        """Collapse behaviorally-identical unary candidates, keeping the *smallest* witness per behavior.

        Two subtleties that keep this from silently dropping a needed candidate:

        * A ``None`` signature means "couldn't probe" (an unprobeable domain, or the candidate errored on
          the battery) — **not** "same behavior". Such candidates, and every non-unary one, are kept
          unconditionally; only genuinely-comparable candidates are deduped.
        * Ties keep the smaller-node-count witness (a ``PrimRef`` beats an equivalent ``Lam``), by an
          explicit size comparison rather than relying on enumeration order.
        """
        result: list[tuple[Program, ArrowType]] = []
        best: dict[tuple[ArrowType, tuple[object, ...]], int] = {}  # behavior -> index in `result`
        for ref, arrow in pool:
            sig = (
                self._function_sig(ref, arrow.params[0], library)
                if len(arrow.params) == 1
                else None
            )
            if sig is None:  # non-unary or unprobeable: not comparable, so never collapse
                result.append((ref, arrow))
                continue
            key = (arrow, sig)
            if key not in best:
                best[key] = len(result)
                result.append((ref, arrow))
            elif ref.size() < result[best[key]][0].size():
                result[best[key]] = (ref, arrow)  # a smaller witness for the same behavior wins
        return result

    def _function_sig(
        self, ref: Program, domain: Type, library: Library
    ) -> tuple[object, ...] | None:
        """A unary function candidate's behaviour: its output as the argument ranges over a battery."""
        battery = self._domain_battery(domain)
        if not battery:
            return None
        try:
            fn = ref.evaluate(_SYNTH_GRID, library)
            return tuple(self._value_key(_apply_unary(fn, arg)) for arg in battery)
        except Exception:
            return None

    def _body_sig(
        self, body: Program, battery: tuple[Value, ...], library: Library
    ) -> tuple[object, ...] | None:
        """A lambda body's behaviour as its bound var (``$0``) ranges over ``battery``."""
        try:
            return tuple(
                self._value_key(body.evaluate(_SYNTH_GRID, library, (), (arg,))) for arg in battery
            )
        except Exception:
            return None

    def _domain_battery(self, domain: Type) -> tuple[Value, ...]:
        """A few distinct values of ``domain`` to probe a function's behaviour (empty = unsupported).

        The batteries span the whole small-value range per type (all ten colors; ints 0..9) so two
        functions differing anywhere in that range are told apart, rather than collapsed — an empty
        battery (an unprobeable type) means "cannot compare", which the callers treat as "keep both".
        """
        if domain == GRID:
            return _SYNTH_GRIDS
        if domain == BOOL:
            return (False, True)
        if domain == COLOR:
            return tuple(range(10))  # every ARC color, so a recolor touching any of 0..9 is visible
        if domain == INT:
            return tuple(range(10))  # small non-negative ints (grid dimensions / coordinates)
        return ()

    def _value_key(self, value: Value) -> object:
        """A hashable identity for a value (grids don't hash directly)."""
        if isinstance(value, Grid):
            return ("grid", value.shape, value.array.tobytes())
        return value


class BeamSearch(Enumerate):
    """Cost-guided enumeration: keep the top-``beam_width`` grid programs per round by ``Cost``.

    Identical to :class:`Enumerate` except the per-round grid frontier is *ranked by an injected*
    :class:`~arc_lab.solvers.dsl.search.cost.Cost` and truncated to ``beam_width``, rather than
    cut in insertion order. This is the first search to actually *consume* a ``Cost`` — the rank
    the substrate defines but the frontier never used — turning ``max_grid_args`` from
    'simplest-by-arrival' into 'cheapest-by-cost'. That is what a richer (object / cell-floor)
    vocabulary needs to stay tractable once the grid pool would otherwise explode. The accumulated
    behaviour pools are unchanged; only *which* grids feed the next round is cost-selected.
    """

    def __init__(
        self,
        *,
        cost: Cost,
        beam_width: int = 16,
        max_depth: int = 2,
        max_pool: int = 600,
        coord_ints: bool = False,
    ) -> None:
        super().__init__(
            max_depth=max_depth,
            max_pool=max_pool,
            max_grid_args=beam_width,
            coord_ints=coord_ints,
        )
        self.cost = cost
        self.beam_width = beam_width

    def _grid_frontier(
        self, candidates: list[Program], task: Task, library: Library
    ) -> list[Program]:
        # Rank the whole grid pool by cost (lower first) and keep the cheapest beam_width. A
        # stable sort preserves insertion (smallest-first) order among cost ties.
        ranked = sorted(candidates, key=lambda program: self.cost.of(program, task, library))
        return ranked[: self.beam_width]


def _leaf_constants(task: Task, *, coord_ints: bool = False) -> tuple[list[int], list[int]]:
    """Task-relevant constants: colors, a consistent scale factor, and (opt) coordinates."""
    grids: list[Grid] = []
    for ex in task.train:
        grids.append(ex.input)
        if ex.output is not None:
            grids.append(ex.output)
    colors = sorted({int(c) for g in grids for c in np.unique(g.array)})

    ratios: list[int | None] = []
    for ex in task.train:
        if ex.output is None:
            ratios.append(None)
            continue
        ih, iw = ex.input.shape
        oh, ow = ex.output.shape
        if ih and iw and oh % ih == 0 and ow % iw == 0 and oh // ih == ow // iw > 1:
            ratios.append(oh // ih)
        else:
            ratios.append(None)
    ints: set[int] = set()
    if ratios and all(r is not None and r == ratios[0] for r in ratios):
        assert ratios[0] is not None
        ints.add(ratios[0])
    if coord_ints:
        # Every in-bounds row/col index of the input grids, for read/set_cell.
        max_dim = max((max(ex.input.shape) for ex in task.train), default=0)
        ints.update(range(max_dim))
    return colors, sorted(ints)
