"""Deterministic dae9d2b5-realizable grids: h x 2w, left half in {0,4}, right half in {0,3}.

No RNG (repo discipline): a stride pattern keyed by (variant, row, col). Every grid is checked to
have BOTH colours present in BOTH halves -- a half with no 4s would let any source colour satisfy
`map_color(half, 4, 6)`, so this is what forces the intended recolour -- and the halves are never
equal, which is what keeps `nth(split_h(g), 0)` and `nth(split_h(g), 1)` distinguishable.
"""

def grid(variant: int, h: int, w: int) -> list[list[int]]:
    rows = []
    for r in range(h):
        west = [4 if (r * 7 + c * 11 + variant * 13) % 5 < 2 else 0 for c in range(w)]
        east = [3 if (r * 5 + c * 13 + variant * 17) % 5 < 2 else 0 for c in range(w)]
        rows.append(west + east)
    return rows

def discriminating(g: list[list[int]]) -> bool:
    w = len(g[0]) // 2
    west = [v for row in g for v in row[:w]]
    east = [v for row in g for v in row[w:]]
    return 4 in west and 0 in west and 3 in east and 0 in east

def emit(name: str, variant: int, shapes: list[tuple[int, int]], solution: str) -> list[str]:
    lines = [f"    task {name} {{", f"        solution: {solution}"]
    for i, (h, w) in enumerate(shapes):
        g = grid(variant + i * 3, h, w)
        assert discriminating(g), f"{name} shape {(h, w)} is not discriminating"
        kind = "test " if i == len(shapes) - 1 else "train"
        lines.append(f"        {kind} " + str(g).replace(" ", ""))
    lines.append("    }")
    return lines

TASKS = [
    ("recolored_west-00", 11, [(3, 3), (4, 4), (2, 3)]),
    ("recolored_west-01", 23, [(5, 3), (2, 5), (3, 4)]),
    ("recolored_west-heldout", 37, [(4, 3), (3, 5), (5, 4)]),
    ("recolored_east-00", 41, [(2, 4), (5, 3), (3, 3)]),
    ("recolored_east-01", 53, [(3, 5), (4, 3), (2, 4)]),
    ("recolored_east-heldout", 67, [(5, 4), (2, 3), (4, 5)]),
]
seen: dict[str, str] = {}
for name, variant, shapes in TASKS:
    rung = "recolored_west" if "west" in name else "recolored_east"
    for line in emit(name, variant, shapes, f"{rung}(input)"):
        print(line)
    for i, (h, w) in enumerate(shapes):        # no two tasks may share a grid
        key = str(grid(variant + i * 3, h, w))
        assert key not in seen, f"{name} reuses a grid from {seen[key]}"
        seen[key] = name
