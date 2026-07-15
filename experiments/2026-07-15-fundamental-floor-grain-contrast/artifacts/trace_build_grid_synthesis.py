"""Instrumented repro: trace `_select_frontier` (actual pool size before truncation) and
`_synthesize_for_hole` (how many times build_grid's hole synthesis is invoked, and how many
Lam candidates it yields) for the isolated 3x3 grain-contrast task under minimal-complete-floor.
Monkey-patches the engine from outside -- no source edits to revert. See notebook.md.
"""

from __future__ import annotations

import sys

from arc_lab.core.dataset import Corpus, load_testbed
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.model.trace_spec import TraceSpec
from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine

_original_select_frontier = BottomUpSearchEngine._select_frontier
_frontier_calls = []


def _traced_select_frontier(self, pool, budget, state):
    before = pool.size()
    result = _original_select_frontier(self, pool, budget, state)
    after = result.size()
    _frontier_calls.append((before, after, budget.max_pool))
    return result


_original_synth_hole = BottomUpSearchEngine._synthesize_for_hole
_synth_calls = []


def _traced_synth_hole(self, primitive, hole, return_type, sibling_values, scope, budget, state, enclosing_target):
    results = list(
        _original_synth_hole(
            self, primitive, hole, return_type, sibling_values, scope, budget, state, enclosing_target
        )
    )
    _synth_calls.append((primitive.name, budget.max_depth, len(results), [str(p) for p, _ in results]))
    yield from results


BottomUpSearchEngine._select_frontier = _traced_select_frontier
BottomUpSearchEngine._synthesize_for_hole = _traced_synth_hole


def main() -> None:
    max_pool = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    full = load_testbed("grain-contrast")
    entries = tuple(e for e in full.entries if e.task.task_id == "grain-rot180-3x3")
    corpus = Corpus(name="grain-contrast-3x3-only", entries=entries)
    config = apply_overrides(
        PRESETS["minimal-complete-floor"], {"budget.max_depth": 6, "budget.max_pool": max_pool}
    )
    run_spec = RunSpec(config=config, corpus=corpus)
    record = execute(run_spec, trace=TraceSpec(capture_all=False), force_recapture=True)
    results = record.results()
    print("solved=", results.get("solved"), "/1")
    print()
    print(f"_synthesize_for_hole invoked {len(_synth_calls)} times:")
    for name, max_depth, n_yielded, progs in _synth_calls:
        print(f"  primitive={name} recursive_budget.max_depth={max_depth} yielded={n_yielded} {progs}")
    print()
    print(f"_select_frontier invoked {len(_frontier_calls)} times:")
    for before, after, cap in _frontier_calls:
        marker = " <-- TRUNCATED" if before > cap else ""
        print(f"  before={before} after={after} cap={cap}{marker}")


if __name__ == "__main__":
    main()
