# ONTOLOGY.md

A living catalog of the **primitives / abstractions** that are — or might be — at play in this system and the ARC task space. Sibling to [EXPERIMENTS.md](EXPERIMENTS.md): that file logs _what we tried_; this file maps _the space of things there are to try_. This maps lever 1 (the primitive vocabulary / Floor); its sibling [MACHINERY.md](MACHINERY.md) maps lever 3 (the search / scoring / learning Machinery); [RESEARCH-2026-07-07.md](RESEARCH-2026-07-07.md) is the frame both are read against.

It exists because the substrate today is a tiny, coarse slice of that space (almost everything shipped is a whole-grid transform), and the research direction is to descend to **more fundamental primitives** and study how the machinery composes them into higher abstractions. You can't chart that climb without a map of the terrain. This is the map.

## How to read / maintain this

- **One row = one primitive / abstraction.** Grouped into sub-tables by _level_ only for readability; treat it as a single logical table.
- The **Description** is a one-line gloss of what it is / how it'd be used — kept terse on purpose.
- Add rows as we imagine them and flip **Status** as they ship. Negative findings ("tried, not worth it") get a note here _and_ an entry in `EXPERIMENTS.md`.
- Keep signatures honest — the **Signature** column is how `search` would type the primitive, and it's the most load-bearing attribute (see `substrate/library.py`).
- This is a catalog of _possibilities_, deliberately over-complete. Most rows are `cand` and may never be built. That's the point: the gaps and the shape matter more than any single row.

## Terminology (the words we're using)

- **Primitive** — a thing's _role in search_: **atomic**, search doesn't look inside it. Relative to a library, not intrinsic (`rot90` is primitive here, composite in a cell-level library).
- **Abstraction** — a thing's _provenance_: a **named factoring of a recurring pattern**, with an internal definition, usually _invented_ by compressing repetition.
- These are **orthogonal, not opposites.** A learned library entry is _both_. The loop is the conversion: `pattern → (governance names it) → abstraction → (folded in) → primitive → reused …`
- **Prior** — not an operation but a **bias over the hypothesis space**. `ProgramSize` is one; more deeply, **the library itself is a prior** — the vocabulary decides which solutions are cheap. Learning a library _is_ learning a prior.
- **Combinator** — a primitive that _glues multiple sub-results_ into one (`overlay`, `tile`). Orthogonal to the transforms it glues; historically where our leverage was (7→19).

## Mental model

Three axes organize everything below.

**Level** — the low→high spine. Each level is a **new representational type**, and climbing a level means _inventing the type_ plus its **constructor** (`grid → type`, a _perceive_) and **eliminator** (`type → grid`, a _render_), plus an algebra over it. Abstraction ≈ richness of the type you hold.

| Code | Level | New type | Intro / Elim example |
| --- | --- | --- | --- |
| L0 | substrate / control (domain-agnostic, "gifted") | Int, Bool, Coord, Fn | literals / — |
| L1 | cell / coordinate | Coord, Cell | `read` / `build_grid`, `with_cell` |
| L2 | whole-grid | Grid (as a unit) | `most_common_color` / — |
| L3 | region / mask | **Mask** | `mask_by_color` / `crop_to_mask` |
| L4 | object | **Object, ObjectSet** | `segment` / `render_objects` |
| L5 | relation / scene | Relation, Scene-graph | `detect_period` / — |
| L6 | schema / task-archetype | Solution template | (whole strategies) |

**Prior** — Chollet's Core Knowledge, the "why these abstractions": **G** geometry/topology · **O** objectness/physics · **N** numerosity/counting · **A** agentness/goals · **—** substrate / none. (Color is an _interchangeable symbol_, not a Core prior — color-only ops are marked **—**.)

**The triad** — at _every_ level a solution has the same three-part shape: **perceive** (X→structure) → **transform** (X→X) → **render** (structure→grid). Today's substrate is almost all _transform_, a sliver of _perceive_, and no rich _render_ — so the missing half of ARC is **perception (parsing) and synthesis (rendering)**: the intro/elim of richer types.

### Legend

- **Role**:
  - `P` perceive (type intro)
  - `T` transform (X→X)
  - `R` render (type elim)
  - `C` combinator (glue)
  - `—` control/value
- **Status**:
  - `✅ done` shipped in a library/solver
  - `🔜 next` proposed & prioritized
  - `⚪ cand` catalogued candidate, not yet prioritized
