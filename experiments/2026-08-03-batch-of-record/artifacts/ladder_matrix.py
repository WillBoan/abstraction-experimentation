"""The ladder cell matrix: what has been run, per ladder, per cell, per arm.

The run census answers "what is in the store". This answers the question above it: for each
LADDER, which of its CELLS exist, under which ARM, and what is missing. Sources:

  - the registry           -> the ladders that could be run
  - committed report.json  -> the batch of record's cells (via `provenance`, 2026-08-03)
  - runs/                  -> everything else, including arms and historical runs

Read-only. Usage: uv run python ladder_matrix.py [--repo PATH]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
from typing import Any

CELL_ORDER = ["chain/L*", "climb/learn", "climb/train-usefulness", "climb/transfer",
              "off-chain", "raw-arm"]


def _fmt(rows: list[tuple[Any, ...]], headers: list[str]) -> str:
    cols = list(zip(*([tuple(headers)] + rows))) if rows else [(h,) for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    out = ["  ".join(str(h).ljust(w) for h, w in zip(headers, widths)),
           "  ".join("-" * w for w in widths)]
    out += ["  ".join(str(c).ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def load_runs(repo: pathlib.Path) -> list[dict[str, Any]]:
    """Every recorded run, with its ladder / cell-kind / learn-metric decoded from the runspec."""
    rows = []
    for path in sorted((repo / "runs").glob("**/runspec.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        corpus = str(spec.get("corpus_name", ""))
        config = spec.get("config") or {}
        learn = config.get("learn")
        metric = None
        if isinstance(learn, dict):
            engine = learn.get("learn_engine") or {}
            metric = (engine.get("metric") or {}).get("kind")
        parts = corpus.split(":")
        if parts[0] == "probe":
            ladder, cell = (parts[1] if len(parts) > 1 else "?"), "probe"
        elif "raw-arm" in parts:
            ladder, cell = parts[0], "raw-arm"
        elif "heldout" in parts:
            ladder, cell = parts[0], "heldout-search"
        elif "train" in parts:
            ladder, cell = parts[0], ("LEARN" if learn else "train-search")
        else:
            ladder, cell = parts[0], "corpus"
        rows.append({
            "run_id": spec.get("run_id"), "ladder": ladder, "cell": cell,
            "library": (config.get("library") or {}).get("name"),
            "metric": metric, "corpus": corpus,
            "completed": (path.parent / "results.json").is_file(),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = pathlib.Path(args.repo).resolve()

    registry = sorted(p.stem for p in (repo / "src/arc_lab/program_search/ladders/registry").glob("*.ladder"))
    runs = load_runs(repo)
    art_dir = repo / "docs/abstraction_ladders/ladders"
    reports = {p.parent.name: json.loads(p.read_text()) for p in art_dir.glob("*/report.json")}

    print("=" * 104)
    print("LADDER CELL MATRIX")
    print("=" * 104)

    # --- 1. registry coverage
    ran = {r["ladder"] for r in runs}
    print(f"\n## 1. Registry coverage: {len(registry)} ladders authored\n")
    never = [n for n in registry if n not in ran]
    probed_only = [n for n in registry
                   if n in ran and not any(r["ladder"] == n and r["cell"] != "probe" for r in runs)]
    committed = sorted(reports)
    print(f"   with a committed report.json (the batch of record) : {len(committed)}")
    print(f"   probed only, never run                             : {len(probed_only)} {probed_only}")
    print(f"   never touched at all                               : {len(never)} {never}")

    # --- 2. the batch of record, cell by cell
    print(f"\n## 2. The batch of record -- cells per ladder (from committed `provenance`)\n")
    rows = []
    for name in sorted(reports):
        prov = reports[name].get("provenance") or []
        kinds = collections.Counter(
            "chain/L*" if str(p["cell"]).startswith("chain/") else p["cell"] for p in prov
        )
        rows.append((
            name,
            kinds.get("chain/L*", 0),
            "y" if kinds.get("climb/learn") else "-",
            "y" if kinds.get("climb/train-usefulness") else "-",
            "y" if kinds.get("climb/transfer") else "-",
            "y" if kinds.get("off-chain") else "-",
            "y" if kinds.get("raw-arm") else "-",
            len(prov),
        ))
    print(_fmt(rows, ["ladder", "chain", "learn", "train-use", "transfer", "off-chain", "raw", "cells"]))
    print(f"\n   total cells in the batch of record: {sum(r[-1] for r in rows)}")

    # --- 3. arms
    print("\n## 3. Arms -- which LEARN configurations have been run, per ladder\n")
    metrics = collections.defaultdict(set)
    for r in runs:
        if r["metric"]:
            metrics[r["ladder"]].add(r["metric"])
    all_metrics = sorted({m for s in metrics.values() for m in s})
    rows = []
    for name in sorted(reports):
        have = metrics.get(name, set())
        rows.append((name, *["y" if m in have else "-" for m in all_metrics]))
    print(_fmt(rows, ["ladder", *all_metrics]))
    climbers = [n for n in sorted(reports) if (reports[n].get("rung_recovery") or [])]
    print(f"\n   ladders that CLIMB (a metric arm is meaningful): {len(climbers)}")
    print(f"   ladders that never climb (rejected -> metric inert): {len(reports) - len(climbers)}")

    # --- 4. proposer arms
    print("\n## 4. Proposer arms (the S15 axis) -- from the store\n")
    props = collections.defaultdict(set)
    for path in sorted((repo / "runs").glob("**/runspec.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        learn = (spec.get("config") or {}).get("learn")
        if not isinstance(learn, dict):
            continue
        engine = learn.get("learn_engine") or {}
        kind = (engine.get("proposer") or {}).get("kind")
        ladder = str(spec.get("corpus_name", "")).split(":")[0]
        if kind:
            props[kind].add(ladder)
    for kind, ladders in sorted(props.items(), key=lambda kv: -len(kv[1])):
        shown = sorted(ladders)
        print(f"   {kind:28} {len(ladders):3} ladders  {shown if len(shown) <= 4 else shown[:4] + ['...']}")

    # --- 5. gaps
    print("\n## 5. Gaps\n")
    gaps = []
    for name in sorted(reports):
        rep = reports[name]
        prov = rep.get("provenance") or []
        kinds = {str(p["cell"]) for p in prov}
        recovery = rep.get("rung_recovery") or []
        reach = rep.get("top_reachable") or {}
        if not any(k.startswith("climb/") for k in kinds):
            gaps.append((name, "no climb", "certificate rejected -> learning never paid for (by design)"))
        if "raw-arm" not in kinds and recovery:
            gaps.append((name, "no raw arm", "RQ1 cited from its cohort sibling (once per cohort)"))
        if "climb/transfer" not in kinds and any(k.startswith("climb/") for k in kinds):
            gaps.append((name, "no transfer run", "no heldout corpus declared for this ladder"))
        if reach.get("chain") is None:
            gaps.append((name, "top unreachable (chain)", "censored -- priced >30M for the d4 tops"))
        elif reach.get("chain") is False:
            gaps.append((name, "top NOT reached (chain)", "the oracle chain cannot solve its own goal"))
        if recovery and reach.get("climb") is None:
            gaps.append((name, "top unreachable (climb)", "the learned library never solved the goal"))
    by_kind = collections.defaultdict(list)
    for name, kind, why in gaps:
        by_kind[(kind, why)].append(name)
    for (kind, why), names in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"   {kind:26} {len(names):3}  -- {why}")
        print(f"      {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
