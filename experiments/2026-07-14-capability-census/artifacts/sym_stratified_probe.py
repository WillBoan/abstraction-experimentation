"""Probe: run `sym` on 3 arc1-train tasks stratified by max train-input dimension
(~10 / ~20 / ~30), to read how search cost (considered/deduped/evicted) scales with
grid size under `harvest-from-instance` constants. See notebook.md, Experiment 2.

Task picks (nearest max-dim to the target, scanned from data/arc-agi-1):
  11852cab  max_dim=10  (3 train examples)
  00d62c1b  max_dim=20  (5 train examples)
  1f85a75f  max_dim=30  (2 train examples)
"""

from __future__ import annotations

from arc_lab.core.dataset import Corpus, load_dataset
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.presets import PRESETS

TASK_IDS = ("11852cab", "00d62c1b", "1f85a75f")


def main() -> None:
    full = load_dataset("arc1-train")
    wanted = set(TASK_IDS)
    slice_corpus = Corpus(
        name="arc1-train-sym-dim-stratified",
        entries=tuple(e for e in full.entries if e.task.task_id in wanted),
    )
    assert len(slice_corpus) == len(TASK_IDS), sorted(e.task.task_id for e in slice_corpus.entries)
    run_spec = RunSpec(config=PRESETS["sym"], corpus=slice_corpus)
    record = execute(run_spec)
    print("run_id:", record.run_id)
    print("run_dir:", record.run_dir)


if __name__ == "__main__":
    main()