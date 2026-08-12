"""Probe: run the fundamental-floor grain-contrast ladder (geom / universal-floor /
minimal-complete-floor) on the real task 3c9b0459 (fixed 3x3 shape, rot180, 4 varied train
examples, already d4-solved) -- the real-task leg alongside the designed `grain-contrast`
testbed. See notebook.md, Experiment 3 (E13).
"""

from __future__ import annotations

from arc_lab.core.dataset import Corpus, load_dataset
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.model.trace_spec import TraceSpec
from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.execution.presets import PRESETS

TASK_ID = "3c9b0459"

#: Match the diagnostic depth used on the designed testbed (universal-floor/minimal-complete-floor
#: were probed at depth=4, not their full depth=6 preset -- see EXPERIMENT_LOG.md E13).
DEPTH_OVERRIDE = {"budget.max_depth": 4, "budget.max_pool": 200}


def main() -> None:
    full = load_dataset("arc1-train")
    entries = tuple(e for e in full.entries if e.task.task_id == TASK_ID)
    assert len(entries) == 1, entries
    corpus = Corpus(name=f"arc1-train-{TASK_ID}", entries=entries)

    for name in ("geom", "universal-floor", "minimal-complete-floor"):
        config = PRESETS[name]
        if name != "geom":
            config = apply_overrides(config, DEPTH_OVERRIDE)
        run_spec = RunSpec(config=config, corpus=corpus)
        record = execute(run_spec, trace=TraceSpec(capture_all=True, capture_all_max=100_000))
        results = record.results()
        considered = results.get("search_stats", {}).get("total", {}).get("considered")
        print(
            f"{name}: run_id={record.run_id} solved={results.get('solved')}/"
            f"{results.get('task_count')} considered={considered}"
        )


if __name__ == "__main__":
    main()
