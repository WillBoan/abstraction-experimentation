"""Passes B + C: derivability over designated floors, then rung-addition deltas.

Pass B: for each floor F (block subsets mirroring _PRIMITIVE_BUNDLES.md, mono
subset), compute size(T | F) for every target primitive T not in F — the
static jump-depth matrix over floors.

Pass C: for each floor, take the *deep* targets (size >= DEEP_AT or underivable)
and the *shallow* targets (size 2..3) as candidate rungs; recompute
size(T | F + {rung}). A pair where the rung collapses a deep/underivable target
to <= SHALLOW_AT is a statically-certified height-2 ladder skeleton:
Floor = F, r1 = rung, top = T.

Run:  uv run python experiments/2026-07-17-derivability-dag/artifacts/pass_bc_floors.py \
        2>&1 | tee experiments/2026-07-17-derivability-dag/artifacts/pass_bc_floors.out
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

# Floors: mono-compatible mirrors of _PRIMITIVE_BUNDLES.md floors + two composites.
FLOORS: dict[str, list[str]] = {
    "d4_gen_min": ["flip_h", "transpose"],
    "recolor_gen": ["map_color"],
    "perceive_recolor": ["map_color", "most_common_color", "least_common_color"],
    "mask_min": ["nonbg_mask", "crop_to_mask"],
    "mask_basic_gen": [
        "mask_by_color", "nonbg_mask", "mask_union", "mask_intersect",
        "mask_complement", "crop_to_mask", "paint_through_mask",
    ],  # withholds bbox_mask, mask_difference, crop_to_content
    "layout_gen": ["translate", "concat_h", "concat_v", "pad", "downsample", "blank"],
    "cell_stateful": ["read", "set_cell"],
    "arith_basic": ["add", "sub", "mul"],
    "atomic": [
        "rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose",
        "anti_transpose", "map_color", "scale",
    ],
    "d4gen_layout": ["flip_h", "flip_v", "transpose", "concat_h", "concat_v"],
    "d4gen_mask_min": ["flip_h", "transpose", "nonbg_mask", "crop_to_mask", "mask_by_color"],
    "perceive_mask": [
        "mask_by_color", "most_common_color", "crop_to_mask", "paint_through_mask", "map_color",
    ],
}

DEEP_AT = 4      # size >= this (or underivable) counts as a deep/ladder-top candidate
SHALLOW_AT = 3   # size <= this counts as a plausible single learnable jump
MAX_RUNGS = 12
MAX_DEEP_SIGS = 40  # safety cap on (leafsig) groups per floor in pass C


def floor_max_size(n_blocks: int) -> int:
    if n_blocks <= 3:
        return 6
    if n_blocks <= 6:
        return 5
    return 4


def measure_floor(
    floor: dict[str, Block], targets: dict[str, Block], max_size: int
) -> dict[str, int | None]:
    """size(T | floor) for each target; None = not derivable <= max_size; missing = skipped."""
    sizes: dict[str, int | None] = {}
    by_sig: dict[tuple[str, ...], list[Block]] = {}
    for t in targets.values():
        if target_valid_count(t) < 6:
            continue
        by_sig.setdefault(t.param_types, []).append(t)
    for sig, group in sorted(by_sig.items()):
        pool = enumerate_pool(floor, sig, max_size)
        for t in group:
            found = find_derivations(t, pool, floor)
            if found is None:
                continue
            derivs, _ = found
            verified = [d for d in derivs if d.verified]
            sizes[t.name] = verified[0].size if verified else None
    return sizes


def main() -> None:
    blocks = mono_blocks()
    all_results: dict[str, dict] = {}

    for fname, members in FLOORS.items():
        missing = [m for m in members if m not in blocks]
        if missing:
            print(f"!! floor {fname}: unknown blocks {missing}", flush=True)
            continue
        floor = {m: blocks[m] for m in members}
        targets = {n: b for n, b in blocks.items() if n not in floor}
        max_size = floor_max_size(len(floor))
        t0 = time.time()
        sizes = measure_floor(floor, targets, max_size)
        print(f"\n=== floor {fname} ({len(floor)} blocks, max_size {max_size}, "
              f"{time.time()-t0:.0f}s) ===", flush=True)
        derivable = {n: s for n, s in sizes.items() if s is not None}
        underivable = sorted(n for n, s in sizes.items() if s is None)
        for n, s in sorted(derivable.items(), key=lambda kv: (kv[1], kv[0])):
            print(f"  size {s}: {n}", flush=True)
        print(f"  underivable (<= {max_size}): {', '.join(underivable) or '-'}", flush=True)

        # ---- pass C: rung addition ----
        rungs = [n for n, s in sorted(derivable.items()) if 2 <= s <= SHALLOW_AT][:MAX_RUNGS]
        deep = [n for n, s in sizes.items() if s is None or s >= DEEP_AT]
        ladder_pairs: list[dict] = []
        if rungs and deep:
            deep_by_sig: dict[tuple[str, ...], list[Block]] = {}
            for n in deep:
                deep_by_sig.setdefault(blocks[n].param_types, []).append(blocks[n])
            for rung in rungs:
                aug = dict(floor)
                aug[rung] = blocks[rung]
                for sig, group in sorted(deep_by_sig.items())[:MAX_DEEP_SIGS]:
                    pool = enumerate_pool(aug, sig, max_size)
                    for t in group:
                        found = find_derivations(t, pool, aug)
                        if found is None:
                            continue
                        derivs, _ = found
                        verified = [d for d in derivs if d.verified]
                        if not verified:
                            continue
                        new_size = verified[0].size
                        old = sizes.get(t.name)
                        # the ladder condition: deep/unreachable collapses to shallow,
                        # and the witness actually routes through the rung
                        if new_size <= SHALLOW_AT and rung in verified[0].support:
                            ladder_pairs.append({
                                "floor": fname, "rung": rung, "top": t.name,
                                "old_size": old, "new_size": new_size,
                                "witness": verified[0].term,
                            })
        if ladder_pairs:
            print(f"  --- height-2 ladder skeletons (rung collapses top to <= {SHALLOW_AT}) ---",
                  flush=True)
            for p in ladder_pairs:
                old = p["old_size"] if p["old_size"] is not None else f">{max_size}"
                print(f"    {fname}: +{p['rung']} => {p['top']}  "
                      f"({old} -> {p['new_size']}): {p['witness']}", flush=True)
        all_results[fname] = {"sizes": sizes, "ladder_pairs": ladder_pairs,
                              "max_size": max_size}

    out = Path(__file__).parent / "pass_bc_results.json"
    out.write_text(json.dumps(all_results, indent=2))
    print(f"\nwrote {out}", flush=True)


if __name__ == "__main__":
    main()
