"""v5 core, iteration 2 -- tests four fixes at once:
  (a) drop largest_filled_square: use relative_tile(g,0,0) for the source tile.
  (b) fragment-demo the Color/Mask rungs (they appear inside grid-valued demo solutions) + StitchProposer
      -> so sleep actually LEARNS them, instead of gifting them task-less.
  (c) ASYMMETRIC source squares (distinct-valued cells) so flip_h/flip_v/rot180 differ (no pattern collision).
  (d) remove write_relative_tile from the floor; placement-free top (a single completed tile) -> the seed
      -recolor rungs no longer share a budget with the 3-grid placement primitive.

Guard dropped from the seed-source read (grids always have >=2 seeds), so no `if`/length/lt -> the read is
depth 3 and its fragment wrapper is depth 5 (fits depth_limit 5).
"""

import numpy as np
from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES as B

# (H, W, src r, c, size s, per-tile [(dr,dc,color),(dr,dc,color)] for right/below/diag). Source square is
# filled with DISTINCT values 1..s^2 (asymmetric) so the three mirrored patterns differ.
SPECS = {
    "G0": (10, 10, 1, 1, 2, [[(0, 0, 8), (1, 1, 4)], [(0, 1, 5), (1, 0, 6)], [(0, 0, 2), (1, 1, 9)]]),
    "G1": (12, 12, 2, 1, 3, [[(0, 1, 5), (2, 0, 6)], [(1, 1, 8), (2, 2, 3)], [(0, 0, 1), (2, 1, 7)]]),
    "G2": (10, 10, 2, 2, 2, [[(0, 1, 2), (1, 0, 9)], [(0, 0, 3), (1, 1, 5)], [(1, 0, 7), (0, 1, 4)]]),
    "G3": (13, 13, 1, 2, 3, [[(1, 1, 1), (2, 2, 7)], [(0, 2, 6), (2, 0, 8)], [(1, 2, 3), (2, 1, 9)]]),
    "G4": (11, 11, 1, 1, 2, [[(0, 0, 3), (1, 0, 5)], [(0, 1, 2), (1, 1, 8)], [(0, 0, 6), (1, 1, 1)]]),
    "G5": (12, 12, 3, 2, 3, [[(0, 0, 4), (1, 2, 5)], [(2, 1, 9), (0, 1, 3)], [(1, 1, 6), (2, 2, 8)]]),
}


def build(h, w, r, c, s, tiles):
    a = np.zeros((h, w), dtype=np.int64)
    v = 1
    for i in range(s):  # DISTINCT nonzero values -> asymmetric square
        for j in range(s):
            a[r + i, c + j] = v
            v += 1
    for (tr, tc), seeds in zip([(r, c + s), (r + s, c), (r + s, c + s)], tiles):
        for dr, dc, col in seeds:
            a[tr + dr, tc + dc] = col
    return Grid(a)


GR = {k: build(*v) for k, v in SPECS.items()}
for k, v in SPECS.items():
    r, c, s = v[2], v[3], v[4]
    src = B["relative_tile"].impl(GR[k], 0, 0)  # relative_tile(g,0,0) == the source square
    assert src.to_list() == [[1 + i * s + j for j in range(s)] for i in range(s)], f"{k} src"
    # asymmetric: the three mirrors differ
    assert B["flip_h"].impl(src).to_list() != B["flip_v"].impl(src).to_list(), f"{k} symmetric!"
    assert r + 2 * s <= v[0] and c + 2 * s <= v[1], f"{k} tiles OOB"
    for d, rt in [(0, 1), (1, 0), (1, 1)]:
        assert len(B["content_coords"].impl(B["relative_tile"].impl(GR[k], d, rt), 0)) >= 2, f"{k}{d}{rt}"


def lit(name):
    return str(GR[name].to_list()).replace(" ", "")


FLOOR = [
    "flip_h: (Grid) -> Grid", "flip_v: (Grid) -> Grid", "map_color: (Grid, Color, Color) -> Grid",
    "mask_by_color: (Grid, Color) -> Mask", "mask_union: (Mask, Mask) -> Mask",
    "mask_complement: (Mask) -> Mask", "paint_through_mask: (Grid, Mask, Color) -> Grid",
    "content_colors: (Grid, Color) -> List[Color]", "nth_or_default: (List[a], Int, a) -> a",
    "content_coords: (Grid, Color) -> List[Coord]", "nth: (List[a], Int) -> a",
    "read_color_at_coord: (Grid, Coord) -> Color",
    "relative_tile: (Grid, Int, Int) -> Grid",  # kept a built-in; NO write_relative_tile
]

DIRS = [("right_pattern(input)", "relative_tile(input, 0, 1)"),
        ("below_pattern(input)", "relative_tile(input, 1, 0)"),
        ("diagonal_pattern(input)", "relative_tile(input, 1, 1)")]

