"""Scratchpad: run the compression<->transfer correlation over E1-E9 and print the scatter.

Also runs an E8 naive-proposer variant to exhibit the divergence itself: the naive
FrequentSubtree proposer compresses train MORE while the (reusability) grade does NOT follow.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

from arc_lab.solvers.dsl.learn.antiunify import FrequentSubtree
from arc_lab.solvers.dsl.learn.experiments import (
    compression_transfer_correlation,
    e8_mirror_index_sub,
    run_experiment,
)

NAMES = [
    "e1-rot90",
    "e2-swap-cells",
    "e3-swap-cols",
    "e4-swap-cols-mdl",
    "e5-rederive-rot90",
    "e6-rederive-d4",
    "e7-rederive-d4-safe",
    "e8-mirror-index-sub",
    "e9-mirror-index-affine",
]

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    points = compression_transfer_correlation(
        NAMES, testbeds_root=root / "testbeds", runs_root=root / "runs"
    )

    print(f"{'experiment':<22}{'compress':>10}{'transfer':>10}{'tr_speedup':>12}{'learned':>9}")
    print("-" * 63)
    for p in points:
        print(
            f"{p.name:<22}{p.compression:>10.2f}{p.transfer:>10d}"
            f"{p.train_speedup:>12.2f}{p.learned:>9d}"
        )

    # The divergence itself: E8 with the *naive* frequent-subtree proposer (no search-scoping).
    print("\n-- E8 divergence: naive vs. search-scoped proposer --")
    naive = replace(e8_mirror_index_sub(), proposer=FrequentSubtree())
    scoped = e8_mirror_index_sub()
    for label, exp in (("naive", naive), ("scoped", scoped)):
        r = run_experiment(exp, testbeds_root=root / "tb2", runs_root=root / "runs2")
        base, learned = r.compare["L1"], r.compare["L2"]
        comp = base.description_length / learned.description_length
        print(
            f"  {label:<7} compress x{comp:>5.2f}  "
            f"transfer(grade)={len(r.heldout)}  train_speedup x{r.usefulness.speedup:>5.2f}  "
            f"learned={[n for n, _ in r.learned]}"
        )
