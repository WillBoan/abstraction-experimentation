"""Backtest `execution/forecast_cost.py` against real funnels, on every ladder rung cell.

Ground truth is the engine itself: for each rung of each ladder we run the demonstrating tasks
under `L_{i-1}` at the pinned budget and read the per-round funnel off `SearchStats.generations`.
(The 2026-07-20 archive holds the same population, but a `Corpus` is deliberately not
reconstructible from a run record, so the typed round-0 census cannot be recovered from it — the
ladder specs supply exactly that, for the same cells.)

Three predictors are compared per completed round:

- `ceiling`   — `estimate_cost`'s untyped worst-case product (what we had before)
- `cold`      — `forecast_cost` with only the DEFAULT_SURVIVAL prior (plan before running)
- `warm`      — `forecast_cost` calibrated on the cell's own first two rounds (probe, then project)

A round is scored only if the search actually completed it (censored runs truncate `composed`,
so their last round is not ground truth).

Usage: uv run python experiments/2026-07-22-rung-probe/artifacts/forecast_backtest.py
"""

from __future__ import annotations

import statistics
from dataclasses import replace

from arc_lab.core.dataset import Corpus
from arc_lab.program_search.execution.estimate_cost import estimate_cost
from arc_lab.program_search.execution.forecast_cost import forecast_cost, survival_from
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder


def main() -> None:
    rows: list[tuple[str, int, str, int, int, int, int, int]] = []
    survival_samples: list[float] = []

    for name in sorted(ladder_paths()):
        spec = make_ladder(name)
        config = spec.reference_config
        by_id = {e.task.task_id: e for e in spec.train_corpus.entries}
        for level, rung in enumerate(spec.rungs, start=1):
            library = spec.oracle_library(level - 1)
            cell = replace(config, library=library)
            for demo in rung.demonstrations:
                entry = by_id.get(demo.task_id)
                if entry is None:
                    continue
                task = entry.task
                result = config.search_engine.run(
                    train_examples=task.train,
                    library=library,
                    constraints=config.constraints,
                    cost=config.cost,
                    budget=config.budget,
                )
                stats = result.stats
                actual = [
                    g.get("composed") for g in stats.generations if isinstance(g.get("composed"), int)
                ]
                if stats.censored and actual:
                    actual = actual[:-1]  # the cut-short round is not a measurement
                if len(actual) < 2:
                    continue
                measured = survival_from(stats)
                survival_samples.extend(measured[1:])  # round 0 is leaves, never a composition

                cold = forecast_cost(cell, task)
                warm = forecast_cost(cell, task, survival=measured[:2] if measured else 0.35)
                ceiling = estimate_cost(RunSpec(config=cell, corpus=Corpus.of("bt", [task])))
                ceil_rounds = [r.considered for r in ceiling.tasks[0].rounds]

                for index, truth in enumerate(actual):
                    if truth <= 0:
                        continue
                    rows.append(
                        (
                            name,
                            level,
                            task.task_id,
                            index,
                            truth,
                            _at(ceil_rounds, index),
                            _at([r.composed for r in cold.rounds], index),
                            _at([r.composed for r in warm.rounds], index),
                        )
                    )

    print(f"scored rounds: {len(rows)}  (across {len({(r[0], r[1]) for r in rows})} rung cells)\n")
    print(f"measured survival (entered_pool/composed): median={statistics.median(survival_samples):.3f} "
          f"mean={statistics.fmean(survival_samples):.3f} n={len(survival_samples)}")

    for label, column in (("ceiling", 5), ("cold", 6), ("warm", 7)):
        ratios = [row[column] / row[4] for row in rows if row[column] > 0]
        if not ratios:
            continue
        within = sum(1 for r in ratios if 0.5 <= r <= 2.0) / len(ratios)
        print(
            f"\n{label:8s} predicted/actual: median={statistics.median(ratios):>12.2f}  "
            f"geomean={_geomean(ratios):>12.2f}  within 2x: {within:5.0%}  "
            f"max={max(ratios):.3g}  min={min(ratios):.3g}"
        )

    print("\nworst cold-forecast cells (predicted/actual):")
    worst = sorted(rows, key=lambda r: -abs(_log_ratio(r[6], r[4])))[:8]
    for name, level, task_id, index, truth, ceil, cold, warm in worst:
        print(
            f"  {name:24s} r{level} {task_id:20s} round {index}: actual={truth:>10,} "
            f"cold={cold:>12,} warm={warm:>12,} ceiling={ceil:>16,}"
        )


def _at(values: list[int], index: int) -> int:
    return values[index] if index < len(values) else 0


def _geomean(values: list[float]) -> float:
    logs = [_safe_log(v) for v in values]
    return 2.718281828459045 ** statistics.fmean(logs)


def _safe_log(value: float) -> float:
    import math

    return math.log(max(value, 1e-9))


def _log_ratio(predicted: int, actual: int) -> float:
    import math

    return math.log(max(predicted, 1) / max(actual, 1))


if __name__ == "__main__":
    main()
