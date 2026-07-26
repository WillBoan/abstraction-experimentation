# v5 floor-lowering: how far can we lower a ladder's floor before search goes intractable?

Investigation, 2026-07-25. Curated abstract: the `## 2026-07-25` entry in [EXPERIMENTS.md](../../EXPERIMENTS.md). Anchor commit: `c6b19bb` (all work on the same uncommitted branch; the lint-severity change below is part of it).

## The question

cfb2ce5a v1 has a floor of **6 bespoke high-level primitives**. The AL program wants to _lower_ that floor — replace each with a composition over smaller, reusable primitives — so a taller v5 ladder climbs from a lower floor, and the v5-vs-v1 gap prices what the perception primitives were worth. The open question: **how much can we lower before the search becomes intractable, and what actually controls that?**

The 6 v1 primitives and their attempted decompositions:

| # | v1 primitive | decomposition | new floor prims |
| --- | --- | --- | --- |
| 1 | `largest_filled_square(g)` | `crop_rect(g, head(filled_squares(g,0)))` | filled_squares, head, crop_rect |
| 2 | `relative_tile(g,d,r)` | (attempt A) coordinate arithmetic | offset, coord, rect, offset_scale, coord_add, … |
| 3 | `nth_seed_source_color(pat,s,i)` | `read_color_at_coord(pat, nth(content_coords(s,0), i))` | content_coords, nth, read_color_at_coord (+ length, lt, if for the guard) |
| 4 | `nth_nonzero_color(s,i)` | `nth_or_default(content_colors(s,0), i, 0)` | content_colors, nth_or_default |
| 5 | `retain_colors(g,c1,c2)` | `paint_through_mask(g, mask_complement(mask_union(mask_by_color(g,c1), mask_by_color(g,c2))), 0)` | mask_by_color, mask_union, mask_complement, paint_through_mask |
| 6 | `write_relative_tile(b,a,t,d,r)` | (not decomposed) | — |

## What ran (three ladder iterations + a controlled pruning sweep)

Each iteration authored a `.ladder`, drove the **real engine per rung** with `probe-ladder`, and read the verdict profile. All under `finite-enumerate-scalars` constants, StitchProposer where fragments are used.

### Iteration 1 — decompose `relative_tile` fully into coordinate arithmetic ("the lattice")

- Rungs: `source_rect` (d2) → `tile_size` (d3) → `tile_origin` (d4) → `relative_tile` (d4).
- **Result: censored** at `tile_origin`/`relative_tile`. The pool filled with search-constructed coordinates — `offset(3213)`, `coord(3240)` — from the `offset`/`coord`/`rect` **constructors** applied to the enumerated int battery. Depth was affordable; breadth killed it.
- ⇒ **Do not decompose `relative_tile` into coordinates.** Keep it a built-in.

### Iteration 2 — partial lowering (lower 4 of the 6; keep `relative_tile` + `write_relative_tile` built-in)

- 18-rung ladder, seed-recolor rungs reused across the 3 tile directions. Lints 0 errors.
- **Result: 0/18 clean.** `rot180`/`right_pattern` as-intended; `source_tile` **collapsed** (`relative_tile(input,0,0)` solves it at d1 — the atomic `relative_tile` subsumes `largest_filled_square`); `below/diagonal_pattern` **collision** (symmetric demo grids); the seed-recolor + placement rungs **censored**, pool dominated by `write_relative_tile: grid(7999)³` — a 3-grid-arg primitive cubing the grid pool that lowering had inflated.
- ⇒ Drop `source_tile` (use `relative_tile(g,0,0)`); asymmetric grids; the placement primitive is a breadth bomb.

### Iteration 3 — the core (source tile = `relative_tile(g,0,0)`; fragment-demo the Color/Mask rungs + StitchProposer; asymmetric grids; **no** `write_relative_tile`; placement-free top; dL 5)

- 12 rungs. Fragment demonstrations for the non-Grid rungs load correctly (`fragment_varying`), and Stitch **recovered** the pattern abstractions — so the fragment + Stitch mechanism _works_ (task-less rungs were unnecessary).
- **Result: still 0/12 clean.** Shallow rungs solve; seed-recolor rungs **censored**, now dominated by `map_color: grid × color²` — the color pool inflated to ~2,200 because the seed-read abstractions produce a color from every (pattern, seeds) pair.
- ⇒ Same wall, third different dominant primitive. Motivated the pruning experiment.

### The pruning sweep (the payoff) — `prune_test.py`, `prune_const_test.py`

For each censored rung, re-ran its **exact wake search** over controlled libraries:

