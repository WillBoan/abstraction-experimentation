"""S17: WHEN does governance prefer a parameterized abstraction? The boundary, characterised.

S16 found `GreedyMDL` discarding an offered arity-2 generalisation in favour of two specialised
arity-1 mints, and gave a mechanical reason: a parameterized abstraction saves LESS per call site
than a specialised one, because the argument still has to be written. `abs0(input)` is 2 nodes
against `half(input, 0)`'s 3, where the un-abstracted term is 4. So with V distinct parameter
values each appearing M times:

    specialise:  V library entries, each saving 2 nodes x M call sites
    generalise:  1 library entry,   saving 1 node  x (V*M) call sites

which predicts specialisation wins at small V and must LOSE as V grows (V entries is linear in V,
the saving advantage is not). S16 observed only the V=2 corner. This sweeps V and M to find the
boundary -- and it is a pure SELECTOR experiment: no search, no ladder, no testbed. The proposer and
the selector are both pure functions of (library, retained programs), so the whole sweep is
milliseconds.

Programs are `map_color(input, c, 6)` for V distinct colours c -- the same shape as the real case
(one varying scalar argument) but with up to 10 available values instead of the 2 a half-index has.
"""

from __future__ import annotations

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.program import Apply, Const, Input, Program
from arc_lab.program_search.substrate.types import COLOR

LIBRARY = PRESETS["synth"].library
assert "map_color" in set(LIBRARY.names()), sorted(LIBRARY.names())

GRID_IN = Grid.from_list([[1, 2], [3, 4]])


def specialised(colour: int) -> Program:
    """`map_color(input, colour, 6)` -- one retained program."""
    return Apply("map_color", (Input(), Const(colour, COLOR), Const(6, COLOR)))


def solved_tasks(programs: list[Program]) -> tuple[SolvedTask, ...]:
    """Wrap programs as SolvedTasks; the selector reads the PROGRAMS, the tasks are carriers."""
    out = []
    for index, program in enumerate(programs):
        output = program.evaluate(GRID_IN, LIBRARY)
        task = Task(task_id=f"t{index}", train=(Example(GRID_IN, output),), test=())
        out.append(SolvedTask(annotated=AnnotatedTask(task=task), program=program))
    return tuple(out)


engine = GreedyMDLLearnEngine(proposer=AntiunifyPairs())
print("programs: map_color(input, c, 6) for V distinct colours c, M occurrences each")
print(f"{'V':>3} {'M':>3} {'offered':>8} {'gen offered':>12} {'kept':>5} {'arities':>12}  verdict")
for values in (2, 3, 4, 5, 6, 8):
    for occurrences in (1, 2, 3):
        colours = [c for c in range(1, 10) if c != 6][:values]
        programs = [specialised(c) for c in colours for _ in range(occurrences)]
        candidates = engine.proposer.propose(list(programs), LIBRARY)
        arities = [make_abstraction("c", cand, LIBRARY).arity for cand in candidates]
        gen_offered = any(a >= 2 for a in arities)
        outcome = engine.run(LIBRARY, solved_tasks(programs))
        kept = [p.arity for p in outcome.added]
        generalised_kept = any(p.arity >= 2 for p in outcome.added)
        verdict = (
            "GENERALISES" if generalised_kept else ("specialises" if kept else "mints nothing")
        )
        print(
            f"{values:>3} {occurrences:>3} {len(candidates):>8} {gen_offered!s:>12} "
            f"{len(kept):>5} {sorted(kept)!s:>12}  {verdict}"
        )
    print()

print(
    "Reading: the column that matters is `gen offered` vs `verdict` -- wherever the arity-2 form is\n"
    "OFFERED but not kept, the loss is GOVERNANCE (S16's mechanism), not proposer reach (S15's)."
)
