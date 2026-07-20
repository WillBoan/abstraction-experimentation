"""The Ladder certificate: the empirical admission gate, read over the oracle-chain runs.

The linter is static; the guarantees that need a search live here (pure reads over the recorded
``L_0..L_k`` runs):

- **jump tractable** -- ``L_{i-1}`` search-solves every rung-``i`` demonstrating task;
- **no skip path** -- ``L_{i-1}`` solves *zero* rung-``(i+1)`` tasks (the top tasks for the last
  rung), so each rung is genuinely necessary and no unintended shortcut exists;
- **demonstration health** -- the retained solution actually routes through the rung below (uses
  ``r_{i-1}``), so what the demonstrations teach is the intended composition.

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

from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders.run import LadderResult
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.substrate.program import Apply, PrimRef, Program


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


def certify(result: LadderResult) -> LadderCertificate:
    spec = result.spec
    solved_below = {level: _search_solved_ids(rec) for level, rec in result.oracle_chain.items()}
    censored_below = {level: search_censored_ids(rec) for level, rec in result.oracle_chain.items()}
    programs_below = {level: _accepted_programs(rec) for level, rec in result.oracle_chain.items()}
    k = len(spec.rungs)

    tractable: dict[int, bool] = {}
    no_skip: dict[int, bool | None] = {}
    health: dict[int, float] = {}
    for i, rung in enumerate(spec.rungs, start=1):
        rung_ids = [demo.task_id for demo in rung.demonstrations]
        solved = solved_below[i - 1]  # under L_{i-1}
        censored = censored_below[i - 1]
        # A censored task is not a tractable jump: we never showed L_{i-1} can solve it.
        tractable[i] = bool(rung_ids) and all(tid in solved for tid in rung_ids)
        next_ids = (
            [demo.task_id for demo in spec.rungs[i].demonstrations]
            if i < k
            else list(spec.top.task_ids)
        )
        if any(tid in solved for tid in next_ids):
            no_skip[i] = False  # a skip path exists -- a real defect, censoring cannot mask it
        elif any(tid in censored for tid in next_ids):
            no_skip[i] = None  # unsolved, but the search was cut short: inconclusive, not a pass
        else:
            no_skip[i] = True
        health[i] = _demonstration_health(i, rung_ids, solved, programs_below[i - 1], spec)
    return LadderCertificate(
        tractable_jumps=tractable, no_skip_paths=no_skip, demonstration_health=health
    )


def _demonstration_health(
    level: int,
    rung_ids: list[str],
    solved: set[str],
    programs: Mapping[str, Program],
    spec: LadderSpec,
) -> float:
    """Fraction of a rung's demonstrations that are solved and (for level >= 2) whose retained
    solution routes through the rung below -- so the demonstration teaches the intended composition,
    not a shortcut that happens to match."""
    if not rung_ids:
        return 0.0
    below_name = spec.rungs[level - 2].name if level >= 2 else None
    healthy = 0
    for tid in rung_ids:
        if tid not in solved:
            continue
        program = programs.get(tid)
        if below_name is None:
            healthy += 1  # rung 1 uses only floor primitives; solved is enough
        elif program is not None and below_name in _primitive_names(program):
            healthy += 1
    return healthy / len(rung_ids)


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
