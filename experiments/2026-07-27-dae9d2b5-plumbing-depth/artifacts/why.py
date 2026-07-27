from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit

from arc_lab.program_search.ladders.lang.load import draft_spec
spec = draft_spec(load_ladder("dae9d2b5-split-recolor"))
lib2 = spec.oracle_library(2)          # L_2 = floor + west + east
print("L_2 entries:", [p.name for p in lib2.primitives])

rung = spec.rungs[2]                    # recolored_west
print("template:", rung.template)
demo = rung.demonstrations[0]
print("demo:", demo.task_id, "solution:", demo.solution)

from arc_lab.program_search.substrate.abstraction import unfold_program
target = unfold_program(demo.solution, spec.oracle_library(len(spec.rungs)), expand=frozenset({rung.name}))
print("TARGET over L_2:", target)
print("  depth:", compositional_depth(target), "needs:", min_depth_limit(target))

entry = {e.task.task_id: e for e in spec.train_corpus.entries}[demo.task_id]
for i, ex in enumerate(entry.task.train):
    got = target.evaluate(ex.input, lib2)
    print(f"  train {i}: match={got == ex.output}  in={ex.input.shape} out={ex.output.shape}")
    if got != ex.output:
        print("    got:", got.array.tolist())
        print("    want:", ex.output.array.tolist())