- **primitive pruning**: library filtered to only the primitives the rung's unfolded program references (~20 → 4–7).
- **constant pruning**: `policy_constants` monkeypatched to mint only the constant _values_ the rung uses (e.g. ints `{0,1}`, colors `{0}` — 21 → 3 constants).
- run at the rung's **matched target depth** (removing depth as a confound).

**Result matrix (all-lowered core, matched depth; `ok:considered` / `CENS:50000`):**

| rung                    | depth | none | prim | const | both          |
| ----------------------- | ----- | ---- | ---- | ----- | ------------- |
| first_target_color      | 4     | CENS | CENS | CENS  | **ok 4,720**  |
| second_target_color     | 4     | CENS | CENS | CENS  | **ok 4,720**  |
| seeded_source_mask      | 4     | CENS | CENS | CENS  | **ok 8,387**  |
| instantiate_first       | 3     | CENS | CENS | CENS  | **ok 13,675** |
| instantiate_seeded_tile | 3     | CENS | CENS | CENS  | **ok 26,051** |
| first_source_color      | 5     | CENS | CENS | CENS  | CENS          |
| second_source_color     | 5     | CENS | CENS | CENS  | CENS          |
| source_mask             | 5     | CENS | CENS | CENS  | CENS          |

Depth sweep on `first_target_color` (target depth 4): dL3 unsolved (unreachable), **dL4 solved 4,720**, dL5 censored — proving depth, not library/constants, was the dominant factor at dL5.

## The finding

**Search cost ≈ (primitives × constants)^depth.** The three "different breadth drivers" across the iterations (coord constructors → `write_relative_tile` grid³ → `map_color` color²) were all the same thing: the **base** of that exponent, with a different primitive dominating each time.

Two consequences, both non-obvious and both measured:

1. **You must cut BOTH the library and the constants — neither alone helps.** The base is a _product_ of primitive-slots × constants-that-fill-them; cutting one factor leaves the other multiplying to explosion. (Primitive-pruning to 4 primitives: still censored. Constant-pruning to 3 values: still censored. Both: solves.)
2. **Depth is the exponent; pruning cannot beat it.** Even both-pruned, depth-5 rungs censor while depth-3/4 rungs solve. Lowering a primitive replaces a built-in with a depth-_d_ composition — it **raises the exponent**. That is the irreducible cost of lowering.

**Actionable rule:** a lowering is tractable iff its rungs stay **shallow** (≲4 with full pruning, ~2–3 without); **no pruning rescues a deep (≥5) decomposition.** This corrects the earlier hypothesis that raw primitive _count_ was the dominant factor — it is one factor of the base, not the exponent, and not sufficient on its own.

Relation to prior work: this is the [breadth axis](../../docs/abstraction_ladders/BREADTH-AXIS-2026-07-24.md) made quantitative — depth vs breadth, with the pruning knobs mapped to the "removal" cashing approach that doc named. It also confirms constants live on the breadth axis (config, not library) and that `finite-enumerate-scalars` alone is not enough at depth ≥5.

## Side-findings (kept for the record)

- **`largest_filled_square` needs no decomposition** — it is `relative_tile(g,0,0)`. Delete it from the floor; no filled_squares/head/crop_rect required.
- **Fragment demonstrations + StitchProposer are the right way to lower non-Grid (Color/Mask) rungs** — they load as `fragment_varying` and Stitch learns them; the earlier "task-less/gifted" choice was unnecessary (and untested learning). Wake breadth still gates them, but the mechanism is correct.
- **Demo-grid discipline:** symmetric source squares make `flip_h/flip_v/rot180` coincide (a false collision); use asymmetric (distinct-valued) squares.
- **Tooling:** the double-jump skip-freeness checks were relaxed error→**warn** this session (certificate-profile reframe), so mixed-depth ladders lint-clean; al10 control preserved (`raw-intractable` + `rewrite-shallow` still error, certificate still rejects). `make check` green.

## Artifacts

- `artifacts/gen_v5_core2.py` — iteration-3 core generator (partial lowering, fragment demos).
- `artifacts/prune_test.py` + `prune_primitive.out` — primitive-pruning alone (still censors).
- `artifacts/prune_const_test.py` + `prune_const_matrix.out` — the 4-mode matrix at matched depth (the payoff).
- `artifacts/probe_core2.out` — iteration-3 full probe verdict profile.

## Open / next

- Deep (≥5) decompositions need breadth machinery beyond removal — weighting or normal-form pruning (BREADTH-AXIS approaches 2–3), or cost-ordered/guided search that beats the depth exponent. Phase 2+.
- The un-pruned vs pruned gap is a _direct measure of the breadth tax of a growing library_ — worth formalizing if the pruned climb is adopted as a control.
