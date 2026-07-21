"""Cross-ladder tables over all 20 reports -- the read side of the 2026-07-21 batch analysis.

Consumes ``reports.json`` (written by ``batch_reports.py``). Pure reads, no execution.

    uv run python experiments/2026-07-21-ladder-batch-analysis/artifacts/cross_ladder_tables.py
"""

from __future__ import annotations

import json
import pathlib

REPORTS = json.loads((pathlib.Path(__file__).parent / "reports.json").read_text())


def headline() -> None:
    print("== HEADLINE: admission, recovery, off-chain necessity, overshoot, loop overhead ==")
    print(f"{'ladder':24}{'adm':5}{'rec':7}{'offch':6}{'overshoot':11}{'loopOH':8}{'amort_low':>12}{'amort_hi':>13}")
    for name, rep in REPORTS.items():
        cost, cmp_ = rep["cost"], rep["comparisons"]
        recovered = sum(r["recovered"] for r in rep["rung_recovery"])
        marginal = cost["laddered_marginal_considered"]
        to_first = cost.get("laddered_marginal_to_first") or 0
        amort = cost.get("amortization_ratio_estimated") or {}
        low, high = amort.get("low"), amort.get("high")
        print(
            f"{name:24}{str(rep['certificate']['admitted'])[0]:5}"
            f"{f'{recovered}/{len(rep['rung_recovery'])}':7}"
            f"{str(cost.get('off_chain_top_solved'))[0]:6}"
            f"{(marginal / to_first if to_first else 0):<11.1f}"
            f"{cmp_.get('loop_overhead_factor', 0):<8.2f}"
            f"{(f'{low:,.0f}' if low else '-'):>12}{(f'{high:,.0f}' if high else '-'):>13}"
        )


def estimator_spread() -> None:
    """The RQ1 estimator's bracket width against how far it had to extrapolate."""
    print("\n== ESTIMATOR: bracket width vs extrapolation distance ==")
    print(f"{'ladder':24}{'d_raw':7}{'rounds':8}{'spread (hi/lo)':>18}")
    rows = []
    for name, rep in REPORTS.items():
        est = rep["cost"].get("raw_estimate") or {}
        amort = rep["cost"].get("amortization_ratio_estimated") or {}
        if not est.get("available") or not amort.get("low"):
            continue
        rows.append((est["rounds_extrapolated"], name, est["d_raw"], amort["high"] / amort["low"]))
    for rounds, name, d_raw, spread in sorted(rows):
        print(f"{name:24}{d_raw:<7}{rounds:<8}{spread:>18,.0f}")


def overhead_vs_iterations() -> None:
    """Loop-overhead factor tracks the wake-iteration count almost exactly."""
    print("\n== LOOP OVERHEAD vs WAKE ITERATIONS ==")
    print(f"{'ladder':24}{'height':8}{'iters':7}{'overhead':>10}")
    for name, rep in sorted(REPORTS.items(), key=lambda kv: len(kv[1]["climb_trace"])):
        print(
            f"{name:24}{rep['shape']['height']:<8}{len(rep['climb_trace']):<7}"
            f"{rep['comparisons'].get('loop_overhead_factor', 0):>10.2f}"
        )


def tax_and_speedup() -> None:
    """Vocabulary tax and the honest (own-task, cost-to-first) rung speedup, per rung."""
    print("\n== VOCABULARY TAX + OWN-TASK SPEEDUP (r1 first) ==")
    for name, rep in REPORTS.items():
        tax = ",".join(f"{v['factor']:.2f}" for v in rep["comparisons"].get("vocabulary_tax", []))
        spd = ",".join(
            f"{v['own_tasks_speedup']:.1f}"
            for v in rep["comparisons"].get("marginal_rung_value", [])
            if v.get("own_tasks_speedup")
        )
        print(f"{name:24} tax={tax or '-':28} speedup={spd or '-'}")


def censoring_and_b_eff() -> None:
    """How much of the cost matrix is a censoring artifact, and how b_eff moves L_0 -> L_k."""
    print("\n== CENSORING + b_eff GROWTH ==")
    print(f"{'ladder':24}{'cells':7}{'censored':10}{'%':>5}   b_eff L_0 -> L_k")
    total = censored = 0
    for name, rep in REPORTS.items():
        cells = [c for row in rep["cost_matrix"] for c in row["columns"].values()]
        n_cens = sum(1 for c in cells if c.get("censored"))
        total, censored = total + len(cells), censored + n_cens
        levels = sorted({k for row in rep["cost_matrix"] for k in row["columns"]}, key=int)
        first = [r["columns"][levels[0]].get("b_eff") for r in rep["cost_matrix"]]
        last = [r["columns"][levels[-1]].get("b_eff") for r in rep["cost_matrix"]]
        first, last = [b for b in first if b], [b for b in last if b]
        growth = f"{min(first):.1f} -> {min(last):.1f}" if first and last else "-"
        print(
            f"{name:24}{len(cells):<7}{n_cens:<10}{100 * n_cens / len(cells):>4.0f}%   {growth}"
        )
    print(f"\nTOTAL cells {total}, censored {censored} ({100 * censored / total:.0f}%)")


if __name__ == "__main__":
    headline()
    estimator_spread()
    overhead_vs_iterations()
    tax_and_speedup()
    censoring_and_b_eff()
