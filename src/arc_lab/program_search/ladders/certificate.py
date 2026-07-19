"""The Ladder certificate: the empirical admission gate, read over the oracle-chain runs.

The linter is static; the guarantees that need a search live here (pure reads over the recorded
``L_0..L_k`` runs):

- **jump tractable** -- ``L_{i-1}`` search-solves every rung-``i`` demonstrating task;
- **no skip path** -- ``L_{i-1}`` solves *zero* rung-``(i+1)`` tasks (the top tasks for the last
  rung), so each rung is genuinely necessary and no unintended shortcut exists;
- **demonstration health** -- the retained solution actually routes through the rung below (uses
  ``r_{i-1}``), so what the demonstrations teach is the intended composition.

A ladder is **admitted** to the batch iff every jump is tractable and no skip path exists.
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
    no_skip_paths: dict[int, bool]
    demonstration_health: dict[int, float]

    @property
    def admitted(self) -> bool:
        return all(self.tractable_jumps.values()) and all(self.no_skip_paths.values())


def certify(result: LadderResult) -> LadderCertificate:
    spec = result.spec
    solved_below = {level: _search_solved_ids(rec) for level, rec in result.oracle_chain.items()}
    programs_below = {level: _accepted_programs(rec) for level, rec in result.oracle_chain.items()}
    k = len(spec.rungs)

    tractable: dict[int, bool] = {}
    no_skip: dict[int, bool] = {}
    health: dict[int, float] = {}
    for i, rung in enumerate(spec.rungs, start=1):
        rung_ids = [demo.task_id for demo in rung.demonstrations]
        solved = solved_below[i - 1]  # under L_{i-1}
        tractable[i] = bool(rung_ids) and all(tid in solved for tid in rung_ids)
        next_ids = (
            [demo.task_id for demo in spec.rungs[i].demonstrations]
            if i < k
            else list(spec.top.task_ids)
        )
        no_skip[i] = not any(tid in solved for tid in next_ids)
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
