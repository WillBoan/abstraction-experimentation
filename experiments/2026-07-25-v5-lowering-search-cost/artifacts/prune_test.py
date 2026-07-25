"""Optimal-pruning test: for each rung that CENSORED under the full library, re-run the SAME wake
search over a library pruned to only the primitives that rung's own (unfolded) program references.
If it now solves within the same budget, optimal pruning lifts the breadth ceiling for that rung.
"""

from pathlib import Path

from arc_lab.program_search.ladders.lang.load import draft_spec, resolve
from arc_lab.program_search.ladders.lang.parse import parse_ladder_file
from arc_lab.program_search.ladders.probe import _search
from arc_lab.program_search.substrate.abstraction import unfold_program
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import AppFn, Apply, If, Lam, Program


def names_in(p: Program) -> set[str]:
    out: set[str] = set()

    def walk(n: Program) -> None:
        if isinstance(n, Apply):
            out.add(n.primitive)
            for a in n.args:
                walk(a)
        elif isinstance(n, If):
            walk(n.cond); walk(n.then); walk(n.orelse)
        elif isinstance(n, AppFn):
            walk(n.fn)
            for a in n.args:
                walk(a)
        elif isinstance(n, Lam):
            walk(n.body)

    walk(p)
    return out


def status(res) -> str:
    if res.stats.censored:
        return "CENSORED"
    return "solved" if res.ranked_programs else "unsolved"


_p = Path("src/arc_lab/program_search/ladders/drafts/cfb2ce5a-5-lowered-core.ladder")
spec = draft_spec(resolve(parse_ladder_file(_p), assume_missing=True))
budget = spec.reference_config.budget
by_id = {e.task.task_id: e for e in spec.train_corpus.entries}

CENSORED_RUNGS = {
    "first_source_color", "second_source_color", "first_target_color", "second_target_color",
    "source_mask", "seeded_source_mask", "instantiate_first", "instantiate_seeded_tile",
}

print(f"depth_limit={budget.depth_limit}  considered_limit={budget.considered_limit}\n")
for level in range(1, len(spec.rungs) + 1):
    rung = spec.rungs[level - 1]
    if rung.name not in CENSORED_RUNGS:
        continue
    below = spec.oracle_library(level - 1)
    at = spec.oracle_library(level)
    d = next(d for d in rung.demonstrations if d.task_id in by_id)
    task = by_id[d.task_id].task
    intended = unfold_program(d.solution, at, expand=frozenset({rung.name}))
    need = names_in(intended)
    pruned_prims = tuple(p for p in below.primitives if p.name in need)
    pruned = Library(name=f"pruned-{rung.name}", primitives=pruned_prims)
    res = _search(spec, task, pruned, budget)
    print(f"{rung.name:24s} |below|={len(below.primitives):2d} -> |pruned|={len(pruned_prims):2d}  "
          f"considered={res.stats.considered:6d}  {status(res)}")
    print(f"    pruned lib: {sorted(p.name for p in pruned_prims)}")
