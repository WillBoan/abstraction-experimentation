"""Read-side CR/LR/HR decomposition of every recorded climb's curriculum spend.

Walks every batch member's committed report.json -> provenance -> climb/learn run dir,
reads trace.jsonl (per-iteration, per-task search_stats), and classifies every
(task, wake) search by REALIZED solve status:

  CR  the first wake at which the task solves (current-rung acquisition)
  LR  any wake after its first solve (re-search of an acquired competence)
  HR  any wake before its first solve, for a task that eventually solves
      (attempt at a not-yet-reachable task)
  UN  never solves in this climb (unreachable throughout -- reported separately,
      NOT folded into HR: an unreachable-at-any-wake task is a different defect)

Costs under two accountings, both read off the same records:

  actual    total.considered -- what the run really paid. The batch's climbs run
            either solution_limit=None generation-end (search exhausts its
            depth-limited space even after solving) or solution_limit=1 immediate.
  to-first  first_index + 1 for searches that solved, considered for the rest --
            the counterfactual stop-at-first bill. Exact either way because
            first_solution_index is stop-independent (deterministic enumeration).

Terminology follows docs/abstraction_ladders/2026-07-29_chatgpt - tax math.md
(lower-rung / current-rung / higher-rung), with the classification realized
(by solve status) rather than authored (by rung assignment).

No searches are run; nothing under runs/ is written or touched.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LADDERS = REPO / "docs" / "abstraction_ladders" / "ladders"
RUNS = REPO / "runs"
OUT = Path(__file__).resolve().parent / "curriculum_decomposition.json"


def resolve_run_dir(run_dir_name: str) -> Path | None:
    date = f"{run_dir_name[:4]}-{run_dir_name[4:6]}-{run_dir_name[6:8]}"
    p = RUNS / date / run_dir_name
    if p.is_dir():
        return p
    for child in RUNS.iterdir():  # fallback: scan all date folders
        q = child / run_dir_name
        if q.is_dir():
            return q
    return None


def trace_events(run_dir: Path, phase: str) -> list[dict]:
    events = []
    with open(run_dir / "trace.jsonl") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("phase") == phase:
                events.append(o)
    return events


def decompose(member: str) -> dict | None:
    report_path = LADDERS / member / "report.json"
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text())
    prov = {row["cell"]: row for row in report.get("provenance", [])}
    learn = prov.get("climb/learn")
    if learn is None:
        return None  # rejected ladder: never climbed
    run_dir = resolve_run_dir(learn["run_dir"])
    if run_dir is None:
        return {"member": member, "error": f"run dir missing: {learn['run_dir']}"}

    spec = json.loads((run_dir / "runspec.json").read_text())
    budget = spec["config"]["budget"]
    wakes = trace_events(run_dir, "wake")
    sleeps = trace_events(run_dir, "sleep")
    if not wakes:
        return {"member": member, "error": "no wake events in trace"}

    # first-solve wake per task, from the per-wake solved lists
    first_solve: dict[str, int] = {}
    all_tasks: set[str] = set()
    for w, ev in enumerate(wakes):
        all_tasks.update(ev["search_stats"].keys())
        for task in ev["solved"]:
            first_solve.setdefault(task, w)

    per_search = []  # one row per (task, wake)
    regressions = []
    for w, ev in enumerate(wakes):
        solved_now = set(ev["solved"])
        for task, ss in ev["search_stats"].items():
            considered = ss["total"]["considered"]
            sol = ss.get("solutions") or {}
            first_index = sol.get("first_index")
            fs = first_solve.get(task)
            if fs is None:
                klass = "UN"
            elif w < fs:
                klass = "HR"
            elif w == fs:
                klass = "CR"
            else:
                klass = "LR"
                if task not in solved_now:
                    regressions.append((task, w))
            to_first = (first_index + 1) if (task in solved_now and first_index is not None) else considered
            per_search.append(
                {
                    "task": task,
                    "wake": w,
                    "klass": klass,
                    "considered": considered,
                    "first_index": first_index if task in solved_now else None,
                    "to_first": to_first,
                    "distance": (w - fs) if fs is not None else None,
                    "censored": bool(ss.get("censored")),
                    "solved_at_generation": ss.get("solved_at_generation"),
                }
            )

    classes = {k: [r for r in per_search if r["klass"] == k] for k in ("CR", "LR", "HR", "UN")}
    n = {k: len(v) for k, v in classes.items()}
    c_actual = {k: sum(r["considered"] for r in v) for k, v in classes.items()}
    c_tofirst = {k: sum(r["to_first"] for r in v) for k, v in classes.items()}
    full_actual = sum(c_actual.values())
    full_tofirst = sum(c_tofirst.values())

    # per-iteration totals and class shares (the flatness diagnosis)
    iters = []
    for w, ev in enumerate(wakes):
        rows = [r for r in per_search if r["wake"] == w]
        iters.append(
            {
                "wake": w,
                "considered": ev.get("considered"),
                "by_class_actual": {k: sum(r["considered"] for r in rows if r["klass"] == k) for k in classes},
                "solved": ev["solved"],
            }
        )

    # LR drift: per re-searched task, cost at wake w vs cost at its CR wake (both accountings)
    drift = []
    for task, fs in first_solve.items():
        cr_row = next((r for r in per_search if r["task"] == task and r["wake"] == fs), None)
        if cr_row is None:
            continue
        for r in per_search:
            if r["task"] == task and r["klass"] == "LR":
                drift.append(
                    {
                        "task": task,
                        "distance": r["distance"],
                        "rho_actual": r["considered"] / cr_row["considered"] if cr_row["considered"] else None,
                        "rho_tofirst": (r["to_first"] / cr_row["to_first"]) if cr_row["to_first"] else None,
                        "first_index_cr": cr_row["first_index"],
                        "first_index_lr": r["first_index"],
                    }
                )

    # solution churn: does a task's retained program change across wakes?
    programs: dict[str, list[str]] = {}
    for ev in wakes:
        for task, prog in (ev.get("programs") or {}).items():
            programs.setdefault(task, []).append(json.dumps(prog, sort_keys=True))
    churned = sorted(t for t, ps in programs.items() if len(set(ps)) > 1)

    return {
        "member": member,
        "run_id": learn["run_id"],
        "run_dir": learn["run_dir"],
        "budget": {
            k: budget.get(k)
            for k in ("depth_limit", "max_pool", "considered_limit", "solution_limit", "solution_limit_mode")
        },
        "n_tasks": len(all_tasks),
        "n_wakes": len(wakes),
        "invocations": {"realized": len(per_search), "idealized_full": len(all_tasks) * len(wakes)},
        "counts": n,
        "cost_actual": c_actual,
        "cost_tofirst": c_tofirst,
        "full_actual": full_actual,
        "full_tofirst": full_tofirst,
        "shares_actual": {k: (c_actual[k] / full_actual if full_actual else None) for k in classes},
        "shares_tofirst": {k: (c_tofirst[k] / full_tofirst if full_tofirst else None) for k in classes},
        "M_actual_vs_CR": full_actual / c_actual["CR"] if c_actual["CR"] else None,
        "M_tofirst_vs_CR": full_tofirst / c_tofirst["CR"] if c_tofirst["CR"] else None,
        "mu_actual": {k: (c_actual[k] / n[k] if n[k] else None) for k in classes},
        "mu_tofirst": {k: (c_tofirst[k] / n[k] if n[k] else None) for k in classes},
        "per_iteration": iters,
        "drift": drift,
        "drift_rho_actual_median": statistics.median(d["rho_actual"] for d in drift) if drift else None,
        "drift_rho_tofirst_median": statistics.median(d["rho_tofirst"] for d in drift) if drift else None,
        "churned_solutions": churned,
        "regressions": regressions,
        "mints_per_iter": [len(s.get("added") or []) for s in sleeps],
        "censored_any": any(r["censored"] for r in per_search),
        "generations": report.get("config_generations"),
    }


def main() -> None:
    members = sorted(p.name for p in LADDERS.iterdir() if (p / "report.json").exists())
    results = []
    for m in members:
        r = decompose(m)
        if r is not None:
            results.append(r)
    OUT.write_text(json.dumps(results, indent=1))

    ok = [r for r in results if "error" not in r]
    errs = [r for r in results if "error" in r]
    print(f"decomposed {len(ok)} climbs ({len(errs)} errors, {len(members) - len(results)} never climbed)\n")
    for r in errs:
        print("ERROR:", r["member"], r["error"])

    hdr = (
        f"{'member':<28} {'wk':>2} {'N C/L/H/U':>12} | {'shares actual C/L/H/U':>26} | "
        f"{'shares to-first C/L/H/U':>26} | {'M_act':>6} {'M_tf':>6} | {'rho_med':>7}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in ok:
        nn = r["counts"]
        sa = r["shares_actual"]
        st = r["shares_tofirst"]

        def pct(d: dict, k: str) -> str:
            v = d[k]
            return f"{v * 100:5.1f}" if v is not None else "    -"

        rho = r["drift_rho_actual_median"]
        print(
            f"{r['member']:<28} {r['n_wakes']:>2} "
            f"{nn['CR']:>2}/{nn['LR']:>2}/{nn['HR']:>2}/{nn['UN']:>2}"
            f"    | {pct(sa, 'CR')} {pct(sa, 'LR')} {pct(sa, 'HR')} {pct(sa, 'UN')}"
            f"     | {pct(st, 'CR')} {pct(st, 'LR')} {pct(st, 'HR')} {pct(st, 'UN')}"
            f"     | {r['M_actual_vs_CR']:>6.2f} {r['M_tofirst_vs_CR']:>6.2f}"
            f" | {rho if rho is not None else float('nan'):>7.3f}"
        )

    # segment and store-wide aggregates
    stopfirst = [r for r in ok if r["budget"]["solution_limit"] == 1]
    exhaust = [r for r in ok if r["budget"]["solution_limit"] is None]
    sf_healthy = [r for r in stopfirst if r["counts"]["UN"] == 0]

    def seg_means(rows: list[dict], key: str) -> str:
        parts = []
        for k in ("CR", "LR", "HR", "UN"):
            vals = [r[key][k] for r in rows if r[key][k] is not None]
            parts.append(f"{k} {statistics.mean(vals) * 100:.1f}%" if vals else f"{k} -")
        return " / ".join(parts)

    print(f"\nsegments: {len(exhaust)} exhaustive (generation-end), {len(stopfirst)} stop-at-first")
    print(f"  exhaustive, actual shares:    {seg_means(exhaust, 'shares_actual')}")
    print(f"  exhaustive, to-first shares:  {seg_means(exhaust, 'shares_tofirst')}")
    print(f"  stop-at-first (UN=0), actual: {seg_means(sf_healthy, 'shares_actual')}")

    tot = {k: sum(r["cost_actual"][k] for r in ok) for k in ("CR", "LR", "HR", "UN")}
    grand = sum(tot.values())
    print(f"\nstore-wide climb spend by class (actual accounting), grand total {grand:,}:")
    for k, v in tot.items():
        print(f"  {k}: {v:>12,} ({v / grand * 100:.1f}%)")

    crlr = sum(r["cost_tofirst"]["CR"] + r["cost_tofirst"]["LR"] for r in ok)
    print(f"\nCR+LR-to-first counterfactual total: {crlr:,} -> removable factor {grand / crlr:.1f}x")

    print("\nchurn / regressions / censoring / invocation-identity deviations:")
    for r in ok:
        notes = []
        if r["churned_solutions"]:
            notes.append(f"churn={len(r['churned_solutions'])} tasks")
        if r["regressions"]:
            notes.append(f"REGRESSIONS={r['regressions']}")
        if r["censored_any"]:
            notes.append("CENSORED-CELLS")
        if r["invocations"]["realized"] != r["invocations"]["idealized_full"]:
            notes.append(f"invocations {r['invocations']['realized']} != full {r['invocations']['idealized_full']}")
        if notes:
            print(f"  {r['member']:<28} {'; '.join(notes)}")


if __name__ == "__main__":
    main()
