"""The Ladder certificate: the empirical admission gate, read over the oracle-chain runs.

The linter is static; the guarantees that need a search live here (pure reads over the recorded
``L_0..L_k`` runs):

- **jump tractable** -- ``L_{i-1}`` search-solves every rung-``i`` demonstrating task;
- **no skip path** -- ``L_{i-1}`` solves *zero* tasks of the layer that CONSUMES rung ``i``, so each
  rung is genuinely necessary and no unintended shortcut exists;
- **demonstration health** -- the retained solution actually routes through the rung's own
  DEPENDENCIES, so what the demonstrations teach is the intended composition.

Both of the latter read the **consumer graph** (``ladders/graph.py``), never a level offset. "The
layer above rung ``i``" is the rungs that call it (the top tasks when nothing but the top does), and
"the rung below" is the rungs its template and demonstrations call. The two readings coincide on a
chain and diverge on a DAG, where ``rungs[i]`` / ``rungs[i-2]`` name a *sibling* -- for
``dae9d2b5-halves-union`` (``west`` and ``east`` are independent branches under one top) the level
reading scored ``east``'s health 0.0 for not calling a rung it has no reason to call.

A ladder is **admitted** to the batch iff every jump is tractable and no skip path exists.

**Censoring makes a verdict inconclusive, never a pass.** Both checks above are read off *unsolved*
sets -- and a search stopped by ``Budget.considered_limit`` is unsolved too. Left untreated, that
turns "we ran out of budget" into a skip-path PASS, certifying a ladder whose skip path the search
merely never reached. So ``no_skip_paths`` is tri-state: ``True`` (searched to completion, solved
nothing), ``False`` (skip path found -- a real defect), ``None`` (censored -- we do not know). Only
``True`` admits. This matters because censoring is the *intended* way to run a ladder whose
tractability is unknown: set ``depth_limit`` from the ladder's semantics, cap the compute with
``considered_limit``, and read censoring as "this ladder is less tractable" -- which is only safe
if a censored cell can never be mistaken for evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders import graph
from arc_lab.program_search.ladders.spec import Rung
from arc_lab.program_search.substrate.program import Apply, PrimRef, Program

if TYPE_CHECKING:  # runtime import would cycle: run.py certifies between its two stages
    from arc_lab.program_search.ladders.run import LadderChainResult


@dataclass(frozen=True, slots=True)
class LadderCertificate:
    """Per-jump empirical verdicts (keyed by rung level) + the batch-admission gate."""

    tractable_jumps: dict[int, bool]
    #: Tri-state per jump: ``True`` no skip path, ``False`` skip path found, ``None`` inconclusive
    #: because a search was censored. See the module docstring -- ``None`` must never admit.
    no_skip_paths: dict[int, bool | None]
    demonstration_health: dict[int, float]

    @property
    def admitted(self) -> bool:
        # `is True`, not truthiness: `None` (inconclusive) must fail the gate exactly as `False` does.
        return all(self.tractable_jumps.values()) and all(
            verdict is True for verdict in self.no_skip_paths.values()
        )


def certify(result: LadderChainResult) -> LadderCertificate:
    """The admission verdict, read entirely off stage 1 (``spec`` + the oracle-chain runs) -- which
    is what lets ``run_ladder`` gate the climb on it before any learning is paid for."""
    spec = result.spec
    solved_below = {level: _search_solved_ids(rec) for level, rec in result.oracle_chain.items()}
    censored_below = {level: search_censored_ids(rec) for level, rec in result.oracle_chain.items()}
    programs_below = {level: _accepted_programs(rec) for level, rec in result.oracle_chain.items()}
    above_ids = graph.consumer_task_ids(spec.rungs, spec.top)
    rung_names = [rung.name for rung in spec.rungs]

    tractable: dict[int, bool] = {}
    no_skip: dict[int, bool | None] = {}
    health: dict[int, float] = {}
    for i, rung in enumerate(spec.rungs, start=1):
        rung_ids = [demo.task_id for demo in rung.demonstrations]
        solved = solved_below[i - 1]  # under L_{i-1}
        censored = censored_below[i - 1]
        # A censored task is not a tractable jump: we never showed L_{i-1} can solve it.
        tractable[i] = bool(rung_ids) and all(tid in solved for tid in rung_ids)
        next_ids = above_ids[rung.name]
        if any(tid in solved for tid in next_ids):
            no_skip[i] = False  # a skip path exists -- a real defect, censoring cannot mask it
        elif any(tid in censored for tid in next_ids):
            no_skip[i] = None  # unsolved, but the search was cut short: inconclusive, not a pass
        else:
            no_skip[i] = True
        health[i] = _demonstration_health(rung, rung_names, solved, programs_below[i - 1])
    return LadderCertificate(
        tractable_jumps=tractable, no_skip_paths=no_skip, demonstration_health=health
    )


def _demonstration_health(
    rung: Rung,
    rung_names: list[str],
    solved: set[str],
    programs: Mapping[str, Program],
) -> float:
    """Fraction of a rung's demonstrations that are solved and whose retained solution routes
    through that demonstration's own rung DEPENDENCIES -- so the demonstration teaches the intended
    composition, not a shortcut that happens to match.

    A demonstration's dependencies are the lower rungs its intended program touches: the ones the
    rung TEMPLATE calls, plus any the demonstration's own wrapper calls around it (rung ``i`` itself
    excluded -- the search under ``L_{i-1}`` cannot use it, which is the point). When that set is
    empty the demonstration composes over the bare floor and being solved is the whole claim -- true
    of every rung-1 demonstration, and on a DAG of any branch rooted at the floor.
    """
    demos = rung.demonstrations
    if not demos:
        return 0.0
    template_deps = graph.rung_calls(rung.template, rung_names)
    healthy = 0
    for demo in demos:
        if demo.task_id not in solved:
            continue
        wrapper_deps = graph.rung_calls(demo.solution, rung_names) - {rung.name}
        expected = template_deps | wrapper_deps
        program = programs.get(demo.task_id)
        routed = program is not None and expected <= _primitive_names(program)
        if not expected or routed:  # no dependencies to route through, or it routed through them
            healthy += 1
    return healthy / len(demos)


def _primitive_names(program: Program) -> set[str]:
    names: set[str] = set()
    for node in program.walk():
        if isinstance(node, Apply):
            names.add(node.primitive)
        elif isinstance(node, PrimRef):
            names.add(node.name)
    return names


def _search_solved_ids(record: RunRecord) -> set[str]:
    """Task ids the SEARCH found a program for (``solved_at_generation`` set), from the trace."""
    solved: set[str] = set()
    for row in record.trace_rows():
        stats = row.get("search_stats")
        tid = row.get("task_id")
        if (
            isinstance(tid, str)
            and isinstance(stats, dict)
            and stats.get("solved_at_generation") is not None
        ):
            solved.add(tid)
    return solved


def search_censored_ids(record: RunRecord) -> set[str]:
    """Task ids whose SEARCH was cut short by ``Budget.considered_limit`` -- so "unsolved" for these
    is a lower bound, not a verdict. ``stopped_early`` is deliberately NOT included: those runs
    succeeded and merely stopped paying, so their verdicts are sound."""
    censored: set[str] = set()
    for row in record.trace_rows():
        stats = row.get("search_stats")
        tid = row.get("task_id")
        if isinstance(tid, str) and isinstance(stats, dict) and stats.get("censored"):
            censored.add(tid)
    return censored


def _accepted_programs(record: RunRecord) -> dict[str, Program]:
    """The retained cheapest solution program per solved task, decoded from the trace."""
    out: dict[str, Program] = {}
    for row in record.trace_rows():
        tid = row.get("task_id")
        programs = row.get("programs")
        if isinstance(tid, str) and isinstance(programs, list) and programs:
            first = programs[0]
            if isinstance(first, dict):
                out[tid] = Program.from_dict(first)
    return out