- **Types**:
  - Live (`ValueType` in `substrate/types.py`):
    - `Grid`
    - `Color`
    - `Int`
    - `Fn`
      - the lambda lift; live but **opaque** (one enum tag, no arrow types yet) — a `Lam` closure, consumed by `build_grid`
  - Not yet implemented:
    - `Bool`
    - `Coord`
      - costs one enum member
      - = `(Int,Int)`
    - `Mask`
    - `Object`
    - `ObjectSet`
  - `*T` = variadic

---

## L0 — substrate / control (domain-agnostic)

The "gifted" machinery — control abstractions, not domain content. A human gets these free from embodiment; withholding them just cripples the substrate, so they're fair to provide. The recursion schemes (`map`/`fold`) are the reified _quantifier_ — the thing that lifts a per-cell step to a whole-grid transform and makes programs size-general.

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| const_int | Literal integer value (task-mined constant). | `→ Int` | L0 | — | — | ✅ done |
| const_color | Literal color value (task-mined constant). | `→ Color` | L0 | — | — | ✅ done |
| add / sub / mul | Integer arithmetic on two ints. `sub` **✅ done** (coordinate math for `build_grid`); add/mul ⚪ cand. | `(Int,Int)→Int` | L0 | — | — | ✅ done |
| floordiv / mod | Integer division & remainder — for coordinate math. | `(Int,Int)→Int` | L0 | — | — | ⚪ cand |
| min / max / abs | Elementary integer functions. | `(Int,Int)→Int` | L0 | — | — | ⚪ cand |
| eq / lt / gt | Compare two values; color eq = symbol match. | `(a,a)→Bool` | L0 | — | — | ⚪ cand |
| and / or / not | Boolean logic. | `(Bool,…)→Bool` | L0 | — | — | ⚪ cand |
| if | Choose between two branches on a condition. | `(Bool,a,a)→a` | L0 | — | — | ⚪ cand |
| map | Apply a function to every element — the quantifier. | `(Fn,[a])→[b]` | L0 | — | — | 🔜 next |
| fold | Accumulate over a sequence — stateful construction. | `(Fn,b,[a])→b` | L0 | — | — | 🔜 next |
| filter | Keep the elements passing a predicate. | `(Fn,[a])→[a]` | L0 | — | — | ⚪ cand |
| zip | Pair up two sequences elementwise. | `([a],[b])→[(a,b)]` | L0 | — | — | ⚪ cand |
| sort_by / argmax / argmin | Order or select by a key function. | `(Fn,[a])→…` | L0 | — | — | ⚪ cand |
| iterate / while | Repeat until a condition — general recursion (search hazard). | `(Fn,a)→a` | L0 | — | — | ⚪ cand |

## L1 — cell / coordinate

The pixel level: a grid _is_ a function `Coord→Color`. `read`/`build_grid` are the intension↔extension pair — the crux of the "set_cell vs build_grid" question. The **stateful half shipped first** (E2/E3): `read`/`set_cell` take plain `Int` coords — no `Coord` type — with literals task-mined via `Enumerate(coord_ints=True)`, and compose as ordinary typed transforms, **no lambda needed** (`substrate/primitives/cells.py`). The **pure half is now shipped too**: the AST gained a De Bruijn bound variable (`Var` = `$i`) and a `Lam` binder (Stitch-compatible; `substrate/program.py`), and `build_grid` (`substrate/primitives/build.py`) expresses geometry through coordinate arithmetic — a single size-general program re-derives each D4 member (rot90 = `read` at a reflected coord). Coords stay two `Int`s (no `Coord` type yet), so `width`/`height` and L0 `sub` are the shipped D4-rederivation clique; `make_coord`, `row`/`col` remain candidates. What's still missing is the *search* that finds these programs (a bespoke `build_grid` enumeration — deferred).

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| width / height | The grid's dimensions. | `Grid→Int` | L1 | G | P | ✅ done |
| shape | The grid's (rows, cols) together. | `Grid→(Int,Int)` | L1 | G | P | 🔜 next |
| make_coord | Pair two ints into a coordinate (Coord intro; monomorphic face of a generic `pair`). | `(Int,Int)→Coord` | L1 | — | — | 🔜 next |
| row / col | A coordinate's components (Coord elim — what makes `shape` and lambda-bound coords consumable). | `Coord→Int` | L1 | — | — | 🔜 next |
| read | Sample the color at a coordinate (intension); shipped on plain `Int` coords. | `(Grid,Int,Int)→Color` | L1 | — | P | ✅ done |
| in_bounds | Whether a coordinate lies inside the grid. | `(Grid,Coord)→Bool` | L1 | G | P | ⚪ cand |
| neighbors4 / neighbors8 | The adjacent coordinates (4- or 8-connectivity). | `Coord→[Coord]` | L1 | G | P | ⚪ cand |
| set_cell | Grid with one cell recolored (functional set-cell; stateful when folded); shipped on plain `Int` coords. | `(Grid,Int,Int,Color)→Grid` | L1 | — | T | ✅ done |
| swap_cells | Exchange the colors of two cells (a transposition — derivable from read+set_cell by re-reading the original grid; E2 *re-derived it* as a learned abstraction, never hand-shipped). | `(Grid,Coord,Coord)→Grid` | L1 | — | T | ⚪ cand |
| build_grid | Construct a grid from a coordinate→color function (regenerates D4 as small programs); the `Fn` is a curried `Lam(Lam(body))`. | `(Int,Int,Fn)→Grid` | L1 | — | R | ✅ done |
| blank / fill | A uniform grid of a single color. | `(Int,Int,Color)→Grid` | L1 | — | R | ⚪ cand |

