"""Inspect the E8 wake corpus: what program does each task actually get, and does the idiom recur?"""

from collections import Counter

from arc_lab.solvers.dsl.analysis.compression import TwoPartMDL
from arc_lab.solvers.dsl.learn.antiunify import FrequentSubtree
from arc_lab.solvers.dsl.learn.experiments import _task, e8_mirror_index_sub
from arc_lab.solvers.dsl.learn.selection import GreedyMDL
from arc_lab.solvers.dsl.search.cost import ProgramSize

exp = e8_mirror_index_sub()
train = [_task(g) for g in exp.tasks if g.split == "train"]
cost = ProgramSize()

corpus = []
print("=== wake corpus (min-cost program per train task) ===")
for task in train:
    res = exp.search.find(task, exp.starting_library)
    if res.programs:
        prog = min(res.programs, key=lambda p: cost.of(p, task, exp.starting_library))
        corpus.append((task, prog))
        print(f"{task.task_id:14} {prog}")
    else:
        print(f"{task.task_id:14} UNSOLVED")

print(f"\nsolved {len(corpus)}/{len(train)}")
programs = [p for _, p in corpus]
print("distinct programs:", len(set(programs)))
print("\n=== proposals ===")
props = FrequentSubtree().propose(programs, exp.starting_library)
for t in props:
    n_match = sum(1 for pr in programs for node in pr.walk() if __import__("arc_lab.solvers.dsl.learn.antiunify", fromlist=["match"]).match(t, node) is not None)
    print(f"   {t}   (matches {n_match} subtrees)")

print("\n=== GreedyMDL.select ===")
chosen = GreedyMDL().select(corpus, exp.starting_library, FrequentSubtree(), TwoPartMDL())
print("chosen:", chosen)
