"""The base-width tax, measured from data already on disk.

Question: at FIXED depth, what does adding one rung to the library cost?

Evidence source 1 -- within-chain library growth: in an exhaustive all-d2 member
(`dae9d2b5-split-recolor-lean`, and its pool-150 twin `dae9d2b5-split-recolor`),
every cost-matrix cell at level L_i is a depth-2 exhaustive enumeration over
floor + i rungs. Reading one task's `considered` across L_0..L_4 is therefore a
direct measurement of d2 space size as a function of library size -- many cells,
order-independent (exhaustion, not to-first).

Evidence source 2 -- the same read over the admitted synthetic batch (exhaustive,
uncompromised), for breadth of floors/arities.

Also prints `b_eff` (the report's effective branching factor) per cell where present.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"

EXHAUSTIVE_REAL = ("dae9d2b5-split-recolor-lean", "dae9d2b5-split-recolor")
SYNTH = (
    "al1-mirror",
    "al2-rot90-calibration",
    "al15-shift-frame",
    "al16-layout-nest",
    "al17-shift-frame-tall",
    "al18-fanin-rotate",
    "al19-fanin-recolor",
    "al20-recolor-telescope",
    "al21-dag-siblings",
)


def show(name: str) -> None:
    p = LADDERS / name / "report.json"
    if not p.exists():
        print(f"== {name}: NO REPORT")
        return
    r = json.loads(p.read_text())
    comp = {c["code"] for c in r.get("compromises", [])}
    if comp:
        print(f"== {name}: SKIP (compromised: {sorted(comp)})")
        return
    print(f"== {name}")
    # one representative task per rung + the top; considered per library level
    seen_rungs: set[str] = set()
    for row in r["cost_matrix"]:
        rung = row.get("rung") or "TOP"
        if rung in seen_rungs:
            continue
        seen_rungs.add(rung)
        cols = row["columns"]
        levels = sorted(cols, key=int)
        cons = [cols[lv]["considered"] for lv in levels]
        cens = ["C" if cols[lv]["censored"] else "." for lv in levels]
        ratios = [
            f"{cons[i + 1] / cons[i]:.2f}x" if cons[i] else "-"
            for i in range(len(cons) - 1)
        ]
        beffs = [cols[lv].get("b_eff") for lv in levels]
        print(f"  {row['task_id']:22} considered/level: {cons}  censored: {''.join(cens)}")
        print(f"  {'':22} growth per added rung: {ratios}")
        print(f"  {'':22} b_eff/level: {[f'{b:.1f}' if b else '-' for b in beffs]}")
    print()


for name in EXHAUSTIVE_REAL:
    show(name)
print("---- synthetics (exhaustive, admitted) ----")
for name in SYNTH:
    show(name)
