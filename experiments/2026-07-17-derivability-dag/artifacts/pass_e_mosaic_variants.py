"""Pass E: layout-mosaic design variants (the col_of_3 sibling question).

Compares the doc's current chain design against the sibling-DAG variant:

  chain    : floor -> row3 -> grid3x3 -> grid9x9
  siblings : floor -> {row3, col3} -> grid3x3 -> grid9x9

The question is whether adding col_of_3 as a level-1 sibling makes grid_3x3's
MINIMAL witness route through both rungs (killing the shadowing that made the
chain design's fan-in claim collapse), and whether rung necessity survives.

Run:  uv run python experiments/2026-07-17-derivability-dag/artifacts/pass_e_mosaic_variants.py \
        2>&1 | tee experiments/2026-07-17-derivability-dag/artifacts/pass_e_mosaic_variants.out
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from enumlib import enumerate_pool, find_derivations, target_valid_count  # noqa: E402
from pass_d_ladders import BLOCKS, GRID3X3, GRID9X9, ROW3, comp  # noqa: E402

_f = {n: b.fn for n, b in BLOCKS.items()}
COL3 = comp("col3", ("grid",), lambda g: _f["concat_v"](g, _f["concat_v"](g, g)))

FLOOR = ["concat_h", "concat_v"]
MAX_SIZE = 6

VARIANTS: list[tuple[str, list, list]] = [
    # (name, staged rung additions, goals to track)
    ("chain (doc's current design)", [ROW3, GRID3X3], [ROW3, COL3, GRID3X3, GRID9X9]),
    ("siblings (+col3 at level 1)", [ROW3, COL3, GRID3X3], [ROW3, COL3, GRID3X3, GRID9X9]),
]


def main() -> None:
    for vname, rungs, goals in VARIANTS:
        floor = {n: BLOCKS[n] for n in FLOOR}
        stages = [dict(floor)]
        for r in rungs:
            nxt = dict(stages[-1])
            nxt[r.name] = r
            stages.append(nxt)
        print(f"\n=== {vname} ===")
        print(f"  floor {{{', '.join(FLOOR)}}}; stages: "
              + " -> ".join("L%d=+%s" % (i + 1, r.name) for i, r in enumerate(rungs)))
        t0 = time.time()
        rows: dict[str, list[str]] = {}
        wit: dict[tuple[str, int], str] = {}
        for i, lib in enumerate(stages):
            pools: dict[tuple[str, ...], object] = {}
            for g in goals:
                if target_valid_count(g) < 6:
                    rows.setdefault(g.name, []).append("SKIP")
                    continue
                if g.param_types not in pools:
                    pools[g.param_types] = enumerate_pool(lib, g.param_types, MAX_SIZE)
                pool = pools[g.param_types]
                found = find_derivations(g, pool, lib)
                ds = [d for d in (found[0] if found else []) if d.verified]
                if ds:
                    rows.setdefault(g.name, []).append(str(ds[0].size))
                    wit[(g.name, i)] = ds[0].term
                else:
                    rows.setdefault(g.name, []).append(f">{MAX_SIZE}{'T' if pool.truncated else ''}")
        header = "".join(f"  L{i:<8d}" for i in range(len(stages)))
        print(f"  {'goal':12s}{header}")
        for g in goals:
            print(f"  {g.name:12s}" + "".join(f"  {v:<9s}" for v in rows[g.name]))
        print("  minimal witnesses:")
        for g in goals:
            for i in range(len(stages)):
                w = wit.get((g.name, i))
                if w:
                    print(f"    {g.name} @ L{i}: {w}")
                    break
            # also show the witness at the last stage where it is cheapest
            last = len(stages) - 1
            w_last = wit.get((g.name, last))
            if w_last and w_last != wit.get((g.name, 0)):
                print(f"    {g.name} @ L{last}: {w_last}")
        print(f"  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
