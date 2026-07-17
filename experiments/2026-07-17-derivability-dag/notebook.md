# Derivability DAG — systematic ladder mining (2026-07-17)

**Question.** The Abstraction Ladder design (docs/abstraction_ladders/ABSTRACTION-LADDERS-2026-07-16.md) needs a supply of well-formed ladders. Instead of inventing them one at a time, can we *enumerate* them from the substrate itself — by computing, for every shipped primitive, its minimal behavioral derivation over (a) the rest of the library and (b) each designated floor, and then reading ladders off the resulting derivability structure?

**Method (probe, not engine).** A self-contained typed bottom-up enumerator over `BASE_PRIMITIVES` impls (`artifacts/enumlib.py`): compositions over typed `Param` leaves, deduped by observational equivalence on a deterministic 16-tuple sample battery, matched against a target primitive's behavior, then **verified on a disjoint 8-tuple holdout battery** (the E13 accidental-symmetry bug is the cautionary tale — and the holdout check caught exactly such degeneracies twice during battery design, see Dead ends). This measures *static compositional structure* (jump depths, witnesses, support sets) — NOT engine search cost; measured `c_i` must still come from real SEARCH runs on any ladder promoted from here.

Size accounting caveat: the probe's "size" is **tree application count without subterm sharing**. Bottom-up search re-uses pooled subterms, so its solve *generation* tracks nesting depth (e.g. `grid9x9` over its floor is tree-size ~14 but nesting-depth ~8). Both accountings preserve every ladder/rung-necessity conclusion below (the collapses are large either way), but the Ladder Linter should eventually compute `d_i` in the engine's own accounting.

Scope (v1): monomorphic first-order primitives only (55 of 71). Excluded: function-typed (`build_grid`, `map`, `filter`, `fold`, `sort_by`), polymorphic (`eq`, `if`, `pair`, `fst`, `snd`, `head`, `length`, `zip`, `shape`), `identity` (dominated by the bare leaf), `tile` (rows*cols arity coupling; `overlay` fixed at 2 grids). No constant leaves — a derivation must route every Color/Int through the target's own parameters or a perceiver (the static analogue of E11's literal-shortcut discipline). `from_cells` / `move_cell` / `swap_cells` skipped (too few valid sample tuples — length-coupled / coordinate-fussy signatures).

## Passes

- **Pass A — leave-one-out** (`artifacts/pass_a_leave_one_out.py` → `.out`, `pass_a_results.json`): minimal derivation of each primitive over ALL_MONO − {itself}; yields the redundancy partition and the "uses" DAG.
- **Pass B — floors** (`artifacts/pass_bc_floors.py` → `.out`, `pass_bc_results.json`): size(T | F) for every target over 12 floors mirroring `_PRIMITIVE_BUNDLES.md` (mono subsets); the static jump-depth matrix.
- **Pass C — rung addition** (same script): for each floor, re-derive each deep target (size ≥ 4 or underivable) over F + {rung} for each shallow (size 2–3) candidate rung; a collapse to ≤ 3 that routes through the rung is a statically-certified **height-2 ladder skeleton**.
- **Pass D — chains** (`artifacts/pass_d_chains.py`, if run): rung pairs → height-3 skeletons.

## Pass A findings (leave-one-out over the full mono library)

Headline: the mono library splits into a **redundant shell** (~21 primitives derivable at size ≤ 3–4 from the rest, all holdout-verified) and an **atom core** (~30 underivable at those sizes).

Notable structure:

