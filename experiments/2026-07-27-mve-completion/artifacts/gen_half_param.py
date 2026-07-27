"""S16: generate `dae9d2b5-half-param` -- the bind-LATE member.

One parameterized rung `half(g, i) = nth(split_h(g), i)` replacing the two monomorphic siblings
`west`/`east`. Same task, same floor, same budget, same (already-paid) raw arm as
`dae9d2b5-split-recolor-lean` -- the ONLY difference is bind-early vs bind-late, which is the
parameterization axis MVE-PLAN names and nothing has sampled.

Demos are FREE: the committed `west-*` grids become `half(input, 0)` demos and the `east-*` grids
become `half(input, 1)` demos, so the free INT param provably VARIES (two distinct values) and
`free-param-varies` holds by construction rather than by luck. Writes a DRAFT; lint/probe gate it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "src/arc_lab/program_search/ladders/registry"
SOURCE = REGISTRY / "dae9d2b5-split-recolor-lean.ladder"
OUT = ROOT / "src/arc_lab/program_search/ladders/drafts/dae9d2b5-half-param.ladder"

src = SOURCE.read_text()


def task_block(name: str) -> str:
    """One `task <name> { ... }` block, verbatim."""
    match = re.search(r"    (heldout )?task " + re.escape(name) + r" \{\n.*?\n    \}\n", src, re.S)
    assert match, name
    return match.group(0)


def rebind(block: str, old_id: str, new_id: str, index: int, heldout: bool = False) -> str:
    """Re-point a `west`/`east` demo at the parameterized rung: same grids, param bound at the
    call site (the al14 convention, `move_cell_up(input, 1, 0)`)."""
    block = block.replace(f"task {old_id} {{", f"task {new_id} {{")
    block = re.sub(r"solution: \w+\(input\)", f"solution: half(input, {index})", block)
    if heldout and not block.lstrip().startswith("heldout"):
        block = block.replace("    task ", "    heldout task ", 1)
    return block


HEADER = """ladder dae9d2b5-half-param

# ``dae9d2b5-half-param``: the BIND-LATE member of the `dae9d2b5` cohort -- ONE parameterized rung
# replacing two monomorphic siblings.
#
# `dae9d2b5-split-recolor-lean` names the two halves as SEPARATE arity-1 rungs (`west`, `east`,
# bind-early: the index is baked into each). Here a single arity-2 rung
# ``half(g, i) = nth(split_h(g), i)`` serves both branches, and the index is bound at the CALL SITE
# by its consumers. Same task, same floor, same `max_pool`, same guard, same already-paid raw arm --
# the ONLY difference is where the index is bound. This is the parameterization axis MVE-PLAN
# declares per sub-cohort ("the bind-early/bind-late choice it is") and that nothing had sampled.
#
# It is also the ONLY cheap structural variation these cohorts still admit: the 2026-07-27 cut-set
# enumeration proved the granularity axis EXHAUSTED (46 cut-sets, every affordable one already
# built), but that enumeration ranges over SUBSETS OF EXISTING INTERMEDIATE TERMS -- and `half` is a
# different FUNCTION (arity 2), so no cut-set can express it.
#
# **REGISTERED PREDICTIONS, written before lint or probe.**
#
# 1. COST -- genuinely undecided, which is why it is worth running. A wider-arity library entry
#    costs more per entry (measured 2026-07-27: ~1.03x round-1 base-width growth for arity-1 mints
#    vs 3.82x at the single arity-3 point), but this member carries one FEWER entry (3 rungs, not
#    4). Which effect dominates is not predictable from anything we have measured.
# 2. LEARNABILITY -- the real prize, and a SECOND falsification route for the proposer question.
#    `AntiunifyPairs` will be offered BOTH readings of the same four retained programs: the two
#    specialised arity-1 templates (each `nth(split_h(input), k)` recurs verbatim, so
#    `Counter(programs)` offers it) AND the generalised arity-2 template from antiunifying the
#    distinct pair (`nth(split_h(input), ?)`). GreedyMDL then chooses. Predicted: the arity-2 form
#    wins (one entry covering four programs beats two entries covering two each) and rung recovery
#    reads 3/3. If instead it SPECIALISES into two arity-1 mints, `half` is not recovered at its
#    intended arity -- a nonzero learned-vs-oracle gap from a second, independent direction, and one
#    that is about GOVERNANCE (what MDL prefers) rather than about proposer reach (S15's mechanism).
#    Either way the readout is clean, because `matches_target` grades arity.
#
# The competence, floor, withheld set and skip argument are unchanged from the cohort's other
# members; only the spine's binding structure moves. `d_raw` stays 4.
#
# **Skip-audit, by hand, before any probe** (LADDER-PROCESS section 5): every rung is d2 and every
# consumer runs at d2, so inlining any rung into its consumer costs d3 against a level budget of 2.
# `half` specifically: skipping it makes `recolored_west` = `map_color(nth(split_h(g),0),4,6)`, d3
# against budget 2 -- unreachable, so skip-freeness holds for the same reason as the sibling form.

config {
    budget.depth_limit: 2
    budget.max_arity: 3
    budget.max_pool: 30
    budget.considered_limit: 2000000
    search_engine.constant_sources: ['finite-enumerate-scalars']
}

floor dae9d2b5-split-L0 {
    use split_h:   (Grid) -> List[Grid]
    use nth:       (List[a], Int) -> a
    use overlay:   (Color, Grid...) -> Grid
    use map_color: (Grid, Color, Color) -> Grid
}

rung {
    half(g: Grid, i: Int) -> Grid = nth(split_h(g), i)

"""

parts = [HEADER]
# The param VARIES across the demo set by construction: two demos at i=0, two at i=1.
parts.append(rebind(task_block("west-00"), "west-00", "half-w0", 0))
parts.append(rebind(task_block("west-01"), "west-01", "half-w1", 0))
parts.append(rebind(task_block("east-00"), "east-00", "half-e0", 1))
parts.append(rebind(task_block("east-01"), "east-01", "half-e1", 1))
parts.append(rebind(task_block("west-heldout"), "west-heldout", "half-heldout", 0, heldout=True))
parts.append("}\n\n")

# The two recolour rungs keep their committed demo grids verbatim; only the template line moves
# from the sibling rung to a parameterized call.
for rung, index, colour in (("recolored_west", 0, 4), ("recolored_east", 1, 3)):
    parts.append(
        f"rung {{\n    {rung}(g: Grid) -> Grid = map_color(half(g, {index}), {colour}, 6)\n\n"
    )
    for suffix in ("00", "01"):
        parts.append(task_block(f"{rung}-{suffix}"))
    parts.append(task_block(f"{rung}-heldout"))
    parts.append("}\n\n")

top = re.search(r"top \{\n.*\n\}\n?$", src, re.S)
assert top
parts.append(top.group(0))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("".join(parts))
print(f"wrote {OUT.relative_to(ROOT)}")
