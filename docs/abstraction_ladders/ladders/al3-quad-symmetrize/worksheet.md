# Ladder: al3-quad-symmetrize

- **Status:** linted
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: build a nested symmetric tower (quad → band → tower)
- Construction method: (2) forward extension

### Reference config

- Floor (`L_0`): `{concat_h, concat_v, flip_h, flip_v}`
- Budget:
  - `depth_limit`: **4** (pinned — the window is [4,4])
  - `max_arity`: 2
  - `max_pool`: TBD — start generous; this floor is binary-heavy and pool-bound behaviour is part of what it measures
- Engine options:
  - constant sources: **none** (fully param-free ladder)
  - function-hole fill: none
  - polymorphism: monomorphize
- Learn:
  - proposer: `AntiunifyPairs` (all demos full_solution)
  - governance: `GreedyMDL`
  - iterations: 6+ (height 4 needs >= 4 climbing wakes plus termination headroom)

### Rung spine

Depths below are **machine-computed** (`compositional_depth` / `unfold_program`, 2026-07-19), not hand-derived.

| i   | Rung  | Template (over `L_{i-1}`)                                       | `d_i` | Inlined double-jump | Free params | Demo kinds    |
| --- | ----- | --------------------------------------------------------------- | ----- | ------------------- | ----------- | ------------- |
| 1   | quad  | `concat_v(concat_h(g, flip_h g), flip_v(concat_h(g, flip_h g)))` | 4     | 6 (skip quad)       | 0           | full_solution |
| 2   | band  | `concat_h(quad(g), flip_h(quad(g)))`                             | 3     | 5 (skip band)       | 0           | full_solution |
| 3   | tower | `concat_v(band(g), flip_v(band(g)))`                             | 3     | —                   | 0           | full_solution |

### Top Rung (goal layer — no abstraction is minted here)

- Reference solution: `concat_v(tower(g), flip_v(tower(g)))`
- `d_top` = 3 over `L_3` · `d_raw` = **10** · top-skip (over `L_2`) = 5

### Sandwich check

- Every `d_i` <= pinned `depth_limit`: 4, 3, 3 <= 4 — OK (no headroom on r1)
- `d_top` <= `depth_limit`: 3 <= 4 — OK
- Every inlined double-jump > `depth_limit`: 6, 5 > 4 — OK
- Top-skip > `depth_limit`: 5 > 4 — OK
- `d_raw` > `depth_limit`: 10 > 4 — OK
- **Validity window: [4, 4]** (width 1)

### Grid-size budget (this floor doubles dimensions — the binding practical constraint)

From a 3x3 seed: quad 6x6 → band 12x6 → tower 12x12 → top 12x24. Under the ARC 30 cap, but only just. Seeds must be **<= 3x3**; a 4x4 seed overflows at the top.

### Per-rung detail

All three rungs are param-free, so there are no variation plans; demo variety comes from distinct seed grids.

- **r1 `quad`** — demos (>= 2): asymmetric 2x2/3x3 seeds, >= 2 train examples each, distinct content per example.
  - Collision risk: symmetric or repeated-column seeds let `concat_h(g,g)`-style shallower programs coincide. Seeds must be asymmetric on **both** axes.
- **r2 `band`** — demos (>= 2): distinct seeds again; output is 4x wide, 2x tall.
- **r3 `tower`** — demos (>= 2): distinct seeds; output 4x wide, 4x tall.
- `involves_lambda`? no (all rungs).

### Heldout split

- 1 task per level (quad / band / tower / top), seeds disjoint from train.

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- **The binary-heavy cost arm.** `concat_h`/`concat_v` are binary, so composition count grows quadratically in pool size — this is the ladder that tells us what binary primitives cost under a depth-4 budget. Nothing else in the batch probes that.
- Fully **param-free with no constant sources** — the clean contrast against `al5`/`al6`, where free COLOR params plus `finite-enumerate` are the cost driver. Same question (what does a climb cost?), opposite end of the cost axis.
- Height 4, jumps [4,3,3] — the deepest single jump in the batch.

### Open problems

1. **Which form of `quad` gets minted.** `quad` has (at least) two depth-4 forms over the floor — the h-then-v nesting written above and the v-then-h commuted form `concat_h(X, flip_h X)` with `X = concat_v(g, flip_v g)`. Both are depth 4, so neither is a shortcut, but cheapest-wins retention picks one and `band`/`tower` must still route through whichever it is. `demonstration_health` in the certificate is the read — if it drops below 1.0, this is why.
2. Pool pressure is untested on a binary floor at depth 4. If `max_pool` binds, the run measures the reachability regime rather than the cost regime (design doc §2.1) — a legitimate result, but it needs labelling rather than silently reading it as a cost number.
3. Window width 1 — a `depth_limit` sweep has exactly one honest cell; every other budget cell is an arm relabel.

### Dead ends / failed bisections

- **(2026-07-19, superseded design)** The original spine was `mirror_pair` (d=2) → `quad` (d=3) with `quad` calling `mirror_pair` twice, chosen to get template-level fan-in > 1. The probe found the minimal `quad` witness is the fan-in-1 commuted form, so the fan-in claim could not survive minimality. Resolved by **dropping fan-in as a selection criterion** and folding `mirror_pair` into `quad` as a single depth-4 rung — which removes the shortcut question entirely, since `mirror_pair` is no longer a rung.
- **(2026-07-19)** First attempt at the goal layer used `flip_h(tower(g))`: `d_top`=2 and top-skip=4, which does **not** exceed `depth_limit`=4 → **empty validity window**. Fixed by deepening the top to `concat_v(tower, flip_v tower)` (top-skip 5). General lesson for deep-jump ladders: the top must nest `r_k` at least two levels down, or the top-skip check fails no matter how deep the jumps are.

### Notes

- Depth figures verified 2026-07-19 by running `compositional_depth`/`unfold_program` against the real registry; templates also pass `make_abstraction` type-checking at every level.
- Minimality is **not** verified — no enumeration was run. The certificate (`no_skip_paths`, `demonstration_health`) is the gate, per the AL1 precedent where lint passed and the certificate caught the real problem.

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/al3_quad.py`): **built** — registry key `al3-quad-symmetrize`
- Generator / committed testbed: **built** — `taskgen al3-quad-symmetrize` -> `testbeds/al3-quad-symmetrize/` (template-driven, regenerates byte-identically)
- Generated artifacts (`spec.md` / `results.md` / `report.json`): — (written on first run)
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: — (lint passes; certificate pending first run)
