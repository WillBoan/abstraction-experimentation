"""Debug: regression (sub-only full beam) + does mirror_index enter the pool / dissolve the cliff."""

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.learn.experiments import _mirror
from arc_lab.solvers.dsl.search.build_grid_search import BuildGridSearch
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY, BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Param
from arc_lab.solvers.dsl.substrate.types import ValueType

_I = ValueType.INT


def rot180_task() -> Task:
    grids = [
        [[1, 2, 3], [4, 5, 6]],
        [[5, 0], [0, 5], [1, 2]],
        [[7, 8, 9, 0], [1, 2, 3, 4]],
    ]
    train = [{"input": g, "output": [row[::-1] for row in g[::-1]]} for g in grids]
    return Task.from_dict("rot180", {"train": train, "test": [{"input": grids[0]}]})


task = rot180_task()
mirror_prim = make_abstraction("mirror_index", _mirror(Param(0, _I), Param(1, _I)), BUILD_LIBRARY)
with_mirror = BUILD_LIBRARY.extended(name="build+mirror", extra=(mirror_prim,))

# Regression + beam sweep across grammars.
for label, lib in [
    ("sub-only", BUILD_LIBRARY),
    ("sub+mirror", with_mirror),
    ("affine", BUILD_AFFINE_LIBRARY),
]:
    for beam in (16, 32, 64, 128):
        res = BuildGridSearch(beam_width=beam).find(task, lib)
        print(f"{label:12} beam={beam:3} solved={len(res.programs) > 0} considered={res.stats.considered}")
    print()

# Inspect the coordinate pool for sub+mirror at beam 16: is the reflection coord present?
search = BuildGridSearch(beam_width=16)
pairs = [(ex.input, ex.output) for ex in task.train]
battery = [(inp, i, j) for inp, out in pairs for i in range(out.height) for j in range(out.width)]
pool = search._coordinate_pool(battery, task, with_mirror)
print(f"sub+mirror beam=16 pool size={len(pool)}; exprs:")
for e in pool:
    print("   ", e, "  cost", e.size())
