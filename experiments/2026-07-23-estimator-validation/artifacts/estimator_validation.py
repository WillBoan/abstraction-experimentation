"""Does the RQ1 raw-cost estimator tell the truth? Head-to-head against measured raw cost.

Every ladder's headline RQ1 number ("the laddered path cost Nx less than raw") rests on
`ladders/report.py::_estimate_raw_cost`: the raw search is stopped at `depth_limit`, so its cost at
`d_raw` is EXTRAPOLATED by fitting the per-round `composed` growth and projecting the missing
rounds. It returns a bracket -- geometric-mean ratio as the low end, last-observed ratio as the high
end -- and claims "the truth sits between". That claim has never been checked. al1's 78x-530x
headline depends on it entirely.

The design doc's plan was a **calibration ladder** where raw is cheap to measure. al2 was built for
exactly that and cannot do the job: its floor `{flip_h, transpose}` generates the 8-element D4
group, so its per-round composed counts are FLAT (1, 2, 4, 4, 4, 2, 0) and the whole space is
exhausted by depth 5. There is no growth regime, so there is nothing for a growth fit to be right
or wrong about. Validating on it would confirm nothing.

So instead of one ladder at one point, this sweeps the estimator across floors that genuinely grow
and across every depth gap it would be asked to bridge:

    for each floor, for each observed depth L, for each d_raw in L+1 .. L+4:
        estimate from the L-run's rounds   vs   MEASURE the d_raw run outright

which yields dozens of (predicted, measured) pairs instead of one, and answers the question the
bracket actually makes: **does it contain the truth?**

It also runs the head-to-head that matters now that a second predictor exists. `_estimate_raw_cost`
is a CURVE FIT over observed rounds; `execution/forecast_cost` is STRUCTURAL (typed census x the
product law, calibrated on the same funnel). If the structural one wins, every ladder's RQ1 number
should be recomputed with it.

Guards: the estimator explicitly assumes "a pool large enough not to bind", so the pool is freed and
every cell reports saturation -- a saturated measurement is not the raw cost of that depth and is
excluded from scoring rather than quietly compared.

Usage: uv run python experiments/2026-07-23-estimator-validation/artifacts/estimator_validation.py
"""

from __future__ import annotations

import time
from dataclasses import replace

from arc_lab.core.task import Task
from arc_lab.program_search.execution.forecast_cost import forecast_cost, survival_from
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.ladders.registry import make_ladder

# A private helper on purpose: this script exists to audit that exact function as the ladder report
# calls it, so importing the public report would only add noise between the claim and the check.
from arc_lab.program_search.ladders.report import _estimate_raw_cost
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.substrate.library import Library

POOL = 200_000
GUARD = 40_000_000

#: (label, ladder, max depth, note). Chosen to span the regimes the estimator is asked to work in --
#: including the degenerate one, because "the estimator cannot be validated here" is itself the
#: finding that retires al2 as the calibration instrument.
#:
#: Max depth is per floor and set by what is MEASURABLE, since a censored run is not ground truth.
#: The two cells that establish those ceilings, both run once and both censored at 40M: geometric
#: depth 5 (670s) and layout+params depth 4 (693s).
FLOORS = [
    ("geometric", "al7-fast-tower", 4, "concat_h/concat_v/flip_h/flip_v -- binary, genuinely grows"),
    ("layout+params", "al17-shift-frame-tall", 3, "concat_v/translate/pad -- INT + COLOR params"),
    ("colour", "al1-mirror", 3, "flip_h/flip_v/map_color -- the ladder whose RQ1 headline is cited"),
    ("d4-group", "al2-rot90-calibration", 5, "flip_h/transpose -- a FINITE group; trivial regime"),
]


def cell(config: Config, library: Library, task: Task, depth: int) -> tuple[SearchResult, float]:
    budget = replace(
        config.budget,
        depth_limit=depth,
        max_pool=POOL,
        considered_limit=GUARD,
        considered_limit_mode="immediate",
    )
    started = time.time()
    result = config.search_engine.run(
        train_examples=task.train,
        library=library,
        constraints=config.constraints,
        cost=config.cost,
        budget=budget,
    )
    return result, time.time() - started


