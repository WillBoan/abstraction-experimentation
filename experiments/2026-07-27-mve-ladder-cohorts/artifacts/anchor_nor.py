"""Ground-truth anchoring (the first hard gate) for the vertical-NOR pair."""
from arc_lab.core.dataset import load_dataset
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.program import Apply, Const, Input
from arc_lab.program_search.substrate.types import COLOR, INT
from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit

lib = Library(name="nor-L0", primitives=tuple(
    BASE_PRIMITIVES[n] for n in ("split_v", "nth", "overlay", "map_color", "swap_colors")))
tasks = {e.task.task_id: e.task for e in load_dataset("arc1-train").entries}

def half(i):
    return Apply("nth", (Apply("split_v", (Input(),)), Const(i, INT)))

def build(c_north, c_south, target):
    rn = Apply("map_color", (half(0), Const(c_north, COLOR), Const(target, COLOR)))
    rs = Apply("map_color", (half(1), Const(c_south, COLOR), Const(target, COLOR)))
    u = Apply("overlay", (Const(0, COLOR), rn, rs))
    return Apply("swap_colors", (u, Const(0, COLOR), Const(target, COLOR)))

for tid in ("94f9d214", "fafffa47"):
    t = tasks[tid]
    arr = t.train[0].input.array
    h = arr.shape[0] // 2
    cn = sorted({int(v) for v in arr[:h].ravel() if v})
    cs = sorted({int(v) for v in arr[h:].ravel() if v})
    print(f"\n{tid}: north colours {cn}, south colours {cs}")
    top = build(cn[0], cs[0], 2)
    print(f"  term d={compositional_depth(top)} needs={min_depth_limit(top)}")
    print(f"  {top}")
    ok = 0
    exs = [*t.train, *t.test]
    for i, ex in enumerate(exs):
        got = top.evaluate(ex.input, lib)
        ok += got == ex.output
        if got != ex.output:
            print(f"    MISMATCH at {i}")
    print(f"  ground truth: {ok}/{len(exs)} match")
