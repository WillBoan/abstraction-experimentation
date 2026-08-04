"""Every search cell recorded on 2026-08-04, keyed on the question the day answered:
does a cell censor, and does that track its DERIVED pool rather than its depth?

Read-side only; walks `runs/2026-08-04/` and prints the two tables in the notebook.
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path("runs/2026-08-04")


def cells() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run_dir in sorted(ROOT.iterdir()):
        try:
            spec = json.loads((run_dir / "runspec.json").read_text())
            results = json.loads((run_dir / "results.json").read_text())
        except (OSError, ValueError):
            continue
        stats = results.get("search_stats")
        if not stats:  # a LEARN run has no funnel
            continue
        budget = spec["config"]["budget"]
        tasks = results.get("task_count") or 0
        rows.append(
            {
                "dir": run_dir.name,
                "corpus": results["corpus_name"],
                "depth": budget["depth_limit"],
                "pool": budget["max_pool"],
                "tasks": tasks,
                "considered": stats["total"]["considered"],
                "guard": (budget.get("considered_limit") or 0) * tasks,
                "censored": bool(stats.get("any_censored")),
            }
        )
    return rows


def main() -> None:
    rows = cells()
    print(f"{'depth':>5} {'pool':>6} {'cells':>6} {'censored':>9}   considered range")
    by_shape: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in rows:
        by_shape.setdefault((int(row["depth"]), int(row["pool"])), []).append(row)
    for (depth, pool), group in sorted(by_shape.items()):
        spend = sorted(int(r["considered"]) for r in group)
        censored = sum(1 for r in group if r["censored"])
        span = f"{spend[0]:,}" if spend[0] == spend[-1] else f"{spend[0]:,} .. {spend[-1]:,}"
        print(f"{depth:>5} {pool:>6} {len(group):>6} {censored:>4}/{len(group):<4} {span}")

    print("\nevery censored cell, against its guard:")
    for row in rows:
        if not row["censored"]:
            continue
        hit = "== guard" if row["considered"] == row["guard"] else "!= guard"
        print(
            f"  {row['corpus']:38s} d={row['depth']} pool={row['pool']:<4} "
            f"{int(row['considered']):>12,} / {int(row['guard']):>12,}  {hit}"
        )

    total = sum(int(r["considered"]) for r in rows)
    censored_spend = sum(int(r["considered"]) for r in rows if r["censored"])
    print(f"\ncells: {len(rows)}  ({Counter(r['censored'] for r in rows)[True]} censored)")
    print(f"considered today:      {total:,}")
    print(f"  censored (unusable): {censored_spend:,}  ({100 * censored_spend / total:.0f}%)")
    print("program history to 2026-08-03: 289,304,962")


if __name__ == "__main__":
    main()