- **D4 is one mutual-derivability clique** (expected — group closure): every member size 2 from two others.
- **`map_color` ↔ `swap_colors` are MUTUALLY derivable** given the mask/overlay machinery: `map_color(g,a,b) = overlay(a, g, swap_colors(g,a,b))` and `swap_colors(g,a,b) = paint_through_mask(map_color(g,a,b), mask_by_color(g,b), a)` (both size ≤ 3, verified). This *refines* `_PRIMITIVE_BUNDLES.md` Constraint 5's "swap_colors is not derivable from map_color" — true within RECOLOR_OPS alone, false once MASK machinery is present. Behavioral-duplicate pressure is floor-relative.
- **Mask algebra is a De Morgan clique**: `intersect`/`difference`/`union` interderivable via `complement` (union needs size 3); `complement` itself is an atom within (mask,)→mask but `nonbg_mask = mask_complement(mask_by_color(g, most_common_color(g)))` (size 3) crosses the perceive→mask seam — a genuine cross-domain rung candidate.
- **Arithmetic**: `sub` alone generates `add` (`p0 − (0 − p1)` via `sub(p0, sub(sub(p0,p0), p1))`); `min`/`max` mutually derivable via `add`/`sub`; `mod = p0 − p1·(p0 ÷ p1)` (Euclid). `mul`, `sub`, `floordiv` are atoms.
- **`height`/`width`** interderivable via one transpose-family member.
- **Atoms** (not derivable ≤ 3, or ≤ 4 for unary grid ops, from the ENTIRE rest of the mono library): `concat_h/v`, `pad`, `translate`, `tile_repeat`, `scale`, `downsample`, `blank`, `cells`, `read`, `set_cell`, `bbox_mask`, `mask_by_color`, `mask_complement`, `paint_through_mask`, `filter_color`, `most/least_common_color`, `palette`, `num_colors`, `count_color`, `mul`, `sub`, `floordiv`, `not`, `and`, `or` (Boolean pair needs size-4 De Morgan through `not`). Parameterized iteration (`tile_repeat`, `scale` with a *free* count parameter) is genuinely inexpressible by fixed-size composition — these need either gifting or a recursion-capable substrate, confirming the bundles doc's gen/full framing.

## Pass B/C findings (floors + rung addition)

Full matrix in `artifacts/pass_bc_floors.out` / `pass_bc_results.json`. Two results:

