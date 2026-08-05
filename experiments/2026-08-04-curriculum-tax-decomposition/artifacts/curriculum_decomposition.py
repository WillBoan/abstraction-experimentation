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

  actual    total.considered -- what the run really paid under its own stop mode.
  to-first  first_index + 1 for searches that solved, considered for the rest --
            the counterfactual stop-at-first bill, exact because
            first_solution_index is stop-independent (deterministic enumeration).

Completion pass (AL-PLAN-2026-08-04 Phase 0 item 1) adds, per member:
  - persisted per-(task, wake) rows (searches[]), so every later view is a derivation;
  - per-class mean / median / geometric-mean costs, both accountings;
  - named tau_LR / tau_HR / tau_UN / tau_total (denominator = the climb's own CR
    compute, NOT C_optimal -- no CR-only arm exists yet; Phase 1 item 6 supplies it);
    Normalized Curriculum Tax is the same quantity as tau_total, one value two names;
  - three-way shares (UN excluded) beside the four-way;
  - systematic rho and signed deltas for BOTH LR and HR rows (vs the task's own CR cost);
  - realized-distance mu(d) curves (LR: wakes since first solve; HR: wakes until it);
  - the authored-rung join (ladder.rungs[].demonstrations[].task_id -> level;
    ladder.top.task_ids -> top level) + authored-distance curves and the
    realized-vs-authored classification agreement matrix. Authored classification
    uses the idealized one-level-per-wake schedule (level j is CR at wake j-1);
  - utilization u_guard = considered / considered_limit per search, plus the BINDING
    classification -- "guard" (censored at considered_limit), "solution" (stopped by
    solution_limit) or "space" (exhausted the depth-limited space): the binding budget
    is NOT the guard on exhaustive members, which is why u needed a definition;
  - M vs H (H = wake count; under the verified every-task-every-wake schedule the
    invocation multiplier is exactly H) and the identity check
    M = 1 + tau_LR + tau_HR + tau_UN (the transcript's form omits tau_UN and holds
    only on UN-free members).

No searches are run; nothing under runs/ is written or touched.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LADDERS = REPO / "docs" / "abstraction_ladders" / "ladders"
RUNS = REPO / "runs"
OUT = Path(__file__).resolve().parent / "curriculum_decomposition.json"

CLASSES = ("CR", "LR", "HR", "UN")


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


def authored_levels(report: dict) -> tuple[dict[str, int], int | None]:
    """task_id -> authored level; top tasks get max(rung level) + 1. Returns (map, top_level)."""
    ladder = report.get("ladder") or {}
    levels: dict[str, int] = {}
    max_level = 0
    for rung in ladder.get("rungs") or []:
        level = rung.get("level")
        if not isinstance(level, int):
            continue
        max_level = max(max_level, level)
        for demo in rung.get("demonstrations") or []:
            tid = demo.get("task_id")
            if isinstance(tid, str):
                levels[tid] = level
    top = ladder.get("top") or {}
    top_level = max_level + 1 if max_level else None
    for tid in top.get("task_ids") or []:
        if isinstance(tid, str) and top_level is not None:
            levels[tid] = top_level
    return levels, top_level


def stats_block(values: list[int | float]) -> dict | None:
    if not values:
        return None
    return {
        "n": len(values),
        "sum": sum(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "geomean": math.exp(statistics.mean(math.log(v) for v in values)) if all(v > 0 for v in values) else None,
        "min": min(values),
        "max": max(values),
    }


def curve(rows: list[dict], dist_key: str, cost_key: str) -> dict[str, dict]:
    """Cost-vs-distance curve: distance -> stats over cost_key. Distances are stringified for JSON."""
    by_d: dict[int, list] = {}
    for r in rows:
        d = r.get(dist_key)
        if isinstance(d, int):
            by_d.setdefault(d, []).append(r[cost_key])
    return {str(d): stats_block(v) for d, v in sorted(by_d.items())}


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
    considered_limit = budget.get("considered_limit")
    stop_first = budget.get("solution_limit") == 1
    wakes = trace_events(run_dir, "wake")
    sleeps = trace_events(run_dir, "sleep")
    if not wakes:
        return {"member": member, "error": "no wake events in trace"}

    levels, top_level = authored_levels(report)
    shape_height = (report.get("shape") or {}).get("height")

    # first-solve wake per task, from the per-wake solved lists
    first_solve: dict[str, int] = {}
    all_tasks: set[str] = set()
    for w, ev in enumerate(wakes):
        all_tasks.update(ev["search_stats"].keys())
        for task in ev["solved"]:
            first_solve.setdefault(task, w)

    cr_cost: dict[str, dict] = {}  # task -> its own CR-wake costs (for rho / deltas)
    for task, fs in first_solve.items():
        ss = wakes[fs]["search_stats"].get(task)
        if ss is None:
            continue
        sol = ss.get("solutions") or {}
        fi = sol.get("first_index")
        cr_cost[task] = {
            "actual": ss["total"]["considered"],
            "to_first": (fi + 1) if fi is not None else ss["total"]["considered"],
        }

    per_search = []
    regressions = []
    unmapped_tasks = sorted(t for t in all_tasks if t not in levels)
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
            solved_here = task in solved_now
            to_first = (first_index + 1) if (solved_here and first_index is not None) else considered

            # binding: what actually terminated this search
            if ss.get("censored"):
                binding = "guard"
            elif solved_here and stop_first:
                binding = "solution"
            else:
                binding = "space"

            level = levels.get(task)
            authored_cr_wake = (level - 1) if isinstance(level, int) else None
            if authored_cr_wake is None:
                authored_class = None
                authored_distance = None
            else:
                authored_distance = w - authored_cr_wake
                authored_class = "HR" if authored_distance < 0 else ("CR" if authored_distance == 0 else "LR")

            base = cr_cost.get(task)
            row = {
                "task": task,
                "wake": w,
                "klass": klass,
                "considered": considered,
                "first_index": first_index if solved_here else None,
                "to_first": to_first,
                "distance": (w - fs) if fs is not None else None,  # signed; >0 LR, <0 HR
                "authored_level": level,
                "authored_distance": authored_distance,
                "authored_class": authored_class,
                "binding": binding,
                "u_guard": (considered / considered_limit) if considered_limit else None,
                "censored": bool(ss.get("censored")),
                "solved_at_generation": ss.get("solved_at_generation"),
                "rho_actual": (considered / base["actual"]) if (base and base["actual"] and klass in ("LR", "HR")) else None,
                "rho_tofirst": (to_first / base["to_first"]) if (base and base["to_first"] and klass in ("LR", "HR")) else None,
                "delta_actual": (considered - base["actual"]) if (base and klass in ("LR", "HR")) else None,
                "delta_tofirst": (to_first - base["to_first"]) if (base and klass in ("LR", "HR")) else None,
            }
            per_search.append(row)

    by_class = {k: [r for r in per_search if r["klass"] == k] for k in CLASSES}
    n = {k: len(v) for k, v in by_class.items()}
    c_actual = {k: sum(r["considered"] for r in v) for k, v in by_class.items()}
    c_tofirst = {k: sum(r["to_first"] for r in v) for k, v in by_class.items()}
    full_actual = sum(c_actual.values())
    full_tofirst = sum(c_tofirst.values())
    three_way_actual = full_actual - c_actual["UN"]
    three_way_tofirst = full_tofirst - c_tofirst["UN"]

    def taus(cost: dict) -> dict | None:
        cr = cost["CR"]
        if not cr:
            return None
        t = {k: cost[k] / cr for k in ("LR", "HR", "UN")}
        t["total"] = t["LR"] + t["HR"]  # transcript's tau_total / Normalized Curriculum Tax: UN excluded
        t["total_incl_UN"] = t["total"] + t["UN"]
        return t

    taus_actual = taus(c_actual)
    taus_tofirst = taus(c_tofirst)
    m_actual = full_actual / c_actual["CR"] if c_actual["CR"] else None
    m_tofirst = full_tofirst / c_tofirst["CR"] if c_tofirst["CR"] else None
    n_wakes = len(wakes)
    identity_err = abs(m_actual - (1 + taus_actual["total_incl_UN"])) if (m_actual and taus_actual) else None

    # realized-vs-authored classification agreement (rows: realized, cols: authored)
    agreement: dict[str, dict[str, int]] = {}
    for r in per_search:
        a = r["authored_class"] or "unmapped"
        agreement.setdefault(r["klass"], {})
        agreement[r["klass"]][a] = agreement[r["klass"]].get(a, 0) + 1
    mismatches = [
        {"task": r["task"], "wake": r["wake"], "realized": r["klass"], "authored": r["authored_class"]}
        for r in per_search
        if r["authored_class"] is not None and r["klass"] != "UN" and r["klass"] != r["authored_class"]
    ]

    # distance curves; LR distance = +d realized, HR rows get positive wakes-until-solve
    lr_rows = by_class["LR"]
    hr_rows = [dict(r, until=(-r["distance"] if isinstance(r["distance"], int) else None)) for r in by_class["HR"]]
    auth_lr = [r for r in per_search if r["authored_class"] == "LR" and r["klass"] != "UN"]
    auth_hr = [
        dict(r, auth_until=-r["authored_distance"])
        for r in per_search
        if r["authored_class"] == "HR" and r["klass"] != "UN"
    ]

    # per-iteration totals and class sums (the flatness diagnosis)
    iters = []
    for w, ev in enumerate(wakes):
        rows = [r for r in per_search if r["wake"] == w]
        iters.append(
            {
                "wake": w,
                "considered": ev.get("considered"),
                "by_class_actual": {k: sum(r["considered"] for r in rows if r["klass"] == k) for k in CLASSES},
                "solved": ev["solved"],
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
        "accounting_mode": "stop-first" if stop_first else "exhaustive",
        "n_tasks": len(all_tasks),
        "n_wakes": n_wakes,
        "invocations": {"realized": len(per_search), "idealized_full": len(all_tasks) * n_wakes},
        "authored_join": {
            "top_level": top_level,
            "shape_height": shape_height,
            "height_matches": (top_level == shape_height) if (top_level and shape_height) else None,
            "unmapped_tasks": unmapped_tasks,
        },
        "counts": n,
        "cost_actual": c_actual,
        "cost_tofirst": c_tofirst,
        "full_actual": full_actual,
        "full_tofirst": full_tofirst,
        "shares_actual": {k: (c_actual[k] / full_actual if full_actual else None) for k in CLASSES},
        "shares_tofirst": {k: (c_tofirst[k] / full_tofirst if full_tofirst else None) for k in CLASSES},
        "shares_actual_3way": {
            k: (c_actual[k] / three_way_actual if three_way_actual else None) for k in ("CR", "LR", "HR")
        },
        "shares_tofirst_3way": {
            k: (c_tofirst[k] / three_way_tofirst if three_way_tofirst else None) for k in ("CR", "LR", "HR")
        },
        "taus_actual": taus_actual,  # denominator: the climb's own CR compute, NOT C_optimal
        "taus_tofirst": taus_tofirst,
        "M_actual_vs_CR": m_actual,
        "M_tofirst_vs_CR": m_tofirst,
        "M_over_H_actual": (m_actual / n_wakes) if m_actual else None,
        "M_over_H_tofirst": (m_tofirst / n_wakes) if m_tofirst else None,
        "identity_abs_err": identity_err,  # |M - (1 + tau_LR + tau_HR + tau_UN)|, must be ~0
        "identity_holds_without_UN": (n["UN"] == 0),
        "class_stats_actual": {k: stats_block([r["considered"] for r in v]) for k, v in by_class.items()},
        "class_stats_tofirst": {k: stats_block([r["to_first"] for r in v]) for k, v in by_class.items()},
        "utilization": {
            k: {
                "bindings": {
                    b: sum(1 for r in v if r["binding"] == b) for b in ("guard", "solution", "space")
                },
                "u_guard_mean": statistics.mean(r["u_guard"] for r in v) if v and considered_limit else None,
                "u_guard_max": max((r["u_guard"] for r in v), default=None) if considered_limit else None,
            }
            for k, v in by_class.items()
            if v
        },
        "distance_curves": {
            "realized_LR_actual": curve(lr_rows, "distance", "considered"),
            "realized_LR_tofirst": curve(lr_rows, "distance", "to_first"),
            "realized_HR_actual": curve(hr_rows, "until", "considered"),
            "authored_LR_actual": curve(auth_lr, "authored_distance", "considered"),
            "authored_HR_actual": curve(auth_hr, "auth_until", "considered"),
        },
        "agreement_realized_vs_authored": agreement,
        "classification_mismatches": mismatches,
        "rho_LR_actual_median": statistics.median([r["rho_actual"] for r in lr_rows if r["rho_actual"]]) if lr_rows else None,
        "rho_LR_tofirst_median": statistics.median([r["rho_tofirst"] for r in lr_rows if r["rho_tofirst"]]) if lr_rows else None,
        "rho_HR_actual_median": statistics.median([r["rho_actual"] for r in by_class["HR"] if r["rho_actual"]]) if by_class["HR"] else None,
        "churned_solutions": churned,
        "regressions": regressions,
        "mints_per_iter": [len(s.get("added") or []) for s in sleeps],
        "censored_any": any(r["censored"] for r in per_search),
        "generations": report.get("config_generations"),
        "per_iteration": iters,
        "searches": per_search,  # the persisted per-(task, wake) rows: every view above is a derivation
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
        f"{'member':<28} {'mode':<10} {'wk':>2} | {'shares actual C/L/H/U':>26} | "
        f"{'tau_L':>7} {'tau_H':>7} {'tau_U':>7} | {'M_act':>7} {'M/H':>5} | {'rhoL':>5} {'rhoH':>6}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in ok:
        sa = r["shares_actual"]

        def pct(d: dict, k: str) -> str:
            v = d[k]
            return f"{v * 100:5.1f}" if v is not None else "    -"

        t = r["taus_actual"] or {}

        def tv(taus: dict, k: str) -> str:
            return f"{taus[k]:7.2f}" if taus.get(k) is not None else "      -"

        rho_l = r["rho_LR_actual_median"]
        rho_h = r["rho_HR_actual_median"]
        print(
            f"{r['member']:<28} {r['accounting_mode']:<10} {r['n_wakes']:>2}"
            f" | {pct(sa, 'CR')} {pct(sa, 'LR')} {pct(sa, 'HR')} {pct(sa, 'UN')}    "
            f" | {tv(t, 'LR')} {tv(t, 'HR')} {tv(t, 'UN')}"
            f" | {r['M_actual_vs_CR']:>7.2f} {r['M_over_H_actual']:>5.2f}"
            f" | {rho_l if rho_l is not None else float('nan'):>5.2f} {rho_h if rho_h is not None else float('nan'):>6.2f}"
        )

    # identity + join integrity
    worst_identity = max((r["identity_abs_err"] for r in ok if r["identity_abs_err"] is not None), default=0.0)
    join_bad = [r["member"] for r in ok if r["authored_join"]["unmapped_tasks"] or r["authored_join"]["height_matches"] is False]
    mism = {r["member"]: len(r["classification_mismatches"]) for r in ok if r["classification_mismatches"]}
    print(f"\nidentity |M - (1 + tau_L + tau_H + tau_U)| worst abs err: {worst_identity:.2e}")
    print(f"members where transcript identity (no tau_UN) suffices: {sum(1 for r in ok if r['identity_holds_without_UN'])}/{len(ok)}")
    print(f"authored-join problems (unmapped tasks or height mismatch): {join_bad or 'none'}")
    print(f"realized-vs-authored classification mismatches (rows, per member): {mism or 'none'}")

    # segment class stats: mean vs median vs geomean (heavy tails)
    for mode in ("exhaustive", "stop-first"):
        seg = [r for r in ok if r["accounting_mode"] == mode]
        print(f"\n{mode} members ({len(seg)}), per-class ACTUAL cost across all rows:")
        for k in CLASSES:
            vals = [v for r in seg for v in [row["considered"] for row in r["searches"] if row["klass"] == k]]
            sb = stats_block(vals)
            if sb:
                gm = f"{sb['geomean']:>12,.0f}" if sb["geomean"] else "           -"
                print(f"  {k}: n={sb['n']:>3}  mean={sb['mean']:>12,.0f}  median={sb['median']:>12,.0f}  geomean={gm}")

    # pooled realized distance curves, mode-stratified
    for mode in ("exhaustive", "stop-first"):
        seg_rows = [row for r in ok if r["accounting_mode"] == mode for row in r["searches"]]
        lr = [r for r in seg_rows if r["klass"] == "LR"]
        hr = [dict(r, until=-r["distance"]) for r in seg_rows if r["klass"] == "HR"]
        print(f"\n{mode}: pooled mu_LR(d) (rho medians by wakes-since-solve) and mu_HR(d) (by wakes-until-solve):")
        for d in sorted({r["distance"] for r in lr}):
            rows = [r for r in lr if r["distance"] == d]
            rhos = [r["rho_actual"] for r in rows if r["rho_actual"]]
            print(f"  LR d={d}: n={len(rows):>3}  median considered={statistics.median([r['considered'] for r in rows]):>10,.0f}  median rho={statistics.median(rhos) if rhos else float('nan'):.3f}")
        for d in sorted({r["until"] for r in hr}):
            rows = [r for r in hr if r["until"] == d]
            print(f"  HR until={d}: n={len(rows):>3}  median considered={statistics.median([r['considered'] for r in rows]):>10,.0f}")

    # utilization summary: bindings by class, and every guard-bound cell
    bindings: dict[str, dict[str, int]] = {}
    guard_cells = []
    for r in ok:
        for row in r["searches"]:
            bindings.setdefault(row["klass"], {})
            bindings[row["klass"]][row["binding"]] = bindings[row["klass"]].get(row["binding"], 0) + 1
            if row["binding"] == "guard":
                guard_cells.append((r["member"], row["task"], row["wake"], row["u_guard"]))
    print(f"\nbinding counts by class (guard = censored at considered_limit; space = exhausted depth-limited space): {bindings}")
    print(f"guard-bound cells (u_guard = 1 by construction): {guard_cells or 'none'}")


if __name__ == "__main__":
    main()
