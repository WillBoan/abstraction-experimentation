"""Full validity + claimability inventory of the 8 real-task ladder reports.

Read-side only. For every member: what stop mode it ran, whether chain and climb
reach the top, which cost quantities are valid under which semantics, and the
per-cohort cost-to-first granularity curve (exact under either stop mode, per the
solution-limit Compromise Option's own registry entry).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"

COHORTS: dict[str, list[tuple[str, int]]] = {
    "dae9d2b5 (pool 30, limit 2M)": [
        ("dae9d2b5-split-halves-lean", 2),
        ("dae9d2b5-split-asym-lean", 3),
        ("dae9d2b5-split-recolor-lean", 4),
    ],
    "94f9d214 (pool 30, limit 2M)": [
        ("94f9d214-nor-halves", 2),
        ("94f9d214-nor-recolor", 4),
    ],
    "fafffa47 (pool 30, limit 2M)": [
        ("fafffa47-nor-halves", 2),
        ("fafffa47-nor-recolor", 4),
    ],
    "dae9d2b5 reference (pool 150)": [
        ("dae9d2b5-split-recolor", 4),
    ],
}


def load(name: str) -> dict:
    return json.loads((LADDERS / name / "report.json").read_text())


def top_row(r: dict) -> dict:
    rows = [x for x in r["cost_matrix"] if x.get("rung") in (None, "", "top")]
    # the top task's row is the one whose task_id has no rung suffix
    rows = [x for x in r["cost_matrix"] if "-" not in x["task_id"]]
    row = rows[0]
    cols = row["columns"]
    return cols[max(cols, key=int)]


def climb_top_solved(r: dict, top_task: str) -> bool:
    return any(top_task in it.get("wake_solved", []) for it in r.get("climb_trace") or [])


for cohort, members in COHORTS.items():
    print(f"\n=== {cohort}")
    hdr = (
        f"{'member':34} {'rungs':>5} {'stop':>10} {'chain-top':>10} {'climb-top':>10}"
        f" {'mrg-first':>10} {'mrg-exh':>10} {'e2e':>10} {'loopov':>7} {'valid?':>26}"
    )
    print(hdr)
    for name, rungs in members:
        r = load(name)
        comp = {c["code"] for c in r.get("compromises", [])}
        stop = "immediate" if "solution-limit" in comp else "exhaust"
        cell = top_row(r)
        top_task = [x["task_id"] for x in r["cost_matrix"] if "-" not in x["task_id"]][0]
        chain_top = (
            "SOLVED"
            if cell["solved"] and not cell["censored"]
            else ("solved+cens" if cell["solved"] else ("CENSORED" if cell["censored"] else "EXHAUST-NO"))
        )
        climb_top = "SOLVED" if climb_top_solved(r, top_task) else "NEVER"
        cost = r["cost"]
        mrg_first = cost.get("laddered_marginal_to_first")
        mrg_exh = cost["laddered_marginal_considered"] if stop == "exhaust" else None
        e2e = cost["laddered_end_to_end_considered"]
        lof = r["comparisons"]["loop_overhead_factor"]
        lof_valid = stop == "exhaust" and cell["solved"] and not cell["censored"]
        verdicts = []
        if not r["certificate"]["admitted"]:
            verdicts.append("NOT-ADMITTED")
        if not cell["solved"]:
            verdicts.append("top-unreached")
        if stop == "immediate":
            verdicts.append("to-first only")
        if not verdicts:
            verdicts.append("fully valid")
        print(
            f"{name:34} {rungs:>5} {stop:>10} {chain_top:>10} {climb_top:>10}"
            f" {mrg_first if mrg_first is not None else '-':>10}"
            f" {mrg_exh if mrg_exh is not None else '-':>10}"
            f" {e2e:>10} {lof:>7.2f} {'; '.join(verdicts):>26}"
        )
        # per-jump to-first detail for the curve
        jtf = cost.get("jump_costs_to_first") or {}
        ttf = cost.get("top_jump_cost_to_first")
        print(f"{'':34}   jumps-to-first: {jtf}  top-to-first: {ttf}")
    print()

print("\n=== RQ1 per cohort (raw arms, sound bounds)")
for name in ("dae9d2b5-split-recolor", "dae9d2b5-split-recolor-lean", "94f9d214-nor-recolor", "fafffa47-nor-recolor"):
    r = load(name)
    arm = r["cost"]["raw_arm"]
    print(
        f"{name:34} ratio>={arm['amortization_ratio']} ({arm['amortization_ratio_kind']})"
        f" guard={arm['guard_per_task']:,} solved={arm['solved']} sound={arm['sound']}"
    )
