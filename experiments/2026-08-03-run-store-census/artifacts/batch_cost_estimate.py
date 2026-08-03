"""What would a batch of record actually cost?

For each ladder, take the largest coherent `(commit, base budget)` group in the store
and sum its wall clock — an estimate of one full pass over that ladder under a single
config generation. Answers the question the planning discussion kept guessing at.

Read-only. Usage: uv run python batch_cost_estimate.py [--repo PATH]
"""

from __future__ import annotations

import argparse
import collections
import pathlib

from run_census import _fmt, census

#: Everything with a committed report, plus the two designed-censored NOR members.
BATCH = [
    "al1-mirror",
    "al2-rot90-calibration",
    "al15-shift-frame",
    "al16-layout-nest",
    "al17-shift-frame-tall",
    "al18-fanin-rotate",
    "al19-fanin-recolor",
    "al20-recolor-telescope",
    "al21-dag-siblings",
    "dae9d2b5-split-recolor",
    "dae9d2b5-split-recolor-lean",
    "dae9d2b5-split-halves-lean",
    "dae9d2b5-split-asym-lean",
    "dae9d2b5-half-param",
    "94f9d214-nor-merged",
    "94f9d214-nor-recolor",
    "94f9d214-nor-halves",
    "fafffa47-nor-merged",
    "fafffa47-nor-recolor",
    "fafffa47-nor-halves",
]

#: Rejected ladders + controls: runs exist, no committed report.json.
UNREPORTED = [
    "al3-quad-symmetrize",
    "al4-mask-crop",
    "al6-mirror-tall",
    "al7-fast-tower",
    "al8-lean-perceiver",
    "al13-symmetry-repair",
    "al14-cell-row-grid",
    "al9-decoy",
    "al10-skippable",
    "al11-greedy-trap",
    "al12-unlearnable",
]


def estimate(rows: list[dict], names: list[str]) -> tuple[list[tuple], float]:
    out, total = [], 0.0
    for name in names:
        rs = [
            r
            for r in rows
            if r["kind"] == "ladder" and r["subject"] == name and r["completed"]
        ]
        groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
        for r in rs:
            groups[(r["commit"], r["budget"].split("/clim")[0])].append(r)
        if not groups:
            out.append((name, 0, "-", "no completed runs"))
            continue
        key, best = max(groups.items(), key=lambda kv: len(kv[1]))
        wall = sum(r["seconds"] or 0.0 for r in best)
        total += wall
        out.append((name, len(best), f"{wall:.0f}s", f"{key[0]} {key[1]}"))
    return out, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="../../..")
    args = ap.parse_args()
    rows = census(pathlib.Path(args.repo).resolve())

    print("ONE FULL PASS PER LADDER, estimated from its largest coherent run group\n")
    print("## Ladders with a committed report.json\n")
    tbl, total = estimate(rows, BATCH)
    print(_fmt(tbl, ["ladder", "cells", "wall", "largest (commit, budget) group"]))
    print(f"\n   subtotal: {total / 60:.0f} min")

    print("\n## Rejected ladders + controls (runs on disk, NO committed report)\n")
    tbl2, total2 = estimate(rows, UNREPORTED)
    print(_fmt(tbl2, ["ladder", "cells", "wall", "largest (commit, budget) group"]))
    print(f"\n   subtotal: {total2 / 60:.0f} min")

    done = [r for r in rows if r["completed"]]
    print(f"\n## Context\n")
    print(f"   estimated batch of record (both sets) : {(total + total2) / 60:.0f} min")
    print(f"   ALL {len(rows)} runs ever recorded      : "
          f"{sum(r['seconds'] or 0.0 for r in done) / 3600:.2f} h")
    print(f"   total candidates ever considered      : "
          f"{sum(r['considered'] or 0 for r in done):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
