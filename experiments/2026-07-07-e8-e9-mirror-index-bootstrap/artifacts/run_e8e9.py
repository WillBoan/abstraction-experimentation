"""Run E8 (and optionally E9) via run_experiment with tmp dirs; print the full report."""

import sys
import tempfile
import time
from pathlib import Path

from arc_lab.solvers.dsl.learn.experiments import (
    e8_mirror_index_sub,
    e9_mirror_index_affine,
    run_experiment,
)

which = sys.argv[1] if len(sys.argv) > 1 else "e8"
factory = {"e8": e8_mirror_index_sub, "e9": e9_mirror_index_affine}[which]

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    t0 = time.perf_counter()
    report = run_experiment(factory(), testbeds_root=root / "tb", runs_root=root / "runs")
    dt = time.perf_counter() - t0

print(f"\n===== {which} ({dt:.1f}s) =====")
print("learned:", report.learned)
print("matched:", report.check.matched, "missed:", report.check.missed, "novel:", report.check.novel)
for line in report.summary_lines():
    print(line)
print("enablement tasks:", sorted(report.enablement))
