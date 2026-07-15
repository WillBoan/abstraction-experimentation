"""Probe: isolate the designed 3x3 rot180 task alone (dropping the far more expensive 10x10 from
the corpus) and push `minimal-complete-floor`'s depth further than the earlier 3/4/5 sweep, to see
whether depth alone (max_pool already ruled out) is what's blocking a solve. See notebook.md.
"""

from __future__ import annotations

import sys

from arc_lab.core.dataset import Corpus, load_testbed
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.model.trace_spec import TraceSpec
from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.execution.presets import PRESETS


def main() -> None:
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    full = load_testbed("grain-contrast")
    entries = tuple(e for e in full.entries if e.task.task_id == "grain-rot180-3x3")
    assert len(entries) == 1, entries
    corpus = Corpus(name="grain-contrast-3x3-only", entries=entries)

    config = apply_overrides(
        PRESETS["minimal-complete-floor"],
        {"budget.max_depth": depth, "budget.max_pool": 200},
    )
    run_spec = RunSpec(config=config, corpus=corpus)
    record = execute(run_spec, trace=TraceSpec(capture_all=True, capture_all_max=3_000_000))
    results = record.results()
    considered = results.get("search_stats", {}).get("total", {}).get("considered")
    print(f"depth={depth} run_id={record.run_id} solved={results.get('solved')}/1 considered={considered}")


if __name__ == "__main__":
    main()
