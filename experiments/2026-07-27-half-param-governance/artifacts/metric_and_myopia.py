"""G1-G4: is `half-param`'s missed rung a governance PATHOLOGY, or a metric CONFIGURATION?

S16/S17 (`experiments/2026-07-27-mve-completion/`) established that `dae9d2b5-half-param`'s rung 1
is missed by GOVERNANCE rather than proposer reach: `AntiunifyPairs` offers the arity-2
generalisation `nth(split_h(#0), #1)` and `GreedyMDL` keeps two arity-1 specialisations instead.
S17 swept V (distinct parameter values) x M (occurrences) and concluded "the boundary is exactly
V=2", generalising to: "greedy-MDL over program size never prunes a specialisation its own
generalisation subsumes".

Two things that analysis did not do, and both bear on whether that conclusion is right:

1. **It never varied the METRIC.** `GreedyMDLLearnEngine`'s default is the flat
   `CompressionMetric` (1.0 bit per primitive, definition size IGNORED) -- whose own docstring
   says it "lets the loop hoard marginal specialisations (observed in E3)" and names `TwoPartMDL`
   as the anti-bloat variant that charges each abstraction its template size. The ladder ran the
   flat one. If `TwoPartMDL` mints the generalisation, the finding is a CONFIGURATION, not a
   property of greedy-MDL.
2. **It never computed the description lengths of the END STATES.** It observed what greedy
   produced and called that MDL's preference. Those are different claims: greedy is explicitly
   myopic (`selection.py::GreedyMDL`'s own TODO names beam/joint selection as the missing
   capability). If the specialised end state has a HIGHER DL than the generalised one, then MDL
   does not prefer specialisation at all -- greedy just cannot reach the better state.

G1 the real case under both metrics; G2 the greedy trajectory round by round (does the corpus
rewrite destroy the pair the generalisation is antiunified from?); G3 direct DL of the end states;
G4 the V x M sweep under both metrics.

Pure selector/metric arithmetic -- no search, no ladder run, milliseconds.
"""

from __future__ import annotations

from dataclasses import replace

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.behavioral import matches_target
from arc_lab.program_search.analysis.compression import (
    CompressionMetric,
    SolvedTask,
    TwoPartMDL,
)
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine, rewrite_with
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program

METRICS = {"CompressionMetric (flat, THE DEFAULT)": CompressionMetric(), "TwoPartMDL (anti-bloat)": TwoPartMDL()}

spec = make_ladder("dae9d2b5-half-param")
ctx = CheckContext(spec, corpus_backed=True)
rung = spec.rungs[0]
library = spec.oracle_library(0)
target = make_abstraction(rung.name, rung.template, library)

by_id = {e.task.task_id: e for e in spec.train_corpus.entries}
demo_targets = ctx.demo_targets[rung.name]
retained = [(task_id, program) for task_id, program in demo_targets]
grids = tuple(ex.input for e in spec.train_corpus.entries for ex in e.task.train)

print("=" * 96)
print("G1 -- the REAL case: `dae9d2b5-half-param` rung 1, under each metric")
print("=" * 96)
print(f"\nintended rung: {rung.name}(g, i) = {rung.template}   arity {target.arity}")
print("retained programs sleep is fed:")
for task_id, program in retained:
    print(f"  {task_id:12} {program}")

solved = tuple(
    SolvedTask(annotated=by_id[task_id], program=program) for task_id, program in retained
)

for label, metric in METRICS.items():
    engine = GreedyMDLLearnEngine(proposer=AntiunifyPairs(), metric=metric)
    outcome = engine.run(library, solved)
    hits = [matches_target(p, target, grids) for p in outcome.added]
    print(f"\n  {label}")
    print(f"    kept {len(outcome.added)}: " + ", ".join(
        f"{p.name}(arity {p.arity}){' <-- IS `half`' if hit else ''}"
        for p, hit in zip(outcome.added, hits, strict=True)
    ))
    print(f"    final DL {outcome.description_length:.1f}   recovers `half`: {any(hits)}")

print()
print("=" * 96)
print("G2 -- the greedy TRAJECTORY: what is on offer at each round, under the default metric")
print("=" * 96)
engine = GreedyMDLLearnEngine(proposer=AntiunifyPairs(), metric=CompressionMetric())
corpus = list(solved)
lib = library
for round_index in range(4):
    candidates = engine.proposer.propose([st.program for st in corpus], lib)
    if not candidates:
        print(f"\n  round {round_index}: proposer offers NOTHING -- loop ends")
        break
    print(f"\n  round {round_index}: corpus = {[str(st.program) for st in corpus]}")
    gen_present = False
    for cand in candidates:
        abstraction = make_abstraction("cand", cand, lib)
        hit = matches_target(abstraction, target, grids)
        gen_present = gen_present or hit
        print(f"      offered: arity {abstraction.arity}  {cand}" + ("   <-- the intended `half`" if hit else ""))
    best = engine.selector.select(corpus, lib, engine.proposer, engine.metric)
    if best is None:
        print("      selector: nothing improves DL -- loop ends")
        break
    print(f"      the arity-2 generalisation is {'ON OFFER' if gen_present else 'GONE'}; selector takes: {best}")
    name = f"abs{round_index}"
    primitive = make_abstraction(name, best, lib)
    lib = lib.extended(name=f"{lib.name}+{name}", extra=(primitive,))
    corpus = [replace(st, program=rewrite_with(st.program, name, best)) for st in corpus]

