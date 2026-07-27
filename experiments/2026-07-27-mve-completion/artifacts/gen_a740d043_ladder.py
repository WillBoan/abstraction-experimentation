"""S19b: verify the `a740d043` ladder's terms, then emit its demo grids.

LADDER-PROCESS: nothing is authored until the terms are verified against the substrate's own
evaluator. Three things get checked here before a `.ladder` file exists:

1. **The route.** The floor withholds `crop_to_content`, `crop_to_mask` and `bbox_mask`, leaving the
   RECT tier as the only way to the content box: `crop_rect(g, bbox(nonbg_mask(g)))`. That must
   equal the anchored `crop_to_mask(g, nonbg_mask(g))` from `test_a740d043_anchor.py` -- if it does
   not, the ladder computes a different function than the one that was anchored.
2. **The top.** `map_color(content_box(input), 1, 0)` must reproduce ground truth on all four
   examples. Note the LITERAL 1 rather than `most_common_color(input)`: every a740d043 example has
   background 1, so the perceiver form is a train-constant subterm beaten by an enumerated literal
   and `constant-subterm` rejects it (correctly -- the ARC task genuinely cannot distinguish them).
   This ladder therefore claims the CROP abstraction, not the perceiver.
3. **The demos.** Synthetic grids for the `content_box` rung, checked against the lint properties
   that literal grids no longer guarantee by construction: distinct train inputs, varying outputs,
   and non-identity (the crop must actually shrink, or the rung demonstrates nothing).
"""

from __future__ import annotations

from arc_lab.core.dataset import load_corpus
from arc_lab.core.grid import Grid
from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR

LIBRARY = Library(name="registry", primitives=tuple(BASE_PRIMITIVES.values()))
G = Input()

#: The rung: content bounding box via the RECT tier (the route the floor leaves open).
CONTENT_BOX: Program = Apply("crop_rect", (G, Apply("bbox", (Apply("nonbg_mask", (G,)),))))
#: The anchored equivalent, via the WITHHELD `crop_to_mask` -- these must agree.
ANCHORED_BOX: Program = Apply("crop_to_mask", (G, Apply("nonbg_mask", (G,))))
#: The top, over `L_1` (the rung is one step).
TOP: Program = Apply("map_color", (CONTENT_BOX, Const(1, COLOR), Const(0, COLOR)))

print("=== 1. the rect route agrees with the anchored route ===")
task = next(e.task for e in load_corpus("arc1-train").entries if e.task.task_id == "a740d043")
examples = [*task.train, *task.test]
agree = all(
    CONTENT_BOX.evaluate(ex.input, LIBRARY) == ANCHORED_BOX.evaluate(ex.input, LIBRARY)
    for ex in examples
)
print(f"  crop_rect(g, bbox(nonbg_mask g)) == crop_to_mask(g, nonbg_mask g)  on all: {agree}")

print("\n=== 2. the top reproduces ground truth ===")
for index, example in enumerate(examples):
    split = "train" if index < len(task.train) else "test "
    got = TOP.evaluate(example.input, LIBRARY)
    print(f"  {split} {index}: {'ok' if got == example.output else 'MISMATCH'}")
TOP_OVER_L1: Program = Apply(
    "map_color", (Apply("content_box", (G,)), Const(1, COLOR), Const(0, COLOR))
)
# `compositional_depth` (the generation, the `d_raw`/`d_i` unit the ladder design speaks) and
# `min_depth_limit` (the budget that puts a program in reach) diverge as soon as a `Lam` appears.
# Every term here is first-order, so they must coincide -- asserted rather than assumed, because if
# they ever diverged the ladder's stated jumps would not be the budgets its levels actually need.
for label, term in (
    ("d_raw (top inlined over the floor)", TOP),
    ("top's jump over L_1", TOP_OVER_L1),
    ("rung's jump over L_0", CONTENT_BOX),
):
    generation, budget = compositional_depth(term), min_depth_limit(term)
    assert generation == budget, f"{label}: generation {generation} != budget {budget}"
    print(f"  {label:36} {generation}  (min_depth_limit agrees)")

# --- 3. demo grids for the `content_box` rung ---------------------------------------------------
# Hand-laid scenes: a background field with a content blob strictly inside it, so the crop is a real
# shrink. Backgrounds and palettes VARY across demos -- `nonbg_mask` perceives the background, so
# holding it fixed would let a literal stand in for the perception the rung is supposed to carry.
DEMOS: dict[str, list[list[list[int]]]] = {
    "content_box-00": [
        [[4, 4, 4, 4, 4], [4, 2, 3, 4, 4], [4, 3, 2, 4, 4], [4, 4, 4, 4, 4]],
        [[7, 7, 7, 7, 7, 7], [7, 7, 5, 5, 7, 7], [7, 7, 5, 6, 7, 7], [7, 7, 7, 7, 7, 7]],
        [[8, 8, 8, 8], [8, 9, 8, 8], [8, 9, 2, 8], [8, 8, 8, 8]],
    ],
    "content_box-01": [
        [[3, 3, 3, 3, 3, 3], [3, 3, 3, 6, 1, 3], [3, 3, 3, 1, 6, 3], [3, 3, 3, 3, 3, 3]],
        [[5, 5, 5, 5, 5], [5, 2, 2, 2, 5], [5, 5, 5, 5, 5], [5, 5, 5, 5, 5]],
        [[1, 1, 1, 1, 1], [1, 1, 4, 1, 1], [1, 1, 4, 7, 1], [1, 1, 1, 1, 1]],
    ],
    "content_box-heldout": [
        [[6, 6, 6, 6, 6], [6, 6, 8, 8, 6], [6, 6, 8, 3, 6], [6, 6, 6, 6, 6]],
        [[2, 2, 2, 2, 2, 2], [2, 9, 9, 2, 2, 2], [2, 9, 1, 2, 2, 2], [2, 2, 2, 2, 2, 2]],
        [[9, 9, 9, 9], [9, 9, 9, 9], [9, 5, 3, 9], [9, 9, 9, 9]],
    ],
}

print("\n=== 3. rung demos (last row of each is the `test` example) ===")
for task_id, rows in DEMOS.items():
    outputs = []
    print(f"  {task_id}")
    for grid_rows in rows:
        grid = Grid.from_list(grid_rows)
        out = CONTENT_BOX.evaluate(grid, LIBRARY)
        outputs.append(out)
        shrinks = (out.height, out.width) != (grid.height, grid.width)
        print(f"    {grid_rows} -> {out.to_list()}   shrinks={shrinks}")
    train_out = outputs[:-1]
    print(f"    distinct-train-inputs={len({tuple(map(tuple, r)) for r in rows[:-1]}) == len(rows) - 1}")
    print(f"    outputs-vary={len({o.to_list().__repr__() for o in train_out}) > 1}")
