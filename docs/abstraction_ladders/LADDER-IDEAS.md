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
- Sandwich sketch (arithmetic at a candidate pinned `depth_limit`)
- Machinery demands (constants · fill/HO · poly · variadics · free params · proposer · other)
- v1-eligible · Tests/drains · Family potential · Corpus notes (only if non-obvious) · Blockers

### Candidates

- **quad-symmetrize** — ADOPTED 2026-07-19 → [ladders/al3-quad-symmetrize/worksheet.md](ladders/al3-quad-symmetrize/worksheet.md) (full content migrated; blocking open problem carried over: the r2 skip route — minimal witness is fan-in 1)

- **mask-crop** — ADOPTED 2026-07-19 → [ladders/al4-mask-crop/worksheet.md](ladders/al4-mask-crop/worksheet.md) (full content migrated; r2 + top still undesigned)

- **perceiver-chain** — ADOPTED 2026-07-19 → [ladders/al5-perceiver-chain/worksheet.md](ladders/al5-perceiver-chain/worksheet.md) (full content migrated; r2 + top still undesigned)

- **layout-mosaic** — "assemble an n x n mosaic" (toward `tile_repeat`)
  - Height: ~3-4
  - Shape: chain; fan-in 3-by-multiplicity at r2 (r1 used 3x)
  - Floor: `LAYOUT_GEN`-ish (`concat_h`, `concat_v`; `tile_repeat` withheld)
  - Rungs:
    - r1 = `row_of_3(g) = concat_h(g, concat_h(g, g))` (d=2, param-free)
    - r2 = `grid_3x3(g) = concat_v(r1(g), concat_v(r1(g), r1(g)))` (d=3, param-free)
  - Top Rung: mosaic-then-X
  - Sandwich sketch: like quad-symmetrize but with heavier inlined compounding (r1 appears 3x); numbers to verify
  - Certified (probe): r1 d=2; minimal r2 witness is `r1(concat_v(g, concat_v(g, g)))` d=3 — **fan-in 1**, wrapping a fresh col-of-3 motif (the intended r1-used-3x form is tree-size 5, shadowed); raw r2 censored > 6; `grid9x9 = r2(r2(g))` d=2 over L2 (a certified self-composition top)
  - ⚠ Same skip-route caveat as quad-symmetrize: the "fan-in 3-by-multiplicity" claim does not survive minimality
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

- **self-composition telescope** — "each rung = the previous rung squared" (geometric depth profile)
  - Height: 3-4
  - Shape: telescope; `r_{i+1} = r_i(r_i(g))` — constant jump d=2 while inlined depth DOUBLES per rung
  - Floor: any param-free `GRID->GRID` motif tower (grid-doubling instances certified: `quad2` over quad-symmetrize, `grid9x9` over layout-mosaic)
  - Sandwich sketch: the maximally efficient ladder geometry — sharpest instrument for characterizing `cost_L(d)` shape (RQ1 secondary)
  - Machinery demands: none beyond the host tower's
  - v1-eligible: yes, as an overlay on quad-symmetrize / layout-mosaic (their certified tops ARE its first rung)
  - Tests: geometric vs linear depth-profile family — an axis the linear-profile candidates can't reach
  - Blocked variant: `translate`/`scale`-by-`2^k` towers need constant leaves (probe scope note); grid-doubling saturates the ARC 30-cap after ~2 squarings on 3x3 inputs

- **domain-genesis: recolor from the universal floor** — "abstraction converts completeness into affordability"
  - Height: ~2-3
  - Shape: chain
  - Floor: `MINIMAL_COMPLETE_FLOOR` + `most_common_color`
  - Rungs: r1 = `map_color` re-derived as a `build_grid` lambda (`if eq(read(g,r,c), a) then b else read(g,r,c)`) · Top: `recolor_bg` over the learned r1 (the E11 composition riding a learned, not gifted, `map_color`)
  - Machinery demands: `fill=lambda-synthesis` + `finite-enumerate` — the E13 cost cliff (~17-24x/round) applies
  - v1-eligible: NO (cost); 3x3 grids only, raw baseline censored
  - Tests: turns E13's expressible-but-unfindable seam into a ladder — connects the fundamental-floor grain contrast to the ladder program

- **perceiver-genesis: re-derive `most_common_color` itself** — perception as rungs
  - Height: ~3
  - Shape: chain crossing `Grid -> [Color] -> Color`
  - Floor: `CELLS_IO` + `fold` + `eq`/`if` + `map_color` (+ arithmetic for the argmax)
  - Rungs: r1 = `count_color` via fold-over-cells · r2 = `most_common_color` via argmax-over-palette · Top: `recolor_bg` riding two LEARNED perceivers
  - Distinct from counting-histogram: rungs are PERCEIVERS (non-Grid→Grid, mid-pipeline), and the target is a shipped primitive — a perceiver gen/full contrast
  - Machinery demands: HO fill · fold body vocabulary (bundles-doc Constraint 4 thin-body warning) · RQ3 fragment visibility for non-Grid→Grid rungs
  - v1-eligible: NO
  - Tests: can sleep mint a perceiver at all (no experiment has yet)