print(
    "\n  ^ If the generalisation is ON OFFER at round 0 but GONE by round 1, it was not weighed and\n"
    "    rejected on the merits -- the first mint's REWRITE destroyed the pair it is derived from."
)

print()
print("=" * 96)
print("G3 -- the END STATES, priced directly: does greedy reach the DL-minimum?")
print("=" * 96)


def end_state(templates: list[Program], names: list[str]) -> tuple[Library, list[SolvedTask]]:
    """Build the library+corpus that minting exactly `templates` would produce."""
    lib = library
    corpus = list(solved)
    for name, template in zip(names, templates, strict=True):
        primitive = make_abstraction(name, template, lib)
        lib = lib.extended(name=f"{lib.name}+{name}", extra=(primitive,))
        corpus = [replace(st, program=rewrite_with(st.program, name, template)) for st in corpus]
    return lib, corpus


cands = AntiunifyPairs().propose([p for _, p in retained], library)
specialised = [c for c in cands if make_abstraction("c", c, library).arity == 1]
generalised = [c for c in cands if make_abstraction("c", c, library).arity >= 2]

states = {
    "do nothing": ([], []),
    "SPECIALISE (what greedy did)": (specialised, [f"s{i}" for i in range(len(specialised))]),
    "GENERALISE (the intended `half`)": (generalised, ["g0"]),
    "BOTH": (specialised + generalised, [f"b{i}" for i in range(len(specialised) + len(generalised))]),
}

for label, metric in METRICS.items():
    print(f"\n  {label}")
    scored: list[tuple[float, str]] = []
    for state_name, (templates, names) in states.items():
        lib, corpus = end_state(list(templates), names)
        dl = metric.describe(corpus, lib)
        scored.append((dl.total, state_name))
        print(
            f"    {state_name:34} DL {dl.total:8.1f}  "
            f"(library {dl.library_bits:6.1f} + programs {dl.program_bits:6.1f})"
        )
    best_dl, best_state = min(scored)
    print(f"    -> DL-minimal end state: {best_state} ({best_dl:.1f})")

print()
print("=" * 96)
print("G4 -- S17's V x M sweep, re-run under BOTH metrics")
print("=" * 96)
from arc_lab.program_search.execution.presets import PRESETS  # noqa: E402
from arc_lab.program_search.substrate.program import Apply, Const, Input  # noqa: E402
from arc_lab.program_search.substrate.types import COLOR  # noqa: E402

SWEEP_LIB = PRESETS["synth"].library
GRID_IN = Grid.from_list([[1, 2], [3, 4]])


def sweep_solved(programs: list[Program]) -> tuple[SolvedTask, ...]:
    out = []
    for index, program in enumerate(programs):
        output = program.evaluate(GRID_IN, SWEEP_LIB)
        task = Task(task_id=f"t{index}", train=(Example(GRID_IN, output),), test=())
        out.append(SolvedTask(annotated=AnnotatedTask(task=task), program=program))
    return tuple(out)


print(f"\n{'V':>3} {'M':>3} | {'flat: kept':>22} {'verdict':>12} | {'TwoPartMDL: kept':>22} {'verdict':>12}")
print("-" * 96)
for values in (2, 3, 4, 6, 8):
    for occurrences in (2, 3, 4):
        colours = [c for c in range(1, 10) if c != 6][:values]
        programs = [
            Apply("map_color", (Input(), Const(c, COLOR), Const(6, COLOR)))
            for c in colours
            for _ in range(occurrences)
        ]
        corpus = sweep_solved(programs)
        cells = []
        for _label, metric in METRICS.items():
            eng = GreedyMDLLearnEngine(proposer=AntiunifyPairs(), metric=metric)
            out = eng.run(SWEEP_LIB, corpus)
            kept = sorted(p.arity for p in out.added)
            verdict = (
                "GENERALISES" if any(a >= 2 for a in kept) and len(kept) == 1
                else "both" if any(a >= 2 for a in kept)
                else "specialises" if kept
                else "nothing"
            )
            cells.append((str(kept), verdict))
        print(
            f"{values:>3} {occurrences:>3} | {cells[0][0]:>22} {cells[0][1]:>12} | "
            f"{cells[1][0]:>22} {cells[1][1]:>12}"
        )
    print()
