"""Pass D: static certification of candidate ladders with COMPOSITE targets.

Passes B/C showed the shipped registry is compositionally flat (height-2 skeletons
only). Taller ladders need composite targets. Here each candidate ladder is a
(floor, rungs, top) spec where rungs/top may be composite reference functions;
the enumerator computes the full static jump matrix — size(goal | L_i) for every
cumulative library L_i = floor + rungs[:i] — which certifies, statically:

  - each intended jump's compositional depth d_i (diagonal of the matrix),
  - double-jump depths (the superdiagonal) for the rung-necessity check,
  - skip paths: the enumerator searches ALL programs, so if a goal is reachable
    cheaper than the intended route, the matrix says so (a cheaper witness).

This is the static half of the design doc's Ladder Certificate (§6); the
empirical half (considered counts, demonstration health) still needs real runs.

Run:  uv run python experiments/2026-07-17-derivability-dag/artifacts/pass_d_ladders.py \
        2>&1 | tee experiments/2026-07-17-derivability-dag/artifacts/pass_d_ladders.out
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from enumlib import (  # noqa: E402
    Block,
    enumerate_pool,
    find_derivations,
    mono_blocks,
    target_valid_count,
)

BLOCKS = mono_blocks()
_f = {n: b.fn for n, b in BLOCKS.items()}


def comp(name: str, param_types: tuple[str, ...], fn) -> Block:
    return Block(name, param_types, "grid", fn)


# ---- composite reference targets (rungs / tops beyond the registry) ----

MIRROR_H = comp("mirror_h", ("grid",), lambda g: _f["concat_h"](g, _f["flip_h"](g)))
QUAD = comp("quad", ("grid",), lambda g: _f["concat_v"](MIRROR_H.fn(g), _f["flip_v"](MIRROR_H.fn(g))))
QUAD2 = comp("quad2", ("grid",), lambda g: QUAD.fn(QUAD.fn(g)))
ROW3 = comp("row3", ("grid",), lambda g: _f["concat_h"](_f["concat_h"](g, g), g))
GRID3X3 = comp("grid3x3", ("grid",), lambda g: _f["concat_v"](_f["concat_v"](ROW3.fn(g), ROW3.fn(g)), ROW3.fn(g)))
GRID9X9 = comp("grid9x9", ("grid",), lambda g: GRID3X3.fn(GRID3X3.fn(g)))
RECOLOR_FLIPPED = comp(
    "recolor_flipped", ("grid", "color", "color"),
    lambda g, a, b: _f["map_color"](_f["rot180"](g), a, b),
)
RECOLOR_BG = comp(
    "recolor_bg", ("grid", "color"),
    lambda g, c: _f["map_color"](g, _f["most_common_color"](g), c),
)
RECOLOR_BG_FLIPPED = comp(
    "recolor_bg_flipped", ("grid", "color"),
    lambda g, c: RECOLOR_BG.fn(_f["rot180"](g), c),
)
CROP_FLIP = comp("crop_flip", ("grid",), lambda g: _f["flip_h"](_f["crop_to_content"](g)))

# ---- ladder specs: (name, floor block names, [rungs...], top, max_size) ----

LADDERS: list[tuple[str, list[str], list[Block], Block, int]] = [
    # registry-mined D4 tower (pass C's best skeleton), E1/E12 territory
    ("d4-tower", ["flip_h", "transpose"], [BLOCKS["rot90"]], BLOCKS["rot180"], 6),
    # ground-truth validation against E12's measured ladder
    ("e12-layered", ["flip_h", "flip_v", "map_color"], [BLOCKS["rot180"]], RECOLOR_FLIPPED, 5),
    # the quad symmetrization tower (round-2 proposal L-A), height 3
    ("quad-tower", ["flip_h", "flip_v", "concat_h", "concat_v"], [MIRROR_H, QUAD], QUAD2, 6),
    # tiling tower with a self-composition top (L-C x L-F), height 3
    ("tile-tower", ["concat_h", "concat_v"], [ROW3, GRID3X3], GRID9X9, 6),
    # perceiver tower extending E11 (round-2 proposal L-B); diamond rungs
    ("perceive-tower", ["flip_h", "flip_v", "map_color", "most_common_color"],
     [BLOCKS["rot180"], RECOLOR_BG], RECOLOR_BG_FLIPPED, 5),
    # mask-domain: learned intermediate-type rung (queued E14 territory)
    ("mask-crop-flip", ["flip_h", "transpose", "nonbg_mask", "crop_to_mask"],
     [BLOCKS["crop_to_content"]], CROP_FLIP, 5),
]


def main() -> None:
    all_out: dict[str, dict] = {}
    for name, floor_names, rungs, top, max_size in LADDERS:
        floor = {n: BLOCKS[n] for n in floor_names}
        stages: list[dict[str, Block]] = [dict(floor)]
        for r in rungs:
            nxt = dict(stages[-1])
            nxt[r.name] = r
            stages.append(nxt)
        goals = list(rungs) + [top]
        print(f"\n=== ladder {name} ===")
        print(f"  floor: {{{', '.join(floor_names)}}}")
        print(f"  rungs: {[r.name for r in rungs]}   top: {top.name}")
        matrix: dict[str, list[object]] = {g.name: [] for g in goals}
        witness: dict[tuple[str, int], str] = {}
        t0 = time.time()
        for i, lib in enumerate(stages):
            pools: dict[tuple[str, ...], object] = {}
            for g in goals:
                if target_valid_count(g) < 6:
                    matrix[g.name].append("SKIP")
                    continue
                if g.param_types not in pools:
                    pools[g.param_types] = enumerate_pool(lib, g.param_types, max_size)
                pool = pools[g.param_types]
                found = find_derivations(g, pool, lib)
                derivs = [d for d in (found[0] if found else []) if d.verified]
                if derivs:
                    matrix[g.name].append(derivs[0].size)
                    witness[(g.name, i)] = derivs[0].term
                else:
                    trunc = "T" if pool.truncated else ""
                    matrix[g.name].append(f">{max_size}{trunc}")
        cols = "".join(f"  L{i:<8d}" for i in range(len(stages)))
        print(f"  {'goal':18s}{cols}")
        for g in goals:
            row = "".join(f"  {str(v):<9s}" for v in matrix[g.name])
            print(f"  {g.name:18s}{row}")
        for i, r in enumerate(rungs):
            w = witness.get((r.name, i))
            if w:
                print(f"  jump {i}->{i+1} ({r.name}): {w}")
        w = witness.get((top.name, len(rungs)))
        if w:
            print(f"  top over L_{len(rungs)} ({top.name}): {w}")
        print(f"  [{time.time()-t0:.0f}s]")
        all_out[name] = {
            "floor": floor_names,
            "rungs": [r.name for r in rungs],
            "top": top.name,
            "matrix": {k: [str(v) for v in vs] for k, vs in matrix.items()},
            "witnesses": {f"{k[0]}@L{k[1]}": v for k, v in witness.items()},
        }
    out = Path(__file__).parent / "pass_d_results.json"
    out.write_text(json.dumps(all_out, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
