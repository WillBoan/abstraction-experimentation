"""Generate the vertical-NOR cohort `.ladder` files (`94f9d214`, `fafffa47`).

The COHORT TEMPLATE, made concrete: one floor + one spine + one demo generator, instantiated per
task. Both tasks are the same rule (vertical NOR -> colour 2) on different palettes, so the only
per-task input is the north half's colour. Committed under experiments/ per LADDER-PROCESS section 8
-- the `.ladder` files are authoritative and regeneration is explicitly NOT the workflow.

No RNG (repo discipline): a stride pattern keyed by (variant, row, col). Every grid is checked to
be DISCRIMINATING -- both colours present in both halves (so each `map_color` is forced), the two
halves differing as patterns (so `north`/`south` are distinguishable), and the NOR non-trivial
(at least one cell blank in both AND at least one filled), which is what stops the top collapsing
to a constant.
"""

TARGET = 2

def grid(variant: int, h: int, w: int, c_north: int) -> list[list[int]]:
    rows = []
    for r in range(h):  # north half
        rows.append([c_north if (r * 7 + c * 11 + variant * 13) % 5 < 2 else 0 for c in range(w)])
    for r in range(h):  # south half
        rows.append([1 if (r * 5 + c * 13 + variant * 17) % 5 < 2 else 0 for c in range(w)])
    return rows

def discriminating(g: list[list[int]], c_north: int) -> bool:
    h = len(g) // 2
    north, south = g[:h], g[h:]
    flat_n = [v for row in north for v in row]
    flat_s = [v for row in south for v in row]
    both_blank = any(north[r][c] == 0 and south[r][c] == 0 for r in range(h) for c in range(len(g[0])))
    either = any(north[r][c] or south[r][c] for r in range(h) for c in range(len(g[0])))
    patterns_differ = [[v != 0 for v in row] for row in north] != [[v != 0 for v in row] for row in south]
    return (c_north in flat_n and 0 in flat_n and 1 in flat_s and 0 in flat_s
            and both_blank and either and patterns_differ)

def task_block(name: str, solution: str, variant: int, shapes, c_north: int, heldout: bool) -> str:
    lines = [f"    {'heldout task' if heldout else 'task'} {name} {{",
             f"        solution: {solution}"]
    for i, (h, w) in enumerate(shapes):
        g = grid(variant + i * 3, h, w, c_north)
        assert discriminating(g, c_north), f"{name} {(h, w)} is not discriminating"
        kind = "test " if i == len(shapes) - 1 else "train"
        lines.append(f"        {kind} " + str(g).replace(" ", ""))
    lines.append("    }")
    return "\n".join(lines)

#: (task id, north colour). South is colour 1 in both; the target is 2 in both.
COHORT = (("94f9d214", 3), ("fafffa47", 9))

#: (demo name, variant, shapes, heldout) -- distinct shapes AND variants per task, so no two
#: tasks in the cohort ever share a grid.
DEMOS = (
    ("north-00", 11, [(3, 3), (4, 4), (2, 3)], False),
    ("north-01", 23, [(5, 3), (2, 5), (3, 4)], False),
    ("north-heldout", 37, [(4, 3), (3, 5), (5, 4)], True),
    ("south-00", 41, [(2, 4), (5, 3), (3, 3)], False),
    ("south-01", 53, [(3, 5), (4, 3), (2, 4)], False),
    ("south-heldout", 67, [(5, 4), (2, 3), (4, 5)], True),
    ("recolored_north-00", 71, [(3, 4), (2, 5), (4, 3)], False),
    ("recolored_north-01", 83, [(4, 5), (3, 3), (5, 3)], False),
    ("recolored_north-heldout", 97, [(2, 5), (5, 4), (3, 4)], True),
    ("recolored_south-00", 101, [(5, 5), (3, 4), (2, 4)], False),
    ("recolored_south-01", 113, [(2, 3), (4, 4), (5, 5)], False),
    ("recolored_south-heldout", 127, [(3, 3), (5, 5), (4, 4)], True),
)


FLOOR = """floor nor-L0 {
    use split_v:     (Grid) -> List[Grid]
    use nth:         (List[a], Int) -> a
    use overlay:     (Color, Grid...) -> Grid
    use map_color:   (Grid, Color, Color) -> Grid
    use swap_colors: (Grid, Color, Color) -> Grid
}"""

CONFIG = """config {
    budget.depth_limit: 3
    budget.max_arity: 3
    budget.max_pool: 30
    budget.considered_limit: 2000000
    search_engine.constant_sources: ['finite-enumerate-scalars']
}"""


