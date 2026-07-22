"""The depth/generation matrix: how compositional depth relates to what search actually does.

For each case: build the target program, derive its static depths, then binary-search the smallest
`depth_limit` at which the engine finds EXACTLY that program (a different program found means the
task admits a cheaper solution -- reported, since it invalidates the row).

Frames: the top level is frame 0; each *function-hole fill* opens a child frame at descent+1.
A curried `Lam(Lam(body))` is ONE fill (`_synthesize_for_hole` calls `budget.descend()` once and
then wraps every binder), so binder count and descent count are different things.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example
from arc_lab.program_search.analysis.depth import compositional_depth as cd
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Lam, Program, Var
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES as B
from arc_lab.program_search.substrate.types import COLOR, INT

MAX_LIMIT = 5
GUARD = 4_000_000


def top_lams(p: Program) -> list[Lam]:
    """Lam nodes reachable without passing through another Lam -- one per hole fill."""
    if isinstance(p, Lam):
        return [p]
    out: list[Lam] = []
    for child in p.children():
        out.extend(top_lams(child))
    return out


def frames(p: Program, descent: int = 0) -> list[tuple[int, int]]:
    """(depth within frame, descent) for the top level and every lambda body."""
    out = [(cd(p), descent)]  # cd's default lam_as_leaf=True stops at a Lam
    for lam in top_lams(p):
        body: Program = lam
        while isinstance(body, Lam):  # peel the curried chain: still ONE fill
            body = body.body
        out.extend(frames(body, descent + 1))
    return out


def binders(p: Program) -> int:
    total = 0
    for lam in top_lams(p):
        node: Program = lam
        while isinstance(node, Lam):
            total += 1
            node = node.body
    return total


def effective_depth(p: Program) -> int:
    return max(depth + descent for depth, descent in frames(p))


def lib(*names: str) -> Library:
    return Library(name="probe", primitives=tuple(B[n] for n in names))


def grids(*rows: list[list[int]]) -> list[Grid]:
    return [Grid.from_list(r) for r in rows]


#: Inputs with DIFFERENT shapes, so literal dimensions can never stand in for height/width.
VARIED = grids([[1, 2, 3], [4, 5, 6]], [[7, 8], [2, 3], [5, 1]])
SQUARE = grids([[1, 2, 3], [4, 5, 6], [7, 8, 9]], [[2, 3, 1], [5, 6, 4], [8, 9, 7]])

R, C = Var(1, INT), Var(0, INT)  # build_grid binds row then column: $1 is r, $0 is c
G = Input()

CASES: list[dict[str, object]] = [
    # -- no lambda: depth should equal generation should equal the minimum depth_limit ----
    {"name": "A0 leaf", "floor": lib("flip_h", "flip_v", "transpose"),
     "prog": Input(), "inputs": VARIED, "consts": ()},
    {"name": "A1 one apply", "floor": lib("flip_h", "flip_v", "transpose"),
     "prog": Apply("flip_h", (G,)), "inputs": VARIED, "consts": ()},
    {"name": "A2 two applies", "floor": lib("flip_h", "flip_v", "transpose"),
     "prog": Apply("flip_h", (Apply("flip_v", (G,)),)), "inputs": VARIED, "consts": ()},
    {"name": "A3 three applies", "floor": lib("flip_h", "flip_v", "transpose"),
     "prog": Apply("transpose", (Apply("flip_h", (Apply("flip_v", (G,)),)),)),
     "inputs": SQUARE, "consts": ()},

    # -- lambda: body depth 0, 1, 2, 3 against a fixed outer depth of 2 -------------------
    {"name": "B0 body depth 0", "floor": lib("build_grid", "read", "height", "width"),
     "prog": Apply("build_grid", (Apply("height", (G,)), Apply("width", (G,)),
                                  Lam(INT, Lam(INT, Const(0, COLOR))))),
     "inputs": VARIED, "consts": ("finite-enumerate",)},
    {"name": "B1 body depth 1", "floor": lib("build_grid", "read", "height", "width"),
     "prog": Apply("build_grid", (Apply("width", (G,)), Apply("height", (G,)),
                                  Lam(INT, Lam(INT, Apply("read", (G, C, R)))))),
     "inputs": VARIED, "consts": ()},
    {"name": "B2 body depth 2", "floor": lib("build_grid", "read", "sub", "height", "width"),
     "prog": Apply("build_grid", (Apply("height", (G,)), Apply("width", (G,)),
                                  Lam(INT, Lam(INT, Apply("read", (G, Apply("sub", (R, R)), C)))))),
     "inputs": VARIED, "consts": ()},  # no constants: sub(r,r) is the only way to reach row 0
    {"name": "B3 body depth 3", "floor": lib("build_grid", "read", "sub", "height", "width"),
     "prog": Apply("build_grid", (Apply("height", (G,)), Apply("width", (G,)),
                                  Lam(INT, Lam(INT, Apply("read", (
                                      G, Apply("sub", (Apply("height", (G,)), Const(1, INT))), C)))))),
     "inputs": VARIED, "consts": ("finite-enumerate",)},

    # -- lambda: outer deeper than the body, so the OUTER constraint binds ----------------
    {"name": "B4 outer depth 3", "floor": lib("build_grid", "read", "height", "width", "flip_h"),
     "prog": Apply("flip_h", (Apply("build_grid", (
         Apply("width", (G,)), Apply("height", (G,)),
         Lam(INT, Lam(INT, Apply("read", (G, C, R)))))),)),
     "inputs": VARIED, "consts": ()},
]


def solution_of(prog: Program, floor: Library, inputs: list[Grid]) -> tuple[Example, ...]:
    return tuple(Example(input=g, output=prog.evaluate_grid(g, floor)) for g in inputs)


def run() -> None:
    rows = []
    for case in CASES:
        prog, floor, inputs = case["prog"], case["floor"], case["inputs"]
        assert isinstance(prog, Program) and isinstance(floor, Library)
        assert isinstance(inputs, list)
        train = solution_of(prog, floor, inputs)
        engine = BottomUpSearchEngine(
            constant_sources=case["consts"],  # type: ignore[arg-type]
            function_hole_fill_mode="lambda-synthesis",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        )
        found_at, generation, considered, other = None, None, None, None
        for limit in range(MAX_LIMIT + 1):
            result = engine.run(
                train_examples=train, library=floor, constraints=(), cost=ProgramSize(),
                budget=Budget(limit, 2, 4000, GUARD, "immediate", None, "generation-end"),
            )
            if not result.ranked_programs:
                continue
            best = result.ranked_programs[0]
            same_shape = cd(best) == cd(prog) and effective_depth(best) == effective_depth(prog)
            if best != prog:
                other = best  # equivalent variant if same_shape, else a genuinely cheaper fit
            if best == prog or same_shape:
                found_at = limit
                generation = result.stats.solved_at_generation
                considered = result.stats.considered
            break
        frame_list = frames(prog)
        rows.append({
            "name": case["name"],
            "prog": str(prog),
            "depth": cd(prog),
            "raw": cd(prog, lam_as_leaf=False),
            "frames": frame_list,
            "binders": binders(prog),
            "effective": effective_depth(prog),
            "min_limit": found_at,
            "gen": generation,
            "considered": considered,
            "other": other,
            "consts": bool(case["consts"]),
        })
    for r in rows:
        print(
            f"{r['name']:20} depth={r['depth']} raw={r['raw']} binders={r['binders']} "
            f"frames={r['frames']} eff={r['effective']} | min_limit={r['min_limit']} "
            f"gen={r['gen']} considered={r['considered']}"
            + (f"\n{'':20} variant-> {r['other']}" if r["other"] is not None else "")
        )
        print(f"{'':20} {r['prog']}")


if __name__ == "__main__":
    run()
