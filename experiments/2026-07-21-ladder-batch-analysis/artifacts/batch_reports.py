"""Generate the ladder report for all 20 ladders from the runs/ cache -- CACHE-ONLY.

Every run id run_ladder would need (LEARN, oracle chain L_0..L_k, off-chain, and the two derived
searches) is verified present before calling it; a ladder with any miss is SKIPPED, never executed.
That guard is the point: ``run_ladder`` silently executes on a cache miss, and an unguarded version
of this script started an uncapped al14 search that ran ~10 minutes before being killed.

The al1-al14 runs of 2026-07-20 were made with a ``considered_limit=50000`` guard that is NOT
carried in the committed LadderSpecs, so their cells are found under the ``cl50k-*`` variants below;
al15-al20 ran as-committed. Writes ``reports.json`` beside this script.

    uv run python experiments/2026-07-21-ladder-batch-analysis/artifacts/batch_reports.py
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import time

from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.ladders.registry import LADDERS, make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report
from arc_lab.program_search.ladders.run import _off_chain_library, run_ladder

HERE = pathlib.Path(__file__).parent
VARIANTS = [
    ({}, "as-committed"),
    ({"considered_limit": 50000, "considered_limit_mode": "generation-end"}, "cl50k-gen"),
    ({"considered_limit": 50000, "considered_limit_mode": "immediate"}, "cl50k-imm"),
]
CACHED = {json.loads(p.read_text())["run_id"] for p in pathlib.Path("runs").glob("*/*/runspec.json")}


def fully_cached(spec) -> bool:
    """True iff every run ``run_ladder(spec)`` needs is already recorded."""
    if RunSpec(config=spec.reference_config, corpus=spec.train_corpus).run_id not in CACHED:
        return False
    ids = [
        RunSpec(
            config=spec.reference_config.with_(library=spec.oracle_library(lvl), learn=None),
            corpus=spec.train_corpus,
        ).run_id
        for lvl in range(len(spec.rungs) + 1)
    ]
    ids.append(
        RunSpec(
            config=spec.reference_config.with_(library=_off_chain_library(spec), learn=None),
            corpus=spec.train_corpus,
        ).run_id
    )
    if not all(i in CACHED for i in ids):
        return False
    # The derived (train-usefulness / transfer) searches key off the GROWN library, so they can
    # only be identified after loading the learn record -- itself a cache read.
    learn = execute(RunSpec(config=spec.reference_config, corpus=spec.train_corpus))
    derived = spec.reference_config.with_(library=learn.learned_library(), learn=None)
    return all(
        RunSpec(config=derived, corpus=c).run_id in CACHED
        for c in (spec.train_corpus, spec.heldout_corpus)
    )


def main() -> None:
    out: dict[str, object] = {}
    for name in LADDERS:
        base = make_ladder(name)
        for over, label in VARIANTS:
            budget = (
                dataclasses.replace(base.reference_config.budget, **over)
                if over
                else base.reference_config.budget
            )
            spec = dataclasses.replace(
                base, reference_config=base.reference_config.with_(budget=budget)
            )
            if not fully_cached(spec):
                continue
            started = time.time()
            report = create_ladder_report(run_ladder(spec))
            report["_variant"] = label
            out[name] = report
            print(f"{name:26} {label:14} {time.time() - started:6.1f}s", flush=True)
            break
        else:
            print(f"{name:26} NO FULLY-CACHED VARIANT -- skipped (would execute)", flush=True)
    (HERE / "reports.json").write_text(json.dumps(out))
    print(f"\nwrote {len(out)}/{len(LADDERS)} reports", flush=True)


if __name__ == "__main__":
    main()
