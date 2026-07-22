# Primitive Bundles

Reference for grouping the 71 primitives in `registry.py::BASE_PRIMITIVES` into bundles, for designing experiments and (eventually) `Library`/`Config` presets (`execution/presets.py`).

Three tiers below:

- **Sub-Bundles** — non-closed reference groupings. Useful vocabulary for talking about a family (`D4`, `CTRL`, `MASK_ALGEBRA`); not meant to be run standalone, and not every one is consumed by a Bundle below — some just make the natural families nameable.
- **Bundles** — type-closed, goal-directed, hole-fill-sufficient sets meant to actually back a `SearchEngine.run(...)` call, i.e. real `Library` candidates.
- **Gap-Exposing Bundles** — candidates that _don't_ close today. Each names the missing primitive that would close it — a byproduct of bundle design that's worth keeping, not a mistake to hide.

## Constraints at play

Hard constraints — violating these makes a bundle non-functional, not just wasteful:

- **Type-closure.** Every non-leaf type a primitive consumes (`MASK`, `GRID`, `FN`) must be producible by something else in the bundle. `INT`/`COLOR` are the exception — they can also come from the `constant_sources` leaf mechanism (`search/leaves.py`), so they're not a hard island risk the way `MASK`/`FN` are (nothing produces a `MASK` except a mask-intro primitive; there's no "mask constant source").
- **Goal-directedness**, not just internal closure. A bundle can be perfectly closed among itself and still be useless if nothing in it ever produces the type the task actually needs (`GRID`, since ARC solves `Grid→Grid`). A closed arithmetic/control/pair bundle with no `build_grid`/`read` never touches `GRID` at all — closed, useless.
- **Hole-fill sufficiency** for `FN`-typed primitives. `build_grid`/`map`/`filter`/`fold`/`sort_by` aren't just "present or absent" — they need enough body vocabulary (coordinate arithmetic, a comparison, a perceiver to compare against) or their inner body search degenerates to identity/const. Including `map` with nothing worth doing per-element is a soft island: type-reachable, practically inert.

Softer constraints — violating these wastes search cost or defeats the bundle's purpose, but doesn't break it:

- **No behavioral duplicates.** Don't include two primitives (or a primitive and a free leaf) that collapse to the same function given the rest of the bundle — pure search-cost tax, no expressivity gain (`background_color`≡`most_common_color` is the precedent in ONTOLOGY; `identity`≡`Input()`, below, is a second, verified instance).
- **Don't leak the answer.** If a bundle exists to watch something get _invented_ (a schema, a re-derivation), it must withhold the primitive that would trivialize exactly that — `swap_cells`/`move_cell` already do this by convention. A deliberate gap is a legitimate, named bundle-design mode, not an oversight — as long as it's named as such.
- **Cost/depth coherence.** Type-reachable isn't the same as reachable within a sane budget — `build_grid` re-deriving `rot90` needs real composition depth under the lambda body, not just the primitive's presence in the library.

**A verified instance of "no behavioral duplicates":** `search/leaves.py::seed_leaves` yields `Input()` unconditionally as a round-0 leaf, regardless of what's in the library. `identity` is therefore strictly dominated by the free `Input()` leaf — same behavior, never cheaper. Every `D4`-family bundle below excludes it on purpose; `registry.py`'s `D4_LIBRARY` ships it anyway, for serialization/registry-completeness reasons unrelated to search value.

---

## Sub-Bundles (non-closed reference groupings)

