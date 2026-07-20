# Ladder: al4-mask-crop

- **Status:** linted
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: normalize a scene — derive the content mask, crop to it, flatten it, stamp it
- Construction method: (2) forward extension

### Reference config

- Floor (`L_0`): `{mask_by_color, most_common_color, least_common_color, mask_complement, mask_union, mask_intersect, crop_to_mask, paint_through_mask, flip_h}`
  - **Withholds** the shipped `nonbg_mask`, `crop_to_content`, `bbox_mask` — they are the re-derivation targets, giving a ready-made gen/full contrast.
- Budget:
  - `depth_limit`: **4** (pinned — the window is [4,4])
  - `max_arity`: 3 (`paint_through_mask` is ternary)
  - `max_pool`: TBD
- Engine options:
  - constant sources: `finite-enumerate` (r2/r3 take free COLOR params)
  - function-hole fill: none
  - polymorphism: monomorphize
- Learn:
  - proposer: **`FrequentSubtree`** (r1 is demonstrated as a fragment — see open problem 1)
  - governance: `GreedyMDL`
  - iterations: 6+

### Rung spine

Depths **machine-computed** (`compositional_depth` / `unfold_program`, 2026-07-19).

| i   | Rung             | Template (over `L_{i-1}`)                                                                      | `d_i` | Inlined double-jump | Free params | Demo kinds    |
| --- | ---------------- | ---------------------------------------------------------------------------------------------- | ----- | ------------------- | ----------- | ------------- |
| 1   | nonbg_mask       | `mask_complement(mask_by_color(g, most_common_color g))` — demoed via a `crop_to_content` wrapper | 3     | 8 (skip nonbg_mask) | 0           | **fragment_identical** |
| 2   | flatten_content  | `paint_through_mask(crop_to_mask(g, nonbg_mask g), nonbg_mask(crop_to_mask(g, nonbg_mask g)), c)` | 4   | 6 (skip flatten)    | 1 (COLOR)   | full_solution |
| 3   | stamp            | `paint_through_mask(flip_h(flatten_content(g,c1)), mask_by_color(flatten_content(g,c1), c1), c2)` | 3 | — | 2 (COLOR)   | full_solution |

### Top Rung (goal layer — no abstraction is minted here)

- Reference solution: `flip_h(flip_v(stamp(g, 3, 5)))`
- `d_top` = 3 over `L_3` · `d_raw` = **12** (the deepest raw in the batch) · top-skip (over `L_2`) = 5

### Sandwich check

- Every `d_i` <= pinned `depth_limit`: 3, 4, 3 <= 4 — OK
- `d_top` <= `depth_limit`: 3 <= 4 — OK
- Every inlined double-jump > `depth_limit`: 8, 6 > 4 — OK (wide margins)
- Top-skip > `depth_limit`: 5 > 4 — OK
- `d_raw` > `depth_limit`: 12 > 4 — OK
- **Validity window: [4, 4]** (width 1)

### Per-rung detail

- **r1 `nonbg_mask`** — param-free. Demos (>= 2): grids with a clear majority background and off-centre content; >= 2 train examples each with **varying background colour** so the literal `mask_by_color(g, k)` shortcut cannot coincide (the E11 trap, in mask form).
  - Demonstrated via the grid-to-grid wrapper `crop_to_mask(g, nonbg_mask g)`, since the target itself is `GRID -> MASK` and can never be a whole solution (open problem 1, resolved).
- **r2 `flatten_content`** — 1 free COLOR param `c` (the flatten target).
  - `c`: free → fixed within task, varied across demonstrating tasks.
  - Demos (>= 2): content off-centre with **varying margins** across examples (a fixed crop must not coincide); content must not touch the border, or the crop is a no-op.
- **r3 `stamp`** — 2 free COLOR params `c1` (flatten target), `c2` (stamp colour).
  - Both free → fixed within task, varied across demos.
  - Demos (>= 2): the stamp mask selects by `c1`, which the flatten step guarantees is present.
- `involves_lambda`? no (all rungs).

### Heldout split

- 1 task per level, disjoint colour/margin choices from train.

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- **The learned-intermediate-type arm.** `nonbg_mask` constructs a `Mask`, and `flatten_content` both constructs and consumes one — the deepest gap-climbing phenomenon on the docket, and the thing no experiment has yet shown sleep can do.
- Deepest `d_raw` in the batch (12) with the widest double-jump margins (8, 6) — structurally the most robust sandwich we have.
- Running it drains the `learned intermediate type` row in EXPERIMENT_QUEUE.md.

### Open problems

1. ~~**Can r1 be demonstrated at all?**~~ **RESOLVED 2026-07-19 — option 3.** `nonbg_mask` is `GRID -> MASK`, so no grid-to-grid task can have it as a whole solution. Resolution: r1's demonstrating tasks are generated from a grid-to-grid **wrapper** that contains it (`crop_to_mask(g, nonbg_mask g)`, ie the withheld `crop_to_content`), the rung is marked `FRAGMENT_IDENTICAL`, and the proposer is `FrequentSubtree` instead of `AntiunifyPairs`. The lint's proposer-compatibility check accepts this and the ladder lints clean. Consequence to carry: al4 is the **only ladder in the batch not using the default proposer**, so cross-ladder cost/mint comparisons involving it are confounded by that choice.


2. `paint_through_mask` is ternary → `max_arity` 3 raises composition counts relative to the arity-2 ladders; not a defect, but it makes cross-ladder cost comparison need care.
3. r2's template repeats `crop_to_mask(g, nonbg_mask g)` twice — a large template. Good for MDL break-even, but check the minted form is the shared-subterm version rather than something the proposer factors differently.

### Dead ends / failed bisections

- **(2026-07-19, build)** `stamp` originally stamped through `mask_by_color(flatten_content(g,c1), least_common_color(g))` — a colour read from the ORIGINAL grid applied to the FLATTENED crop, where it need not survive. Generation died with `mask selects no cells`. Fixed to reference `c1` (the flatten colour, present in the result by construction). General rule for mask ladders: never select by a colour derived from a different grid than the one being masked.
- **(2026-07-19, build)** Generic seeds produced grids whose cropped content was uniform, so the *inner* `nonbg_mask` was empty. Fixed by giving `seed_grids` a `background` frame option (border of one colour, multi-coloured interior), which guarantees a non-empty margin, an unambiguous majority background, and a non-empty mask after cropping. Seeds are now 4x5 framed.

- **(2026-07-19)** First goal layer was `flip_h(stamp(...))`: `d_top`=2, top-skip=4, not exceeding `depth_limit`=4 → **empty validity window**. Fixed by nesting `stamp` one level deeper (`flip_h(flip_v(stamp))`, top-skip 5). Same failure and fix as al3 — see that worksheet's note on deep-jump tops.
- **(2026-07-19, considered and rejected)** A mask-algebra rung built from `mask_intersect`/`mask_complement` over two perceivers: De Morgan makes the intended form and its dual the same depth, so the rung below buys nothing and the double-jump check fails. Mask algebra is too collapsing to carry a rung on its own — it has to be paired with the irreversible crop/paint operations, as above.

### Notes

- Depths verified 2026-07-19 against the real registry; every template passes `make_abstraction` type-checking at its level.
- Minimality not verified — the certificate is the gate.

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/al4_mask_crop.py`): **built** — registry key `al4-mask-crop`
- Generator / committed testbed: **built** — `taskgen al4-mask-crop` -> `testbeds/al4-mask-crop/` (template-driven, regenerates byte-identically)
- Generated artifacts (`spec.md` / `results.md` / `report.json`): — (written on first run)
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: — (lint passes; certificate pending first run)