def header(tid: str, c_north: int, fine: bool) -> str:
    name = f"{tid}-nor-{'recolor' if fine else 'halves'}"
    cut = "FOUR rungs" if fine else "TWO rungs"
    return f"""ladder {name}

# ``{name}``: the vertical NOR-of-two-halves competence of the real ARC task ``{tid}``
# (arc1-train), cut at {cut}, over the Grid-valued half-split floor.
#
# The competence: a ``2h x w`` grid carries colour {c_north} on its NORTH half and 1 on its SOUTH;
# the answer is the ``h x w`` grid holding 2 exactly where NEITHER half is filled. Verified against
# arc1-train ground truth before authoring (``test_real_arc_anchoring.py``); ``d_raw`` is 5.
#
# **A cohort template, not a bespoke build.** ``94f9d214`` and ``fafffa47`` are the SAME rule on
# different palettes -- the only per-task input is the north half's colour ({c_north} here, the
# other task's is the other value). One floor, one spine, one demo generator
# (``experiments/2026-07-27-mve-ladder-cohorts/artifacts/gen_nor_ladders.py``), instantiated twice.
# That is the multiplier for ladder COUNT: the marginal cost of the second task is a constant.
#
# **NOR without the mask tier.** The obvious route -- ``mask_by_color`` + ``mask_complement`` +
# ``paint_through_mask`` -- forces Mask-valued rungs (every demo then needs a wrapper, costing a
# depth level: the demo-affordability law) AND puts a TERNARY mask writer in the floor, which is
# the known breadth bomb. Instead ``swap_colors`` inverts at the GRID level: recolour each half to
# the target, ``overlay`` them (grid-level OR), then swap 0 with the target, which turns OR into
# NOR in one step. Every rung stays Grid-valued, so every demonstration is a full solution.
#
# **Withheld primitives:** the mask algebra above, and any single-step half-merger (none exists).
# The floor is otherwise the minimum the top needs; ``d_raw`` 5 against a derived top budget of 3
# falls out of that, so the RQ1 bound is FLOOR-RELATIVE, as always.
#
# **Skip-audit, by hand, before any probe:** every rung is d2 and the top is d3, so inlining any
# rung into its consumer costs at least d3 against a level budget of 2. The
# ``map_color``-distributes-over-``overlay`` law that convicted a merge rung on ``dae9d2b5``
# cannot bite: the top is already stated in the distributed form, and there is no merge rung.
# ``swap_colors`` does NOT distribute over ``overlay`` (it is not colour-wise monotone), so it
# cannot be pushed inside the halves either.
#
# Budget: the pool is the 2026-07-27 calibrated value (30), licensed by the
# ``dae9d2b5-split-recolor`` / ``-lean`` pair, which reproduced its parent's verdict profile
# exactly at 25.4x less spend.

{CONFIG}

{FLOOR}
"""


def rung(name: str, body: str, demos) -> str:
    inner = "\n\n".join(demos)
    return f"rung {{\n    {name}(g: Grid) -> Grid = {body}\n\n{inner}\n}}"


def build(tid: str, c_north: int, fine: bool) -> str:
    from gen_nor_ladders import DEMOS, task_block  # self-import keeps the helpers in one place
    by_name = {d[0]: d for d in DEMOS}

    def demos_for(prefix: str, solution_rung: str):
        return [task_block(n, f"{solution_rung}(input)", v, s, c_north, ho)
                for (n, v, s, ho) in DEMOS if n.startswith(prefix + "-")]

    parts = [header(tid, c_north, fine)]
    parts.append(rung("north", "nth(split_v(g), 0)", demos_for("north", "north")))
    parts.append(rung("south", "nth(split_v(g), 1)", demos_for("south", "south")))
    if fine:
        parts.append(rung("recolored_north", f"map_color(north(g), {c_north}, {TARGET})",
                          demos_for("recolored_north", "recolored_north")))
        parts.append(rung("recolored_south", f"map_color(south(g), 1, {TARGET})",
                          demos_for("recolored_south", "recolored_south")))
        top_body = (f"swap_colors(overlay(0, recolored_north(input), recolored_south(input)), "
                    f"0, {TARGET})")
    else:
        top_body = (f"swap_colors(overlay(0, map_color(north(input), {c_north}, {TARGET}), "
                    f"map_color(south(input), 1, {TARGET})), 0, {TARGET})")
    return "\n\n".join(parts) + "\n\n" + top_block(tid, top_body) + "\n"


def top_block(tid: str, body: str) -> str:
    """The top's tasks are the REAL ARC grids, verbatim -- inputs only; outputs are derived."""
    from arc_lab.core.dataset import load_dataset
    task = next(e.task for e in load_dataset("arc1-train").entries if e.task.task_id == tid)
    train = [ex.input.array.tolist() for ex in task.train]
    test = [ex.input.array.tolist() for ex in task.test]
    lines = [f"top {{", f"    task {tid} {{", f"        solution: {body}"]
    for g in train[:-1]:
        lines.append("        train " + str(g).replace(" ", ""))
    lines.append("        test  " + str(train[-1]).replace(" ", ""))
    lines.append("    }")
    lines.append(f"    heldout task {tid}-heldout {{")
    lines.append(f"        solution: {body}")
    for g in test:
        lines.append("        train " + str(g).replace(" ", ""))
    lines.append("        train " + str(train[0]).replace(" ", ""))
    lines.append("        test  " + str(train[1]).replace(" ", ""))
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)
