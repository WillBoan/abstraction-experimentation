"""Rung recovery, and *why* a rung was not recovered.

``recovered`` -- does some minted abstraction behave as the intended rung? -- is the right primary
question and is unchanged here. What this adds is the diagnosis when the answer is no, because
"not recovered" has covered three mechanically different failures that the report rendered
identically:

- **no-material** -- the rung's demonstrating tasks were never solved, so sleep never saw the
  programs the abstraction would be mined from. A wake/budget failure, upstream of learning.
- **not-proposed** -- the material was there and the proposer never offered a behavioural match.
  Proposer *reach*: measured 2026-07-27 as ``FrequentSubtree``'s 0/4, 0/5, 0/2, whose cause is
  structural (``propose`` mines ``walk()[1:]``, so a full-solution demo's own root is invisible).
- **proposed-not-selected** -- the proposer offered a match and governance kept something else.
  Governance *preference*: ``dae9d2b5-half-param``, where ``nth(split_h(#0), #1)`` was on offer and
  ``GreedyMDL`` discarded it.

The first two are defects. **The third need not be** -- the 2026-07-27 audit priced the end states
and found that at the batch's real operating point (two distinct parameter values, two occurrences
each) minting *nothing* is the DL-optimum, so the learner was right and the ladder was wrong. That
matters now rather than academically: a governance-objective arm is expected to move rungs into
this bucket by design, and an instrument that scores them as failures cannot read such an arm at
all.

Everything here is derived from the recorded LEARN run: the wake rows carry each iteration's
solved programs, the sleep rows carry the library each sleep produced, and proposers are pure
frozen dataclasses. So the proposals are *recomputed* rather than logged -- no new telemetry, no
re-run, and nothing that touches run identity.

What is deliberately NOT computed here: whether declining was DL-optimal. That needs the end states
priced under the run's own metric (see ``experiments/2026-07-27-half-param-governance/``), which is
an analysis, not a report field -- and a wrong verdict on it would be worse than none.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from arc_lab.core.grid import Grid
from arc_lab.program_search.analysis.behavioral import matches_target
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders.run import LadderResult
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.learn.antiunify import AbstractionProposer
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Program

#: Diagnoses for a rung that was not recovered, in the order the pipeline can fail.
NO_MATERIAL = "no-material"
NOT_PROPOSED = "not-proposed"
PROPOSED_NOT_SELECTED = "proposed-not-selected"
#: The proposals could not be recomputed (no proposer reachable on the configured learn engine), so
#: reach and preference cannot be told apart. Recorded rather than guessed -- claiming
#: ``not-proposed`` without having asked the proposer would be an unearned finding.
UNDIAGNOSED = "undiagnosed"


def _wake_programs(row: Mapping[str, object]) -> list[Program]:
    """The solutions one wake retained, deserialized. A torn row yields nothing, never a crash."""
    programs = row.get("programs")
    if not isinstance(programs, dict):
        return []
    out: list[Program] = []
    for payload in programs.values():
        if not isinstance(payload, dict):
            continue
        try:
            out.append(Program.from_dict(payload))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _solved_ids(row: Mapping[str, object]) -> set[str]:
    solved = row.get("solved")
    return {str(t) for t in solved} if isinstance(solved, list) else set()


def _library_after(row: Mapping[str, object]) -> Library | None:
    payload = row.get("library")
    if not isinstance(payload, dict):
        return None
    try:
        return Library.from_dict(payload)
    except (KeyError, TypeError, ValueError):
        return None


def _iteration_views(
    record: RunRecord, floor: Library
) -> tuple[list[tuple[int, Library, list[Program]]], dict[int, set[str]]]:
    """Per iteration: ``(iteration, the library sleep operated OVER, the wake's programs)``, plus
    the solved-id set per iteration.

    The library *before* iteration ``i``'s sleep is the floor at ``i == 0`` and the library the
    previous sleep produced thereafter -- which is what the sleep rows record.
    """
    wake: dict[int, Mapping[str, object]] = {}
    sleep: dict[int, Mapping[str, object]] = {}
    for row in record.trace_rows():
        iteration = row.get("iteration")
        if not isinstance(iteration, int):
            continue
        if row.get("phase") == "wake":
            wake[iteration] = row
        elif row.get("phase") == "sleep":
            sleep[iteration] = row

    views: list[tuple[int, Library, list[Program]]] = []
    solved_by_iter: dict[int, set[str]] = {}
    library = floor
    for iteration in sorted(wake):
        solved_by_iter[iteration] = _solved_ids(wake[iteration])
        views.append((iteration, library, _wake_programs(wake[iteration])))
        grown = _library_after(sleep[iteration]) if iteration in sleep else None
        if grown is not None:
            library = grown
    return views, solved_by_iter


def _as_primitive(name: str, template: Program, library: Library) -> Primitive | None:
    """A proposal as a callable Primitive, or ``None`` if it cannot be built over ``library``."""
    try:
        return make_abstraction(name, template, library)
    except (KeyError, TypeError, ValueError):
        return None


def _proposers_of(spec: LadderSpec) -> list[AbstractionProposer]:
    """Every proposer on the configured learn engine, found by field type rather than by engine
    class -- ``GreedyMDLLearnEngine`` carries one (``proposer``), the Stitch engine carries two
    (``corpus_proposer``, ``refactor_proposer``), and a future engine carries whatever it carries.
    """
    learn = spec.reference_config.learn
    if learn is None:
        return []
    engine = learn.learn_engine
    return [
        value
        for field in dataclasses.fields(engine)
        if isinstance(value := getattr(engine, field.name, None), AbstractionProposer)
    ]


def _first_iteration_proposing(
    spec: LadderSpec,
    views: list[tuple[int, Library, list[Program]]],
    target: Primitive,
    probes: tuple[Grid, ...],
) -> tuple[bool, int | None]:
    """``(could we check?, earliest iteration whose proposer offered a behavioural match)``.

    Recomputed, not logged: the run records ``proposal_count`` only. Proposers are pure functions
    of ``(programs, library)``, both of which the trace carries, so this reproduces exactly what
    sleep saw. The first element is ``False`` when no proposer was reachable -- an honest "cannot
    tell", never a silent ``not-proposed``.
    """
    proposers = _proposers_of(spec)
    if not proposers:
        return False, None
    for iteration, library, programs in views:
        if not programs:
            continue
        for proposer in proposers:
            proposals = proposer.propose(list(programs), library)
            for index, proposal in enumerate(proposals):
                candidate = _as_primitive(f"proposal{index}", proposal, library)
                if candidate is not None and matches_target(candidate, target, probes):
                    return True, iteration
    return True, None


def rung_recovery_rows(result: LadderResult) -> list[dict[str, Any]]:
    """One row per rung: was it recovered, by what, and -- when not -- where the pipeline broke.

    Empty when the climb never ran: absent, not zero (a rejected ladder's rungs were never offered
    to a learner, so "not recovered" would be a claim about nothing).
    """
    if result.learn is None:
        return []
    spec = result.spec
    learned = result.learn.learn.learned_library()
    floor = spec.floor()
    floor_names = {p.name for p in floor.primitives}
    invented = [p for p in learned.primitives if p.name not in floor_names]
    probes = tuple(
        example.input for entry in spec.train_corpus.entries for example in entry.task.train
    )
    views, solved_by_iter = _iteration_views(result.learn.learn, floor)
    ever_solved: set[str] = set()
    for ids in solved_by_iter.values():
        ever_solved |= ids

    rows: list[dict[str, Any]] = []
    for index, rung in enumerate(spec.rungs, start=1):
        target = make_abstraction(rung.name, rung.template, spec.oracle_library(index - 1))
        matched = [p.name for p in invented if matches_target(p, target, probes)]
        row: dict[str, Any] = {
            "rung": rung.name,
            "level": rung.level,
            "recovered": bool(matched),
            "matched_by": matched,
            "not_recovered_because": None,
            "proposed_at_iteration": None,
        }
        if not matched:
            demo_ids = {demo.task_id for demo in rung.demonstrations}
            if demo_ids and not demo_ids <= ever_solved:
                row["not_recovered_because"] = NO_MATERIAL
            else:
                checked, proposed_at = _first_iteration_proposing(spec, views, target, probes)
                row["proposed_at_iteration"] = proposed_at
                if not checked:
                    row["not_recovered_because"] = UNDIAGNOSED
                else:
                    row["not_recovered_because"] = (
                        NOT_PROPOSED if proposed_at is None else PROPOSED_NOT_SELECTED
                    )
        rows.append(row)
    return rows
