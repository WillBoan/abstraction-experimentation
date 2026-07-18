# Ideas for Ladders and Rungs

A parking lot for:

- **Ladder ideas** – Ideas for candidate ladders, which may be not yet fully formed.
- **Rung ideas** – Candidate abstractions that could be rungs in a ladder, but are not yet attached to any ladder.

Notes:

- Reference: ([Design doc](ABSTRACTION-LADDERS-2026-07-16.md)).
- Keep entries cheap; one piece of info per bullet.
- When a rung is adopted into a ladder, move it to that worksheet and delete it here; a rung wanted by several ladders is worth noting as such.
- NOT restricted to Ladder-#1-shaped ideas — complicated/ambitious ladders are extremely important; get them down even when blocked, with the blocker named.

---

## Ladder Ideas

Format (per idea; one piece of info per bullet; omit fields that are empty/obvious):

- **slug** — anchor competence (header line)
- Height · Shape (chain / telescope / fan-in / DAG) · Floor
- Rungs (one bullet per rung: name = template, `d_i`, free params) · Top Rung (goal layer)
- Sandwich sketch (arithmetic at a candidate reference `max_generation`)
- Machinery demands (constants · fill/HO · poly · variadics · free params · proposer · other)
- v1-eligible · Tests/drains · Family potential · Corpus notes (only if non-obvious) · Blockers

### Candidates

- **quad-symmetrize** — "build the 4-fold symmetric completion"
  - Height: ~3
  - Shape: chain; **fan-in 2** at r2 (uses r1 twice)
  - Floor: `{concat_h, concat_v, flip_h, flip_v}`
  - Rungs:
    - r1 = `mirror_pair(g) = concat_h(g, flip_h(g))` (d=2, param-free)
    - r2 = `quad_symmetrize(g) = concat_v(r1(g), flip_v(r1(g)))` (d=3, param-free)
  - Top Rung: symmetrize-then-X tasks (X = recolor via added `map_color`, or concat-with-original — floor addition TBD)
  - Sandwich sketch: closes at reference `max_generation=3` (`max_depth=4`) — jumps d=2,3 <= 3; inlined double-jump depth 4 > 3
  - Machinery demands: no constants · no HO (`fill=none`) · param-free rungs (no variation plans) · proposer: `AntiunifyPairs`
  - v1-eligible: **YES** — current #1 pick
  - Tests: first non-telescope climb (fan-in 2); real size-compounding in the inlined form
  - Family potential: +frame/recolor rung → height 4; deeper r1 motif → jump-depth variant

- **mask-crop** — "normalize content position/extent" (learned intermediate type)
  - Height: ~3
  - Shape: telescope (likely — natural r2 shapes wrap r1)
  - Floor: `MASK_MIN` (`nonbg_mask`, `crop_to_mask`), possibly + `map_color`/a perceiver
  - Rungs:
    - r1 = `crop_to_content(g) = crop_to_mask(g, nonbg_mask(g))` (d=2, param-free, var-sharing — `g` used twice)
    - r2 = compose on the normalized grid (eg crop-then-recolor — design open)
  - Top Rung: TBD
  - Machinery demands: no constants (± `finite-enumerate` if recolor joins) · no HO · a learned **Mask**-typed intermediate · proposer: `AntiunifyPairs`
  - v1-eligible: yes-ish (r2 + top undesigned)
  - Tests: construct-AND-consume a learned `Mask` type — the deepest gap-climbing phenomenon
  - Drains: the EXPERIMENT_QUEUE.md "learned intermediate type" row

- **perceiver-chain** — "recolor relative to perceived colors"
  - Height: ~3
  - Shape: chain (fan-in 1)
  - Floor: `{map_color, most_common_color, least_common_color}`
  - Rungs:
    - r1 = `recolor_bg(g,c) = map_color(g, most_common_color(g), c)` (d=2, one free param — the proven E11 abstraction)
    - r2 = a two-perceiver composite (eg "recolor bg to 0, then recolor the dominant remaining color" — design open)
  - Top Rung: TBD
  - Machinery demands: `finite-enumerate` constants · no HO · free params → variation plans (background-within / target-across) · proposer: `AntiunifyPairs`
  - v1-eligible: yes — deliberately after quad-symmetrize (free params exercise the variation-plan machinery under climbing)
  - Tests: free-parameter rungs at height 3; the E11 corpus discipline inside a ladder

