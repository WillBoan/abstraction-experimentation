from arc_lab.core.dataset import load_dataset
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.regions import SPLIT_H
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.program import Apply, Const, Input
from arc_lab.program_search.substrate.types import COLOR, INT
from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit

by_name = BASE_PRIMITIVES
lib = Library(name="dae9d2b5-split-L0", primitives=(
    by_name["split_h"], by_name["nth"], by_name["map_color"], by_name["overlay"]))

def half(i):
    return Apply("nth", (Apply("split_h", (Input(),)), Const(i, INT)))

west, east = half(0), half(1)
rw = Apply("map_color", (west, Const(4, COLOR), Const(6, COLOR)))
re = Apply("map_color", (east, Const(3, COLOR), Const(6, COLOR)))
top = Apply("overlay", (Const(0, COLOR), rw, re))

print("west  d=", compositional_depth(west),  "needs=", min_depth_limit(west))
print("rw    d=", compositional_depth(rw),    "needs=", min_depth_limit(rw))
print("top   d=", compositional_depth(top),   "needs=", min_depth_limit(top))

task = next(e.task for e in load_dataset("arc1-train").entries if e.task.task_id == "dae9d2b5")
ok = 0
for i, ex in enumerate([*task.train, *task.test]):
    got = top.evaluate(ex.input, lib)
    tag = "train" if i < len(task.train) else "TEST"
    print(f"  {tag} {i}: {'OK' if got == ex.output else 'MISMATCH'}  in={ex.input.shape} out={ex.output.shape}")
    ok += got == ex.output
print(f"{ok}/{len(task.train)+len(task.test)} match ground truth")
