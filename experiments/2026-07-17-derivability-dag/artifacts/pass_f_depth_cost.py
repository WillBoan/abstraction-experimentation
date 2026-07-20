"""Pass F: what does a deep jump actually COST? (engine cost-vs-depth on ladder floors)

The design question this answers: the register's ladders all have jump depth 2 and
height <= 3. To build height 4-6 ladders with jump depth 3-5 we need to know where
the affordable `depth_limit` ceiling actually is, per candidate floor -- because
`d_i <= depth_limit` is the binding sandwich constraint.

Drives the REAL engine (`BottomUpSearchEngine`) at increasing `depth_limit` on
candidate param-free floors, on a deliberately unsolvable target (so every run pays
cost-paid-full = the full budgeted space -- the worst case a wake iteration pays).

Run:  uv run python experiments/2026-07-17-derivability-dag/artifacts/pass_f_depth_cost.py \
        2>&1 | tee experiments/2026-07-17-derivability-dag/artifacts/pass_f_depth_cost.out
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.registry import resolve_primitive

sys.path.insert(0, str(Path(__file__).parent))

#: Candidate deep-ladder floors -- all param-free, no constant sources (the cheapest
#: regime; constants are what blew up the `synth` census).
FLOORS: dict[str, tuple[str, ...]] = {
    "d4_gen_min": ("flip_h", "transpose"),
    "concat2": ("concat_h", "concat_v"),
    "quad_floor": ("concat_h", "concat_v", "flip_h", "flip_v"),
    "quad_floor+pad": ("concat_h", "concat_v", "flip_h", "flip_v", "crop_to_content"),
}

DEPTHS = (2, 3, 4, 5, 6)
MAX_POOL = 50_000  # deliberately generous: measure the space, not the pool cap
TIME_BUDGET_S = 90.0  # skip deeper cells for a floor once one cell exceeds this


def probe_grid(h: int, w: int, off: int) -> Grid:
    return Grid(
        np.array(
            [[(r * 1 + c * 2 + off) % 10 for c in range(w)] for r in range(h)],
            dtype=np.int8,
        )
    )


def main() -> None:
    engine = BottomUpSearchEngine(
        constant_sources=(),  # param-free floors: no constant leaves
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )
    cost = ProgramSize()
    # An unreachable target (a differently-sized noise grid): forces cost-paid-full.
    examples = tuple(
        Example(input=probe_grid(2, 3, off), output=probe_grid(5, 7, off + 1))
        for off in (0, 1)
    )
    print(f"{'floor':16s}{'depth':>7s}{'considered':>14s}{'pool':>10s}{'ratio':>9s}{'secs':>9s}")
    for fname, prim_names in FLOORS.items():
        library = Library(
            name=fname, primitives=tuple(resolve_primitive(n) for n in prim_names)
        )
        prev = None
        for depth in DEPTHS:
            budget = Budget(depth_limit=depth, max_arity=2, max_pool=MAX_POOL)
            t0 = time.time()
            result = engine.run(
                train_examples=examples,
                library=library,
                constraints=(),
                cost=cost,
                budget=budget,
            )
            dt = time.time() - t0
            considered = result.stats.considered
            gens = result.stats.generations
            pool = gens[-1].get("pool_size_after", -1) if gens else -1
            ratio = f"{considered / prev:.1f}x" if prev else "-"
            print(
                f"{fname:16s}{depth:>7d}{considered:>14,d}{pool:>10}{ratio:>9s}{dt:>8.1f}s",
                flush=True,
            )
            prev = considered
            if dt > TIME_BUDGET_S:
                print(f"{'':16s}{'':>7s}(stopping this floor: cell exceeded "
                      f"{TIME_BUDGET_S:.0f}s)", flush=True)
                break


if __name__ == "__main__":
    main()
