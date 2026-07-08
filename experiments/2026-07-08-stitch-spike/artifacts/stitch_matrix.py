"""Isolate the mechanism: does higher-order OR the cost model dissolve the E8 divergence?

2x2 matrix over the 6 D4 build_grid programs (task labels = member names):
  cost model   : {stitch-default (prim=100), node-count (all costs = 1, ~ TwoPartMDL/ProgramSize)}
  hole class   : {higher-order (default), first-order (no_curried_metavars=True)}

For each cell, report the TOP abstraction (mirror_index-shaped? read-body/COLOR-shaped?) and ratio.
A read-body top pick == E8's "divergence reproduced"; a mirror_index top pick == dissolved.
"""

from __future__ import annotations

import stitch_core as sc

from arc_lab.solvers.dsl.learn.experiments import _d4_targets
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Param, Program, Var


def to_sexpr(p: Program) -> str:
    if isinstance(p, Input):
        return "input"
    if isinstance(p, Const):
        return str(p.value)
    if isinstance(p, Var):
        return f"${p.index}"
    if isinstance(p, Param):
        return f"x{p.index}"
    if isinstance(p, Lam):
        return f"(lam {to_sexpr(p.body)})"
    if isinstance(p, Apply):
        return f"({p.primitive} {' '.join(to_sexpr(a) for a in p.args)})"
    raise TypeError(p)


targets = _d4_targets(Input())
members = list(targets.keys())
corpus = [to_sexpr(targets[m]) for m in members]

NODE_COUNT = dict(cost_app=1, cost_lam=1, cost_var=1, cost_ivar=1, cost_prim_default=1)


def classify(body: str) -> str:
    if body is None:
        return "?"
    if "read" in body:
        return "READ-BODY (COLOR, unreusable by search)"
    if "sub" in body and "1" in body:
        return "mirror_index-shaped (INT coord)"
    return "other"


def run(label: str, **kw) -> None:
    r = sc.compress(corpus, tasks=members, iterations=5, max_arity=3, silent=True, **kw)
    absts = getattr(r, "abstractions", None) or r.json["abstractions"]
    print(f"\n### {label}  (ratio {round(r.json['compression_ratio'], 3)}, "
          f"{len(absts)} absts)")
    for i, a in enumerate(absts):
        tag = " <-- TOP" if i == 0 else ""
        print(f"    [{i}] arity={a.arity}: {a.body}   [{classify(a.body)}]{tag}")


print(f"corpus: {len(corpus)} programs, tasks={members}")
run("A1  default-cost x higher-order")
run("A2  default-cost x first-order", no_curried_metavars=True)
run("B1  node-count x higher-order", **NODE_COUNT)
run("B2  node-count x first-order", no_curried_metavars=True, **NODE_COUNT)

# Also isolate allow_single_task under the repo-faithful cell (node-count, first-order).
print("\n--- allow_single_task toggle (node-count x first-order) ---")
run("B2a  node-count x first-order x allow_single_task", no_curried_metavars=True,
    allow_single_task=True, **NODE_COUNT)
