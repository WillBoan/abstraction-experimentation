"""``CheckContext``: everything the checks read, derived once and lazily.

The old monolithic ``lint()`` computed its derivations inline, in the order the checks happened to
need them -- which is why the corpus- and unfold-backed quantities were computed even for a
structural-tier lint, and why the top solutions were unfolded twice. Here every derivation is a
``cached_property``: a check that never asks for the unfolds never pays for them, and a quantity
two checks share is computed once.

Deliberately a plain mutable object, not a frozen dataclass: it is ephemeral per-lint scratch
space, never hashed, never serialized, never part of run identity.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit
from arc_lab.program_search.ladders import graph
from arc_lab.program_search.ladders.breadth import RungBreadth, rung_breadth
from arc_lab.program_search.ladders.shape import RungShape
from arc_lab.program_search.substrate.abstraction import unfold_program
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Lam, Program

if TYPE_CHECKING:
    from arc_lab.program_search.ladders.spec import LadderSpec, Rung


class CheckContext:
    """One lint's shared, lazily-derived reading of a :class:`~..spec.LadderSpec`."""

    def __init__(self, spec: LadderSpec, *, corpus_backed: bool) -> None:
        self.spec = spec
        #: ``False`` runs the STRUCTURAL tier only -- ``CORPUS``-stage checks are skipped and named.
        self.corpus_backed = corpus_backed

    # -- the ladder's own parts -----------------------------------------------------

    @property
    def rungs(self) -> tuple[Rung, ...]:
        return self.spec.rungs

    @property
    def k(self) -> int:
        """The number of bridging rungs (the top layer sits at ``L_k``)."""
        return len(self.spec.rungs)

    @property
    def ref_limit(self) -> int:
        """The pinned reference ``depth_limit`` -- what a ``PINNED`` ladder runs every level at.

        Under the default ``DERIVED`` regime this is no longer the budget any level runs at; it
        survives as the value the source file states and as the ``PINNED`` fallback. Every sandwich
        claim is stated against :meth:`limit_at` instead.
        """
        return self.spec.reference_config.budget.depth_limit

    @cached_property
    def depth_schedule(self) -> tuple[int, ...]:
        """The ``depth_limit`` per oracle-chain level, ``L_0 .. L_k`` (see
        :class:`~..spec.DepthScheduleMode`).

        ``L_j`` serves rung ``j+1``: its search must find that rung's demonstrations and must NOT
        find that rung's consumers. So its budget is the rung's ``jump_needs`` -- the smallest that
        puts the jump in reach, and therefore the largest one that leaves the most double-jumps out
        of it. ``L_k`` faces no rung above and carries the top's own need.
        """
        from arc_lab.program_search.ladders.spec import DepthScheduleMode

        if self.spec.depth_schedule_mode is DepthScheduleMode.PINNED:
            return (self.ref_limit,) * (self.k + 1)
        top = max(self.top_needs, default=self.ref_limit)
        return (*(shape.jump_needs for shape in self.rung_shapes), top)

    def limit_at(self, level: int) -> int:
        """The ``depth_limit`` the ``L_level`` search runs at -- the budget every depth claim about
        that level (affordability of the rung above, intractability of skipping it) is stated in."""
        schedule = self.depth_schedule
        return schedule[level] if 0 <= level < len(schedule) else self.ref_limit

    @cached_property
    def full_lib(self) -> Library:
        """``L_k``: the floor with every intended rung gifted."""
        return self.spec.oracle_library(self.k)

    @cached_property
    def libraries(self) -> tuple[Library, ...]:
        """``L_0 .. L_k`` -- the oracle chain, for the checks that ask what a SKIPPED rung leaves."""
        return tuple(self.spec.oracle_library(level) for level in range(self.k + 1))

    @cached_property
    def by_id(self) -> dict[str, AnnotatedTask]:
        """The train corpus indexed by task id (the heldout corpus is read separately)."""
        return {entry.task.task_id: entry for entry in self.spec.train_corpus.entries}

    @property
    def all_entries(self) -> tuple[AnnotatedTask, ...]:
        """Train + heldout entries, in that order."""
        return (*self.spec.train_corpus.entries, *self.spec.heldout_corpus.entries)

    # -- the dependency graph -------------------------------------------------------

    @cached_property
    def consumer_programs(self) -> dict[str, list[tuple[str, Program]]]:
        """Per rung, the ``(consumer id, program)`` pairs that call it -- higher rung templates and
        top solutions. An empty list is a dead rung.

        The STRUCTURAL reading of the graph: who mentions whom. ``is_chain``, the fan-out shape and
        the rendered dependency list are facts about templates and read this. Anything asking what
        a SEARCH would have to find reads :attr:`consumer_targets` instead.
        """
        return graph.consumer_programs(self.rungs, self.spec.top)

    @cached_property
    def consumer_targets(self) -> dict[str, list[tuple[str, Program]]]:
        """Per rung, the programs a SEARCH will actually look for that call it.

        The search-side twin of :attr:`consumer_programs`, and the one every depth claim about
        skipping is stated over. A consuming rung contributes its DEMONSTRATION TARGETS (each demo
        solution over ``L_{j-1}``, :attr:`demo_targets`) rather than its template, because the wake
        at that rung searches for its demonstrations -- the top already contributed its reference
        solutions, so this makes the two halves of the graph speak the same unit.

        Identical to :attr:`consumer_programs` whenever every demonstration is a full solution
        (wrapper depth 1). It diverges exactly where a demo WRAPS its rung, and there the wrapper's
        depth is depth a skip would also have to pay -- so the template reading UNDERSTATES the
        double-jump, and the validity window came out narrower than the truth.
        """
        names = [rung.name for rung in self.rungs]
        out: dict[str, list[tuple[str, Program]]] = {name: [] for name in names}
        for rung in self.rungs:
            # A rung with no demonstrations (a draft) falls back to its template, so a lower rung
            # never silently loses its consumer and `double-jump-intractable` keeps firing.
            targets = [target for _, target in self.demo_targets[rung.name]] or [rung.template]
            for target in targets:
                for lower in names:  # a target over L_{j-1} can only call strictly-lower rungs
                    if graph.calls(target, lower):
                        out[lower].append((rung.name, target))
        for task_id, solution in zip(
            self.spec.top.task_ids, self.spec.top.reference_solutions, strict=False
        ):
            for name in names:
                if graph.calls(solution, name):
                    out[name].append((f"top:{task_id}", solution))
        return out

    @cached_property
    def consumers(self) -> dict[str, list[str]]:
        """The same graph, consumer ids only."""
        return {name: [cid for cid, _ in progs] for name, progs in self.consumer_programs.items()}

    @cached_property
    def is_chain(self) -> bool:
        """Do the rung edges form the simple spine ``r_1 <- ... <- r_k``? (Derived, not declared.)"""
        return graph.is_chain(self.consumers, [rung.name for rung in self.rungs])

    @cached_property
    def inlined_consumers(self) -> dict[str, list[tuple[str, Program]]]:
        """Per rung, each consumer TARGET with THIS rung expanded -- what skipping it would cost.

        The DAG generalisation of "the immediate successor": for a chain the only consumer is the
        next rung, so this is the historical adjacency measurement exactly.
        """
        return {
            rung.name: [
                (cid, unfold_program(prog, self.full_lib, expand=frozenset({rung.name})))
                for cid, prog in self.consumer_targets[rung.name]
            ]
            for rung in self.rungs
        }

    # -- unfolds (the expensive tier; the shared cache) ------------------------------

    @cached_property
    def demo_targets(self) -> dict[str, list[tuple[str, Program]]]:
        """Per rung, each demonstration's solution expressed over ``L_{i-1}`` -- the program the
        wake at that rung must ACTUALLY find.

        Only this rung is expanded: a demo may also call strictly-lower rungs (NAM-5), and those
        are already in ``L_{i-1}``, so they stay folded. What is left is exactly the target the
        climb searches for before sleep has minted anything at this level.

        Distinct from :attr:`unfolded_templates`, which is the rung's own body: for a rung whose
        demonstration wraps it (any non-Grid rung must be wrapped -- a task solution has to produce
        a Grid), the wrapper adds depth the template does not carry.
        """
        return {
            rung.name: [
                (
                    demo.task_id,
                    unfold_program(demo.solution, self.full_lib, expand=frozenset({rung.name})),
                )
                for demo in rung.demonstrations
            ]
            for rung in self.rungs
        }

    @cached_property
    def unfolded_templates(self) -> tuple[Program, ...]:
        """Every rung template unfolded to the floor, in level order."""
        return tuple(unfold_program(rung.template, self.full_lib) for rung in self.rungs)

    @cached_property
    def unfolded_top(self) -> tuple[Program, ...]:
        """Every top reference solution unfolded to the floor (``d_raw``'s program)."""
        return tuple(
            unfold_program(sol, self.full_lib) for sol in self.spec.top.reference_solutions
        )

    @cached_property
    def skipped_top(self) -> tuple[Program, ...]:
        """Every top reference solution with ``r_k`` inlined -- the top over ``L_{k-1}``."""
        # `rungs[-1]` is a LEVEL read, and correct as one on a DAG too: `L_{k-1}` is defined as the
        # floor plus rungs 1..k-1, so the one rung to inline is exactly the level-k rung, whoever
        # calls it. (Contrast the consumer-graph reads in `certificate.py`, which ask who consumes
        # a rung -- a question levels cannot answer.)
        expand = frozenset({self.rungs[-1].name})
        return tuple(
            unfold_program(sol, self.full_lib, expand=expand)
            for sol in self.spec.top.reference_solutions
        )

    @cached_property
    def unfolded_stated(self) -> tuple[tuple[str, Program], ...]:
        """``(task id, floor form)`` for every solution the ladder STATES -- demonstrations,
        distractors and top solutions alike.

        Collapse lives in the floor's term space (al14's ``sub(1, 1)`` only appears after
        unfolding), so the evaluation-backed checks all read these. The top entries reuse
        :attr:`unfolded_top`: one unfold per top solution, not two.
        """
        top = [
            (task_id, self.unfolded_top[index])
            for index, task_id in enumerate(self.spec.top.task_ids)
            if index < len(self.unfolded_top)
        ]
        return (
            *(
                (demo.task_id, unfold_program(demo.solution, self.full_lib))
                for rung in self.rungs
                for demo in rung.demonstrations
            ),
            *(
                (d.task_id, unfold_program(d.solution, self.full_lib))
                for d in self.spec.distractors
            ),
            *top,
        )

    @cached_property
    def unfolded_by_id(self) -> dict[str, Program]:
        return dict(self.unfolded_stated)

    # -- corpus reads ---------------------------------------------------------------

    @cached_property
    def train_inputs(self) -> dict[str, tuple[Grid, ...]]:
        """Each task's train input grids, train and heldout corpora alike."""
        return {
            entry.task.task_id: tuple(ex.input for ex in entry.task.train)
            for entry in self.all_entries
        }

    @cached_property
    def probe_inputs(self) -> dict[str, tuple[Grid, ...]]:
        """Grids to confirm a rewrite witness on: a rung's demonstrations' train inputs (keyed by
        rung name), and each top task's own train inputs (keyed by task id)."""
        probes: dict[str, tuple[Grid, ...]] = {
            rung.name: tuple(
                ex.input
                for demo in rung.demonstrations
                if demo.task_id in self.by_id
                for ex in self.by_id[demo.task_id].task.train
            )
            for rung in self.rungs
        }
        for task_id in self.spec.top.task_ids:
            if task_id in self.by_id:
                probes[task_id] = tuple(ex.input for ex in self.by_id[task_id].task.train)
        return probes

    # -- the derived shape ----------------------------------------------------------

    @cached_property
    def top_depths(self) -> tuple[int, ...]:
        """``compositional_depth`` of each top reference solution over ``L_k``."""
        return tuple(compositional_depth(sol) for sol in self.spec.top.reference_solutions)

    @cached_property
    def raw_depth_profile(self) -> tuple[int, ...]:
        """``d_raw`` per top solution: its depth unfolded all the way to the floor."""
        return tuple(compositional_depth(prog) for prog in self.unfolded_top)

    @cached_property
    def top_needs(self) -> tuple[int, ...]:
        """``min_depth_limit`` of each top reference solution over ``L_k``."""
        return tuple(min_depth_limit(sol) for sol in self.spec.top.reference_solutions)

    @cached_property
    def raw_needs(self) -> tuple[int, ...]:
        """``min_depth_limit`` of each top solution unfolded all the way to the floor."""
        return tuple(min_depth_limit(prog) for prog in self.unfolded_top)

    @cached_property
    def rung_shapes(self) -> tuple[RungShape, ...]:
        """The per-rung derived quantities the report, certificate and renderer all consume.

        Both depth bounds are stated over the programs the ladder's searches will ACTUALLY run:
        the lower over each rung's demonstration targets, the upper over its consumers' targets.
        The rung template is reported alongside as ``template_depth``, because it is still what
        sleep has to mint -- it is simply not what the wake has to find.
        """
        names = {rung.name for rung in self.rungs}
        shapes: list[RungShape] = []
        for rung in self.rungs:
            inlined = self.inlined_consumers[rung.name]
            targets = self.demo_targets[rung.name]
            # `max`/`min` keep the FIRST extremal element, so ties resolve to declaration order --
            # the earliest offending demonstration, and the shallowest-first consumer.
            binding = max(targets, key=lambda item: min_depth_limit(item[1])) if targets else None
            template_depth = compositional_depth(rung.template)
            template_needs = min_depth_limit(rung.template)
            shallowest = (
                min(inlined, key=lambda item: min_depth_limit(item[1])) if inlined else None
            )
            shapes.append(
                RungShape(
                    level=rung.level,
                    name=rung.name,
                    template_depth=template_depth,
                    template_needs=template_needs,
                    jump_depth=(
                        compositional_depth(binding[1]) if binding is not None else template_depth
                    ),
                    jump_needs=(
                        min_depth_limit(binding[1]) if binding is not None else template_needs
                    ),
                    depth_source="demonstrations" if binding is not None else "template",
                    deepest_demonstration=binding[0] if binding is not None else None,
                    double_jump_depth=(
                        compositional_depth(shallowest[1]) if shallowest is not None else None
                    ),
                    double_jump_needs=(
                        min_depth_limit(shallowest[1]) if shallowest is not None else None
                    ),
                    fan_in=graph.fan_in(rung.template, names),
                    demonstration_count=len(rung.demonstrations),
                    involves_lambda=any(isinstance(n, Lam) for n in rung.template.walk()),
                )
            )
        return tuple(shapes)

    @cached_property
    def rung_breadth(self) -> tuple[RungBreadth, ...]:
        """Per rung, the round-1 breadth census over the library its search actually runs on.

        Corpus-backed: the constant battery is a function of grid size, so a rung whose first
        demonstration is not in the corpus (a draft, or a structural-tier lint) is skipped rather
        than priced against imaginary grids. An INDICATOR -- see :mod:`..breadth`.
        """
        if not self.corpus_backed:
            return ()
        engine = self.spec.reference_config.search_engine
        sources = getattr(engine, "constant_sources", ())
        max_arity = self.spec.reference_config.budget.max_arity
        out: list[RungBreadth] = []
        for rung in self.rungs:
            targets = self.demo_targets[rung.name]
            if not targets:
                continue
            task_id, target = targets[0]
            entry = self.by_id.get(task_id)
            if entry is None:
                continue
            out.append(
                rung_breadth(
                    level=rung.level,
                    name=rung.name,
                    library=self.libraries[rung.level - 1],
                    program=target,
                    grids=[ex.input for ex in entry.task.train],
                    constant_sources=tuple(sources),
                    max_arity=max_arity,
                )
            )
        return tuple(out)

    @cached_property
    def validity_window(self) -> tuple[int, int]:
        """``(lower, upper)`` inclusive, in ``depth_limit`` units: every jump affordable and no
        inlined double-jump (nor the raw top) reachable. ``lower > upper`` is a degenerate ladder.

        Stated in ``min_depth_limit`` throughout -- the smallest budget that puts a program in
        REACH -- to match every check that reads it. That exceeds ``compositional_depth`` only when
        a lambda body needs its own descended budget, so the two agree on first-order ladders.
        """
        lower = max([*(s.jump_needs for s in self.rung_shapes), *self.top_needs])
        intractables = [
            *(s.double_jump_needs for s in self.rung_shapes if s.double_jump_needs is not None),
            *self.raw_needs,
        ]
        upper = min(intractables) - 1 if intractables else self.ref_limit
        return (lower, upper)
