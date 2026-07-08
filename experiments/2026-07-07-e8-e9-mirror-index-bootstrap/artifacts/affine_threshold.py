"""Find the affine beam threshold that lets the base search solve a reflection (to seed the bootstrap)."""

import time

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.learn.experiments import _d4_solutions, _nonsquare_grids
from arc_lab.solvers.dsl.search.build_grid_search import BuildGridSearch
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY


def member_task(member: str) -> Task:
    sol = _d4_solutions()[member]
    grids = _nonsquare_grids()[:3]
    train = [{"input": g.to_list(), "output": sol(g).to_list()} for g in grids]
    return Task.from_dict(member, {"train": train, "test": [{"input": grids[0].to_list()}]})


for member in ("rot90", "flip_h", "rot180"):
    print(f"--- affine {member} ---")
    for beam in (128, 160, 192, 224, 256, 320):
        t0 = time.perf_counter()
        res = BuildGridSearch(beam_width=beam).find(member_task(member), BUILD_AFFINE_LIBRARY)
        dt = (time.perf_counter() - t0) * 1000
        print(f"   beam={beam:4} solved={bool(res.programs)} considered={res.stats.considered:6} {dt:6.0f}ms")
