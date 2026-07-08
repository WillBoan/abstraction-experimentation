"""Why does GreedyMDL reject mirror_index? Print the probe DL per candidate.

NOTE: dl_probe.out was captured against PRE-rewrite-fix code — it shows folds?=0 for every
candidate (nothing folded), the bug that pins program_bits at 288. That was the diagnostic that
found rewrite_with didn't descend Lam bodies. Re-running against current (fixed) code folds, so
the .out no longer reproduces — it's the historical bug-discovery output (events, not state).
"""

from arc_lab.solvers.dsl.analysis.compression import TwoPartMDL
from arc_lab.solvers.dsl.learn.antiunify import FrequentSubtree, rewrite_with
from arc_lab.solvers.dsl.learn.experiments import _task, e8_mirror_index_sub
from arc_lab.solvers.dsl.search.cost import ProgramSize
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction

exp = e8_mirror_index_sub()
train = [_task(g) for g in exp.tasks if g.split == "train"]
cost = ProgramSize()
lib = exp.starting_library
metric = TwoPartMDL()

corpus = []
for task in train:
    res = exp.search.find(task, lib)
    prog = min(res.programs, key=lambda p: cost.of(p, task, lib))
    corpus.append((task, prog))

baseline = metric.describe(corpus, lib)
print(f"baseline: lib={baseline.library_bits} prog={baseline.program_bits} total={baseline.total}")

candidates = FrequentSubtree().propose([p for _, p in corpus], lib)
print(f"\n{'template':52} {'libbits':>8} {'progbits':>9} {'total':>7} {'folds?':>7}")
for i, t in enumerate(candidates):
    probe_lib = lib.extended(name="probe", extra=(make_abstraction(f"__p{i}", t, lib),))
    rewritten = [(task, rewrite_with(p, f"__p{i}", t)) for task, p in corpus]
    dl = metric.describe(rewritten, probe_lib)
    folded = sum(1 for _, p in rewritten if f"__p{i}" in str(p))
    mark = "WIN" if dl.total < baseline.total else ""
    print(f"{str(t):52} {dl.library_bits:8.0f} {dl.program_bits:9.0f} {dl.total:7.0f} {folded:5}   {mark}")

# Spot-check the fold on one rot90 program.
rot90 = next(p for task, p in corpus if task.task_id == "rot90-00")
mirror = next(t for t in candidates if str(t) == "sub(sub(#0, #1), 1)")
print("\nrot90 before:", rot90, "size", rot90.size())
after = rewrite_with(rot90, "mirror_index", mirror)
print("rot90 after :", after, "size", after.size())