1. **Registry-mined height-2 skeletons exist, but only a few.** The certified pairs:
   - `d4_gen_min` (`{flip_h, transpose}`): `rot180` is the deepest D4 member (size 4) and collapses to 2 via any one of four rungs (`rot90`, `rot270`, `flip_v`, `anti_transpose`) — four *alternative* rung choices for the same ladder, itself a nice metaparameter axis.
   - `mask_basic_gen`: `+map_color` ⇒ `swap_colors` (4 → 3, routing through the rung).
   - Same D4 skeleton survives unchanged inside the composite `d4gen_mask_min` floor — first static evidence the skeleton is robust to unrelated vocabulary (the *cost* of that vocabulary is E12's ~4x lesson, a separate matter).
2. **The shipped registry is compositionally FLAT across domains.** Layout, cell, arithmetic, and atomic floors derive essentially *nothing* (layout's members are mutually independent at ≤ 5 without int sources; `cell_stateful` needs coordinate constants the no-constants scope forecloses — consistent with E2 having had to mine `coord_ints`). So **no height-3 ladder exists among shipped mono primitives**: the supply of taller ladders must come from composite targets beyond the registry — which motivates pass D.

Noise rows to ignore (sampling blind spots, both flagged inline): `abs ≡ p0` (true on ARC's non-negative ints) and `overlay ≡ base grid` (the sampled transparency color is rarely present in the base; overlay's base-transparency semantics make it the identity then).

## Pass D findings — six statically certified ladders

`artifacts/pass_d_ladders.out` / `pass_d_results.json`. Each cell = minimal derivation size of a goal over cumulative library `L_i` (floor + first `i` rungs); `>N` = censored at the enumeration bound (`T` = pool truncation).

| ladder | floor | rungs → top | jump profile (diagonal) | double-jump check |
| --- | --- | --- | --- | --- |
| `d4-tower` | `{flip_h, transpose}` | `rot90` → `rot180` | 2, 2 | rot180 raw = 4 |
| `e12-layered` | `{flip_h, flip_v, map_color}` | `rot180` → `recolor_flipped` | 2, 2 | top raw = 3 |
| `quad-tower` | `{flip_h, flip_v, concat_h, concat_v}` | `mirror_h` → `quad` → `quad2` | 2, 3, 2 | quad raw = 6; quad2 > 6 even over L1 |
| `tile-tower` | `{concat_h, concat_v}` | `row3` → `grid3x3` → `grid9x9` | 2, 3, 2 | grid3x3 raw > 6; grid9x9 > 6 over L1 |
| `perceive-tower` | `{flip_h, flip_v, map_color, most_common_color}` | `rot180`, `recolor_bg` → `recolor_bg_flipped` | 2, 2, 2 | top raw = 4 (diamond — see below) |
| `mask-crop-flip` | `{flip_h, transpose, nonbg_mask, crop_to_mask}` | `crop_to_content` → `crop_flip` | 2, 2 | top raw = 3 |

Key observations:

- **`e12-layered` reproduces E12's measured ground truth exactly** (rung jump 2, top 3 → 2) — the probe's static depths agree with the one ladder we have real LEARN data for. This is the probe's validation anchor.
- **`quad-tower` and `tile-tower` are certified height-3**: raw top depth ≥ 12 static (self-composition doubling), every jump ≤ 3, and the double-jump condition holds *with censoring to spare* (`quad2` underivable at ≤ 6 even over L1). These are the first certified ladders taller than anything measured so far, both zero-constant (immune to the `synth` census's constant-blowup cost regime).
- **The enumerator found cheaper routes than my intended templates — live skip-path detection.** Intended `quad = concat_v(mirror_h(g), flip_v(mirror_h(g)))` (size 4); true minimal is `mirror_h(concat_v(g, flip_v(g)))` (size 3 — mirror the vertical pair). Same for `grid3x3 = row3(col3(g))` (size 3) vs nested concats of `row3` (size 5). Hand-computed jump depths were simply *wrong*; the design doc's Ladder Linter should compute `d_i` this way, never trust the designer's arithmetic.
- **`perceive-tower` is a diamond, not a chain** (its two rungs are independent — `recolor_bg` stays size 2 whether or not `rot180` is present), and the probe's matrix makes that legible mechanically (a rung whose column-entry doesn't drop when an earlier rung lands). Worth keeping as the deliberate diamond-vs-chain contrast arm.
- **`mask-crop-flip`'s top commutes**: minimal witness is `crop_to_content(flip_h(g))`, not `flip_h(crop_to_content(g))` — same behavior. Route normalization is another thing task design must not assume.

## Ladder candidates extracted (what to promote to real runs)

Priority order, per the batch-design axes in the design doc §1:

1. **`quad-tower`** — the anchored height-3 ladder #1 candidate (method 2, zero constants, real-ARC-adjacent symmetry completion). Needs: a `taskgen` generator with asymmetric grids (mirror/quad/quad2 task families) + a `StudySpec`, patterned on E12's.
2. **`tile-tower`** — the second height-3, different proposer shape (repeated-argument var-sharing `concat_h(p0, concat_h(p0, p0))` vs `quad-tower`'s shared-subterm shape) — a real RQ3-relevant contrast.
3. **`d4-tower`** — calibration ladder (raw cost actually measurable; four interchangeable rungs as a free metaparameter axis).
4. **`e12-layered`** — already built and measured; becomes ladder #0 / the validation anchor.
5. **`perceive-tower`** — the constants+perceiver family member and the diamond-topology arm (E11's corpus discipline applies).
6. **`mask-crop-flip`** — the learned-intermediate-type arm (E14 territory).

Not extractable from the registry (negative findings worth keeping): no height-3 chain among shipped primitives; parameterized iteration (`tile_repeat`, `scale`, `translate`-towers) is inexpressible by fixed composition without constants or recursion — the self-composition tower idea survives only in the grid-doubling form (`quad2`, `grid9x9`), which is exactly what `quad-tower`/`tile-tower` use.

## Dead ends / battery-design notes

- First battery: aligned mask tuples were identical or nested pairs → `mask_intersect` "matched" `p0`; bool pool of 2 never produced (T,F)/(F,T) → `or` "matched" `p0`. Both were **caught by the holdout battery** (reported `!! HOLDOUT-UNVERIFIED`, no false positive escaped), then fixed at the source: masks now 3x3 pairwise set-incomparable, bool pool covers all ordered pairs.
- Second battery: all masks had full-grid bounding boxes, making `crop_to_mask` extensionally the identity on primary samples (again holdout-caught). Fixed with corner-localized masks.
- Moral for the Ladder Linter (design doc §6): *sample-battery adequacy is a first-class correctness concern* — a task-collision check needs adversarially varied instances, and a holdout battery is cheap and catches real failures.
