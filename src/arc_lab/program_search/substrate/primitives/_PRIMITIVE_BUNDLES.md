# Primitive Bundles

A reference for grouping the ~71 primitives in [registry.py](registry.py)::`BASE_PRIMITIVES` into
**bundles**, for designing experiments and (eventually) `Library`/`Config` presets
([execution/presets.py](../../execution/presets.py)). A bundle is not just a set of primitives — it
is a set *plus the engine policies that make it runnable*. The tables below carry both.

**Three tiers:**

- **Fragments** — reusable reference groupings, by role (`D4`, `CTRL`, `MASK_ALGEBRA`). Not meant to
  run standalone; many are deliberately non-closed (an island, or a producer of a type nothing
  consumes). They make the natural families nameable and compose into floors.
- **Floors** — type-closed, goal-directed, hole-fill-sufficient sets meant to actually back a
  `SearchEngine.run(...)` call: real `Library` candidates. A floor is the thing you hand an
  experiment.
- **Gap-Exposing Bundles** — candidates that *don't* close today, each naming the missing primitive
  that would close it. A byproduct of bundle design worth keeping, not a mistake to hide.

Some fragments are already floors on their own (`D4` consumes Grid and produces Grid — trivially
closed and goal-directed). The Fragment/Floor line is *reusable block* vs. *experiment-ready
starting library*, not closure per se.

**Checkable counterpart.** [execution/bundle_sheet.py](../../execution/bundle_sheet.py)::`BUNDLES`
mirrors these tables as data; `uv run arc-lab check-library-coherence <NAME>` checks one and
`uv run arc-lab check-primitive-bundles` batch-checks all (see
[_PRIMITIVE_BUNDLE_COMMANDS.md](_PRIMITIVE_BUNDLE_COMMANDS.md)). Doc is the source of truth; the
sheet is updated to match, then the checker regresses it.

## How to read this

- **Grain (gen / full).** Most domains come in two grains: a **generator** variant that *withholds*
  the primitive an experiment wants to watch get invented, and a **full** variant that gifts it.
  `D4_GEN` vs `D4`, `MASK_MIN` vs `MASK_BASIC`, `RECOLOR_GEN` vs `RECOLOR`. Withholding-to-observe is
  then "pick the gen variant", not an ad-hoc per-experiment subtraction (Constraint 6).
- **Required policies.** The minimal engine config a bundle *implies* (fields on
  `BottomUpSearchEngine`); ignore them and the bundle is present-but-inert. The recurring three:
  - `function_hole_fill_mode` — any `Fn`-typed primitive (`build_grid`, `map`/`filter`/`fold`/
    `sort_by`) needs `point-free` or `lambda-synthesis`; `build_grid` specifically needs
    `lambda-synthesis` (its body is a coordinate-function search).
  - `constant_sources` — a bundle needing a `Color`/`Int` not already in the input grid needs
    `finite-enumerate`; `harvest-from-instance` suffices when every needed literal is present in the
    inputs. Shown per floor in the **Const** column.
  - `polymorphism_instantiation` / `unpinned_type_var_mode` — polymorphic ops (`eq`, `if`,
    `map`/`fold`, `zip`/`head`) need instantiation `bounded`+; `map`'s unshared codomain needs
    `unpinned_type_var_mode="eager_grounding_over_universe"`.
- **Off-ramp** — the primitive that carries the bundle's key non-leaf type *back to Grid*. A floor
  with no off-ramp is an island (Constraint 2). Stated per floor so goal-directedness is checkable.
- **Module note.** Fragment role-names are *not* module names. `add`/`sub`/`mul`/`width`/`height`/
  `build_grid` live in [build.py](build.py), not an arithmetic module; the read-side
  [capabilities.py](../../analysis/capabilities.py) categorizes a primitive by its *defining
  module*, so a partition readout buckets `add`/`sub`/`mul` under `build`, not `arithmetic`.
