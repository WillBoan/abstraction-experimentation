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
        """The pinned reference ``depth_limit`` -- every sandwich claim is stated against it."""
        return self.spec.reference_config.budget.depth_limit

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
        top solutions. An empty list is a dead rung."""
        return graph.consumer_programs(self.rungs, self.spec.top)

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
        """Per rung, each consumer program with THIS rung expanded -- what skipping it would cost.

        The DAG generalisation of "the immediate successor": for a chain the only consumer is the
        next rung, so this is the historical adjacency measurement exactly.
        """
        return {
            rung.name: [
                (cid, unfold_program(prog, self.full_lib, expand=frozenset({rung.name})))
                for cid, prog in self.consumer_programs[rung.name]
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
    def rung_shapes(self) -> tuple[RungShape, ...]:
        """The per-rung derived quantities the report, certificate and renderer all consume."""
        names = {rung.name for rung in self.rungs}
        shapes: list[RungShape] = []
        for rung in self.rungs:
            inlined = self.inlined_consumers[rung.name]
            shapes.append(
                RungShape(
                    level=rung.level,
                    name=rung.name,
                    jump_depth=compositional_depth(rung.template),
                    jump_needs=min_depth_limit(rung.template),
                    double_jump_depth=(
                        min(compositional_depth(prog) for _, prog in inlined) if inlined else None
                    ),
                    fan_in=graph.fan_in(rung.template, names),
                    demonstration_count=len(rung.demonstrations),
                    involves_lambda=any(isinstance(n, Lam) for n in rung.template.walk()),
                )
            )
        return tuple(shapes)

    @cached_property
    def validity_window(self) -> tuple[int, int]:
        """``(lower, upper)`` inclusive, in ``depth_limit`` units: every jump affordable and no
        inlined double-jump (nor the raw top) reachable. ``lower > upper`` is a degenerate ladder."""
        lower = max([*(s.jump_depth for s in self.rung_shapes), *self.top_depths])
        intractables = [
            *(s.double_jump_depth for s in self.rung_shapes if s.double_jump_depth is not None),
            *self.raw_depth_profile,
        ]
        upper = min(intractables) - 1 if intractables else self.ref_limit
        return (lower, upper)
