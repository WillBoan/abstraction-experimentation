"""Minimal reproduction: example propagation makes a wrapped higher-order call unreachable.

Target: `flip_h(build_grid(width g, height g, lam r c: read(g, c, r)))` -- flip_h of a transpose.
Its effective depth is 3 (top frame depth 3; body depth 1 one descent down), so it should be
found at `depth_limit=3`. It is not found at ANY depth_limit with the engine as shipped.

The only variable here is `build_grid`'s `body_sampler`: the second run keeps its contexts but
returns `body_target=None`, which is the documented "complete baseline" path (ARCHITECTURE.md §8).
With the target dropped the program is found immediately, at exactly the predicted depth.

Why the propagated target is wrong: `enclosing_target` at the top level is the TASK's outputs
(ARCHITECTURE.md §7). Here the `build_grid` subterm must produce the *pre-`flip_h`* grid, not the
task output. The engine's gate for propagating is that the primitive's return type unifies with the
target's type -- `grid` vs `grid`, so it passes -- and the correct body is then discarded by
`entry.sig != body_target`.
"""

from __future__ import annotations

import dataclasses

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example
from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Input, Lam, Var
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES as B
from arc_lab.program_search.substrate.types import INT

G, R, C = Input(), Var(1, INT), Var(0, INT)
TRANSPOSE = Apply(
    "build_grid",
    (
        Apply("width", (G,)),
        Apply("height", (G,)),
        Lam(INT, Lam(INT, Apply("read", (G, C, R)))),
    ),
)
TARGET = Apply("flip_h", (TRANSPOSE,))  # the higher-order call WRAPPED by a same-type primitive

#: Different shapes, so literal dimensions cannot stand in for height/width.
INPUTS = [Grid.from_list([[1, 2, 3], [4, 5, 6]]), Grid.from_list([[7, 8], [2, 3], [5, 1]])]


def main() -> None:
    print("effective depth of the target = 3 (top frame 3 + descent 0; body 1 + descent 1)")
    print("compositional depth =", compositional_depth(TARGET), "\n")

    original = B["build_grid"]

    def baseline_sampler(train, siblings, enclosing):  # type: ignore[no-untyped-def]
        contexts, _target = original.body_sampler(train, siblings, enclosing)
        return contexts, None  # same contexts, propagation dropped

    variants = (
        ("propagation ON  (as shipped)", original),
        ("propagation OFF (baseline)  ", dataclasses.replace(original, body_sampler=baseline_sampler)),
    )
    for label, build_grid in variants:
        floor = Library(
            name="probe",
            primitives=(build_grid, *(B[n] for n in ("read", "height", "width", "flip_h"))),
        )
        train = tuple(
            Example(input=g, output=TARGET.evaluate_grid(g, floor)) for g in INPUTS
        )
        engine = BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="lambda-synthesis",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        )
        for limit in (3, 4, 5):
            result = engine.run(
                train_examples=train,
                library=floor,
                constraints=(),
                cost=ProgramSize(),
                budget=Budget(limit, 2, 4000, 4_000_000, "immediate", None, "generation-end"),
            )
            best = result.ranked_programs[0] if result.ranked_programs else None
            print(
                f"{label} depth_limit={limit}: solved={best is not None} "
                f"gen={result.stats.solved_at_generation} considered={result.stats.considered}"
            )
            if best is not None:
                print(f"      {best}")
                break


if __name__ == "__main__":
    main()