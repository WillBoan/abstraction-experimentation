"""S19: is the lint's `proposer-compat` capability table WRONG about `FrequentSubtree`?

S15 measured `FrequentSubtree` recovering 0/4 and 0/5 rungs on ladders whose rungs are demoed as
FULL solutions, and traced it to `antiunify.py`'s miner taking `list(program.walk())[1:]` -- each
program's own ROOT excluded. But `checks/learnability.py::_PROPOSER_CAPABILITIES` declares

    "FrequentSubtree": {FULL_SOLUTION, FRAGMENT_IDENTICAL}

If the root exclusion is real, that entry lets `proposer-compat` PASS a ladder that structurally
cannot mint any of its rungs -- a lint that certifies an unlearnable ladder as learnable.

This script tests the mechanism directly, then checks the RETRODICTION on `al4-mask-crop`, the one
ladder in the batch actually configured with `FrequentSubtree`: if the corrected table is right, it
should flag exactly al4's rungs that failed to recover in the real run (register: "Rung recovery: r1
only") and NOT flag r1.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.registry import load_ladder
from arc_lab.program_search.learn.antiunify import (
    AntiunifyPairs,
    FrequentSubtree,
    SearchScopedFrequentSubtree,
    TypeScopedFrequentSubtree,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Input, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import GRID

LIBRARY = Library(name="registry", primitives=tuple(BASE_PRIMITIVES.values()))

# --- 1. The mechanism, minimally ------------------------------------------------------------
# Two programs that ARE the same idiom at their root -- exactly a FULL_SOLUTION demonstration pair
# (what every non-al4 ladder in the batch shows its rungs at).
ROOT_ONLY: list[Program] = [
    Apply("crop_to_mask", (Input(), Apply("nonbg_mask", (Input(),)))),
    Apply("crop_to_mask", (Input(), Apply("nonbg_mask", (Input(),)))),
]
# The same idiom sitting UNDER a wrapper -- a FRAGMENT_IDENTICAL demonstration pair (al4's r1).
#
# The wrappers must DIFFER, and that is not cosmetic: with two IDENTICAL wrappers the whole root is
# itself the best compressor, so `StitchProposer` offers the WRAPPER and looks incapable. It is not
# -- `fragment_identical` means the fragment recurs across DISTINCT solutions, so distinct wrappers
# are the faithful fixture. (First run of this script used identical ones and mis-convicted Stitch.)
WRAPPED: list[Program] = [
    Apply("flip_h", (ROOT_ONLY[0],)),
    Apply("flip_v", (ROOT_ONLY[1],)),
]

TARGET = "crop_to_mask"


def offers(proposer: object, programs: list[Program]) -> list[Program]:
    return proposer.propose(programs, LIBRARY)  # type: ignore[attr-defined,no-any-return]


def build_proposers() -> list[object]:
    """Every proposer `_PROPOSER_CAPABILITIES` makes a claim about -- so the correction is
    evidence-based for each entry, not extrapolated from `FrequentSubtree` by analogy."""
    proposers: list[object] = [
        AntiunifyPairs(),
        FrequentSubtree(),
        TypeScopedFrequentSubtree(result_type=GRID),
        SearchScopedFrequentSubtree(composes=lambda _params, _ret: True),
    ]
    try:  # dep-gated; absent is a skip, never a claim
        from arc_lab.program_search.learn.stitch_shim import StitchProposer

        proposers.append(StitchProposer())
    except Exception as exc:  # noqa: BLE001
        print(f"  (StitchProposer unavailable: {type(exc).__name__}: {exc})")
    return proposers


print("=== 1. mechanism: can the proposer offer the demonstrated idiom? ===")
PROPOSERS = build_proposers()
for label, programs in (("FULL_SOLUTION demos", ROOT_ONLY), ("FRAGMENT_IDENTICAL demos", WRAPPED)):
    for proposer in PROPOSERS:
        name = type(proposer).__name__
        try:
            got = offers(proposer, programs)
        except Exception as exc:  # noqa: BLE001
            print(f"  {label:26} {name:28} ERROR {type(exc).__name__}: {exc}")
            continue
        hit = any(isinstance(t, Apply) and t.primitive == TARGET for t in got)
        print(f"  {label:26} {name:28} offers={len(got):2}  target-offered={hit}")

# --- 2. the retrodiction on al4-mask-crop ---------------------------------------------------
print("\n=== 2. retrodiction: al4-mask-crop (the batch's only FrequentSubtree ladder) ===")
loaded = load_ladder("al4-mask-crop")
for level, (block, demos) in enumerate(
    zip(loaded.document.rungs, loaded.demonstrations, strict=True), start=1
):
    kinds = sorted({demo.kind.value for demo in demos})
    minable = "full_solution" not in kinds
    print(f"  r{level} {block.name:18} demo-kinds={kinds}  corrected-check-says-minable={minable}")
print("  register records of the real run: 'Rung recovery: r1 only'")
