"""S14b: the transfer baseline -- without it, "5/5 heldout solved" means nothing.

The transfer run searches the HELDOUT corpus with the LEARNED library and solves everything. That
is close to vacuous on its own: the heldout corpus holds held-out INSTANCES of the same competences
(`west-heldout` is a new grid pair for the same `west`), and the learned library contains
abstractions that ARE those competences -- so each rung heldout is a depth-1 application. Of course
it solves.

The claim that is NOT vacuous is about the heldout **TOP**: the goal on unseen data. So this runs
the same heldout corpus over the BARE FLOOR at the same budget and diffs the solved sets. What the
learned library genuinely buys is exactly what the floor misses.

Each cell is an ordinary recorded run (cached, resumable) over a 3-6 task corpus -- cheap.
"""

from __future__ import annotations

from dataclasses import replace

from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import _search_solved_ids
from arc_lab.program_search.ladders.run import pool_for_depth, run_ladder

MEMBERS = (
    "dae9d2b5-split-recolor-lean",
    "dae9d2b5-split-halves-lean",
    "dae9d2b5-split-asym-lean",
    "94f9d214-nor-recolor",
    "94f9d214-nor-merged",
    "fafffa47-nor-recolor",
    "fafffa47-nor-merged",
)

print(f"{'member':32} {'heldout task':26} {'floor':>8} {'learned':>9}  verdict")
for name in MEMBERS:
    spec = make_ladder(name)
    result = run_ladder(spec, raw_arm_k=0)
    assert result.learn is not None and result.learn.transfer is not None
    learned_solved = _search_solved_ids(result.learn.transfer)

    # The floor baseline at the CLIMB's budget -- the same budget the transfer run used, so the
    # only thing that differs between the two columns is the library.
    budget = spec.reference_config.budget
    floor_budget = replace(budget, max_pool=pool_for_depth(budget.max_pool, budget.depth_limit))
    floor_config = spec.reference_config.with_(
        library=spec.floor(), budget=floor_budget, learn=None
    )
    floor_record = execute(RunSpec(config=floor_config, corpus=spec.heldout_corpus))
    floor_solved = _search_solved_ids(floor_record)

    top_ids = set(spec.top.task_ids)
    for entry in spec.heldout_corpus.entries:
        tid = entry.task.task_id
        is_top = any(tid.startswith(x) for x in top_ids)
        f, ln = tid in floor_solved, tid in learned_solved
        verdict = (
            "**ABSTRACTION BUYS THE GOAL**"
            if is_top and ln and not f
            else ("free at the floor" if f and ln else ("learned only" if ln and not f else "?"))
        )
        print(
            f"{name:32} {tid:26} {('yes' if f else 'NO'):>8} {('yes' if ln else 'NO'):>9}  "
            f"{'TOP · ' if is_top else ''}{verdict}"
        )
    print(flush=True)
