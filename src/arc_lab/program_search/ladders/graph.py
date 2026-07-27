"""The rung dependency graph: who calls whom, and what shape that makes.

Pure functions over programs and rung names -- no ``LadderSpec``, no context, no findings -- so
both the checks and ``LadderSpec.render()`` read them without an import cycle. References point
only downward (a rung elaborates over ``L_{i-1}``, enforced at load), so "reachable from the top"
is exactly "has a consumer".
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from arc_lab.program_search.substrate.program import Apply, Program

if TYPE_CHECKING:
    from arc_lab.program_search.ladders.spec import Rung, TopRung


def calls(program: Program, name: str) -> int:
    """How many times ``program`` calls the named abstraction -- 0 means structurally unused."""
    return sum(1 for node in program.walk() if isinstance(node, Apply) and node.primitive == name)


def fan_in(template: Program, rung_names: set[str]) -> int:
    """How many rung calls the template makes, with multiplicity (fan-in > 1 == recombining)."""
    return sum(
        1 for node in template.walk() if isinstance(node, Apply) and node.primitive in rung_names
    )


def consumer_programs(rungs: Sequence[Rung], top: TopRung) -> dict[str, list[tuple[str, Program]]]:
    """For each rung, the CONSUMER programs that call it: every higher rung's template and every
    top solution that references it, each tagged by a consumer id (the higher rung's name, or
    ``top:<task_id>``).

    The program is what a double-jump inlines this rung INTO: the DAG generalisation of "the next
    rung", correct for a chain and for a rung that feeds several, or non-adjacent, consumers.
    """
    names = [rung.name for rung in rungs]
    out: dict[str, list[tuple[str, Program]]] = {name: [] for name in names}
    for level, rung in enumerate(rungs):
        for lower in names[:level]:  # only strictly-lower rungs can be called
            if calls(rung.template, lower):
                out[lower].append((rung.name, rung.template))
    for task_id, solution in zip(top.task_ids, top.reference_solutions, strict=False):
        for name in names:
            if calls(solution, name):
                out[name].append((f"top:{task_id}", solution))
    return out


def consumer_graph(rungs: Sequence[Rung], top: TopRung) -> dict[str, list[str]]:
    """The consumer ids per rung (names only) -- :func:`consumer_programs` without the programs."""
    return {
        name: [cid for cid, _ in progs] for name, progs in consumer_programs(rungs, top).items()
    }


def consumer_task_ids(rungs: Sequence[Rung], top: TopRung) -> dict[str, list[str]]:
    """For each rung, the TASK IDS of "the layer above it" -- what the empirical reads (the
    certificate's skip check, the report's marginal rung value) must search for under ``L_{i-1}``.

    Rung consumers take precedence and the top is the fallback, mirroring how the static lint
    splits the same claim: ``double-jump-intractable`` measures rung consumers and skips a rung the
    top alone consumes, leaving that case to ``top-double-jump-intractable``. On a chain this is
    byte-identical to the ``rungs[i]``-then-``top`` reading it replaces (rung ``i<k`` is consumed by
    ``r_{i+1}``; ``r_k`` only by the top); on a DAG it names the *actual* consumers instead of a
    level-adjacent sibling that may never call the rung at all.
    """
    demos_by_rung = {rung.name: [d.task_id for d in rung.demonstrations] for rung in rungs}
    out: dict[str, list[str]] = {}
    for name, consumers in consumer_graph(rungs, top).items():
        above = [cid for cid in consumers if not cid.startswith("top:")]
        ids = (
            [tid for cid in above for tid in demos_by_rung.get(cid, ())]
            if above
            else [cid[len("top:") :] for cid in consumers]
        )
        out[name] = list(dict.fromkeys(ids))
    return out


def rung_calls(program: Program, rung_names: Sequence[str]) -> set[str]:
    """Which of ``rung_names`` the program calls -- its rung DEPENDENCIES, without multiplicity."""
    names = set(rung_names)
    return {
        node.primitive
        for node in program.walk()
        if isinstance(node, Apply) and node.primitive in names
    }


def is_chain(consumers: dict[str, list[str]], rung_names: Sequence[str]) -> bool:
    """Do the rung->rung edges form the simple spine ``r_1 <- ... <- r_k``?

    True iff each rung is consumed only by its immediate successor (top solutions ignored -- they
    are the goal layer, free to reach past the spine). Any other shape -- a rung with two rung
    consumers, or a non-adjacent one -- is a DAG.
    """
    for level, name in enumerate(rung_names):
        rung_consumers = [c for c in consumers[name] if not c.startswith("top:")]
        expected = [rung_names[level + 1]] if level + 1 < len(rung_names) else []
        if rung_consumers != expected:
            return False
    return True