## L2 — whole-grid (≈ everything shipped today)

Grid-as-a-unit. Most are _derivable_ from L0+L1 — which is exactly why they're the first tier of learnable abstractions (the dream: watch the system re-derive D4 from L1).

**Geometry**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| identity | Return the grid unchanged. | `Grid→Grid` | L2 | G | T | ✅ done |
| rot90 / rot180 / rot270 | Rotate the grid (D4). | `Grid→Grid` | L2 | G | T | ✅ done |
| flip_h / flip_v | Mirror the grid horizontally / vertically (D4). | `Grid→Grid` | L2 | G | T | ✅ done |
| transpose / anti_transpose | Reflect across a diagonal (D4; group closed under ∘). | `Grid→Grid` | L2 | G | T | ✅ done |
| translate / shift | Move all cells by an offset (fill or wrap). | `(Grid,Int,Int)→Grid` | L2 | G | T | ⚪ cand |
| scale | Upsample each cell to a k×k block (`np.kron`, cap 30). | `(Grid,Int)→Grid` | L2 | G | T | ✅ done |
| downsample | Shrink by an integer factor — inverse of scale. | `(Grid,Int)→Grid` | L2 | G | T | ⚪ cand |
| crop | Cut out a sub-region (see L3). | `(Grid,Mask)→Grid` | L2 | G | T | ⚪ cand |
| pad | Add a border of a color around the grid. | `(Grid,Int,Color)→Grid` | L2 | G | T | ⚪ cand |
| tile_repeat | Repeat the whole grid in an r×c layout (≠ combinator `tile`). | `(Grid,Int,Int)→Grid` | L2 | G | T | ⚪ cand |
| concat_h / concat_v | Join two grids side by side / stacked. | `(Grid,Grid)→Grid` | L2 | G | C | ⚪ cand |

