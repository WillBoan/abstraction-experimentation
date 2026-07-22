# Primitive Bundles

A reference for grouping primitives into **bundles** for experiment design. A bundle is not just a set of primitives — it is a set _plus the engine policies that make it runnable_. The tables below carry both.

Two kinds of grouping:

- **Fragments** — reusable building blocks, grouped by role. Not necessarily runnable alone (a fragment may be an island, or produce a type nothing consumes). Compose them into floors.
- **Floors** — a fragment (or union of fragments) that is **runnable as a starting library**: it satisfies all four hard constraints below. A floor is the thing you actually hand an experiment.

Some fragments are already floors on their own (`D4` consumes Grid and produces Grid — trivially closed and goal-directed). The `Fragment`/`Floor` line is about _reusable block_ vs. _experiment-ready starting library_, not about closure per se.

## How to read this

- **Grain (gen / full).** Most domains come in two grains: a **generator** variant that withholds the primitive an experiment wants to _watch get invented_, and a **full** variant that gifts it. `D4_GEN` (3 generators) vs `D4` (all 7) is the pattern; `MASK_MIN` vs `MASK_BASIC` follows it. Withholding-to-observe is then "pick the gen variant", not an ad-hoc per-experiment subtraction.
- **Required policies.** The minimal engine config a bundle _implies_ (fields on `BottomUpSearchEngine`). Ignore these and the bundle is present-but-inert. The recurring three:
  - `function_hole_fill_mode` — any `Fn`-typed primitive (`build_grid`, `map`/`filter`/`fold`/ `sort_by`) needs `point-free` or `lambda-synthesis`; `build_grid` specifically needs `lambda-synthesis` (its body is a coordinate function search).
  - `constant_sources` — any bundle needing a `Color`/`Int` not already in the input grid (`map_color` to a _new_ color, `blank`/`pad`'s color, `tile`'s dims) needs `finite-enumerate`; `harvest-from-instance` suffices when every needed literal is present in the inputs.
  - `polymorphism_instantiation` / `unpinned_type_var_mode` — polymorphic ops (`eq`/`lt`/`gt`, `if`, `map`/`fold`, `zip`/`head`) need instantiation `bounded`+; `map`'s unshared codomain needs `unpinned_type_var_mode="eager_grounding_over_universe"`.
- **Off-ramp.** The primitive that carries the bundle's key non-leaf type _back to Grid_. A bundle with no off-ramp is an island (Constraint 2). Stated per floor so goal-directedness is checkable.
- **Module note.** Fragment role-names are _not_ module names. `add`/`sub`/`mul`/`width`/`height`/ `build_grid` live in [build.py](build.py), not an arithmetic module; the read-side [capabilities.py](../../analysis/capabilities.py) categorizes a primitive by its _defining module_, so a partition readout will bucket `add`/`sub`/`mul` under `build`, not `arithmetic`.

---

## Constraints at play

### Hard (a floor that violates one is broken)