- **Unions.** A few fragments are convenience unions of others (`CTRL`, `HIGHER_ORDER`, `PERCEIVE`,
  `BOOL_CMP`, `MASK_BASIC`); the [Coverage](#coverage) count is over *atomic* fragments only.
- Notation: `[a]` = list, `(a,b)` = pair.

---

## Constraints at play

### Hard — violating one makes a floor non-functional, not just wasteful

1. **Type-closure.** Every non-leaf type a primitive *consumes* (`MASK`, `GRID`, `FN`) must be
   *produced* by something else in the bundle. `INT`/`COLOR` are the exception — they can also come
   from the `constant_sources` leaf mechanism ([search/leaves.py](../../search/leaves.py)), so they
   are not a hard island risk the way `MASK`/`FN` are (nothing produces a `MASK` except a mask-intro
   primitive; there is no "mask constant source").
2. **Goal-directedness**, not just internal closure. A bundle can be perfectly closed among itself
   and still be useless if nothing produces the type the task needs (`GRID`, since ARC solves
   `Grid->Grid`). A closed arithmetic/control/pair bundle with no `build_grid`/`read` never touches
   `GRID` — closed, useless. Every floor needs an on-ramp *and* an off-ramp on a typed path
   `Grid -> ... -> Grid` (the connectivity law, SEARCH-SPACE.md).
3. **Goal type is GRID.** `derive_goal_type` is unbuilt (the engine's goal type is hardwired
   `GRID`). A bundle whose natural answer is `Color`/`Int` ("what is the background color", "how many
   objects") **cannot be a top-level floor yet** — such perceivers are only usable *mid-pipeline*,
   feeding a Grid-producing consumer. Bounds runnability, not just closure.
4. **Hole-fill sufficiency** for `FN`-typed primitives. `build_grid`/`map`/`filter`/`fold`/`sort_by`
   need enough body vocabulary (coordinate arithmetic, a comparison, a perceiver to compare against)
   *and* the matching `function_hole_fill_mode`, or the inner body search degenerates to
   identity/const. `map` with nothing worth doing per-element is a soft island: type-reachable,
   practically inert.

### Softer — violating one wastes cost or defeats the purpose, but still runs

5. **No behavioral duplicates.** Two primitives that collapse to the same function *given the rest of
   the bundle* are a pure search-cost tax. `mask_difference(a,b) == mask_intersect(a,
   mask_complement(b))` (derivable — redundant inside `MASK_BASIC`). Counter-example worth knowing:
   `swap_colors` is **not** derivable from `map_color` (sequential `1->2` then `2->1` collapses), so
   it is a legitimately distinct primitive.
6. **Don't leak the answer.** A bundle that exists to watch something get invented must withhold the
   primitive that trivializes exactly that — the *gen* grain, a legitimate named design mode, not an
   oversight (`swap_cells`/`move_cell` withheld from `CELL_FLOOR` by convention).
7. **Cost/depth coherence.** Type-reachable != reachable within a sane budget — `build_grid`
   re-deriving a reflection needs real composition depth *under the lambda body* (a reflection
   coordinate is two `sub`s deep), not just the primitive's presence.
8. **Variadic x budget interaction.** `overlay`/`tile`/`build` are variadic, bounded by
   `Budget.max_arity` (a 3x3 mosaic is 9 `tile` args — the pinned `sym` tile-9 limit), and
   `finite-enumerate` on a wide grid mints many size-1 `Int` constants that can starve a narrow beam
   of `GRID` (the `beam` 0/400 finding). A variadic bundle is under-specified without its arity/beam
   note.

**Verified instance of Constraint 5 (`identity` = `Input()`).** `search/leaves.py::seed_leaves`
yields `Input()` unconditionally as a round-0 leaf, regardless of the library. `identity` is
strictly dominated by that free leaf — same behavior, never cheaper. Every `D4`-family bundle below
excludes it on purpose; `registry.py`'s `D4_LIBRARY` ships it anyway for serialization completeness,
unrelated to search value. (This is why `D4` is 7, not 8.)

---

## Fragments (reusable reference groupings)

Atomic fragments first (each primitive in exactly one), then convenience unions.

| Fragment | Count | Primitives | Signature | Module | Notes |
| --- | --- | --- | --- | --- | --- |
| ARITH_BASIC | 3 | `add`, `sub`, `mul` | `(INT,INT)->INT` | **build.py** | coordinate/affine arithmetic |
| ARITH_DIV | 2 | `floordiv`, `mod` | `(INT,INT)->INT` | arithmetic.py | partial — zero divisor raises |
| ARITH_FN | 3 | `min`, `max`, `abs` | `(INT,INT)->INT` / `(INT)->INT` | arithmetic.py | elementary integer functions |
| EQ | 1 | `eq` | `(a,a)->BOOL` | control.py | the one **polymorphic** comparison |
| ORDERING | 2 | `lt`, `gt` | `(INT,INT)->BOOL` | control.py | integer-only ordering |
| IF | 1 | `if` | `(BOOL,a,a)->a` | control.py | compiles to short-circuit `If` AST node, never applied as a function |
| BOOL_LOGIC | 3 | `and`, `or`, `not` | `(BOOL,BOOL)->BOOL` / `(BOOL)->BOOL` | control.py | Boolean connectives |
| PAIR | 3 | `pair`, `fst`, `snd` | `(a,b)->(a,b)` / `->a` / `->b` | pairs.py | product intro/elim |
| LIST_OPS | 3 | `zip`, `length`, `head` | `([a],[b])->[(a,b)]` / `[a]->INT` / `[a]->a` | lists.py | first-order (hole-free) list ops |
| HO_BASIC | 4 | `map`, `filter`, `fold`, `sort_by` | `(FN,[a])->...` | higher_order.py | inert without body vocab (Constraint 4) |
| HO_GRID | 1 | `build_grid` | `(INT,INT,FN)->GRID` | build.py | `FN` is curried `row->(col->COLOR)` |
| PERCEIVE_COLOR | 2 | `most_common_color`, `least_common_color` | `(GRID)->COLOR` | perceive.py | Grid->Color on-ramp |
| PERCEIVE_INT | 4 | `count_color`, `num_colors`, `palette`, `shape` | `(GRID[,COLOR])->INT` / `->[COLOR]` / `->(INT,INT)` | perceive.py | island without a consumer (Constraint 3) |
| CELLS_IO | 2 | `cells`, `from_cells` | `GRID->[COLOR]` / `(INT,INT,[COLOR])->GRID` | cells.py | the Grid<->List[Color] intro/elim pair |
| CELL_STATEFUL | 2 | `read`, `set_cell` | `(GRID,INT,INT)->COLOR` / `(GRID,INT,INT,COLOR)->GRID` | cells.py | the L1 stateful pair (= unwired `CELL_LIBRARY`) |
| CELL_TARGETS | 2 | `swap_cells`, `move_cell` | `(GRID,INT,INT,INT,INT)->GRID` | cells.py | hand-shipped re-derivation targets — withhold by convention |
| RECOLOR_OPS | 3 | `map_color`, `swap_colors`, `filter_color` | `(GRID,COLOR,COLOR)->GRID` / `(GRID,COLOR)->GRID` | color.py | whole-grid recolor; off-ramp to Grid |
| MASK_INTRO | 3 | `mask_by_color`, `nonbg_mask`, `bbox_mask` | `(GRID[,COLOR])->MASK` | mask.py | the only Mask sources |
| MASK_ALGEBRA | 4 | `mask_union`, `mask_intersect`, `mask_difference`, `mask_complement` | `(MASK,MASK)->MASK` / `(MASK)->MASK` | mask.py | Boolean lattice on Mask; `mask_difference` derivable (dup) |
| MASK_ELIM | 3 | `crop_to_mask`, `paint_through_mask`, `crop_to_content` | `(GRID,MASK)->GRID` / `(GRID,MASK,COLOR)->GRID` / `(GRID)->GRID` | mask.py | Mask off-ramp; `crop_to_content` = `crop_to_mask(g, nonbg_mask(g))` |
| COMBINATORS | 2 | `overlay`, `tile` | `(COLOR,*GRID)->GRID` / `(INT,INT,*GRID)->GRID` | combinators.py | **variadic** merge (Constraint 8); escape D4 group-closure |
| LAYOUT_OPS | 7 | `translate`, `concat_h`, `concat_v`, `pad`, `tile_repeat`, `downsample`, `blank` | `(GRID,...)->GRID` ; `blank:(INT,INT,COLOR)->GRID` | layout.py | size-changing/positional; `blank` is a Grid-from-Int *source* |
| SCALE | 1 | `scale` | `(GRID,INT)->GRID` | scaling.py | integer grid scaling |
| D4_GEN_MIN | 2 | `flip_h`, `transpose` | `(GRID)->GRID` | geometry.py | **verified-minimal** generating pair — BFS confirms `{flip_h, transpose}` reaches all 8 D4 elements (`flip_v` derivable at depth 2); matches the E1 study |
| D4_GEN | 3 | D4_GEN_MIN + `flip_v` | `(GRID)->GRID` | geometry.py | conventional generators (both reflections + transpose); `flip_v` gifted for convenience |
| D4 | 7 | D4_GEN + `rot90`, `rot180`, `rot270`, `anti_transpose` | `(GRID)->GRID` | geometry.py | full group, one application each; excludes `identity` (dup) |
| OBJECT_OPS &#9888; | ~5 | `segment`, `render`, `obj_color`, `obj_size`, `obj_bbox` | `(GRID)->[Object]` / `([Object])->GRID` / ... | **unbuilt** | needs the Object pathway |

**Unions (convenience names, not counted in coverage):** `BOOL_CMP` = EQ + ORDERING (3) · `CTRL` =
IF + BOOL_LOGIC + BOOL_CMP (7) · `HIGHER_ORDER` = HO_BASIC + HO_GRID (5) · `PERCEIVE` =
PERCEIVE_COLOR + PERCEIVE_INT (6) · `CELL_IO` = CELLS_IO + CELL_STATEFUL (4) · `MASK_BASIC` =
MASK_INTRO + MASK_ALGEBRA + MASK_ELIM (10).

---

## Floors (runnable starting libraries)

Organized **domain x grain**. `Status`: `= X` a shipped `Library`/preset is identical (modulo the
`identity` note); `new` not yet built. All satisfy the four hard constraints. Fill/poly policy is
`fill=none` unless the Notes say otherwise.

### Coordinate / pixel domain (one grain lattice, low -> complete)

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `FLOOR` | `read`, `build_grid`, `width`, `height`, `sub` | GRID, INT | `build_grid` | none | = `build` (unwired) | smallest coherent floor; the D4-rederivation clique (E5–E9). `fill=lambda-synthesis`, min body depth ~2 |
| `FLOOR_AFFINE` | FLOOR + `add`, `mul` | GRID, INT | `build_grid` | none | = `build-affine` (unwired) | wider affine coordinate grammar |
| `FLOOR_DIV` | FLOOR_AFFINE + ARITH_DIV | GRID, INT | `build_grid` | none | new | modular coordinates — periodic patterns (checkerboards, stripes) without size-specific constants |
| `MINIMAL_COMPLETE_FLOOR` | `build_grid`, `read`, `if`, `eq` | GRID, INT, BOOL | `build_grid` | `finite-enumerate` **required** (must mine every coordinate literal `eq` compares) | new | the "zero added prior" completeness witness: `if`+`eq`+mined literals express any per-cell lookup table. Isolates *completeness* from what's added purely to *shorten* programs |
| `UNIVERSAL_FLOOR` | FLOOR_DIV + CTRL (16) | GRID, INT, BOOL, COLOR | `build_grid` | `finite-enumerate` | new (ONTOLOGY's "zero-cheating complete floor") | **globally complete**; per-cell decision tree over reads. Contrast vs `MINIMAL_COMPLETE_FLOOR` to separate expressiveness from cost. `fill=lambda-synthesis`, poly `bounded` |

### Geometry domain

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `GEOM` (gen `D4_GEN` / full `D4`) | see D4 | GRID | any member | none | full = `d4` preset | the transformational control for D4-rederivation studies |
| `ATOMIC` | `D4` + `map_color` + `scale` | GRID, COLOR, INT | any | `finite`/`harvest` | ≈ `synth`/`beam` presets | geometry + one color op + one size op, two nested applications |
| `SYMMETRY` | `D4` + COMBINATORS (+ `scale`) | GRID, COLOR, INT | `overlay`/`tile` | `harvest` | ≈ `sym` preset (ships 8 D4 incl. `identity`; this has 7) | symmetry-repair / mosaic. **Variadic** — mind `max_arity` (tile-9) + beam starvation (Constraint 8) |
| `SYMMETRY_PERCEIVED` | `D4` + `overlay` + `least_common_color` | GRID, COLOR | `overlay` | none | new | cheaper than `sym`: swaps color-constant enumeration for a real perceiver |

### Color / perception domain

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `RECOLOR` (gen `map_color` / full RECOLOR_OPS) | see RECOLOR_OPS | GRID, COLOR | `map_color` | `finite-enumerate` | new | whole-grid color rewrite. `swap_colors` is *not* a `map_color` dup (Constraint 5) |
| `PERCEIVE_TRANSFORM` | RECOLOR + PERCEIVE_COLOR | GRID, COLOR | `map_color` | `finite-enumerate` | new (the E11 floor) | perceiver-conditioned recolor. PERCEIVE_COLOR alone is an island — this is its closed form; PERCEIVE_INT stays an island here without CTRL |

### Cell domain

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `CELL_FLOOR` | CELL_STATEFUL (`read`, `set_cell`) | GRID, INT, COLOR | `set_cell` | `finite-enumerate` | = `cells` (unwired) | the stateful L1 pair. Needs a constant source for Int **coordinates** (no `width`/`height` here) — the coherence check flags `const=()` as INCOHERENT; E2 likewise mined `coord_ints` |
| `CELL_FLOOR_WITH_TARGETS` | CELL_FLOOR + CELL_TARGETS | GRID, INT, COLOR | `set_cell` | `finite-enumerate` | new | "targets included" — only when *not* running a re-derivation study (contrast `CELL_FLOOR`, which withholds them) |

### Region / mask domain

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `MASK_MIN` (gen) | `nonbg_mask`, `crop_to_mask` | GRID, MASK | `crop_to_mask` | none | new | the withheld floor for the `crop_to_content` gap-climb |
| `MASK_BASIC` (full) | MASK_INTRO + MASK_ALGEBRA + MASK_ELIM | GRID, MASK, COLOR | `crop_to_mask`/`paint_through_mask` | `finite`/`harvest` | = `mask` | full region logic. `mask_difference` derivable (dup); `crop_to_content` gifted here |
| `MASK_PERCEIVED` | MASK_BASIC + `most_common_color`, `palette` | GRID, MASK, COLOR | `crop_to_mask` | none | new | removes the brute-force COLOR-enumeration dependency — color args derived, not enumerated |
| `SELECT_AND_CROP` | `nonbg_mask`, `crop_to_content`, `crop_to_mask` + `D4` + `map_color` | GRID, MASK, COLOR | `crop_to_mask`/`map_color` | `finite`/`harvest` | new | targets ONTOLOGY's `select_and_transform` (🔜) as an *emergent* composition, not a hand-coded schema |

### Spatial / layout domain

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `LAYOUT` (gen `LAYOUT_GEN` withholds `tile_repeat` / full `LAYOUT_FULL` + `width`, `height`) | LAYOUT_OPS (+ `scale`) | GRID, INT, COLOR | any member | `finite`/`harvest` | new | structural assembly: translate / concat / pad / mosaic / downsample. `blank` builds a grid from ints; `tile_repeat` ~ nested `concat` (a clean gen/full invention target) |

### Higher-order & list domain

| Floor | Composition | Types | Off-ramp | Const | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `HO_RECOLOR` | HO_BASIC + CELLS_IO + `width`, `height` + CTRL + PERCEIVE_COLOR | GRID, [COLOR], COLOR, BOOL, INT, FN | `from_cells` | `finite-enumerate` | new (enriches `hof`) | the *usable* higher-order floor — `map` over cells with a real per-element body. `map` alone is inert. `fill=lambda-synthesis`, poly `bounded`, `unpinned=eager_grounding`; expect the eager-grounding cost (EXPERIMENTS 2026-07-11) |
| `HOF_COLOR` | `map`, `filter` + CELLS_IO + `width`, `height` + `eq` + PERCEIVE_COLOR | GRID, COLOR, INT, BOOL, FN | `from_cells` | none | new | leaner `HO_RECOLOR`. **Coherence warning:** only `eq` is reachable *inside* the per-element hole (perceivers need a Grid, out of element scope) — body is thin (Constraint 4). Add a Color source in-scope to enrich it |
| `LIST_ALGEBRA` | CELLS_IO + LIST_OPS + PAIR + `fold`, `sort_by` | GRID, [COLOR], INT | `from_cells` | none | new | isolates L0 recursion-scheme composition from all grid geometry. **Coherence warning:** `fold`/`sort_by` bodies see only `pair` — thin (Constraint 4); add a comparison/arithmetic for a non-trivial key |

---

## Gap-Exposing Bundles (not closed — each names the missing piece)

| Bundle | Primitives | What's missing | Description |
| --- | --- | --- | --- |
| `OBJECT` &#9888; | OBJECT_OPS + PERCEIVE_COLOR | the whole **Object pathway** — an `Object` type + `segment`/`render` + accessors (SEARCH-SPACE.md Table A) | the largest ARC slice not yet reachable; unbuilt |
| `OBJECT_PRECURSOR` | `palette`, `map`, `mask_by_color`, `crop_to_mask`, `sort_by`, `fold` (6) | a `MASK->INT` cardinality primitive (e.g. `mask_count`) — none of the ~71 produce one; `count_color` is `(GRID,COLOR)->INT`, not `MASK->INT` | tests whether `map(mask_by_color, palette(g))` + `sort_by`/`fold` can fake `segment_by_color`+`select_largest` *without* an `Object` type. Surfaces a concrete uncatalogued candidate primitive |

---

## Coverage

Every primitive in `BASE_PRIMITIVES` appears in exactly one *atomic* fragment above, except
`identity` — deliberately unbundled (dominated by the free `Input()` leaf; see the Constraint 5
note). The unions re-group atomics and are not counted.

## Composite floors (for axis-2 experiments)

- `UNIVERSAL_FLOOR + MASK_BASIC` — global completeness **plus** cheap region logic; the natural floor
  for mask/object experiments that still want a completeness fallback.
- `UNIVERSAL_FLOOR + D4` / `+ LAYOUT` — completeness plus gifted mid-level geometry/spatial grain, for
  measuring how a gifted derived primitive *shortcuts* the search-cost graph (axis 2) against the
  complete-but-deep baseline.