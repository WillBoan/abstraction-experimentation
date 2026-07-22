"""S-F: the wake/sleep currency conversion `w` (design doc 3.6), measured per ladder.

Wake cost is counted in candidates considered; sleep cost in proposals + antiunify pairs. The
amortization denominators need sleep in considered-equivalents:

    w = (sleep wall-seconds x wake candidates/second) / (proposals + pairs)

Wake throughput comes from the ladder's own recorded L_0 column (considered & seconds per task);
sleep is `GreedyMDLLearnEngine.run` timed fresh on the ladder's recorded wake-0 solutions (rebuilt
from the learn trace -- no search). Stated per batch, as the doc requires.

Usage: uv run python experiments/2026-07-23-sleep-probes/artifacts/w_calibration.py
"""

from __future__ import annotations

import time

from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import run_ladder_chain
from arc_lab.program_search.substrate.program import Program

LADDERS = ["al1-mirror", "al15-shift-frame", "al16-layout-nest", "al17-shift-frame-tall",
           "al18-fanin-rotate", "al19-fanin-recolor", "al20-recolor-telescope"]

print(f"{'ladder':24s} {'wake cand/s':>11s} {'sleep sec':>9s} {'props+pairs':>11s} {'w':>8s}")
ws = []
for name in LADDERS:
    spec = make_ladder(name)
    chain = run_ladder_chain(spec)  # cache hits
    considered = seconds = 0.0
    for row in chain.oracle_chain[0].trace_rows():
        stats = row.get("search_stats")
        if isinstance(stats, dict) and isinstance(row.get("seconds"), (int, float)):
            considered += stats["total"]["considered"]
            seconds += row["seconds"]
    rate = considered / seconds

    learn_spec = spec.reference_config.learn
    assert learn_spec is not None
    learn_record = execute(  # cache hit on the recorded LEARN run
        RunSpec(config=spec.reference_config, corpus=spec.train_corpus)
    )
    wake0 = next(r for r in learn_record.trace_rows() if r.get("phase") == "wake")
    entries = {e.task.task_id: e for e in spec.train_corpus.entries}
    solutions = tuple(
        SolvedTask(annotated=entries[tid], program=Program.from_dict(data))
        for tid, data in wake0["programs"].items()
    )
    started = time.perf_counter()
    outcome = learn_spec.learn_engine.run(spec.floor(), solutions)
    sleep_seconds = time.perf_counter() - started
    units = outcome.proposal_count + outcome.antiunify_pair_count
    w = sleep_seconds * rate / units if units else float("nan")
    ws.append(w)
    print(f"{name:24s} {rate:>11,.0f} {sleep_seconds:>9.3f} {units:>11,} {w:>8,.0f}")

ws.sort()
print(f"\nbatch w: median {ws[len(ws)//2]:,.0f} considered-equivalents per sleep unit "
      f"(range {ws[0]:,.0f} - {ws[-1]:,.0f})")