1. **Type-closure.** Every non-leaf type a primitive _consumes_ must be _produced_ by something else in the bundle. `Mask` and `Fn` are the real island risks — nothing produces a `Mask` except a mask-intro primitive, and there is no "mask constant source". `Int`/`Color` are special: they can also be supplied by `constant_sources`, so they are not a hard island risk.
2. **Goal-directedness.** Internal closure is not enough — something must produce **Grid**, because ARC is Grid->Grid. A pile of `add`/`sub`/`eq`/`if`/`pair` is perfectly closed on Int/BOOL/Pair and reaches Grid _never_. Every floor needs an on-ramp _and_ an off-ramp on a typed path Grid -> ... -> Grid. (This is the connectivity law from SEARCH-SPACE.md.)
3. **Goal type is GRID.** `derive_goal_type` is unbuilt (the engine's goal type is hardwired `GRID`). So a bundle whose natural answer is `Color`/`Int` ("what is the background color", "how many objects") **cannot be a top-level floor yet** — such perceivers are only usable _mid-pipeline_, feeding a Grid-producing consumer. This bounds runnability, not just closure.
4. **Hole-fill sufficiency.** An `Fn`-typed primitive needs enough body vocabulary (coordinate arithmetic, comparisons, a perceiver to compare against) _and_ the matching `function_hole_fill_mode` (above), or its inner body search degenerates to identity/const. `map` with nothing to do per-element is a soft island: type-reachable, practically inert.

### Softer (a floor that violates one still runs, but pays or misleads)

5. **No behavioral duplicates.** Two primitives that collapse to the same function _given the rest of the bundle_ are a pure search-cost tax. Examples: `mask_difference(a,b) == mask_intersect(a, mask_complement(b))` (derivable — redundant inside `MASK_BASIC`); `identity` is a duplicate of the bare input (why `D4` is 7, not 8). Counter-example worth knowing: `swap_colors` is **not** derivable from `map_color` (sequential `1->2` then `2->1` collapses), so it is a legitimately distinct primitive, not a duplicate.
6. **Don't leak the answer.** A bundle that exists to watch something get invented must withhold the primitive that trivializes exactly that — this is the _gen_ grain, a legitimate design mode, not an oversight, as long as it is named.
7. **Cost/depth coherence.** Type-reachable != reachable within a sane budget. `build_grid` re-deriving a reflection needs real depth _under the lambda body_ (a reflection coordinate is two `sub`s deep), not just the primitive's presence. Note a floor's min viable depth.
8. **Variadic x budget interaction.** `overlay`/`tile`/`build` are variadic, bounded by `Budget.max_arity` (a 3x3 mosaic is 9 `tile` args — the pinned `sym` tile-9 limit), and `finite-enumerate` on a wide grid mints many size-1 `Int` constants that can starve a narrow beam of the `GRID` type (the `beam` 0/400 finding). A variadic bundle is under-specified without its arity/beam note.

---

## Fragments (reusable building blocks)

Grouped by role. `Module` flags where role-name and file diverge. `[a]` = list, `(a,b)` = pair.

| Fragment | Count | Primitives | Signature | Module | Notes |
| --- | --- | --- | --- | --- | --- |
| ARITH_BASIC | 3 | `add`, `sub`, `mul` | `(Int,Int)->Int` | **build.py** | coordinate/affine arithmetic |
| ARITH_DIV | 2 | `floordiv`, `mod` | `(Int,Int)->Int` | arithmetic.py | periodic/tiling coordinate math |
| ARITH_FN | 3 | `min`, `max`, `abs` | `(Int,Int)->Int` / `(Int)->Int` | arithmetic.py | elementary int functions |
| IF | 1 | `if` | `(BOOL,a,a)->a` | control.py | branching; polymorphic |
| BOOL_LOGIC | 3 | `and`, `or`, `not` | `(BOOL,BOOL)->BOOL` / `(BOOL)->BOOL` | control.py |  |
| BOOL_CMP | 3 | `eq`, `lt`, `gt` | `(a,a)->BOOL` | control.py | polymorphic; O(pool^2) source |
| CTRL | 7 | IF + BOOL_LOGIC + BOOL_CMP | — | control.py | the L0 control block |
| PAIR | 3 | `pair`, `fst`, `snd` | `(a,b)->(a,b)` / `(a,b)->a` / `(a,b)->b` | pairs.py |  |
| LIST_OPS | 3 | `zip`, `length`, `head` | `([a],[b])->[(a,b)]` / `[a]->Int` / `[a]->a` | lists.py | island without a list on/off-ramp |
| HO_BASIC | 4 | `map`, `filter`, `fold`, `sort_by` | `(Fn,[a])->...` | higher_order.py | inert without body vocab (Constraint 4) |
| HO_GRID | 1 | `build_grid` | `(Int,Int,Fn)->Grid` | build.py | Fn is curried `row->(col->Color)` |
| PERCEIVE_COLOR | 2 | `most_common_color`, `least_common_color` | `(Grid)->Color` | perceive.py | Grid->Color on-ramp |
| PERCEIVE_INT | 4 | `count_color`, `num_colors`, `palette`, `shape` | `(Grid[,Color])->Int` / `->[Color]` / `->(Int,Int)` | perceive.py | island unless CTRL/Int consumer present (Constraint 3) |
| CELL_IO | 4 | `read`, `set_cell`, `cells`, `from_cells` | `(Grid,Int,Int)->Color` / `(Grid,Int,Int,Color)->Grid` / `(Grid)->[Color]` / `(Int,Int,[Color])->Grid` | cells.py | the per-cell list pathway |
| RECOLOR_OPS | 3 | `map_color`, `swap_colors`, `filter_color` | `(Grid,Color,Color)->Grid` / `(Grid,Color)->Grid` | color.py | whole-grid color rewrite; off-ramp to Grid |
| MASK_INTRO | 3 | `mask_by_color`, `nonbg_mask`, `bbox_mask` | `(Grid[,Color])->Mask` | mask.py | the only Mask sources |
| MASK_ALGEBRA | 4 | `mask_union`, `mask_intersect`, `mask_difference`, `mask_complement` | `(Mask,Mask)->Mask` / `(Mask)->Mask` | mask.py | `mask_difference` derivable (dup) |
| MASK_ELIM | 3 | `crop_to_mask`, `paint_through_mask`, `crop_to_content` | `(Grid,Mask)->Grid` / `(Grid,Mask,Color)->Grid` / `(Grid)->Grid` | mask.py | Mask off-ramp; `crop_to_content` = `crop_to_mask(g,nonbg_mask(g))` |
| COMBINATORS | 2 | `overlay`, `tile` | `(Color,*Grid)->Grid` / `(Int,Int,*Grid)->Grid` | combinators.py | **variadic** (Constraint 8) |
| LAYOUT_OPS | 7 | `translate`, `concat_h`, `concat_v`, `pad`, `tile_repeat`, `downsample`, `blank` | `(Grid,...)->Grid` ; `blank:(Int,Int,Color)->Grid` | layout.py | `blank` is a Grid-from-Int _source_ |
| SCALE | 1 | `scale` | `(Grid,Int)->Grid` | scaling.py | integer grid scaling |
| D4_GEN | 3 | `flip_h`, `flip_v`, `transpose` | `(Grid)->Grid` | geometry.py | D4 generators only |
| D4 | 7 | D4_GEN + `rot90`, `rot180`, `rot270`, `anti_transpose` | `(Grid)->Grid` | geometry.py | full group (excl. `identity`, a dup) |
| OBJECT_OPS &#9888; | ~5 | `segment`, `render`, `obj_color`, `obj_size`, `obj_bbox` | `(Grid)->[Object]` / `([Object])->Grid` / ... | **unbuilt** | needs the Object pathway |

---

## Floors (runnable starting libraries)

Organized **domain x grain**. `Off-ramp` names the Grid producer; `Const` = `constant_sources` needed; `Fill/poly` = the other required policies; `Complete?` flags the one globally-complete floor (the zero-cheating control). All satisfy the four hard constraints.

### Coordinate / pixel domain (one grain lattice, low -> complete)

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Complete? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `FLOOR` | gen | `read`, `build_grid`, `width`, `height`, `sub` | Grid, Int | `build_grid` | none | `fill=lambda-synthesis` | no | smallest coherent floor; the D4-rederivation clique. Min depth ~2 under the body |
| `FLOOR_AFFINE` | + | FLOOR + ARITH_BASIC (`add`,`mul`) | Grid, Int | `build_grid` | none | `fill=lambda-synthesis` | no | wider affine coordinate grammar |
| `FLOOR_DIV` | + | FLOOR_AFFINE + ARITH_DIV | Grid, Int | `build_grid` | none | `fill=lambda-synthesis` | no | periodic/tiling coordinate math (`mod`) |
| `UNIVERSAL_FLOOR` | full | FLOOR_DIV + CTRL | Grid, Int, BOOL, Color | `build_grid` | `finite-enumerate` | `fill=lambda-synthesis`, poly `bounded` | **yes** | ONTOLOGY's zero-cheating complete floor: per-cell decision tree over reads. Summons branching (Table A) |

### Geometry domain

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GEOM` | gen/full | `D4_GEN` / `D4` | Grid | any member | none | `fill=none` | the simplest transformational floor; the control for D4-rederivation studies |
| `SYMMETRY` | full | `D4` + COMBINATORS (+ `SCALE`) | Grid, Color, Int | `overlay`/`tile` | `harvest` | `fill=none` | symmetry-repair / mosaic (the `sym` family). **Variadic** — mind `max_arity` (tile-9) and beam starvation (Constraint 8) |

### Color / perception domain

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RECOLOR` | gen/full | `{map_color}` / RECOLOR_OPS | Grid, Color | `map_color` | `finite-enumerate` | `fill=none` | whole-grid color rewrite. `swap_colors` is _not_ a `map_color` duplicate (Constraint 5) |
| `PERCEIVE_TRANSFORM` | full | RECOLOR + PERCEIVE_COLOR | Grid, Color | `map_color` | `finite-enumerate` | `fill=none` | perceiver-conditioned recolor (the E11 floor). PERCEIVE_COLOR alone is an island — this is its closed form. **PERCEIVE_INT stays an island here** without CTRL (Constraint 3) |

### Spatial / layout domain

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `LAYOUT` | gen/full | LAYOUT_OPS (gen withholds `tile_repeat`) | Grid, Int, Color | any member | `finite-enumerate`/`harvest` | `fill=none` | structural assembly: translate / concat / pad / mosaic / downsample. `blank` builds a grid from ints. `tile_repeat` ~ nested `concat` -> a clean gen/full invention target |

### Region / mask domain

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MASK_MIN` | gen | `nonbg_mask`, `crop_to_mask` | Grid, Mask | `crop_to_mask` | none | `fill=none` | the withheld floor for the `crop_to_content` gap-climb |
| `MASK_BASIC` | full | MASK_INTRO + MASK_ALGEBRA + MASK_ELIM | Grid, Mask, Color, Int | `crop_to_mask`/`paint_through_mask` | `finite-enumerate`/`harvest` | `fill=none` | full region logic. `mask_difference` is a derivable dup (Constraint 5); `crop_to_content` gifted here |

### Higher-order domain

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `HO_RECOLOR` | full | HO_BASIC + `cells` + `from_cells` + `width` + `height` + CTRL + PERCEIVE_COLOR | Grid, [Color], Color, BOOL, Int | `from_cells` | `finite-enumerate` | `fill=lambda-synthesis`, poly `bounded`, `unpinned=eager_grounding_over_universe` | the _usable_ higher-order floor — `map` over cells with a real per-element body. `map` alone is inert (Constraint 4). Expect the `eager_grounding` cost (EXPERIMENTS 2026-07-11) |

### Object domain &#9888; (unbuilt)

| Floor | Grain | Primitives | Non-leaf types | Off-ramp | Const | Fill/poly | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OBJECT` &#9888; | full | OBJECT_OPS + PERCEIVE_COLOR | Grid, [Object], Color, Int | `render` | `harvest` | `fill=none`, beam | the largest ARC slice not yet reachable. **Blocked on the Object pathway** (`Object` type + `segment`/`render` + accessors) — SEARCH-SPACE.md Table A |

### Composite notes

- `UNIVERSAL_FLOOR + MASK_BASIC` = global completeness **plus** cheap region logic — the natural floor for mask/object experiments that still want a completeness fallback.
- `UNIVERSAL_FLOOR + D4` / `+ LAYOUT` = completeness plus gifted mid-level geometry/spatial grain, for measuring how a gifted derived primitive shortcuts the search-cost graph (axis 2) against the complete-but-deep baseline.
