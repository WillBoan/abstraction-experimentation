"""Comprehensive census of the arc-lab `runs/` store.

Walks every recorded run, parses `runspec.json` (identity + config) and `results.json`
(outcome), classifies each run by kind / ladder / arm, and writes a flat CSV plus a
set of rollups. Read-only: touches nothing under `runs/`.

Usage:  uv run python run_census.py [--repo PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys
from typing import Any

# ---------------------------------------------------------------- parsing


def _load(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        with path.open() as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def classify(corpus_name: str) -> tuple[str, str, str]:
    """(kind, subject, arm) from a corpus name.

    Corpus naming, as observed in the store:
      probe:<ladder>:<library>[:pruned]:<task>   -> a per-rung probe cell
      <ladder>:train | :heldout [ :raw-arm ]     -> a ladder chain/climb/raw cell
      <dataset|testbed>[:split]                  -> a plain search/learn corpus
    """
    parts = corpus_name.split(":")
    if parts[0] == "probe":
        ladder = parts[1] if len(parts) > 1 else "?"
        arm = "pruned" if "pruned" in parts else "probe"
        return "probe", ladder, arm
    subject = parts[0]
    tail = parts[1:]
    if "raw-arm" in tail:
        return "ladder", subject, "raw-arm"
    if "heldout" in tail:
        return "ladder", subject, "heldout"
    if "train" in tail:
        return "ladder", subject, "train"
    return "corpus", subject, ":".join(tail) or "-"


def budget_fingerprint(cfg: dict[str, Any]) -> str:
    """The cost-relevant budget knobs, as one comparable token."""
    b = cfg.get("budget") or {}
    return (
        f"d{b.get('depth_limit')}"
        f"/pool{b.get('max_pool')}"
        f"/arity{b.get('max_arity')}"
        f"/clim{b.get('considered_limit')}:{b.get('considered_limit_mode')}"
        f"/slim{b.get('solution_limit')}:{b.get('solution_limit_mode')}"
    )


def engine_fingerprint(cfg: dict[str, Any]) -> str:
    e = cfg.get("search_engine") or {}
    return (
        f"{e.get('kind')}"
        f"/const={','.join(e.get('constant_sources') or []) or 'none'}"
        f"/fill={e.get('function_hole_fill_mode')}"
        f"/poly={e.get('polymorphism_instantiation')}"
        f"/allow={len(e.get('constant_allowlist') or [])}"
    )


def learn_fingerprint(cfg: dict[str, Any]) -> tuple[str, str, str, str]:
    """(engine, proposer, metric, iterations) — '-' for SEARCH runs."""
    ln = cfg.get("learn")
    if not ln:
        return "-", "-", "-", "-"
    le = ln.get("learn_engine") or {}
    metric = (le.get("metric") or {}).get("kind", "?")
    proposer = (le.get("proposer") or {}).get("kind", "?")
    return le.get("kind", "?"), proposer, metric, str(ln.get("iterations"))


def outcome(results: dict[str, Any] | None) -> dict[str, Any]:
    if results is None:
        return {
            "completed": False,
            "solved": None,
            "task_count": None,
            "considered": None,
            "censored": None,
            "stopped_early": None,
            "seconds": None,
            "first_solution_index": None,
        }
    stats = results.get("search_stats") or {}
    total = stats.get("total") or {}
    tasks = results.get("tasks") or []
    fsi = [
        t.get("first_solution_index")
        for t in tasks
        if isinstance(t.get("first_solution_index"), int)
    ]
    return {
        "completed": True,
        "solved": results.get("solved"),
        "task_count": results.get("task_count"),
        "considered": total.get("considered"),
        "censored": stats.get("any_censored"),
        "stopped_early": stats.get("any_stopped_early"),
        "seconds": round(sum(t.get("seconds") or 0.0 for t in tasks), 3),
        "first_solution_index": min(fsi) if fsi else None,
    }


# ---------------------------------------------------------------- census


def census(repo: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runs_dir = repo / "runs"
    for spec_path in sorted(runs_dir.glob("**/runspec.json")):
        spec = _load(spec_path)
        if spec is None:
            continue
        run_dir = spec_path.parent
        cfg = spec.get("config") or {}
        corpus = spec.get("corpus_name", "?")
        kind, subject, arm = classify(corpus)
        lengine, proposer, metric, iters = learn_fingerprint(cfg)
        rel = run_dir.relative_to(repo)
        # date folder, tolerating the legacy flat layout
        date = rel.parts[1] if len(rel.parts) > 2 else "flat"
        rows.append(
            {
                "run_id": spec.get("run_id"),
                "date": date,
                "started_at": spec.get("run_started_at"),
                "commit": (spec.get("commit") or "")[:8],
                "kind": kind,
                "subject": subject,
                "arm": arm,
                "corpus_name": corpus,
                "corpus_hash": spec.get("corpus_hash"),
                "spec_task_count": spec.get("task_count"),
                "library": (cfg.get("library") or {}).get("name"),
                "n_primitives": len((cfg.get("library") or {}).get("primitives") or []),
                "run_type": "LEARN" if cfg.get("learn") else "SEARCH",
                "budget": budget_fingerprint(cfg),
                "engine": engine_fingerprint(cfg),
                "learn_engine": lengine,
                "proposer": proposer,
                "metric": metric,
                "iterations": iters,
                "attempts_per_test": cfg.get("attempts_per_test"),
                "n_constraints": len(cfg.get("constraints") or []),
                "cost": (cfg.get("cost") or {}).get("kind"),
                "dir": str(rel),
                **outcome(_load(run_dir / "results.json")),
            }
        )
    return rows


# ---------------------------------------------------------------- rollups


def _fmt(rows: list[tuple[Any, ...]], headers: list[str]) -> str:
    cols = list(zip(*([tuple(headers)] + rows))) if rows else [(h,) for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    out = ["  ".join(str(h).ljust(w) for h, w in zip(headers, widths))]
    out.append("  ".join("-" * w for w in widths))
    for r in rows:
        out.append("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    return "\n".join(out)


def rollups(rows: list[dict[str, Any]], repo: pathlib.Path) -> str:
    out: list[str] = []
    P = out.append

    P("=" * 100)
    P(f"RUN CENSUS — {len(rows)} recorded runs under runs/")
    P("=" * 100)

    # --- 1. by kind x run_type
    P("\n## 1. Runs by kind and type\n")
    kt = collections.Counter((r["kind"], r["run_type"]) for r in rows)
    P(
        _fmt(
            [(k, t, n) for (k, t), n in sorted(kt.items(), key=lambda x: -x[1])],
            ["kind", "type", "runs"],
        )
    )

    # --- 2. by date + commit
    P("\n## 2. Runs by date (and the commits that produced them)\n")
    by_date: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)
    tbl = []
    for d in sorted(by_date):
        rs = by_date[d]
        commits = sorted({r["commit"] for r in rs if r["commit"]})
        tbl.append(
            (
                d,
                len(rs),
                sum(1 for r in rs if r["kind"] == "probe"),
                sum(1 for r in rs if r["kind"] == "ladder"),
                sum(1 for r in rs if r["run_type"] == "LEARN"),
                sum(1 for r in rs if not r["completed"]),
                len(commits),
                ",".join(commits[:3]) + ("..." if len(commits) > 3 else ""),
            )
        )
    P(
        _fmt(
            tbl,
            ["date", "runs", "probe", "ladder", "LEARN", "incomplete", "#commits", "commits"],
        )
    )

    # --- 3. incomplete runs
    inc = [r for r in rows if not r["completed"]]
    P(f"\n## 3. Incomplete runs (no results.json — crashed or interrupted): {len(inc)}\n")
    if inc:
        P(
            _fmt(
                [(r["date"], r["run_id"], r["kind"], r["subject"], r["arm"]) for r in inc[:40]],
                ["date", "run_id", "kind", "subject", "arm"],
            )
        )

    # --- 4. per-ladder inventory
    P("\n## 4. Per-ladder inventory (ladder-corpus runs only; probes counted separately)\n")
    subjects = sorted({r["subject"] for r in rows if r["kind"] in ("ladder", "probe")})
    tbl = []
    for s in subjects:
        lad = [r for r in rows if r["kind"] == "ladder" and r["subject"] == s]
        prb = [r for r in rows if r["kind"] == "probe" and r["subject"] == s]
        if not lad and not prb:
            continue
        arms = collections.Counter(r["arm"] for r in lad)
        budgets = {r["budget"] for r in lad}
        commits = {r["commit"] for r in lad + prb if r["commit"]}
        dates = sorted({r["date"] for r in lad + prb})
        tbl.append(
            (
                s,
                len(lad),
                len(prb),
                arms.get("train", 0),
                arms.get("heldout", 0),
                arms.get("raw-arm", 0),
                sum(1 for r in lad if r["run_type"] == "LEARN"),
                len(budgets),
                len(commits),
                f"{dates[0]}..{dates[-1]}" if dates else "-",
            )
        )
    P(
        _fmt(
            tbl,
            [
                "ladder",
                "ladder-runs",
                "probes",
                "train",
                "heldout",
                "raw",
                "LEARN",
                "#budgets",
                "#commits",
                "dates",
            ],
        )
    )

    # --- 5. config drift within a ladder
    P("\n## 5. CONFIG DRIFT — ladders whose runs span more than one budget fingerprint\n")
    P("   (cells under different budgets are not cost-comparable; see the 25.4x pool result)\n")
    for s in subjects:
        lad = [r for r in rows if r["kind"] == "ladder" and r["subject"] == s]
        budgets = collections.Counter(r["budget"] for r in lad)
        if len(budgets) > 1:
            P(f"  {s}  ({len(lad)} runs, {len(budgets)} budgets)")
            for b, n in budgets.most_common():
                dates = sorted({r["date"] for r in lad if r["budget"] == b})
                P(f"      {n:3}x  {b}   [{','.join(dates)}]")

    # --- 6. learn-side config census
    P("\n## 6. LEARN runs — proposer / metric / engine census\n")
    lrn = [r for r in rows if r["run_type"] == "LEARN"]
    lc = collections.Counter((r["proposer"], r["metric"], r["iterations"]) for r in lrn)
    P(
        _fmt(
            [(p, m, i, n) for (p, m, i), n in lc.most_common()],
            ["proposer", "metric", "iterations", "runs"],
        )
    )

    # --- 7. commit spread
    P("\n## 7. Commits represented in the store (machinery generations)\n")
    cc = collections.Counter(r["commit"] for r in rows if r["commit"])
    tbl = []
    for c, n in cc.most_common():
        rs = [r for r in rows if r["commit"] == c]
        dates = sorted({r["date"] for r in rs})
        subs = sorted({r["subject"] for r in rs})
        tbl.append((c, n, f"{dates[0]}..{dates[-1]}", len(subs)))
    P(_fmt(tbl, ["commit", "runs", "dates", "#subjects"]))

    # --- 8. committed artifacts vs the store
    P("\n## 8. Committed report.json artifacts vs runs still on disk\n")
    known = {r["run_id"] for r in rows}
    art_dir = repo / "docs/abstraction_ladders/ladders"
    tbl = []
    for rep_path in sorted(art_dir.glob("*/report.json")):
        rep = _load(rep_path)
        if rep is None:
            continue
        name = rep_path.parent.name
        ids = set()

        def walk(o: Any) -> None:
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("run_id", "run_ids") and isinstance(v, str):
                        ids.add(v)
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(rep)
        lad_runs = [r for r in rows if r["kind"] == "ladder" and r["subject"] == name]
        tbl.append(
            (
                name,
                len(ids),
                len(ids & known) if ids else "-",
                len(lad_runs),
                len({r["budget"] for r in lad_runs}),
                len({r["commit"] for r in lad_runs if r["commit"]}),
            )
        )
    P(
        _fmt(
            tbl,
            ["artifact", "run_ids_in_report", "still_on_disk", "store_runs", "#budgets", "#commits"],
        )
    )

    # --- 9. orphans
    P("\n## 9. Subjects present in runs/ with NO committed report.json\n")
    have_art = {p.parent.name for p in art_dir.glob("*/report.json")}
    orphan = collections.Counter(
        r["subject"] for r in rows if r["kind"] in ("ladder", "probe") and r["subject"] not in have_art
    )
    P(
        _fmt(
            [(s, n) for s, n in orphan.most_common()],
            ["subject", "runs"],
        )
    )

    # --- 10. cost concentration
    P("\n## 10. Where the compute actually went (top 25 runs by considered)\n")
    done = [r for r in rows if r["completed"] and isinstance(r["considered"], int)]
    done.sort(key=lambda r: -(r["considered"] or 0))
    P(
        _fmt(
            [
                (
                    r["date"],
                    r["subject"][:28],
                    r["arm"],
                    r["run_type"],
                    f"{r['considered']:,}",
                    f"{r['seconds']:.0f}s" if r["seconds"] else "-",
                    r["censored"],
                )
                for r in done[:25]
            ],
            ["date", "subject", "arm", "type", "considered", "wall", "censored"],
        )
    )
    tot = sum(r["considered"] or 0 for r in done)
    P(f"\n   total considered across all completed runs: {tot:,}")
    P(f"   total wall-clock across all completed runs:  {sum(r['seconds'] or 0 for r in done)/3600:.2f} h")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    repo = pathlib.Path(args.repo).resolve()
    outdir = pathlib.Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    rows = census(repo)
    if not rows:
        print("no runs found", file=sys.stderr)
        return 1

    csv_path = outdir / "run_census.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    report = rollups(rows, repo)
    (outdir / "run_census.txt").write_text(report + "\n")
    print(report)
    print(f"\n[wrote {csv_path} and {outdir / 'run_census.txt'}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