**Color (symbol)**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| map_color | Recolor one source color to a target (can't express a _swap_). | `(Grid,Color,Color)→Grid` | L2 | — | T | ✅ done |
| swap_colors | Exchange two colors throughout (what map_color collapses on at depth-2). | `(Grid,Color,Color)→Grid` | L2 | — | T | 🔜 next |
| permute_palette | Apply a bijective color remapping. | `(Grid,Perm)→Grid` | L2 | — | T | ⚪ cand |
| invert_palette | Reverse / complement the palette. | `Grid→Grid` | L2 | — | T | ⚪ cand |
| filter_color | Keep one color, blank the rest to background. | `(Grid,Color)→Grid` | L2 | — | T | ⚪ cand |

**Perceive (grid → scalar): the "derive the parameter" unlock**

Turns a _constant_ argument into a _perceived_ one — what finally makes depth-2 pay.

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| most_common_color | The most frequent color (feeds map_color / overlay mask). | `Grid→Color` | L2 | N | P | 🔜 next |
| least_common_color | The rarest color present. | `Grid→Color` | L2 | N | P | 🔜 next |
| background_color | The dominant / background color (usually the majority). | `Grid→Color` | L2 | O | P | 🔜 next |
| palette | The set of colors present. | `Grid→[Color]` | L2 | — | P | 🔜 next |
| count_color | How many cells have a given color (feeds scale / tile dims). | `(Grid,Color)→Int` | L2 | N | P | 🔜 next |
| num_colors | How many distinct colors are present. | `Grid→Int` | L2 | N | P | 🔜 next |
| is_symmetric | Whether the grid has a symmetry (predicate for schema selection). | `Grid→Bool` | L2 | G | P | ⚪ cand |

**Combinators**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| overlay | Merge grids by non-mask consensus (the symmetry-repair engine). | `(Color,*Grid)→Grid` | L2 | G/O | C | ✅ done |
| tile | Assemble cells into an r×c mosaic. | `(Int,Int,*Grid)→Grid` | L2 | G | C | ✅ done |
| mask_merge | Pick each cell from grid A or B by a mask. | `(Mask,Grid,Grid)→Grid` | L2 | — | C | ⚪ cand |

## L3 — region / mask (type: **Mask** — reserved, unbuilt)

The bridge from "grid" to "object". Cheap, high-value, small search cost — likely the first new type to pay off. `crop_to_content` alone probably clears several train tasks.

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| mask_by_color | Select all cells of a given color as a mask (intro). | `(Grid,Color)→Mask` | L3 | O | P | 🔜 next |
| mask_by_predicate | Select cells passing a predicate (intro). | `(Grid,Fn)→Mask` | L3 | — | P | ⚪ cand |
| nonbg_mask | Select all non-background cells (intro). | `Grid→Mask` | L3 | O | P | 🔜 next |
| flood_region | The connected same-color region from a seed cell. | `(Grid,Coord)→Mask` | L3 | O | P | ⚪ cand |
| bbox_mask | The bounding-box region of the content. | `Grid→Mask` | L3 | G | P | ⚪ cand |
| union / intersect / difference | Combine two masks set-wise. | `(Mask,Mask)→Mask` | L3 | — | T | ⚪ cand |
| complement | Invert a mask. | `Mask→Mask` | L3 | — | T | ⚪ cand |
| dilate / erode | Grow / shrink a mask (morphology). | `Mask→Mask` | L3 | O | T | ⚪ cand |
| boundary / interior | Edge vs. inside of a mask (topology). | `Mask→Mask` | L3 | G | T | ⚪ cand |
| crop_to_mask | Crop the grid to a mask's bounds (elim). | `(Grid,Mask)→Grid` | L3 | G | R | 🔜 next |
| extract_subgrid | Pull out the masked region as a new grid (elim). | `(Grid,Mask)→Grid` | L3 | G | R | ⚪ cand |
| paint_through_mask | Recolor only the masked cells (elim). | `(Grid,Mask,Color)→Grid` | L3 | — | R | 🔜 next |
| crop_to_content | Crop to the bounding box of all non-background cells (high value, cheap). | `Grid→Grid` | L3 | G | R | 🔜 next |
| trim_border | Drop a uniform surrounding frame. | `Grid→Grid` | L3 | G | R | ⚪ cand |

## L4 — object (types: **Object, ObjectSet** — reserved, unbuilt)

Where most of ARC lives. The big unlock — and the big search cost: `ObjectSet` is a variable-length collection the current Cartesian `Enumerate` will choke on, so this layer likely needs a beam / frontier search _first_ (see the search notes in `EXPERIMENTS.md`).

**Intro — segmentation (`Grid → ObjectSet`)**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| segment_connected | Split into connected non-bg components (4/8-conn) (intro). | `Grid→ObjectSet` | L4 | O | P | 🔜 next |
| segment_by_color | One object per color (intro). | `Grid→ObjectSet` | L4 | O | P | 🔜 next |
| segment_by_frame | Partition by grid-lines / separators. | `Grid→ObjectSet` | L4 | O | P | ⚪ cand |
| segment_by_period | Split by a detected tiling period. | `Grid→ObjectSet` | L4 | G | P | ⚪ cand |

**Object properties & predicates (`Object → …`)**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| area | Cell count of an object. | `Object→Int` | L4 | N | P | 🔜 next |
| bbox | An object's bounding box. | `Object→Mask` | L4 | G | P | ⚪ cand |
| obj_shape | An object's normalized (position-free) mask. | `Object→Mask` | L4 | G | P | ⚪ cand |
| obj_color | An object's color. | `Object→Color` | L4 | — | P | ⚪ cand |
| centroid | An object's center coordinate. | `Object→Coord` | L4 | G | P | ⚪ cand |
| num_holes | Number of enclosed holes (topology / genus). | `Object→Int` | L4 | O | P | ⚪ cand |
| obj_is_symmetric | Whether an object is symmetric. | `Object→Bool` | L4 | G | P | ⚪ cand |
| is_rectangle / is_line / is_single_cell | An object's shape class. | `Object→Bool` | L4 | G | P | ⚪ cand |
| touches_border | Whether an object reaches the grid edge. | `(Object,Grid)→Bool` | L4 | O | P | ⚪ cand |

**Object transforms (`Object → Object`)**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| move_obj | Translate an object by an offset. | `(Object,Int,Int)→Object` | L4 | O | T | ⚪ cand |
| rotate_obj / flip_obj | Apply a D4 transform to one object. | `Object→Object` | L4 | G | T | ⚪ cand |
| recolor_obj | Change an object's color. | `(Object,Color)→Object` | L4 | — | T | ⚪ cand |
| scale_obj | Resize an object by a factor. | `(Object,Int)→Object` | L4 | G | T | ⚪ cand |
| normalize_obj | Crop an object to its own bounding box. | `Object→Object` | L4 | G | T | ⚪ cand |

**ObjectSet operations (`ObjectSet → …`)**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| count_objects | How many objects are in the set. | `ObjectSet→Int` | L4 | N | P | 🔜 next |
| filter_objects | Keep objects passing a predicate. | `(ObjectSet,Fn)→ObjectSet` | L4 | — | T | ⚪ cand |
| sort_objects | Order objects by size / position. | `(ObjectSet,Fn)→ObjectSet` | L4 | N | T | ⚪ cand |
| select_largest / select_smallest | Pick the biggest / smallest object. | `ObjectSet→Object` | L4 | N | T | 🔜 next |
| select_unique / odd_one_out | Pick the object unlike the others (relational). | `ObjectSet→Object` | L4 | O | T | ⚪ cand |
| group_by_shape / group_by_color | Cluster objects by shape / color. | `ObjectSet→[ObjectSet]` | L4 | — | T | ⚪ cand |
| dedup_by_shape | Drop duplicate shapes (congruence up to D4). | `ObjectSet→ObjectSet` | L4 | G | T | ⚪ cand |

**Elim — render (`ObjectSet/Object → Grid`)**

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| render_objects | Paint objects onto a canvas (elim). | `(ObjectSet,Grid)→Grid` | L4 | O | R | 🔜 next |
| place_object | Stamp one object at a position. | `(Grid,Object,Coord)→Grid` | L4 | O | R | ⚪ cand |
| stack_objects | Overlay objects in z-order. | `ObjectSet→Grid` | L4 | O | R/C | ⚪ cand |

## L5 — relation / scene (types: Relation, Scene-graph)

Reasoning _between_ objects, or object↔grid structure. Mostly perceivers of relations. This is a layer we've thought least rigorously about — and where "invent it, don't target it" bites hardest.

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| adjacent / touching | Whether two objects are next to each other. | `(Object,Object)→Bool` | L5 | O | P | ⚪ cand |
| contains / inside | Whether one object is inside another (topology). | `(Object,Object)→Bool` | L5 | O | P | ⚪ cand |
| aligned_row / aligned_col | Whether two objects share a row / column. | `(Object,Object)→Bool` | L5 | G | P | ⚪ cand |
| above / below / left / right | The relative position of two objects. | `(Object,Object)→Bool` | L5 | G | P | ⚪ cand |
| distance | The gap between two objects. | `(Object,Object)→Int` | L5 | G | P | ⚪ cand |
| same_shape / same_color / same_size | Whether two objects match on an attribute. | `(Object,Object)→Bool` | L5 | — | P | ⚪ cand |
| congruent | Whether two objects are equal up to a D4 transform. | `(Object,Object)→Bool` | L5 | G | P | ⚪ cand |
| is_copy_of / is_reflection_of | Whether one object is a copy / mirror of another. | `(Object,Object)→Bool` | L5 | G | P | ⚪ cand |
| match_objects | Pair input objects with output objects (correspondence). | `(ObjectSet,ObjectSet)→[(Object,Object)]` | L5 | O | P | ⚪ cand |
| detect_gridlines | Find separator rows / columns. | `Grid→[Int]` | L5 | G | P | ⚪ cand |
| detect_frame | Find a bounding frame. | `Grid→Mask` | L5 | G | P | ⚪ cand |
| detect_period | Find the tiling period of a pattern. | `Grid→(Int,Int)` | L5 | G | P | ⚪ cand |
| detect_symmetry_axis | Find an axis of symmetry (for repair). | `Grid→Axis` | L5 | G | P | ⚪ cand |
| rank_by_count | Order objects by frequency (most / least common shape). | `ObjectSet→[Object]` | L5 | N | P | ⚪ cand |

## L6 — schema / task-archetype (solution templates — the "observables")

The most abstract layer: recurring whole-task _strategies_. These are the abstractions we most want to see **emerge** rather than hand-code — the ones the "targets are observables, not inputs" rule is about. Two already exist, as bespoke solver strategies.

| Name | Description | Signature | Lvl | Prior | Role | Status |
| --- | --- | --- | --- | --- | --- | --- |
| symmetry_repair | Fill occlusions using the grid's symmetry (dream: see it invented). | `Grid→Grid` | L6 | G/O | — | ✅ done |
| mosaic / tiling | Generate output by tiling transformed copies. | `Grid→Grid` | L6 | G | — | ✅ done |
| select_and_transform | Find the special object and transform it. | `Grid→Grid` | L6 | O | — | 🔜 next |
| denoise | Remove stray / isolated pixels. | `Grid→Grid` | L6 | O | — | ⚪ cand |
| gravity | Let objects fall / settle in a direction. | `Grid→Grid` | L6 | O/A | — | ⚪ cand |
| flood_fill_regions | Color in bounded regions. | `Grid→Grid` | L6 | O | — | ⚪ cand |
| count_then_render | Count something, then draw N of something. | `Grid→Grid` | L6 | N | — | ⚪ cand |
| pattern_completion | Extrapolate a periodic pattern. | `Grid→Grid` | L6 | G | — | ⚪ cand |
| connect_the_dots | Draw lines between marker cells. | `Grid→Grid` | L6 | G/A | — | ⚪ cand |
| learned_colormap | Apply a consistent input→output recoloring. | `Grid→Grid` | L6 | — | — | ⚪ cand |
| crop_to_salient | Zoom to the interesting region. | `Grid→Grid` | L6 | O | — | ⚪ cand |
| outline_objects | Draw borders around objects. | `Grid→Grid` | L6 | G/O | — | ⚪ cand |
| analogy_within_grid | Apply a rule demonstrated elsewhere in the same grid. | `Grid→Grid` | L6 | A/G | — | ⚪ cand |

---

## What the map shows

- **Almost everything `done` is L2** (+ two L6 schemas built as bespoke searches, + task-mined L0 leaves, + the L1 cell floor). L1 now has **both halves**: the stateful pair `read`/`set_cell` (E2/E3) and the pure render `build_grid` (+ `width`/`height`/`sub` and the `Lam`/`Var` substrate) — though the *search* that finds `build_grid` programs is still deferred. Whole layers — L3, L4, L5 — remain empty. `Mask`/`OBJECTS` are IOUs in the type enum.
- **The vocabulary is transform-heavy, perception-poor, render-poor.** Count the `Role` column: `done` rows are almost all `T`. The object half of ARC is gated behind one missing intro (`segment`) and one missing elim (`render_objects`). Ferré's ARC-MDL/MADIL is a worked existence proof that the _descriptive_ (perceive/render) paradigm — a single model that both parses and generates — is viable and human-legible; this is now read as the **highest-leverage empty region** (see [RESEARCH-2026-07-07.md](RESEARCH-2026-07-07.md) §Where we sit).
- **Cheapest high-value moves** (fit the current engine, low regression risk): the L2 _perceivers_ (`most_common_color`, `count_color`, …) that turn constants into derived values, and the L3 `Mask` intro/elim pair (esp. `crop_to_content`).
- **Biggest unlock, biggest cost**: L4 objects — needs a beam/frontier search before the vocabulary, or the Cartesian `Enumerate` truncates and risks the regression locks.
- **Highest abstraction, hand-code least**: L6 schemas are what we want the machinery to _invent_.
