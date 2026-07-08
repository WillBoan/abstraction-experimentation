"""Per-experiment held-out breakdown: how many held-out tasks the base (L1) vs the learned (L2)
library solves *at the shallow enablement budget* — the exact decomposition of the transfer count.
transfer = |(L2 solves) - (L1 solves)| restricted to held-out ids.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from arc_lab.core.dataset import Dataset
from arc_lab.solvers.dsl.learn.experiments import _REGISTRY, _task, make_experiment
from arc_lab.solvers.dsl.learn.harness import compare_libraries
from arc_lab.solvers.dsl.learn.loop import learn
from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    hdr = f"{'experiment':<22}{'held-out':>9}{'base solves':>12}{'L2 solves':>11}{'transfer':>10}"
    print(hdr)
    print("-" * len(hdr))
    for name in _REGISTRY:
        exp = make_experiment(name)
        ho = frozenset(g.task_id for g in exp.tasks if g.split == "heldout")
        train = [_task(g) for g in exp.tasks if g.split == "train"]
        full = Dataset(name=exp.name, tasks=tuple(_task(g) for g in exp.tasks))
        sleep = exp.sleep or GreedyMDLSleep(exp.proposer, metric=exp.metric)
        result = learn(
            library=exp.starting_library, search=exp.search, tasks=train, sleep=sleep, cost=exp.cost
        )
        shallow = compare_libraries(
            {"L1": exp.starting_library, "L2": result.library},
            search=exp.enablement_search,
            cost=exp.cost,
            dataset=full,
            out_dir=root / "runs",
            metric=exp.metric,
        )
        base_ho = shallow["L1"].solved_ids & ho
        aug_ho = shallow["L2"].solved_ids & ho
        transfer = aug_ho - base_ho
        print(
            f"{name:<22}{len(ho):>9}{len(base_ho):>12}{len(aug_ho):>11}{len(transfer):>10}"
        )
