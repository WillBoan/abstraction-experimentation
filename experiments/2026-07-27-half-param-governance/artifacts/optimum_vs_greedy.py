"""G5: separate what MDL PREFERS from what greedy DOES, across V x M and both metrics.

G1-G4 found two things that need disentangling:
  - under the flat `CompressionMetric`, greedy specialises at V=2 and keeps EVERYTHING at V>=3;
  - under `TwoPartMDL` it generalises cleanly (one arity-2 entry) from V=3 up.

S17 read the first pattern as a property of greedy-MDL ("never prunes a specialisation its own
generalisation subsumes"). But "what greedy produced" is not "what the metric prefers": greedy is
explicitly myopic, and G2 showed the arity-2 candidate is DESTROYED by the first mint's corpus
rewrite, so it cannot be reconsidered even if it were better.

This prices all four reachable end states DIRECTLY under each metric and compares the DL-minimum
with greedy's output. Where they agree, greedy is fine and the METRIC is the whole story. Where
they differ, that difference is myopia -- and it is attributable, not asserted.

End states, each built by minting the named templates and rewriting the corpus:
  none | specialise (V arity-1 entries) | generalise (1 arity-2 entry) | both.
"""

from __future__ import annotations

from dataclasses import replace

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.compression import (
    CompressionMetric,
    SolvedTask,
    TwoPartMDL,
)
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine, rewrite_with
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Program
from arc_lab.program_search.substrate.types import COLOR

LIB = PRESETS["synth"].library
GRID_IN = Grid.from_list([[1, 2], [3, 4]])
METRICS = {"flat": CompressionMetric(), "TwoPart": TwoPartMDL()}


def corpus_for(programs: list[Program]) -> tuple[SolvedTask, ...]:
    out = []
    for index, program in enumerate(programs):
        output = program.evaluate(GRID_IN, LIB)
        task = Task(task_id=f"t{index}", train=(Example(GRID_IN, output),), test=())
        out.append(SolvedTask(annotated=AnnotatedTask(task=task), program=program))
    return tuple(out)


def end_state(
    base_corpus: tuple[SolvedTask, ...], templates: list[Program]
) -> tuple[Library, list[SolvedTask]]:
    lib = LIB
    corpus = list(base_corpus)
    for i, template in enumerate(templates):
        name = f"e{i}"
        primitive = make_abstraction(name, template, lib)
        lib = lib.extended(name=f"{lib.name}+{name}", extra=(primitive,))
        corpus = [replace(st, program=rewrite_with(st.program, name, template)) for st in corpus]
    return lib, corpus


print("Programs: map_color(input, c, 6) for V distinct colours, M occurrences each.")
print("`optimum` = DL-minimal of {none, specialise, generalise, both}, priced directly.")
print("`greedy`  = what GreedyMDLLearnEngine actually mints.\n")

for metric_label, metric in METRICS.items():
    print("=" * 100)
    print(f"METRIC: {metric_label}")
    print("=" * 100)
    print(
        f"{'V':>3} {'M':>3} | {'none':>7} {'specialise':>11} {'generalise':>11} {'both':>7} | "
        f"{'OPTIMUM':>11} | {'GREEDY':>11} | agree?"
    )
    print("-" * 100)
    for values in (2, 3, 4, 6, 8):
        for occurrences in (2, 3, 4, 6):
            colours = [c for c in range(1, 10) if c != 6][:values]
            programs = [
                Apply("map_color", (Input(), Const(c, COLOR), Const(6, COLOR)))
                for c in colours
                for _ in range(occurrences)
            ]
            base = corpus_for(programs)
            cands = AntiunifyPairs().propose(list(programs), LIB)
            spec_t = [c for c in cands if make_abstraction("c", c, LIB).arity == 1]
            gen_t = [c for c in cands if make_abstraction("c", c, LIB).arity >= 2]

            options = {
                "none": [],
                "specialise": spec_t,
                "generalise": gen_t,
                "both": spec_t + gen_t,
            }
            dls: dict[str, float] = {}
            for name, templates in options.items():
                if name != "none" and not templates:
                    continue
                lib, corpus = end_state(base, list(templates))
                dls[name] = metric.describe(corpus, lib).total

            optimum = min(dls, key=lambda k: dls[k])
            out = GreedyMDLLearnEngine(proposer=AntiunifyPairs(), metric=metric).run(LIB, base)
            kept = sorted(p.arity for p in out.added)
            if not kept:
                greedy = "none"
            elif kept == [2]:
                greedy = "generalise"
            elif all(a == 1 for a in kept):
                greedy = "specialise"
            else:
                greedy = "both"
            agree = "yes" if greedy == optimum else "** NO **"
            cells = " ".join(
                f"{dls[k]:>{w}.1f}" if k in dls else f"{'-':>{w}}"
                for k, w in (("none", 7), ("specialise", 11), ("generalise", 11), ("both", 7))
            )
            print(
                f"{values:>3} {occurrences:>3} | {cells} | {optimum:>11} | {greedy:>11} | {agree}"
            )
        print()
