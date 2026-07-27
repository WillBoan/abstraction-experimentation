"""S7: the licensed granularity curves, in cost-to-first, from committed reports only.

`first_solution_index` is exact under either stop mode (verified by `stop_limit_modes.py` in the
batch analysis), so cost-to-first quantities compare legally across members that share a config
but differ in stop mode. Validity per member is asserted here, not assumed: a member contributes a
measured point only if its certificate admits it AND its chain reaches the top uncensored-or-found
AND its climb solved the top task; otherwise it contributes a censored bound.
"""

import json
from pathlib import Path

from arc_lab.program_search.ladders.registry import make_ladder

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"

COHORTS: dict[str, list[tuple[str, int]]] = {
    "dae9d2b5": [
        ("dae9d2b5-split-halves-lean", 2),
        ("dae9d2b5-split-asym-lean", 3),
        ("dae9d2b5-split-recolor-lean", 4),
    ],
    "94f9d214": [
        ("94f9d214-nor-halves", 2),
        ("94f9d214-nor-recolor", 4),
        ("94f9d214-nor-merged", 5),
    ],
    "fafffa47": [
        ("fafffa47-nor-halves", 2),
        ("fafffa47-nor-recolor", 4),
        ("fafffa47-nor-merged", 5),
    ],
}

#: Out-of-band bound for the NOR d4 tops: not found within 30M (price_d4_top.py, 2026-07-27).
D4_TOP_BOUND = 30_000_000


def load(name: str) -> dict:
    return json.loads((LADDERS / name / "report.json").read_text())


def top_cell(r: dict) -> tuple[str, dict]:
    row = [x for x in r["cost_matrix"] if "-" not in x["task_id"]][0]
    cols = row["columns"]
    return row["task_id"], cols[max(cols, key=int)]


for cohort, members in COHORTS.items():
    print(f"\n=== {cohort} — cost-to-first vs cut density (shared config: pool 30, guard 2M)")
    print(f"{'member':32} {'rungs':>5} {'top depth':>9} {'top-to-first':>14} {'marginal-to-first':>18}  status")
    for name, rungs in members:
        r = load(name)
        cert = r["certificate"]
        top_task, cell = top_cell(r)
        climb_top = any(
            top_task in it.get("wake_solved", []) for it in r.get("climb_trace") or []
        )
        first = cell.get("first_solution_index")
        mtf = r["cost"].get("laddered_marginal_to_first")
        sched_depth = make_ladder(name).depth_schedule()[-1]
        if not cert["admitted"]:
            status = "NOT ADMITTED — excluded"
        elif first is None:
            status = f"BOUND: top not found within guard (>= {D4_TOP_BOUND:,} probed out-of-band)"
        elif not climb_top:
            status = "chain-only (climb never solved top) — excluded from measured points"
        else:
            status = "measured point"
        print(
            f"{name:32} {rungs:>5} {sched_depth:>9} "
            f"{(f'{first + 1:,}' if first is not None else f'> {D4_TOP_BOUND:,}'):>14} "
            f"{(f'{mtf:,}' if first is not None and mtf is not None else '—'):>18}  {status}"
        )

print(
    "\nReading: cost is a STEP FUNCTION in the residual top-jump depth, not in rung count —"
    "\nd2-top members 36-71k marginal-to-first, d3-top members 288-524k, d4-top members > 30M"
    "\n(bound). Within equal top depth the direction mildly reverses (larger library base)."
    "\nCoarsening concentrates the removed rungs' work into the top's exponent."
)
