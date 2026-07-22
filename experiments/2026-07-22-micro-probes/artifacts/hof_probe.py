"""Battery E: the higher-order tax — `map` / `filter` / `fold`, and the two ways to fill their holes.

The other four batteries move factors the batch already had *some* reading on. This one has none:
no ladder in the 20-ladder batch has a higher-order floor, so "how much does a HOF cost?" has been
answered only by argument. It is also the factor with the most structure to it, because a function
hole can be filled two ways and they are not the same kind of expensive:

* `point-free` — the hole is filled from POOLED function values (a `PrimRef`, or a pooled lambda).
  Cost is a product term like any other slot: |functions of the right arrow type| x |list values|.
* `lambda-synthesis` — the hole is filled by a RECURSIVE BODY SEARCH per candidate. Cost is not a
  product term at all; it is a whole nested search per candidate, which is why
  `execution/forecast_cost` refuses to model it and flags its own answer as a lower bound.

There is a third knob that turns out to matter more than either: `unpinned_type_var_mode`. A hole
whose RETURN type is a free type variable (`map : (a) -> b`) cannot be synthesised under the
default `reject`, so `map @ lambda-synthesis` silently degrades to point-free fill. `filter`
(`(a) -> bool`) and `fold` (`(acc) -> (a) -> acc`) have pinned hole returns and are unaffected.
The battery runs both modes so the gap is on the record rather than inferred.

Same harness, same fixed task and budget as `micro_probes.py`; the floor gains list plumbing
(`cells` / `from_cells`) in every cell so a list-typed value exists for a HOF to consume.

Usage: uv run python experiments/2026-07-22-micro-probes/artifacts/hof_probe.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from micro_probes import CONFIG, library, run_cell, show  # a sibling artifact script

#: List plumbing present in EVERY cell of this battery, HOF or not: without a `list[color]` value
#: in the pool a higher-order primitive has nothing to be applied to, and the comparison would be
#: between a floor that can build lists and one that cannot rather than between HOF policies.
PLUMBING = ("cells", "from_cells")


def battery_hof(depth: int) -> None:
    lib_control = library("plumbing", PLUMBING)
    cells = [run_cell("plumbing only (no HOF)", lib_control, depth=depth)]
    for hof in ("map", "filter", "fold"):
        lib = library(f"plumbing+{hof}", (*PLUMBING, hof))
        for mode in ("none", "point-free", "lambda-synthesis"):
            cells.append(
                run_cell(
                    f"+ {hof} @ {mode}",
                    lib,
                    depth=depth,
                    engine=replace(CONFIG.search_engine, function_hole_fill_mode=mode),
                )
            )
        cells.append(
            run_cell(
                f"+ {hof} @ synth, grounded",
                lib,
                depth=depth,
                engine=replace(
                    CONFIG.search_engine,
                    function_hole_fill_mode="lambda-synthesis",
                    unpinned_type_var_mode="eager_grounding_over_universe",
                ),
            )
        )
    show(
        f"E. Higher-order tax (depth {depth})",
        "Every cell carries the same list plumbing; only the HOF and its hole-fill policy move.\n"
        "`none` is the control: it shows what a HOF costs when its holes can never be filled.\n"
        "`synth, grounded` re-runs lambda-synthesis with `unpinned_type_var_mode` relaxed, which\n"
        "is the only cell where `map`'s free hole return type can be resolved at all.",
        cells,
    )


def main() -> None:
    print("# Battery E: the higher-order tax")
    for depth in (2, 3):
        battery_hof(depth)


if __name__ == "__main__":
    main()