- **layout-mosaic** — "assemble an n x n mosaic" (toward `tile_repeat`)
  - Height: ~3-4
  - Shape: chain; fan-in 3-by-multiplicity at r2 (r1 used 3x)
  - Floor: `LAYOUT_GEN`-ish (`concat_h`, `concat_v`; `tile_repeat` withheld)
  - Rungs:
    - r1 = `row_of_3(g) = concat_h(g, concat_h(g, g))` (d=2, param-free)
    - r2 = `grid_3x3(g) = concat_v(r1(g), concat_v(r1(g), r1(g)))` (d=3, param-free)
  - Top Rung: mosaic-then-X
  - Sandwich sketch: like quad-symmetrize but with heavier inlined compounding (r1 appears 3x); numbers to verify
  - Machinery demands: no constants · no HO · param-free · proposer: `AntiunifyPairs` · verify concat arity/type details
  - v1-eligible: likely
  - Tests: heavy re-embedding compounding; the bundles doc flags `tile_repeat` ~ nested `concat` as a clean gen/full invention target
  - Family potential: natural jump-size family via n = 2, 3, ...

- **cross-domain normalize** — "canonicalize a scene: crop, then normalize colors"
  - Height: ~3
  - Shape: **DAG, not a chain** — two level-1 siblings; fan-in 2 ACROSS domains at r2
  - Floor: `MASK_MIN` + `{map_color, most_common_color}` (mask + color domains together)
  - Rungs:
    - r1a = `crop_to_content` (mask domain)
    - r1b = `recolor_bg` (color domain) — two INDEPENDENT rungs at the same level
    - r2 = `normalize(g,c) = recolor_bg(crop_to_content(g), c)`
  - Top Rung: normalize-then-X
  - Machinery demands: `finite-enumerate` constants · no HO · sibling-level support in `LadderSpec` (separate `Rung`s sharing a `level` — deferred)
  - v1-eligible: NO as-is — needs the sibling-level widening
  - Tests: cross-domain recombination; the first non-chain topology; whether sleep mints two sibling abstractions in one iteration
  - Blockers: sibling-level `LadderSpec` support (cheap retrofit — see design discussion)

- **counting-histogram** — "count markers per line and paint runs" (4093f84a-style)
  - Height: ~4-5
  - Shape: deep chain (quantity pipeline)
  - Floor: `UNIVERSAL_FLOOR`-ish, or HO (`fold` + CELLS_IO + PAIR)
  - Rungs: bar/orientation detection → per-line counting (`count_left_of`-style, non-Grid→Grid) → run-painting. Worked case study: [4093f84a-EXPRESSIBILITY-2026-07-15.md](../task_specific/4093f84a-EXPRESSIBILITY-2026-07-15.md)
  - Top Rung: the real ARC task (or a synthetic sibling)
  - Machinery demands: HO (`fill=lambda-synthesis`) or CTRL-heavy floor + `finite-enumerate` · **quantity-typed (non-Grid→Grid) rungs** → embedded fragments (`FrequentSubtree`/`StitchProposer`), RQ3 fragment visibility, or probe tasks
  - v1-eligible: NO
  - Tests: quantity-typed rungs — the real-ARC-anchored deep ladder
  - Blockers: HO floors (fold body sampler), RQ3 options, or probe-task corpus design

- **object-precursor** — "select the largest color-region" (ladder-driven primitive discovery)
  - Height: ~3-4
  - Shape: chain
  - Floor: the `OBJECT_PRECURSOR` bundle (`palette`, `map`, `mask_by_color`, `crop_to_mask`, `sort_by`, `fold`)
  - Rungs:
    - r1 = `masks_by_palette(g) = map(mask_by_color(g), palette(g))`
    - r2 = select-largest — needs `MASK->INT` cardinality, the registry's known missing primitive
  - Top Rung: crop-to-largest tasks
  - Machinery demands: HO (`map`/`fold`/`sort_by`) · poly `bounded` · the missing `mask_count` primitive
  - v1-eligible: NO
  - Tests: whether **ladder demand surfaces a missing primitive** — the climb fails at r2 in a way that names `mask_count` exactly; a deliberate gap-exposing ladder
  - Blockers: HO + the `mask_count` gap (small build once demanded)

