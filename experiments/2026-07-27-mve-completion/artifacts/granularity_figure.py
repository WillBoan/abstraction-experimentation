"""S7 figure: cost-to-first against residual top-jump depth, from committed reports only.

Same source and same validity rule as `tofirst_curves.py` -- this only draws what that prints.
Cost is plotted as TOP-to-first (the top task's own first-solution index) because it is the one
quantity available for every member: the two d4-top members never find their top, so they have no
marginal-to-first at all and contribute a lower bound instead.

Regenerate with:  uv run python experiments/2026-07-27-mve-completion/artifacts/granularity_figure.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from arc_lab.program_search.ladders.registry import make_ladder

ROOT = Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs/abstraction_ladders/ladders"
OUT = Path(__file__).resolve().parent / "granularity.svg"

COHORTS: dict[str, list[tuple[str, int]]] = {
    "dae9d2b5 (OR)": [
        ("dae9d2b5-split-halves-lean", 2),
        ("dae9d2b5-split-asym-lean", 3),
        ("dae9d2b5-split-recolor-lean", 4),
    ],
    "94f9d214 (NOR)": [
        ("94f9d214-nor-halves", 2),
        ("94f9d214-nor-recolor", 4),
        ("94f9d214-nor-merged", 5),
    ],
    "fafffa47 (NOR)": [
        ("fafffa47-nor-halves", 2),
        ("fafffa47-nor-recolor", 4),
        ("fafffa47-nor-merged", 5),
    ],
}

#: Out-of-band bound for the NOR d4 tops: not found within 30M (price_d4_top.py, 2026-07-27).
D4_TOP_BOUND = 30_000_000

COLOURS = {"dae9d2b5 (OR)": "#1f77b4", "94f9d214 (NOR)": "#d62728", "fafffa47 (NOR)": "#2ca02c"}
MARKERS = {2: "o", 3: "s", 4: "^", 5: "D"}


def top_cell(report: dict) -> dict:
    row = [x for x in report["cost_matrix"] if "-" not in x["task_id"]][0]
    cols = row["columns"]
    return cols[max(cols, key=int)]


fig, ax = plt.subplots(figsize=(7.2, 4.4))

for cohort, members in COHORTS.items():
    for name, rungs in members:
        report = json.loads((LADDERS / name / "report.json").read_text())
        depth = make_ladder(name).depth_schedule()[-1]
        first = top_cell(report).get("first_solution_index")
        colour = COLOURS[cohort]
        if first is None:  # never found: draw the lower bound as an upward arrow
            ax.scatter(depth, D4_TOP_BOUND, s=90, facecolors="none", edgecolors=colour,
                       marker=MARKERS[rungs], linewidths=1.6, zorder=3)
            ax.annotate("", xy=(depth, D4_TOP_BOUND * 6), xytext=(depth, D4_TOP_BOUND * 1.25),
                        arrowprops={"arrowstyle": "-|>", "color": colour, "lw": 1.4})
        else:
            ax.scatter(depth, first + 1, s=90, color=colour, marker=MARKERS[rungs], zorder=3)

ax.set_yscale("log")
ax.set_xticks([2, 3, 4])
ax.set_xlim(1.6, 4.4)
ax.set_xlabel("residual top-jump depth")
ax.set_ylabel("candidates considered to first solution (log)")
ax.set_title("Cost tracks the depth of the top jump, not the number of rungs")
ax.grid(axis="y", which="major", alpha=0.25)
ax.grid(axis="y", which="minor", alpha=0.10)
ax.set_axisbelow(True)

cohort_handles = [
    plt.Line2D([], [], color=c, marker="o", linestyle="", label=k) for k, c in COLOURS.items()
]
rung_handles = [
    plt.Line2D([], [], color="#666", marker=m, linestyle="", label=f"{r} rungs")
    for r, m in MARKERS.items()
]
hollow = plt.Line2D([], [], color="#666", marker="o", linestyle="", markerfacecolor="none",
                    label=f"not found within {D4_TOP_BOUND:,} (bound)")
ax.legend(handles=[*cohort_handles, *rung_handles, hollow], fontsize=8,
          loc="upper left", frameon=False, ncol=2)

fig.tight_layout()
fig.savefig(OUT, format="svg")
print(f"wrote {OUT.relative_to(ROOT)}")
