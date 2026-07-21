"""al14's diagnosis: the r1 tasks solve at depth 2, and sleep mints the wrong abstraction.

Four steps, all cheap (seconds):

1. Solve an r1 demonstrating task at ``depth_limit=2`` -- one below the rung's stated jump depth of
   3 -- and print the program found. It skips ``sub(ROW,1)`` entirely: within a task the row index
   is FIXED (the batch's "free params fixed within-task" convention) and the floor enumerates INT
   constants, so the destination row is available as a literal. The depth ``sub`` was supposed to
   contribute does not exist for the search.
2. Print the full generation funnel at ``depth_limit=2`` (exact, uncensored).
3. Measure the pool's type split at truncation -- the term that decides generation-3 cost, since
   ``set_cell`` composes as ``|GRID| x |INT|^2 x |COLOR|``.
4. Run the reference proposer on the two retained r1 solutions and print what it would mint.

    uv run python experiments/2026-07-21-ladder-batch-analysis/artifacts/al14_literal_collapse.py
"""

from __future__ import annotations

import collections
import dataclasses
import time

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.search import search_engine as engine_module
from arc_lab.program_search.search.tracking import SearchTracker
from arc_lab.program_search.substrate.program import Param

SPEC = make_ladder("al14-cell-row-grid")
CONFIG = SPEC.reference_config
R1_TASKS = [e.task for e in SPEC.train_corpus.entries if e.task.task_id.startswith("move_cell_up")]


def solve_at(task, depth_limit: int, max_pool: int = 2000, tracker: SearchTracker | None = None):
    budget = dataclasses.replace(CONFIG.budget, depth_limit=depth_limit, max_pool=max_pool)
    return CONFIG.search_engine.run(
        train_examples=task.train,
        library=SPEC.floor(),
        constraints=(),
        cost=CONFIG.cost,
        budget=budget,
        tracker=tracker,
    )


def step1_shortcut() -> list:
    print("== 1. r1 solves at depth 2, though its template is depth 3 ==")
    print(f"intended r1 : {SPEC.rungs[0].template}   (2 free INT params)\n")
    retained = []
    for task in R1_TASKS:
        result = solve_at(task, depth_limit=2)
        program = result.ranked_programs[0] if result.ranked_programs else None
        if program is not None:
            retained.append(program)
        print(f"{task.task_id:20} -> {program}")
    print(
        "\nNote task -01: it reads (0,2) to write (1,1) -- a coincidence fit that holds only "
        "because\nthose cells share a colour in both train examples. A task collision, not a solution."
    )
    return retained


def step2_funnel() -> None:
    print("\n== 2. exact generation funnel at depth_limit=2 (uncensored) ==")
    tracker = SearchTracker()
    started = time.time()
    solve_at(R1_TASKS[0], depth_limit=2, tracker=tracker)
    elapsed = time.time() - started
    generations = tracker.generations()
    composed = sum(g.get("composed", 0) or 0 for g in generations)
    print(f"{elapsed:.1f}s  composed={composed:,}  rate={composed / max(elapsed, 1e-9):,.0f}/s")
    for gen in generations:
        print(f"   {gen}")


def step3_pool_split() -> None:
    print("\n== 3. pool type split at truncation (drives generation-3 cost) ==")
    captured: dict[str, collections.Counter[str]] = {}
    original = engine_module.Pool.cheapest

    def spy(self, n):  # noqa: ANN001, ANN202 - throwaway probe
        counter: collections.Counter[str] = collections.Counter()
        for item in self.entries():
            counter[str(item[0] if isinstance(item, tuple) else getattr(item, "type", None))] += 1
        captured["types"] = counter
        return original(self, n)

    engine_module.Pool.cheapest = spy
    try:
        solve_at(R1_TASKS[0], depth_limit=2)
    finally:
        engine_module.Pool.cheapest = original

    types = captured.get("types", collections.Counter())
    print("pool at truncation:", dict(types))
    grids = sum(v for k, v in types.items() if "grid" in k.lower())
    ints = sum(v for k, v in types.items() if "int" in k.lower())
    colors = sum(v for k, v in types.items() if "color" in k.lower())
    print(f"|GRID|={grids} |INT|={ints} |COLOR|={colors}")
    capped = 2000 - ints - colors  # max_pool keeps the cheapest 2000 overall
    print(
        f"generation-3 set_cell compositions ~ |GRID| x |INT|^2 x |COLOR|\n"
        f"   at max_pool=2000  : {capped * ints * ints * colors:,}\n"
        f"   untruncated pool  : {grids * ints * ints * colors:,}"
    )
    for rate in (18847, 5231):  # measured in al14_reachability.py
        print(f"   {capped * ints * ints * colors / rate / 60:6.1f} min/task at {rate:,}/s")


def step4_what_sleep_mints(retained: list) -> None:
    print("\n== 4. what sleep would mint from those two shortcuts ==")
    if len(retained) < 2:
        print("fewer than 2 retained solutions -- AntiunifyPairs has nothing to pair")
        return
    ints = 17  # measured in step 3
    for proposed in AntiunifyPairs().propose(tuple(retained), SPEC.floor()):
        params = len({n.index for n in proposed.walk() if isinstance(n, Param)})
        print(f"proposed : {proposed}")
        print(
            f"           {params} params vs the intended 3 -- generation-1 cost with it "
            f"~ 2000 x {ints}^{params - 1} = {2000 * ints ** (params - 1):,}\n"
            f"           (intended 2-INT-param form: 2000 x {ints}^2 = {2000 * ints**2:,})"
        )


if __name__ == "__main__":
    solutions = step1_shortcut()
    step2_funnel()
    step3_pool_split()
    step4_what_sleep_mints(solutions)