- **scheme-ladder: a function-typed rung** — `symmetrize_by`
  - Height: ~2-3
  - Shape: chain; the RUNG is a scheme, not a ground template
  - Floor: `D4_GEN` + `overlay`
  - Rungs: r1 (HO) = `symmetrize_by(g, f) ~ overlay(c, g, f(g))` — demonstrating tasks vary the D4 element `f` ACROSS tasks · Top: `full_symmetrize` = `symmetrize_by` chained over two axes
  - Machinery demands: the proposer must hole a FUNCTION — `StitchProposer` (the 2026-07-08 HO stack produces exactly this mint type); out of `AntiunifyPairs`' reach · variadic `overlay` caveats
  - v1-eligible: NO — a deliberate probe of the design doc's v1 scope boundary (mintable library abstractions vs substrate HO)
  - Tests: does the ladder framework extend past first-order antiunify

- **recolor-over-mask** — "re-derive swap_colors over mask machinery" (registry-mined)
  - Height: 2
  - Shape: chain
  - Floor: `mask_basic_gen` (`mask_by_color`, `nonbg_mask`, mask algebra minus `mask_difference`, `crop_to_mask`, `paint_through_mask`; withholds `swap_colors`, `map_color`, `crop_to_content`, `bbox_mask`)
  - Rungs: r1 = `map_color` (d=2 over this floor) · Top: `swap_colors(g,a,b) = paint_through_mask(map_color(g,a,b), mask_by_color(g,b), a)` (4 → 3 via r1, certified)
  - Machinery demands: `finite-enumerate` colors · 2 free params per rung → variation plans
  - v1-eligible: no (free-param pressure; the finding is the interest, not the climb)
  - Tests: the ONLY non-D4 skeleton the shipped registry yields; also a live floor-design caveat — `map_color` ↔ `swap_colors` are MUTUALLY derivable once mask machinery is present (refines the bundles doc's Constraint 5, which is floor-relative)

- **control ladders** — decoy / skippable / greedy-trap (measurement instruments)
  - Shape: each = a proven ladder + ONE deliberate violation of a linter rule
  - `decoy`: add a learnable-but-unused rung — does the loop pay only vocabulary tax, or derail?
  - `skippable`: a consecutive pair with deliberately TRACTABLE double-jump — measures what rung-necessity enforcement buys (settles design doc §7 empirically, not by fiat)
  - `greedy-trap`: the MDL-best mint at step i is wrong for step i+1 — governance stress test
  - Machinery demands: none new; the probe certifies each statically for free
  - v1-eligible: not #1, but EARLY — they gate the interpretation of every other ladder's results
  - Tests: negative controls for the whole batch

---

- **(negative note) D4-only ladders cap out** — the group has 8 elements, all reachable at depth <= 4 from the generators, so double-jump intractability is nearly unachievable: validity windows empty or one budget wide. D4 material = calibration ladders (height 2), not taller ladders.
  - Quantified (probe): `rot180` is the unique deepest member (d=4 over `{flip_h, transpose}`), collapsing to 2 via any of FOUR interchangeable rungs (`rot90`/`rot270`/`flip_v`/`anti_transpose`) — a free rung-choice metaparameter for the calibration arm.

- **(negative note, quantified) registry mining caps at height 2** — exhaustive derivability pass (leave-one-out + 12 bundles-doc floors, [probe artifacts](../../experiments/2026-07-17-derivability-dag/)): the shipped mono registry yields exactly two ladder skeletons (the D4 one above; recolor-over-mask). Cross-domain floors derive nothing — layout/cell/arith members are mutually independent at these depths. Height >= 3 requires composite (unshipped) targets, always.

---

### Based on previous experiments

Note: under the goal-layer Top-Rung framing, NO previous experiment is a complete ladder — each needs a top layer added (tasks that use the top bridging rung as a fragment).

- **e1-rot90-retrofit** — ADOPTED 2026-07-19 as **rot90-calibration** → [ladders/al2-rot90-calibration/worksheet.md](ladders/al2-rot90-calibration/worksheet.md) (the calibration arm; rot180-as-`rot90∘rot90` self-composition top)
- **e12-layered-retrofit** — **REALIZED as `al1-mirror`** (built, ADMITTED + run 2026-07-18) → [ladders/al1-mirror/worksheet.md](ladders/al1-mirror/worksheet.md). AL1 = this floor/rung pair (`mirror_recolor` = `recolor_flipped`) + the second-recolor top; it is the batch's pure-telescope shape-control arm. Historical note kept: the probe reproduces E12's measured jumps exactly (r1 d=2; r2 3 → 2) — the probe's ground-truth anchor
- E2: ...
- [Other previous experiments to be added here, if they have a relevant ladder...]

### Based on "Finding abstraction ladders" Claude chat

- Geometrically minimal ladder
- [I'll add more details of this chat's findings and ideas here.]

---

### Possible ladder sources/seeds

- Based on previous experiments (E1, E2, ...).
- Based on real ARC tasks.
  - Specific procedure — **backward decomposition**: hand-write arc-lab-DSL solutions for a motif cluster of unsolved arc1 tasks, bisect the ASTs at the most-reused subterms (method (2) seeded by evidence), antiunify across the cluster → rungs AND demonstrating tasks fall out together. Needs no external DSL and no Object pathway for the grid-level subset.
- **Reservoir mining of failed runs** — the §5.1 sampling reservoirs already record candidates from big-budget FAILED searches; frequent deep subterms on near-miss tasks = empirically-almost-useful rung candidates. Uses existing recorded atoms; no new machinery.
- **Canonical towers from other fields** — translate an ordering that is independently known to be natural: hyperoperations (succ → add → mul → pow), image-morphology (dilate-once → open/close → connected components — the Object pathway's natural rung ordering), predicate → dispatch → interpreter, developmental (subitize → count → compare), simple dynamics (fall-one-step → fall-until-blocked). The translation into grid-land is the design work; the rung ORDER comes free.
- **Inverted desiderata** — generate control ladders by violating exactly one Ladder-Linter rule at a time; the linter checklist doubles as a control-ladder generator (see control ladders above).
- Based on Hodel's 160-ish-sized DSL for ARC + Hodel's canonical ARC task solutions.
  - Immediate use: **mine rung statistics** — which sub-programs recur across the canonical solutions → empirically-grounded rung candidates and ladder shapes; plus the grid-level subset of solutions translates cheaply today (→ real-ARC anchor corpora + reference solutions).
  - Fuller use is gated by the **Object pathway** (arc-lab has no Object type yet) — a modest, near-term build if we want it, with Hodel's object primitives as its natural blueprint. Not a distant thing.
- Ladders come up with in the "Finding abstraction ladders" Claude chat; or using approaches developed in that chat.
- **The derivability probe** ([experiments/2026-07-17-derivability-dag/](../../experiments/2026-07-17-derivability-dag/)) — a reusable certifier for ANY candidate on this page: computes minimal `d_i`, double-jump censoring, and skip routes by enumeration over the real impls (holdout-verified).
  - Both hand-computed fan-in templates on this page had cheaper skip routes — **compute `d_i` by enumeration, never by hand**; fold this into the Ladder Linter.
  - Accounting caveat: the probe counts tree applications (no subterm sharing); the sandwich sketches here use nesting depth (`depth_limit` units) — translate before comparing.
  - Registry mining itself is exhausted (see the quantified negative note above); the probe's remaining value is certifying composite candidates.

---

## Selection rubric (grading candidates; #1 first)

- non-HO floor (`fill=none`) → exact depth accounting
- 2 bridging rungs, `d_i` in {2,3}; sandwich closes at a small `depth_limit`; non-empty (ideally wide) validity window
- 0-1 free params per rung → trivial variation plans; AntiunifyPairs-proven path
- fan-in > 1 somewhere (avoid pure telescope)
- primitives already shipped; taskgen precedent exists
- nameable anchor competence
- family potential (obvious height / jump-depth variants)
- statically certified: `d_i` probe-computed, double-jump censored-intractable, no un-understood skip route (2026-07-17 probe)

Current ranking: **quad-symmetrize (#1)** · mask-crop (#2) · perceiver-chain (#3) · rot90-calibration (calibration arm) — all four ADOPTED 2026-07-19 (worksheets under [ladders/](ladders/), indexed in [LADDERS.md](LADDERS.md)) · counting-histogram + object-precursor + Hodel-mined as the ambitious track.

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
- **nonbg_mask-from-perceiver** — `GRID->MASK` = `mask_complement(mask_by_color(g, most_common_color(g)))` (d=3, certified) — perceive + mask-gen — derives a Mask _source_ from a perceiver; mask-genesis rung, ready-made gen/full contrast on `nonbg_mask`.
- **swap_colors-via-mask** — `(GRID,COLOR,COLOR)->GRID` = `paint_through_mask(map_color(g,a,b), mask_by_color(g,b), a)` (d=3, certified) — mask + recolor — the registry-mined duplicate-pair rung (see recolor-over-mask).
- **mask De Morgan closures** — `mask_union`/`mask_intersect`/`mask_difference` interderivable via `mask_complement` (d<=3, certified) — mask-algebra gen floors — algebraic mini-rungs for a mask-genesis ladder.
- **quad2 / grid9x9 self-composition tops** — `GRID->GRID` = `r2(r2(g))` (d=2 over L2, certified) — the cheapest possible goal layer for any param-free tower; doubles inlined depth per application (the geometric depth-profile family).
- **symmetrize_by** — `(GRID, GRID->GRID)->GRID` ~ `overlay(c, g, f(g))` — `D4_GEN` + `overlay` — the function-typed scheme rung (see scheme-ladder); StitchProposer territory.
- **dilate_once** — `MASK->MASK` (or `GRID->GRID`) neighborhood expansion — no shipped neighbor primitive; expressible only as an expensive `build_grid` lambda — first rung of the morphology tower toward `segment`; names a concrete primitive gap like `mask_count` does.