| Bundle Name | Count | Primitives | Signature | Description |
| --- | --- | --- | --- | --- |
| ARITHMETIC_BASIC | 3 | `add`, `sub`, `mul` | `(INT,INT)→INT` | Integer arithmetic on two ints. |
| ARITHMETIC_DIV | 2 | `floordiv`, `mod` | `(INT,INT)→INT` | Integer division & remainder (partial — zero divisor raises). |
| ARITHMETIC_FUNCTIONS | 3 | `min`, `max`, `abs` | `(INT,INT)→INT` / `INT→INT` | Elementary integer functions. |
| EQ | 1 | `eq` | `(a,a)→BOOL` | Polymorphic equality — the one comparison not restricted to `INT`. |
| ORDERING | 2 | `lt`, `gt` | `(INT,INT)→BOOL` | Integer-only ordering. |
| COMPARISON | 3 | EQ + ORDERING | mixed (see components) | All value/order comparisons together. |
| IF | 1 | `if` | `(BOOL,a,a)→a` | Conditional branching — compiles to the short-circuit `If` AST node, never actually applied as a function. |
| BOOLEAN_LOGIC | 3 | `and`, `or`, `not` | `(BOOL,BOOL)→BOOL` / `BOOL→BOOL` | Boolean connectives. |
| CTRL | 7 | IF + BOOLEAN_LOGIC + COMPARISON | mixed (see components) | Full control-flow + comparison vocabulary. |
| PAIR | 3 | `pair`, `fst`, `snd` | `(a,b)→(a,b)` / `(a,b)→a` / `(a,b)→b` | Product type intro/elim. |
| LIST | 3 | `zip`, `length`, `head` | `([a],[b])→[(a,b)]` / `[a]→INT` / `[a]→a` | First-order (hole-free) list ops — the structural companions to HIGHER_ORDER_BASIC. |
| HIGHER_ORDER_BASIC | 4 | `map`, `filter`, `fold`, `sort_by` | mixed (see components) | The `FN`-hole list ops — each pins its hole against a sibling `[a]`. |
| HIGHER_ORDER_GRID | 1 | `build_grid` | `(INT,INT,FN)→GRID` | The `FN`-hole grid render. |
| HIGHER_ORDER | 5 | HIGHER_ORDER_BASIC + HIGHER_ORDER_GRID | mixed (see components) | Every primitive that takes a function argument. |
| CELLS_IO | 2 | `cells`, `from_cells` | `GRID→[COLOR]` / `(INT,INT,[COLOR])→GRID` | The Grid↔List[Color] intro/elim pair (row-major). |
| CELL_STATEFUL | 2 | `read`, `set_cell` | `(GRID,INT,INT)→COLOR` / `(GRID,INT,INT,COLOR)→GRID` | The L1 stateful pair — matches the (unwired) `CELL_LIBRARY`. |
| CELL_TARGETS | 2 | `swap_cells`, `move_cell` | `(GRID,INT,INT,INT,INT)→GRID` | Hand-shipped re-derivation targets — withhold by convention; not starting vocabulary. |
| D4_GEN | 2 | `flip_h`, `transpose` | `GRID→GRID` | The verified-minimal D4 generating pair — composition-closure BFS confirms `{flip_h, transpose}` alone reaches all 8 D4 elements (`flip_v` is derivable at depth 2). |
| D4 | 7 | D4_GEN + `rot90`, `rot180`, `rot270`, `flip_v`, `anti_transpose` | `GRID→GRID` | The full D4 group, one application each. Deliberately excludes `identity` — see the constraints note above. |
| COLOR_OPS | 3 | `map_color`, `swap_colors`, `filter_color` | `(GRID,COLOR,COLOR)→GRID` / `(GRID,COLOR)→GRID` | Atomic color recoloring ops. |
| COMBINATORS | 2 | `overlay`, `tile` | `(COLOR,*GRID)→GRID` / `(INT,INT,*GRID)→GRID` | Variadic merge combinators — escape D4's group closure. |
| LAYOUT | 8 | `blank`, `translate`, `concat_h`, `concat_v`, `pad`, `tile_repeat`, `downsample`, `scale` | mixed (see components) | Size-changing / positional grid ops. |
| PERCEIVE | 6 | `most_common_color`, `least_common_color`, `count_color`, `num_colors`, `palette`, `shape` | mixed (see components) | Grid→scalar/summary perceivers — turn constants into derived values. |
| MASK_INTRO | 3 | `mask_by_color`, `nonbg_mask`, `bbox_mask` | `(GRID,COLOR)→MASK` / `GRID→MASK` | Mask constructors. |
| MASK_ALGEBRA | 4 | `mask_union`, `mask_intersect`, `mask_difference`, `mask_complement` | `(MASK,MASK)→MASK` / `MASK→MASK` | The Boolean lattice on `MASK`. |
| MASK_ELIM | 3 | `crop_to_mask`, `paint_through_mask`, `crop_to_content` | `(GRID,MASK)→GRID` / `(GRID,MASK,COLOR)→GRID` / `GRID→GRID` | Mask eliminators — render back to `GRID`. |
| MASK_BASIC | 10 | MASK_INTRO + MASK_ALGEBRA + MASK_ELIM | mixed (see components) | The full L3 region family. |

---

## Bundles (type-closed, goal-directed, hole-fill sufficient)

`Status` cross-references code that already exists: `= X` means a shipped `Library`/preset is identical (or differs only by the `identity` exclusion noted above); `new` means not yet built.