- **cell-swap** — "swap/move cell contents"
  - Height: ~2-3
  - Shape: single rung / short chain
  - Floor: `CELL_FLOOR` (`read`, `set_cell`)
  - Rungs:
    - r1 = `swap_cells` (d=3, FOUR free INT params, var-sharing — the registry's withheld re-derivation target)
    - r2: unclear without iteration/HO
  - Machinery demands: `finite-enumerate` coordinates (constant explosion) · heavy variation plans (4 free params) · proposer: `AntiunifyPairs`
  - v1-eligible: parked
  - Tests: high-arity free-param rungs (variation-plan stress test)
  - Blockers: no clean r2; coordinate-constant cost

- **tall-telescope** — height-family instrument (deliberately degenerate chain)
  - Height: 4-5
  - Shape: telescope by design (fan-in 1 throughout — the shape control)
  - Floor: any proven floor; rungs = repeated single-wrap
  - v1-eligible: not #1 — the Family-A instrument for height-scaling + vocabulary-tax compounding once the machinery works
  - Tests: does the climb stall as the library fattens — with shape held constant

- **(negative note) D4-only ladders cap out** — the group has 8 elements, all reachable at depth <= 4 from the generators, so double-jump intractability is nearly unachievable: validity windows empty or one budget wide. D4 material = calibration ladders (height 2), not taller ladders.

### Based on previous experiments

Note: under the goal-layer Top-Rung framing, NO previous experiment is a complete ladder — each needs a top layer added (tasks that use the top bridging rung as a fragment).

- **e1-rot90-retrofit** (calibration)
  - Height: 2 · Shape: single rung · Floor: `{flip_h, transpose}`
  - Rungs: r1 = `rot90` (d=2, param-free) · Top Rung: NEW layer using rot90 as fragment
  - v1-eligible: yes (calibration arm) — testbed/study exist; raw cost actually measurable
- **e12-layered-retrofit**
  - Height: ~3 · Shape: pure telescope (fan-in 1 throughout) — the shape-control counterpart to quad-symmetrize
  - Floor: `{flip_h, flip_v, map_color}` · Rungs: r1 = `rot180`, r2 = `recolor_flipped` · Top Rung: NEW layer
  - v1-eligible: yes (calibration / shape-control arm)
- E2: ...
- [Other previous experiments to be added here, if they have a relevant ladder...]

### Based on "Finding abstraction ladders" Claude chat

- Geometrically minimal ladder
- [I'll add more details of this chat's findings and ideas here.]

---

### Possible ladder sources/seeds

- Based on previous experiments (E1, E2, ...).
- Based on real ARC tasks.
- Based on Hodel's 160-ish-sized DSL for ARC + Hodel's canonical ARC task solutions.
  - Immediate use: **mine rung statistics** — which sub-programs recur across the canonical solutions → empirically-grounded rung candidates and ladder shapes; plus the grid-level subset of solutions translates cheaply today (→ real-ARC anchor corpora + reference solutions).
  - Fuller use is gated by the **Object pathway** (arc-lab has no Object type yet) — a modest, near-term build if we want it, with Hodel's object primitives as its natural blueprint. Not a distant thing.
- Ladders come up with in the "Finding abstraction ladders" Claude chat; or using approaches developed in that chat.

---

## Selection rubric (grading candidates; #1 first)

- non-HO floor (`fill=none`) → exact depth accounting
- 2 bridging rungs, `d_i` in {2,3}; sandwich closes at a small `max_generation`; non-empty (ideally wide) validity window
- 0-1 free params per rung → trivial variation plans; AntiunifyPairs-proven path
- fan-in > 1 somewhere (avoid pure telescope)
- primitives already shipped; taskgen precedent exists
- nameable anchor competence
- family potential (obvious height / jump-depth variants)

Current ranking: **quad-symmetrize (#1)** · mask-crop (#2) · perceiver-chain (#3) · retrofits as calibration ladders · counting-histogram + object-precursor + Hodel-mined as the ambitious track.

---

## Rung Ideas

Format: **name** — type/template sketch — floor it presumes — why interesting.

- **mirror_pair** — `GRID->GRID` = `concat_h(g, flip_h(g))` — layout + D4 generators — the canonical symmetry-building motif; wanted by quad-symmetrize and symmetry-repair.
- **quad_symmetrize** — `GRID->GRID` = `concat_v(mirror_pair(g), flip_v(mirror_pair(g)))` — builds on mirror_pair (fan-in 2).
- **crop_to_content** — `GRID->GRID` = `crop_to_mask(g, nonbg_mask(g))` — `MASK_MIN` — constructs+consumes Mask; already gifted in `MASK_BASIC`, so the gen/full contrast is ready-made.
- **recolor_bg** — `(GRID,COLOR)->GRID` = `map_color(g, most_common_color(g), c)` — perceive+recolor — proven mintable (E11); one free param.
- **normalize** — `(GRID,COLOR)->GRID` = `recolor_bg(crop_to_content(g), c)` — mask + color floors — cross-domain fan-in 2.
- **frame / border-add** — `(GRID,COLOR)->GRID` — layout (`pad`) + recolor — the height-4 extension rung for quad-symmetrize.
- **row_of_n / grid_nxn** — `GRID->GRID` — concat chains — the `tile_repeat` invention path; jump-size dial via n.
- **symmetry-repair overlay** — `GRID->GRID` ~ `overlay(c, g, flip_h(g))` — `SYMMETRY` floor — variadic (mind `max_arity` / beam starvation).
- **swap_cells** — `(GRID,INT,INT,INT,INT)->GRID` — `CELL_FLOOR` — the registry's withheld re-derivation target; high-arity variation-plan stress test.
- **mirror_index** — `(INT,INT)->INT` = `sub(sub(n,k),1)` — coordinate/HO floors — the E8/E9 reusable idiom; blocked on HO for v1.
- **count-per-line / mask_count consumers** — non-Grid→Grid — blocked on the `MASK->INT` gap (`OBJECT_PRECURSOR`) and/or RQ3 fragment visibility; the quantity-rung family.
