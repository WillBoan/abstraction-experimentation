import numpy as np
from arc_lab.core.dataset import load_dataset
tasks = {e.task.task_id: e.task for e in load_dataset("arc1-train").entries}

RULES = {
    "OR":   lambda a, b: a | b,
    "AND":  lambda a, b: a & b,
    "NOR":  lambda a, b: ~(a | b),
    "NAND": lambda a, b: ~(a & b),
    "XOR":  lambda a, b: a ^ b,
    "XNOR": lambda a, b: ~(a ^ b),
}
for tid, axis in (("dae9d2b5", "h"), ("94f9d214", "v"), ("fafffa47", "v")):
    t = tasks[tid]
    verdicts = {}
    for name, fn in RULES.items():
        ok = True
        for ex in [*t.train, *t.test]:
            arr = ex.input.array
            if axis == "h":
                w = arr.shape[1] // 2
                a, b = arr[:, :w] != 0, arr[:, w:] != 0
            else:
                h = arr.shape[0] // 2
                a, b = arr[:h] != 0, arr[h:] != 0
            want = ex.output.array != 0
            ok &= bool(np.array_equal(fn(a, b), want))
        verdicts[name] = ok
    out_colours = sorted({int(v) for ex in t.train for v in ex.output.array.ravel() if v})
    print(f"{tid} [{axis}] out_colour={out_colours}  ->  {[k for k, v in verdicts.items() if v] or 'NONE MATCH'}")
