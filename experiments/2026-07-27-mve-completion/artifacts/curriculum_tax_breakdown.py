"""Curriculum tax as an additive percentage breakdown, from recorded LEARN runs.

Search cost is per-task, so a climb's total cost partitions exactly over
(iteration x task) cells. Each cell is classified by what that task was, at that
iteration:

  productive      -- first solved at this iteration (the search that bought a solution)
  already-solved  -- solved at an earlier iteration, re-searched anyway  [tax]
  not-yet-solved  -- searched to the full budget without solving          [tax]
  distractor      -- not part of the ladder at all                        [tax]  (never present)

Costs sum, so percentages are well-defined. Contrast with the primitive/constant
dimension, where a candidate program contains several primitives at once and no
such partition exists.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs"


def learn_runs() -> list[Path]:
    out = []
    for spec in RUNS.glob("*/*/runspec.json"):
        try:
            d = json.loads(spec.read_text())
        except Exception:
            continue
        cfg = d.get("config", {})
        if cfg.get("learn"):
            out.append(spec.parent)
    return sorted(out)


def corpus_name(run: Path) -> str:
    d = json.loads((run / "runspec.json").read_text())
    return d.get("corpus_name", "?")


def breakdown(run: Path) -> tuple[str, str, dict[str, int], int, int, int]:
    rows = [json.loads(line) for line in (run / "trace.jsonl").read_text().splitlines()]
    wakes = [r for r in rows if r.get("phase") == "wake" and "search_stats" in r]
    schedules = {r.get("schedule") for r in wakes}
    schedule = schedules.pop() if len(schedules) == 1 else "mixed"
    solved_before: set[str] = set()
    buckets = {"productive": 0, "already-solved": 0, "not-yet-solved": 0}
    censored_cost = 0
    for row in wakes:
        stats = row["search_stats"]
        # `solved` is CUMULATIVE: it lists every task solved as of this iteration,
        # including ones solved earlier. `solved_before` is what separates them.
        solved_now = set(row.get("solved") or [])
        for task, st in stats.items():
            considered = (st.get("total") or {}).get("considered") or 0
            if st.get("censored"):
                censored_cost += considered
            if task in solved_before:
                buckets["already-solved"] += considered
            elif task in solved_now:
                buckets["productive"] += considered
            else:
                buckets["not-yet-solved"] += considered
        solved_before |= solved_now
    total = sum(buckets.values())
    return corpus_name(run), schedule, buckets, total, len(wakes), censored_cost


rows = []
for run in learn_runs():
    try:
        name, schedule, buckets, total, iters, censored = breakdown(run)
    except Exception:
        continue
    if total:
        rows.append((name, schedule, buckets, total, iters, censored, run.name))

# The wake schedule DEFINES which taxes can appear: the `curriculum` schedule searches
# each rung's tasks only at its own level, so its already-solved bucket is zero by
# construction, and `skip-solved` drops solved tasks after they are solved. Only `full`
# rows are comparable to each other. Keep the most recent `full` run per corpus.
latest: dict[str, tuple] = {}
for name, schedule, buckets, total, iters, censored, rid in rows:
    if schedule != "full":
        continue
    if name not in latest or rid > latest[name][4]:
        latest[name] = (buckets, total, iters, censored, rid)

print("Wake schedule: `full` only (see note in source). Percentages are shares of the")
print("climb's total wake cost, which partitions exactly over (iteration x task) cells.\n")
print(
    f"{'corpus (ladder train set)':34} {'iters':>5} {'total':>12} "
    f"{'productive':>15} {'already-solved':>15} {'not-yet-solved':>15} {'of which capped':>15}"
)
for name in sorted(latest):
    buckets, total, iters, censored, _ = latest[name]

    def pct(k: str, buckets: dict[str, int] = buckets, total: int = total) -> str:
        return f"{buckets[k]:>9,} {100 * buckets[k] / total:5.1f}%"

    cap = f"{censored:>9,} {100 * censored / total:5.1f}%"
    print(
        f"{name:34} {iters:>5} {total:>12,} "
        f"{pct('productive'):>15} {pct('already-solved'):>15} "
        f"{pct('not-yet-solved'):>15} {cap:>15}"
    )
print()
print("`of which capped` = cost incurred by searches that hit their candidate limit")
print("without solving. That cost is set by our budget, not by the task -- it is a")
print("measure of what we chose to spend, not of an intrinsic cost.")
