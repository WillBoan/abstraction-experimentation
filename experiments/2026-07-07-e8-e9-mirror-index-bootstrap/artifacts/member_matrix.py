"""Per-member solvability across grammars/beams — to set the tight beam and read the matrix."""

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.learn.experiments import _d4_solutions, _mirror, _nonsquare_grids
from arc_lab.solvers.dsl.search.build_grid_search import BuildGridSearch
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY, BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Param
from arc_lab.solvers.dsl.substrate.types import ValueType

_I = ValueType.INT
_MEMBERS = ("transpose", "flip_h", "flip_v", "rot90", "rot180", "rot270")


def member_task(member: str) -> Task:
    sol = _d4_solutions()[member]
    grids = _nonsquare_grids()[:3]
    train = [{"input": g.to_list(), "output": sol(g).to_list()} for g in grids]
    return Task.from_dict(member, {"train": train, "test": [{"input": grids[0].to_list()}]})


mirror = _mirror(Param(0, _I), Param(1, _I))
sub_mirror = BUILD_LIBRARY.extended(
    name="b+m", extra=(make_abstraction("mirror_index", mirror, BUILD_LIBRARY),)
)
aff_mirror = BUILD_AFFINE_LIBRARY.extended(
    name="a+m", extra=(make_abstraction("mirror_index", mirror, BUILD_AFFINE_LIBRARY),)
)
libs = {"sub": BUILD_LIBRARY, "sub+mir": sub_mirror, "affine": BUILD_AFFINE_LIBRARY, "aff+mir": aff_mirror}

for beam in (48, 64, 96, 128):
    print(f"=== beam={beam} ===   " + "  ".join(f"{m[:6]:>6}" for m in _MEMBERS))
    for name, lib in libs.items():
        cells = []
        for m in _MEMBERS:
            res = BuildGridSearch(beam_width=beam).find(member_task(m), lib)
            cells.append("  Y   " if res.programs else "  .   ")
        print(f"{name:8}          " + "".join(cells))
    print()
