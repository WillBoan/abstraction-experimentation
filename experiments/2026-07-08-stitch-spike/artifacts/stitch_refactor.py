"""Decisive test I skipped: does FIRST-ORDER library refactoring recover clean mirror_index?

Two orthogonal axes I conflated in the first spike:
  (1) what you feed Stitch : raw corpus   vs   the minted definitions (refactoring)
  (2) hole expressiveness  : first-order  vs   higher-order

My earlier "higher-order is the root fix" came from feeding the RAW CORPUS (axis 1a),
where first-order loses to the bigger read-body. But the loop-relevant question is axis 1b:
feed the two minted read-body DEFINITIONS and mine across them. Once the read-body is already
a definition, the competing bigger subtree is gone — so first-order refactoring should extract
the clean general mirror_index(n,k) with NO higher-order needed. Testing that here.
"""

from __future__ import annotations

import stitch_core as sc

from arc_lab.solvers.dsl.learn.experiments import _d4_targets, _mirror
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import ValueType

_I, _G = ValueType.INT, ValueType.GRID


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


NODE = dict(cost_app=1, cost_lam=1, cost_var=1, cost_ivar=1, cost_prim_default=1)

# The two minted read-body definitions (params: #0=grid, #1/#2=coords).
_g, _p1, _p2 = Param(0, _G), Param(1, _I), Param(2, _I)
width_def = Apply("read", (_g, _p1, _mirror(Apply("width", (_g,)), _p2)))
height_def = Apply("read", (_g, _mirror(Apply("height", (_g,)), _p1), _p2))
defs = [to_sexpr(width_def), to_sexpr(height_def)]

mirror_general = to_sexpr(_mirror(Param(0, _I), Param(1, _I)))  # "(sub (sub x0 x1) 1)"
print("read-body definitions fed to Stitch (the 'library' as a corpus):")
for d in defs:
    print("   ", d)
print(f"target: general first-order mirror_index(n,k) = {mirror_general}\n")


def run(label: str, **kw) -> None:
    r = sc.compress(defs, iterations=3, max_arity=2, silent=True, **kw)
    absts = getattr(r, "abstractions", None) or r.json["abstractions"]
    print(f"### {label}  (ratio {round(r.json['compression_ratio'], 3)})")
    for i, a in enumerate(absts):
        print(f"    [{i}] arity={a.arity}: {a.body}")
    print()


run("first-order library refactoring (node-count)", no_curried_metavars=True, **NODE)
run("higher-order library refactoring (node-count)", **NODE)
