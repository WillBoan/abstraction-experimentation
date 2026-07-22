"""The wake-schedule comparison, completed: full / skip-solved / curriculum across the admitted set.

`full` is the honest baseline (every wake re-searches every task); `skip-solved` is the honest
cheap mode (carry solutions, re-search only the unsolved); `curriculum` is the ORACLE-schedule arm
-- iteration i wakes exactly rung i+1's demos (then the top), which injects the ladder's own
structure and so is an UPPER BOUND on what perfect scheduling could save, not an honest cell.

Per schedule per ladder: end-to-end considered, rungs recovered, and mints (the arm label's point
-- a cheaper schedule that dirties the library is not a free lunch). Curriculum is built from each
spec's own rung demonstrations: one group per level, top last.

Usage: uv run python experiments/2026-07-23-schedule-comparison/artifacts/schedule_comparison.py
"""

from __future__ import annotations

import dataclasses

from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.analysis.behavioral import matches_target

LADDERS = ["al1-mirror", "al15-shift-frame", "al16-layout-nest", "al17-shift-frame-tall",
           "al18-fanin-rotate", "al19-fanin-recolor", "al20-recolor-telescope"]


def curriculum_of(spec) -> tuple[tuple[str, ...], ...]:
    """One group per level (rung i's demos), the top tasks last -- the intended climb order."""
    groups = [tuple(d.task_id for d in rung.demonstrations) for rung in spec.rungs]
    groups.append(tuple(spec.top.task_ids))
    return tuple(groups)


def recovered(spec, record) -> int:
    """Rungs whose intended abstraction has a behavioral match in the learned library."""
    learned = record.learned_library()
    floor_names = {p.name for p in spec.floor().primitives}
    invented = [p for p in learned.primitives if p.name not in floor_names]
    probes = tuple(ex.input for e in spec.train_corpus.entries for ex in e.task.train)
    n = 0
    for i, rung in enumerate(spec.rungs, start=1):
        target = make_abstraction(rung.name, rung.template, spec.oracle_library(i - 1))
        if any(matches_target(p, target, probes) for p in invented):
            n += 1
    return n


def run(spec, schedule: str):
    learn = spec.reference_config.learn
    kwargs: dict = {"wake_schedule": schedule}
    if schedule == "curriculum":
        kwargs["curriculum"] = curriculum_of(spec)
    config = spec.reference_config.with_(learn=dataclasses.replace(learn, **kwargs))
    record = execute(RunSpec(config=config, corpus=spec.train_corpus))
    wakes = [r for r in record.trace_rows() if r.get("phase") == "wake"]
    e2e = sum(r["considered"] for r in wakes if isinstance(r.get("considered"), int))
    results = record.results()
    return e2e, len(spec.rungs), recovered(spec, record), list(results["added"])


print(f"{'ladder':22s} {'schedule':>12s} {'e2e considered':>14s} {'vs full':>7s} "
      f"{'recovery':>8s} {'mints (intended k)':>20s}")
for name in LADDERS:
    spec = make_ladder(name)
    full_e2e = None
    for schedule in ("full", "skip-solved", "curriculum"):
        e2e, k, rec, mints = run(spec, schedule)
        if schedule == "full":
            full_e2e = e2e
        ratio = f"{full_e2e / e2e:.2f}x" if e2e else "-"
        extra = "" if len(mints) == k else f"  (+{len(mints) - k} JUNK)"
        print(f"{name:22s} {schedule:>12s} {e2e:>14,} {ratio:>7s} {rec:>3d}/{k:<4d} "
              f"{str(mints):>20s}{extra}", flush=True)
    print()
