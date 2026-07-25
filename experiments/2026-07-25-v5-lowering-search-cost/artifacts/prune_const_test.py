"""Does OPTIMAL CONSTANT PRUNING lift the ceiling where primitive pruning did not?

For each censored rung, run its wake search under 4 modes:
  none      - full library, full constant enumeration (the baseline: censored)
  prim      - library pruned to referenced primitives, full constants
  const     - full library, constants pruned to the values the rung's program uses
  both      - pruned library + pruned constants
"""

import contextlib
from pathlib import Path

import arc_lab.program_search.search.leaves as leaves
from arc_lab.program_search.ladders.lang.load import draft_spec, resolve
from arc_lab.program_search.ladders.lang.parse import parse_ladder_file
from arc_lab.program_search.ladders.probe import _search
from arc_lab.program_search.substrate.abstraction import unfold_program
from arc_lab.program_search.substrate.library import Library
import dataclasses

from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.substrate.program import AppFn, Apply, Const, If, Lam


def walk(p, on):
    on(p)
    if isinstance(p, Apply):
        for a in p.args:
            walk(a, on)
    elif isinstance(p, If):
        walk(p.cond, on); walk(p.then, on); walk(p.orelse, on)
    elif isinstance(p, AppFn):
        walk(p.fn, on)
        for a in p.args:
            walk(a, on)
    elif isinstance(p, Lam):
        walk(p.body, on)


def names_in(p):
    out = set()
    walk(p, lambda n: out.add(n.primitive) if isinstance(n, Apply) else None)
    return out


def consts_in(p):
    out = set()
    walk(p, lambda n: out.add((n.value, n.value_type.name)) if isinstance(n, Const) else None)
    return out


_orig_policy = leaves.policy_constants


@contextlib.contextmanager
def restrict_constants(allowed):
    """Patch policy_constants to mint only Const leaves whose (value, type) is in `allowed`."""
    def patched(grids, sources, library):
        for prog, typ in _orig_policy(grids, sources, library):
            if isinstance(prog, Const) and (prog.value, prog.value_type.name) in allowed:
                yield prog, typ
    leaves.policy_constants = patched
    try:
        yield
    finally:
        leaves.policy_constants = _orig_policy


def status(res):
    s = "CENS" if res.stats.censored else ("ok" if res.ranked_programs else "no")
    return f"{s}:{res.stats.considered}"


_p = Path("src/arc_lab/program_search/ladders/drafts/cfb2ce5a-5-lowered-core.ladder")
spec = draft_spec(resolve(parse_ladder_file(_p), assume_missing=True))
budget = spec.reference_config.budget
by_id = {e.task.task_id: e for e in spec.train_corpus.entries}
CENSORED = {"first_source_color", "second_source_color", "first_target_color",
            "second_target_color", "source_mask", "seeded_source_mask",
            "instantiate_first", "instantiate_seeded_tile"}

print(f"considered_limit={budget.considered_limit}  (each rung run at depth_limit = its target depth)")
print(f"{'rung':22s} {'dL':>3s} {'none':>11s} {'prim':>11s} {'const':>11s} {'both':>11s}")
for level in range(1, len(spec.rungs) + 1):
    rung = spec.rungs[level - 1]
    if rung.name not in CENSORED:
        continue
    below = spec.oracle_library(level - 1)
    at = spec.oracle_library(level)
    d = next(d for d in rung.demonstrations if d.task_id in by_id)
    task = by_id[d.task_id].task
    intended = unfold_program(d.solution, at, expand=frozenset({rung.name}))
    need_names, allowed = names_in(intended), consts_in(intended)
    pruned = Library(name="pruned", primitives=tuple(p for p in below.primitives if p.name in need_names))
    dl = compositional_depth(intended)
    b = dataclasses.replace(budget, depth_limit=dl)  # matched to target depth (removes depth confound)

    r_none = _search(spec, task, below, b)
    r_prim = _search(spec, task, pruned, b)
    with restrict_constants(allowed):
        r_const = _search(spec, task, below, b)
        r_both = _search(spec, task, pruned, b)
    print(f"{rung.name:22s} {dl:>3d} {status(r_none):>11s} {status(r_prim):>11s} "
          f"{status(r_const):>11s} {status(r_both):>11s}")
