"""Integrity / comparability analysis over the arc-lab run store.

Answers, from the runs themselves rather than from the docs:
  A. Is there, for any ladder, a COMPLETE cell set at a single config generation?
  B. How much compute was paid twice for the same search under two stop modes?
  C. Which runs predate the RunSpec layout entirely (no runspec.json)?
  D. Can a committed report.json number be traced back to the run that produced it?

Read-only. Usage: uv run python run_integrity.py [--repo PATH]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
from typing import Any

from run_census import _fmt, _load, budget_fingerprint, census, classify, engine_fingerprint


def base_budget(cfg: dict[str, Any]) -> str:
    """Budget fingerprint with the stop-mode knobs removed — the SEARCH SPACE, not the stop."""
    b = cfg.get("budget") or {}
    return f"d{b.get('depth_limit')}/pool{b.get('max_pool')}/arity{b.get('max_arity')}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = pathlib.Path(args.repo).resolve()

    rows = census(repo)
    by_id = {r["run_id"]: r for r in rows}

    # reload raw specs for the fields census() flattens away
    specs: dict[str, dict[str, Any]] = {}
    for p in (repo / "runs").glob("**/runspec.json"):
        s = _load(p)
        if s:
            specs[s["run_id"]] = s

    print("=" * 100)
    print("A. IS THERE A COMPLETE, SINGLE-GENERATION CELL SET PER LADDER?")
    print("=" * 100)
    print("   For each ladder: its runs grouped by (commit, base budget). A usable batch")
    print("   of record needs ONE group holding every cell. Multiple groups = the ladder's")
    print("   numbers come from runs made under different machinery/budgets.\n")

    subjects = sorted({r["subject"] for r in rows if r["kind"] == "ladder"})
    tbl = []
    for s in subjects:
        lad = [r for r in rows if r["kind"] == "ladder" and r["subject"] == s]
        groups: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
        for r in lad:
            cfg = (specs.get(r["run_id"]) or {}).get("config") or {}
            groups[(r["commit"], base_budget(cfg))].append(r)
        biggest = max(groups.values(), key=len)
        tbl.append(
            (
                s,
                len(lad),
                len(groups),
                len(biggest),
                f"{len(biggest) / len(lad):.0%}",
                sorted({r["commit"] for r in biggest})[0],
            )
        )
    tbl.sort(key=lambda t: -t[2])
    print(
        _fmt(
            tbl,
            ["ladder", "runs", "#(commit,budget) groups", "largest group", "share", "its commit"],
        )
    )

    print("\n" + "=" * 100)
    print("B. DOUBLE-PAID CELLS — the same search space run under two stop modes")
    print("=" * 100)
    print("   compromise.py: the default is NO compromise 'precisely so one exhaustive run")
    print("   yields three cost quantities at once'. Pairs below mean it was paid twice.\n")

    key_of: dict[tuple, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        if not r["completed"]:
            continue
        cfg = (specs.get(r["run_id"]) or {}).get("config") or {}
        b = cfg.get("budget") or {}
        key = (
            r["subject"],
            r["arm"],
            r["corpus_hash"],
            r["library"],
            r["run_type"],
            base_budget(cfg),
            b.get("considered_limit"),
            engine_fingerprint(cfg),
        )
        key_of[key].append(r)

    dup = {k: v for k, v in key_of.items() if len(v) > 1}
    dup_runs = sum(len(v) - 1 for v in dup.values())
    dup_cost = sum(sum(x["considered"] or 0 for x in v[1:]) for v in dup.values())
    dup_secs = sum(sum(x["seconds"] or 0 for x in v[1:]) for v in dup.values())
    total_cost = sum(r["considered"] or 0 for r in rows if r["completed"])
    total_secs = sum(r["seconds"] or 0 for r in rows if r["completed"])
    print(f"   duplicate-key cell groups : {len(dup)}")
    print(f"   redundant runs            : {dup_runs}  ({dup_runs / len(rows):.0%} of all runs)")
    print(f"   redundant considered      : {dup_cost:,}  ({dup_cost / total_cost:.0%} of all compute)")
    print(f"   redundant wall-clock      : {dup_secs / 60:.0f} min  ({dup_secs / total_secs:.0%})")

    stopmodes = collections.Counter()
    for k, v in dup.items():
        modes = set()
        for r in v:
            b = ((specs.get(r["run_id"]) or {}).get("config") or {}).get("budget") or {}
            modes.add((b.get("solution_limit"), b.get("solution_limit_mode")))
        stopmodes[tuple(sorted(map(str, modes)))] += 1
    print("\n   what differs inside a duplicate group (solution_limit, mode):")
    for m, n in stopmodes.most_common(8):
        print(f"      {n:4}x  {m}")

    print("\n   top duplicate groups by redundant compute:")
    ranked = sorted(dup.items(), key=lambda kv: -sum(x["considered"] or 0 for x in kv[1][1:]))
    print(
        _fmt(
            [
                (
                    k[0][:28],
                    k[1],
                    k[5],
                    len(v),
                    f"{sum(x['considered'] or 0 for x in v[1:]):,}",
                )
                for k, v in ranked[:12]
            ],
            ["ladder", "arm", "budget", "runs", "redundant considered"],
        )
    )

    print("\n" + "=" * 100)
    print("C. PRE-RUNSPEC RUNS — recorded before the run model existed")
    print("=" * 100)
    legacy = [d for d in (repo / "runs").glob("*/*") if d.is_dir() and not (d / "runspec.json").exists()]
    print(f"   run dirs with NO runspec.json: {len(legacy)}")
    if legacy:
        names = collections.Counter(d.name.split("_")[1] if "_" in d.name else "?" for d in legacy)
        print("   by experiment corpus:")
        for n, c in names.most_common():
            print(f"      {c:3}x  {n}")
        print(f"   dates: {sorted({d.parent.name for d in legacy})}")
        print(f"   files present: {sorted({f.name for d in legacy for f in d.iterdir()})}")

    print("\n" + "=" * 100)
    print("D. PROVENANCE — can a committed report be traced to its runs?")
    print("=" * 100)
    art = repo / "docs/abstraction_ladders/ladders"
    missing = []
    for rep_path in sorted(art.glob("*/report.json")):
        raw = rep_path.read_text()
        has = any(tok in raw for tok in ('"run_id"', '"run_ids"', '"commit"', '"run_dir"'))
        if not has:
            missing.append(rep_path.parent.name)
    print(f"   committed reports          : {len(list(art.glob('*/report.json')))}")
    print(f"   with NO run/commit provenance: {len(missing)}")
    print(f"   -> {', '.join(missing[:6])}{' ...' if len(missing) > 6 else ''}")

    print("\n   Consequence: a committed number cannot be re-checked against the run that")
    print("   produced it, and staleness cannot be detected mechanically (the run_ids are")
    print("   content-hashed, but the artifact never records which ones it used).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