def saturated(result: SearchResult) -> int | None:
    return next(
        (
            index
            for index, g in enumerate(result.stats.generations)
            if index > 0 and g.get("composed") == 0 and not g.get("incomplete")
        ),
        None,
    )


def main() -> None:
    print(f"# Estimator validation — pool {POOL:,}, guard {GUARD:,}\n")
    scored: list[tuple[str, float, float, float, bool]] = []

    for label, ladder, max_depth, note in FLOORS:
        spec = make_ladder(ladder)
        config = replace(spec.reference_config, learn=None)
        floor = spec.floor()
        task = next(
            e.task
            for e in spec.train_corpus.entries
            if e.task.task_id == spec.rungs[0].demonstrations[0].task_id
        )
        print(f"\n## {label} — {note}\n")

        # Measure every depth once; both the observed-run and the ground-truth roles read from here.
        measured: dict[int, tuple[SearchResult, float]] = {}
        for depth in range(2, max_depth + 1):
            result, elapsed = cell(config, floor, task, depth)
            measured[depth] = (result, elapsed)
            flag = ""
            if result.stats.censored:
                flag = " CENSORED (guard) — not a measurement"
            elif saturated(result) is not None:
                flag = f" SATURATED at round {saturated(result)} — starvation, not depth cost"
            print(
                f"  measured depth {depth}: {result.stats.considered:>12,} considered "
                f"({elapsed:>6.1f}s){flag}",
                flush=True,
            )
            if result.stats.censored:
                break

        print(
            f"\n  {'observed':>8s} {'d_raw':>5s} {'measured':>12s} {'est low':>12s} {'est high':>12s} "
            f"{'in bracket':>10s} {'forecast':>12s} {'fc/actual':>9s}"
        )
        for observed_depth in (2, 3):
            if observed_depth not in measured:
                continue
            observed = measured[observed_depth][0]
            if observed.stats.censored:
                continue
            generations = list(observed.stats.generations)
            for d_raw in range(observed_depth + 1, max_depth + 1):
                truth = measured.get(d_raw)
                if truth is None or truth[0].stats.censored:
                    continue
                actual = truth[0].stats.considered
                estimate = _estimate_raw_cost(generations, d_raw, observed_depth)
                if not estimate.get("available"):
                    print(f"  {observed_depth:>8d} {d_raw:>5d}  unavailable: {estimate['reason']}")
                    continue
                low = int(estimate["estimate_low"])  # type: ignore[call-overload]
                high = int(estimate["estimate_high"])  # type: ignore[call-overload]
                forecast = forecast_cost(
                    replace(config, library=floor),
                    task,
                    survival=survival_from(observed.stats),
                    depth_limit=d_raw,
                ).total_considered
                inside = low <= actual <= high
                usable = saturated(truth[0]) is None
                print(
                    f"  {observed_depth:>8d} {d_raw:>5d} {actual:>12,} {low:>12,} {high:>12,} "
                    f"{('YES' if inside else 'no'):>10s} {forecast:>12,} "
                    f"{forecast / actual:>8.2f}x" + ("" if usable else "   (saturated)"),
                    flush=True,
                )
                if usable:
                    scored.append((label, low / actual, high / actual, forecast / actual, inside))

    print("\n## Summary (unsaturated cells only)\n")
    if not scored:
        print("  nothing scorable")
        return
    inside = sum(1 for *_, hit in scored if hit)
    print(f"  scorable cells: {len(scored)}")
    print(f"  measured inside the estimator's bracket: {inside}/{len(scored)}")
    for name, index in (("est low/actual", 1), ("est high/actual", 2), ("forecast/actual", 3)):
        values = sorted(row[index] for row in scored)  # type: ignore[misc]
        median = values[len(values) // 2]
        print(f"  {name:18s} median={median:>10.2f}x  min={values[0]:>10.2f}x  max={values[-1]:>10.2f}x")


if __name__ == "__main__":
    main()
