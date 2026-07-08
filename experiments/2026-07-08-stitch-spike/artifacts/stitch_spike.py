"""Offline Stitch spike — does library-refactoring mode recover `mirror_index`?

See the approved plan: this is a THROWAWAY qualitative probe. It never touches the loop,
adds no dependency to pyproject, and needs no deserializer. Two runs:

  Run A  — feed Stitch the 6 solved `build_grid` programs (the wake corpus).
           E8 predicts Stitch prefers the big COLOR read-body idiom over `mirror_index`.
  Run B  — feed Stitch the two minted read-body *definition bodies* (library refactoring).
           The `🔜 via Stitch` arrow predicts it factors out `(sub (sub #0 #1) 1)` = mirror_index.

Run with:  uv run --with stitch_core python <this file>
"""

from __future__ import annotations

import stitch_core as sc

from arc_lab.solvers.dsl.learn.experiments import _d4_targets, _mirror
from arc_lab.solvers.dsl.substrate.program import (
    Apply,
    Const,
    Input,
    Lam,
    Param,
    Program,
    Var,
)
from arc_lab.solvers.dsl.substrate.types import ValueType

_I = ValueType.INT
_G = ValueType.GRID


# --------------------------------------------------------------------------- #
# Serializer: Program AST -> Stitch s-expression.                             #
# A 6-case recursion mirroring Program.__str__ (already `$i`/`#j`/`lam`-shaped #
# by construction; only Apply needs prefix brackets). Stitch input programs   #
# must be closed (no free `#j`), so `Param(k)` is encoded as a distinct nullary#
# terminal `x{k}` — Stitch treats it as an opaque leaf, exactly how a fresh    #
# argument behaves for pattern-matching. That's all Run B needs: whether the   #
# shared `(sub (sub _ _) 1)` sub-structure gets extracted.                     #
# --------------------------------------------------------------------------- #
def to_sexpr(p: Program) -> str:
    if isinstance(p, Input):
        return "input"
    if isinstance(p, Const):
        return str(p.value)
    if isinstance(p, Var):
        return f"${p.index}"
    if isinstance(p, Param):
        return f"x{p.index}"  # closed-term encoding of a `#j` hole (see note above)
    if isinstance(p, Lam):
        return f"(lam {to_sexpr(p.body)})"
    if isinstance(p, Apply):
        return f"({p.primitive} {' '.join(to_sexpr(a) for a in p.args)})"
    raise TypeError(f"unhandled node: {type(p).__name__}")


def _dump_result(tag: str, result: sc.CompressionResult) -> None:
    print(f"\n----- {tag}: stitch result -----")
    j = result.json
    print("json keys:", sorted(j.keys()))
    for k in ("original_cost", "final_cost", "compression_ratio"):
        if k in j:
            print(f"  {k}: {j[k]}")
    absts = getattr(result, "abstractions", None)
    if absts is None:
        absts = j.get("abstractions", [])
    print(f"  #abstractions: {len(absts)}")
    for i, a in enumerate(absts):
        body = getattr(a, "body", None)
        arity = getattr(a, "arity", None)
        name = getattr(a, "name", None)
        if body is None and isinstance(a, dict):  # fall back to raw json entries
            body, arity, name = a.get("body"), a.get("arity"), a.get("name")
        print(f"  [{i}] name={name} arity={arity}\n       body= {body}")


def _print_corpus(tag: str, progs: list[str]) -> None:
    print(f"\n===== {tag} — {len(progs)} programs fed to Stitch =====")
    for s in progs:
        print("  ", s)


# --------------------------------------------------------------------------- #
# 0. Serializer sanity oracle.                                                #
# --------------------------------------------------------------------------- #
rot90 = _d4_targets(Input())["rot90"]
expected = (
    "(build_grid (width input) (height input) "
    "(lam (lam (read input $0 (sub (sub (width input) $1) 1)))))"
)
got = to_sexpr(rot90)
assert got == expected, f"serializer oracle failed:\n got= {got}\n want={expected}"
print("serializer oracle OK (rot90 round-trips to the expected Stitch s-expr)")


# --------------------------------------------------------------------------- #
# RUN A — the wake corpus (tests E8's prediction).                            #
# --------------------------------------------------------------------------- #
corpus_a = [to_sexpr(prog) for prog in _d4_targets(Input()).values()]
_print_corpus("RUN A (corpus)", corpus_a)
res_a = sc.compress(corpus_a, iterations=5, max_arity=3, silent=True)
_dump_result("RUN A (corpus)", res_a)


# --------------------------------------------------------------------------- #
# RUN B — the minted read-body definitions (tests the `via Stitch` arrow).    #
# The two "axis half-reflections" the naive proposer + greedy MDL prefer;     #
# both share `(sub (sub _ _) 1)` = mirror_index. Built directly as templates. #
# --------------------------------------------------------------------------- #
_g, _p1, _p2 = Param(0, _G), Param(1, _I), Param(2, _I)
width_twin = Apply("read", (_g, _p1, _mirror(Apply("width", (_g,)), _p2)))
height_twin = Apply("read", (_g, _mirror(Apply("height", (_g,)), _p1), _p2))

corpus_b = [to_sexpr(width_twin), to_sexpr(height_twin)]
_print_corpus("RUN B (read-body defs)", corpus_b)
res_b = sc.compress(corpus_b, iterations=3, max_arity=2, silent=True)
_dump_result("RUN B (read-body defs)", res_b)

# Did library-refactoring mode recover mirror_index?
mirror_sexpr = to_sexpr(_mirror(Param(0, _I), Param(1, _I)))  # "(sub (sub x0 x1) 1)"
print(f"\nmirror_index target body (param-encoded): {mirror_sexpr}")
absts_b = getattr(res_b, "abstractions", None) or res_b.json.get("abstractions", [])
found = [getattr(a, "body", a.get("body") if isinstance(a, dict) else None) for a in absts_b]
print("Run B abstraction bodies:", found)
print(
    "RESULT:",
    "mirror_index RECOVERED" if any(f and "sub" in f and "1" in f for f in found)
    else "no mirror_index-shaped abstraction",
)