# (name, signature, body, kind, wrapper)   kind: 'g' grid rung demo=rung(input); 'ps'/'s' vary over dirs;
# non-Grid rungs give a Grid-valued WRAPPER with the rung as a fragment (wrapper uses {p},{s}).
RUNGS = [
    ("rot180", "(g: Grid) -> Grid", "flip_h(flip_v(g))", "g", None),
    ("right_pattern", "(g: Grid) -> Grid", "flip_h(relative_tile(g, 0, 0))", "g", None),
    ("below_pattern", "(g: Grid) -> Grid", "flip_v(relative_tile(g, 0, 0))", "g", None),
    ("diagonal_pattern", "(g: Grid) -> Grid", "rot180(relative_tile(g, 0, 0))", "g", None),
    ("first_source_color", "(pattern: Grid, seeds: Grid) -> Color",
     "read_color_at_coord(pattern, nth(content_coords(seeds, 0), 0))", "ps",
     "map_color({p}, first_source_color({p}, {s}), 0)"),
    ("second_source_color", "(pattern: Grid, seeds: Grid) -> Color",
     "read_color_at_coord(pattern, nth(content_coords(seeds, 0), 1))", "ps",
     "map_color({p}, second_source_color({p}, {s}), 0)"),
    ("first_target_color", "(seeds: Grid) -> Color",
     "nth_or_default(content_colors(seeds, 0), 0, 0)", "s",
     "map_color({s}, 0, first_target_color({s}))"),
    ("second_target_color", "(seeds: Grid) -> Color",
     "nth_or_default(content_colors(seeds, 0), 1, 0)", "s",
     "map_color({s}, 0, second_target_color({s}))"),
    ("source_mask", "(pattern: Grid, seeds: Grid) -> Mask",
     "mask_union(mask_by_color(pattern, first_source_color(pattern, seeds)), "
     "mask_by_color(pattern, second_source_color(pattern, seeds)))", "ps",
     "paint_through_mask({p}, source_mask({p}, {s}), 0)"),
    ("seeded_source_mask", "(pattern: Grid, seeds: Grid) -> Grid",
     "paint_through_mask(pattern, mask_complement(source_mask(pattern, seeds)), 0)", "ps", None),
    ("instantiate_first", "(pattern: Grid, seeds: Grid) -> Grid",
     "map_color(seeded_source_mask(pattern, seeds), first_source_color(pattern, seeds), "
     "first_target_color(seeds))", "ps", None),
    ("instantiate_seeded_tile", "(pattern: Grid, seeds: Grid) -> Grid",
     "map_color(instantiate_first(pattern, seeds), second_source_color(pattern, seeds), "
     "second_target_color(seeds))", "ps", None),
]

out = ["ladder cfb2ce5a-5-lowered-core", ""]
out += ["# v5 core (iteration 2): source tile = relative_tile(g,0,0); Color/Mask rungs are FRAGMENT-demoed",
        "# and learned by Stitch; asymmetric squares; NO write_relative_tile; placement-free top.", ""]
out += ["config {", "    budget.depth_limit: 5", "    budget.max_pool: 6000",
        "    search_engine.constant_sources: ['finite-enumerate-scalars']",
        "    learn.learn_engine.proposer: 'StitchProposer'", "}", ""]
out += ["floor cfb2ce5a-lowered-core-L0 {"] + [f"    use {f}" for f in FLOOR] + ["}", ""]

TRIP = [("G0", "G1", "G2"), ("G2", "G3", "G4"), ("G4", "G5", "G0")]


def task(tid, sol, trains, test, heldout=False):
    kw = "heldout task" if heldout else "task"
    return [f"    {kw} {tid} {{", f"        solution: {sol}"] + \
        [f"        train {lit(g)}" for g in trains] + [f"        test  {lit(test)}", "    }"]


for name, sig, body, kind, wrap in RUNGS:
    out.append("rung {")
    out.append(f"    {name}{sig} = {body}")
    if kind in ("ps", "s"):
        for i, (tr0, tr1, te) in enumerate(TRIP):
            p, s = DIRS[i]
            sol = wrap.format(p=p, s=s) if wrap else (
                f"{name}({p}, {s})" if kind == "ps" else f"{name}({s})")
            out += task(f"{name}-{i}", sol, [tr0, tr1], te, heldout=(i == 2))
    else:
        out += task(f"{name}-00", f"{name}(input)", ["G0", "G1"], "G2")
        out += task(f"{name}-01", f"{name}(input)", ["G2", "G3"], "G4")
        out += task(f"{name}-heldout", f"{name}(input)", ["G4", "G5"], "G0", heldout=True)
    out += ["}", ""]

out += ["top {", "    task completed-diagonal-tile {",
        "        solution: instantiate_seeded_tile(diagonal_pattern(input), relative_tile(input, 1, 1))",
        f"        train {lit('G0')}", f"        train {lit('G1')}", f"        test  {lit('G2')}",
        "    }", "}"]

path = "src/arc_lab/program_search/ladders/drafts/cfb2ce5a-5-lowered-core.ladder"
open(path, "w").write("\n".join(out) + "\n")
print("wrote", path, "-", len(RUNGS), "rungs")