| Bundle Name | Count | Composition | Types | Constant Sources | Status | Description |
| --- | --- | --- | --- | --- | --- | --- |
| FLOOR | 5 | `read`, `build_grid`, `width`, `height`, `sub` | GRID, INT | none | `= BUILD_LIBRARY` (unwired to any preset) | The bare D4-rederivation clique; smallest coherent starting point (E5–E9 lineage). |
| FLOOR_AFFINE | 7 | FLOOR + `add`, `mul` | GRID, INT | none | `= BUILD_AFFINE_LIBRARY` (unwired) | Wider affine coordinate grammar over the same floor. |
| FLOOR_DIV | 9 | FLOOR_AFFINE + ARITHMETIC_DIV | GRID, INT | none | new | Adds modular coordinate arithmetic — periodic patterns (checkerboards, striping) without size-specific constants. |
| MINIMAL_COMPLETE_FLOOR | 4 | `build_grid`, `read`, `if`, `eq` | GRID, INT, BOOL | `finite-enumerate` or `harvest-from-instance`, **required** (must mine every coordinate literal used in `eq`) | new | The "zero added prior" completeness witness: `if`+`eq`+mined literals alone can express any per-cell lookup table in principle. Isolates what's needed for _completeness_ from what's added purely to shorten programs. |
| UNIVERSAL_FLOOR | 16 | FLOOR_DIV + CTRL | GRID, INT, BOOL | none | new — named in ONTOLOGY (RESEARCH-08 "zero-cheating complete floor") but not yet packaged as one `Library` | The practical complete floor; contrast against MINIMAL_COMPLETE_FLOOR to separate expressiveness from cost. |
| CELL_FLOOR | 2 | CELL_STATEFUL | GRID, INT, COLOR | none | `= CELL_LIBRARY` (unwired) | The stateful L1 pair, standalone. |
| CELL_FLOOR_WITH_TARGETS | 4 | CELL_FLOOR + CELL_TARGETS | GRID, INT, COLOR | none | new | Explicit "targets included" variant — only when _not_ running a re-derivation study (contrast with CELL_FLOOR, which withholds them by convention). |
| MASK_BASIC | 10 | MASK_BASIC (sub-bundle) | GRID, MASK, COLOR | `finite-enumerate`/`harvest-from-instance` (for `mask_by_color`/`paint_through_mask`'s COLOR args) | new | The full L3 region family in isolation. |
| MASK_PERCEIVED | 12 | MASK_BASIC + `most_common_color`, `palette` | GRID, MASK, COLOR | none | new | Removes MASK_BASIC's dependency on brute-force COLOR enumeration — color args are derived, not enumerated. |
| SYMMETRY_REPAIR | 9 | D4 + COMBINATORS | GRID, COLOR | `finite-enumerate`/`harvest-from-instance` (for `overlay`'s mask-color arg) | ≈ `SYMMETRY_LIBRARY`/`sym` preset (the shipped version has 8 D4 elements incl. `identity`; this bundle's leaner D4 correctly has 7) | Symmetry repair from group elements + merge combinators, no perception needed. |
| SYMMETRY_REPAIR_PERCEIVED | 9 | D4 + `overlay`, `least_common_color` | GRID, COLOR | none | new | Cheaper alternative to `sym` — swaps brute-force color-constant enumeration for a real perceiver. |
| ATOMIC | 9 | D4 + `map_color`, `scale` | GRID, COLOR, INT | `finite-enumerate`/`harvest-from-instance` | ≈ `ATOMIC_LIBRARY`/`synth`+`beam` presets, same `identity` note as SYMMETRY_REPAIR | Geometry + one color op + one size op, two nested applications. |
| SELECT_AND_CROP | 11 | `nonbg_mask`, `crop_to_content`, `crop_to_mask` + D4 + `map_color` | GRID, MASK, COLOR | `finite-enumerate`/`harvest-from-instance` (for `map_color`'s args) | new | Targets ONTOLOGY's `select_and_transform` (🔜 next) as an _emergent_ composition instead of a hand-coded L6 schema. |
| HOF_COLOR | 9 | `map`, `filter` + CELLS_IO + `width`, `height` + `eq` + `most_common_color`, `least_common_color` | GRID, COLOR, INT, BOOL, FN | none | new — enriches the shipped `HOF_LIBRARY` (`map`+`cells`+`from_cells`+`width`+`height` only) with a real predicate | Gives `map`/`filter`'s body search a non-degenerate predicate (compare-to-derived-color) instead of only identity/const. |
| LIST_ALGEBRA | 10 | CELLS_IO + LIST + PAIR + `fold`, `sort_by` | GRID, COLOR, INT | none | new | Isolates L0 recursion-scheme composition from all grid geometry. |
| LAYOUT_FULL | 10 | LAYOUT + `width`, `height` | GRID, INT, COLOR | none | new | Isolates size-changing composition (grow/shrink/tile/pad) from D4/color; dimension args come from `width`/`height`, not `constant_sources`. |

---

## Gap-Exposing Bundles (not closed — each names the missing piece)

| Bundle Name | Primitives | What's missing | Description |
| --- | --- | --- | --- |
| OBJECT_PRECURSOR | `palette`, `map`, `mask_by_color`, `crop_to_mask`, `sort_by`, `fold` (6) | A `MASK→INT` cardinality primitive (e.g. `mask_count`) — none of the 71 produce one; `count_color` is `(GRID,COLOR)→INT`, not `MASK→INT` | Tests whether `map(mask_by_color, palette(g))` + `sort_by`/`fold` can fake `segment_by_color`+`select_largest` (ONTOLOGY L4, unbuilt) without ever inventing an `Object`/`ObjectSet` type. Surfaces a concrete, currently-uncatalogued candidate primitive. |

---

## Coverage

All 71 `BASE_PRIMITIVES` appear in exactly one Sub-Bundle above, except `identity` — deliberately unbundled (dominated by the free `Input()` leaf; see the constraints note).
