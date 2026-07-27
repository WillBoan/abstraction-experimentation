"""S14: does the learned library TRANSFER? The recorded run nobody has ever read.

`run_ladder` -> `run_search_learn(config, train_corpus, heldout_corpus)` produces THREE recorded
runs: the LEARN run, a `train_usefulness` SEARCH over the train corpus with the grown library, and
a `transfer` SEARCH over the HELDOUT corpus with the same grown library. The report says so itself,
under "Not computed here": *"needs the heldout transfer run's per-task costs ... the runs exist,
the view does not yet."* Every claim the program has made to date -- 43/43 rungs recovered, 0 junk,
every cost curve -- is about the TRAIN corpus.

**What the heldout corpus is here, stated precisely so the claim is not overread:** each `.ladder`
declares a `heldout task <rung>-heldout` per rung plus `<task>-heldout` for the top. These are
held-out INSTANCES of the same competences (new grids, same functions), not unseen competences. So
this measures generalisation to new data, not cross-task transfer. That is still the first time the
question is asked at all.

Read-side: every ladder here has been run under current code, so `run_ladder` is a cache hit and
returns the full `LadderResult` in seconds. No new search.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import _per_task_cells, _search_solved_ids
from arc_lab.program_search.ladders.run import run_ladder

MEMBERS = (
    "dae9d2b5-split-recolor-lean",
    "dae9d2b5-split-halves-lean",
    "dae9d2b5-split-asym-lean",
    "94f9d214-nor-recolor",
    "94f9d214-nor-merged",
    "fafffa47-nor-recolor",
    "fafffa47-nor-merged",
    "al1-mirror",
    "al21-dag-siblings",
)

print(f"{'member':32} {'stage':16} {'solved':>14}  detail")
for name in MEMBERS:
    spec = make_ladder(name)
    result = run_ladder(spec, raw_arm_k=0)
    learn = result.learn
    if learn is None:
        print(f"{name:32} {'(no climb)':16}", flush=True)
        continue

    top_ids = set(spec.top.task_ids)
    heldout_ids = [e.task.task_id for e in spec.heldout_corpus.entries]
    heldout_top = [t for t in heldout_ids if any(t.startswith(x) for x in top_ids)]

    for label, record, ids in (
        (
            "train_usefulness",
            learn.train_usefulness,
            [e.task.task_id for e in spec.train_corpus.entries],
        ),
        ("transfer", learn.transfer, heldout_ids),
    ):
        if record is None:
            print(f"{name:32} {label:16} {'MISSING':>14}", flush=True)
            continue
        solved = _search_solved_ids(record)
        cells = _per_task_cells(record)
        hit = [t for t in ids if t in solved]
        miss = [t for t in ids if t not in solved]
        top_hit = [
            t for t in (heldout_top if label == "transfer" else sorted(top_ids)) if t in solved
        ]
        top_ct = len(heldout_top) if label == "transfer" else len(top_ids)
        costs = [
            cells[t].get("first_solution_index")
            for t in hit
            if isinstance(cells.get(t, {}).get("first_solution_index"), int)
        ]
        print(
            f"{name:32} {label:16} {f'{len(hit)}/{len(ids)}':>14}  "
            f"top {len(top_hit)}/{top_ct}"
            + (f" · to-first max {max(costs):,}" if costs else "")
            + (f" · MISSED {miss}" if miss else ""),
            flush=True,
        )
    print(flush=True)
