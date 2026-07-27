"""S18: ground-truth anchoring for `a740d043` -- the FIRST HARD GATE for a second task family.

LADDER-PROCESS section 2: hand-author the solution term over the current substrate, verify it
against *all* train examples AND the held-out tests, before any floor, spine or demo work. Every
downstream artifact derives from the term, so nothing else is worth doing until this passes.

`a740d043` is a CROP-AND-RECOLOUR task -- structurally unlike the two-halves family every existing
real-task ladder belongs to (split + combine), and it routes through a PERCEIVER
(`most_common_color`) rather than a fixed colour constant. Read off the grids: the background is the
most common colour, the answer is the bounding box of the non-background content with the
background recoloured to 0.

Candidate terms, cheapest first -- and the cheap ones are tested precisely so a shallower reading
cannot be missed (a term deeper than necessary manufactures a false `d_raw`).
"""

from __future__ import annotations

from arc_lab.core.dataset import load_corpus
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR

TASK_ID = "a740d043"
# The whole registry: anchoring asks what the SUBSTRATE can express, not what any floor holds.
LIBRARY = Library(name="registry", primitives=tuple(BASE_PRIMITIVES.values()))

G = Input()
BG = Apply("most_common_color", (G,))
CROP = Apply("crop_to_content", (G,))
#: `crop_to_content` unfolded -- the withheld-primitive route a ladder floor would actually use.
CROP_VIA_MASK = Apply("crop_to_mask", (G, Apply("nonbg_mask", (G,))))
NONBG_VIA_ALGEBRA = Apply("mask_complement", (Apply("mask_by_color", (G, BG)),))

CANDIDATES: list[tuple[str, Program]] = [
    (
        "map_color(crop_to_content(g), 1, 0)",
        Apply("map_color", (CROP, Const(1, COLOR), Const(0, COLOR))),
    ),
    (
        "map_color(crop_to_content(g), most_common_color(g), 0)",
        Apply("map_color", (CROP, BG, Const(0, COLOR))),
    ),
    (
        "map_color(crop_to_mask(g, nonbg_mask(g)), most_common_color(g), 0)",
        Apply("map_color", (CROP_VIA_MASK, BG, Const(0, COLOR))),
    ),
    (
        "map_color(crop_to_mask(g, mask_complement(mask_by_color(g, mcc(g)))), mcc(g), 0)",
        Apply("map_color", (Apply("crop_to_mask", (G, NONBG_VIA_ALGEBRA)), BG, Const(0, COLOR))),
    ),
]

task = next(e.task for e in load_corpus("arc1-train").entries if e.task.task_id == TASK_ID)
examples = [*task.train, *task.test]
print(f"{TASK_ID}: {len(task.train)} train + {len(task.test)} test example(s)\n")

for label, term in CANDIDATES:
    results = []
    for example in examples:
        try:
            got = term.evaluate(example.input, LIBRARY)
        except Exception as exc:
            results.append(f"ERR({type(exc).__name__})")
            continue
        results.append("ok" if got == example.output else "MISMATCH")
    verdict = "ANCHORED" if all(r == "ok" for r in results) else "no"
    print(f"{verdict:9} {len(results) - results.count('ok')}/{len(results)} bad  {label}")
    if verdict == "no" and "ERR" not in "".join(results):
        print(f"          per-example: {results}")
