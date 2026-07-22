"""Sleep-side micro-probes: ONE solution set, ONE factor changed -- what does sleep mint?

The search side got exact single-factor attribution (2026-07-22 micro-probes); the learn side has
had none -- every claim about mints rests on confounded cross-ladder readings. Same recipe here:
synthetic solved-task sets over a tiny floor, `GreedyMDLLearnEngine.run` per cell, no search at
all, milliseconds per cell. Batteries:

  S-A  demonstration count      -- the pairing floor (al12's lesson, parameterized)
  S-B  parameter mix -> arity   -- varied / frozen / equal-valued params (al13/al14's lessons)
  S-C  governance break-even    -- motif size x use count: what GreedyMDL actually refuses
  S-D  stale-input mints        -- the mechanism witnessed 2026-07-23 under skip-solved
  S-E  proposer head-to-head    -- AntiunifyPairs vs FrequentSubtree on whole-similar vs
                                   fragment-shared sets (the al4/register claim, isolated)

Usage: uv run python experiments/2026-07-23-sleep-probes/artifacts/sleep_probes.py
"""

from __future__ import annotations

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.learn.antiunify import AntiunifyPairs, FrequentSubtree
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.learn.learn_engine import LearnEngine
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, GRID

FLOOR = Library(
    name="sleep-floor",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("flip_h", "flip_v", "rot90", "map_color", "pad")),
)


def _grid(seed: int) -> Grid:
    return Grid.from_list([[(seed + r * 3 + c) % 10 for c in range(3)] for r in range(3)])


def _solved(programs: list[Program], library: Library) -> tuple[SolvedTask, ...]:
    """One solved task per program; outputs evaluated so the tasks are genuine."""
    out = []
    for i, program in enumerate(programs):
        grid = _grid(i)
        task = Task(
            task_id=f"t{i}",
            train=(Example(input=grid, output=program.evaluate(grid, library)),),
            test=(),
        )
        out.append(SolvedTask(annotated=AnnotatedTask(task, None), program=program))
    return tuple(out)


def col(value: int) -> Const:
    return Const(value=value, value_type=COLOR)


def run(label: str, programs: list[Program], engine: LearnEngine | None = None,
        library: Library = FLOOR) -> None:
    outcome = (engine or GreedyMDLLearnEngine(proposer=AntiunifyPairs())).run(
        library, _solved(programs, library)
    )
    mints = "; ".join(f"{p.name}/{p.arity}: {p.template}" for p in outcome.added) or "NOTHING"
    print(f"  {label:44s} -> {mints}")


def mirror(*args: Program) -> Program:
    return Apply("flip_h", (Apply("flip_v", args),))


def recolor(a: int, b: int) -> Program:
    return Apply("map_color", (mirror(Input()), col(a), col(b)))


print("## S-A. Demonstration count (motif = flip_h(flip_v(g)))")
for n in (1, 2, 3, 4):
    run(f"{n} demo(s)", [mirror(Input()) for _ in range(n)])

print("\n## S-B. Parameter mix -> mint arity (intended: map_color(mirror(#0), #1, #2), arity 3)")
run("params vary independently: (1,2) (3,4)", [recolor(1, 2), recolor(3, 4)])
run("params frozen: (1,2) (1,2)", [recolor(1, 2), recolor(1, 2)])
run("one frozen: (1,2) (1,4)", [recolor(1, 2), recolor(1, 4)])
run("params equal-valued: (2,2) (5,5)", [recolor(2, 2), recolor(5, 5)])

print("\n## S-C. Governance break-even (motif size x use count; distinct remainders)")
for depth, motif_label in ((2, "2-op motif"), (3, "3-op motif")):
    def motif(g: Program, d: int = depth) -> Program:
        out = g
        for name in ("flip_v", "flip_h", "rot90")[:d]:
            out = Apply(name, (out,))
        return out
    for uses in (2, 3):
        programs = [
            Apply("map_color", (motif(Input()), col(1 + i), col(5 + i))) for i in range(uses)
        ]
        run(f"{motif_label} x {uses} uses (in distinct wrappers)", programs)

print("\n## S-D. Stale input (library already holds abs0 = mirror; the skip-solved mechanism)")
_ABS0 = make_abstraction("abs0", mirror(Param(index=0, value_type=GRID)), FLOOR)
GROWN = FLOOR.extended(name="sleep-floor+abs0", extra=(_ABS0,))
fresh = [Apply("abs0", (Input(),)), Apply("abs0", (Input(),))]
stale = [mirror(Input()), mirror(Input())]  # old-library spelling of the same solutions
run("all fresh (re-expressed in abs0)", fresh, library=GROWN)
run("all stale (old unfolded spelling)", stale, library=GROWN)
run("mixed fresh + stale", [*fresh[:1], *stale[:1]], library=GROWN)
run("stale specialized: recolor(3,4) x2 carried", [recolor(3, 4), recolor(3, 4)], library=GROWN)

print("\n## S-E. Proposer head-to-head (whole-similar vs fragment-shared sets)")
whole = [recolor(1, 2), recolor(3, 4)]
fragment = [  # the SAME mirror motif buried inside otherwise-distinct programs
    Apply("map_color", (mirror(Input()), col(1), col(2))),
    Apply("pad", (mirror(Input()), Const(value=1, value_type=BASE_PRIMITIVES["pad"].param_types[1]), col(5))),
    Apply("rot90", (mirror(Input()),)),
]
for proposer_label, proposer in (("AntiunifyPairs", AntiunifyPairs()),
                                 ("FrequentSubtree", FrequentSubtree(min_frequency=2))):
    engine = GreedyMDLLearnEngine(proposer=proposer)
    run(f"{proposer_label} on whole-similar", whole, engine=engine)
    run(f"{proposer_label} on fragment-shared", fragment, engine=engine)
