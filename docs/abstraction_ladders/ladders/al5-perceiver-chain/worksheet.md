# Ladder: al5-perceiver-chain

- **Status:** linted
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: recolour relative to perceived colours, chained
- Construction method: (2) forward extension
- **Family:** shares its floor with [al6-mirror-tall](../al6-mirror-tall/worksheet.md). al5 is height 4, al6 is height 5 — together they are the batch's **height axis** with everything else held constant. They are siblings, not independent data points.

### Reference config

- Floor (`L_0`): `{map_color, most_common_color, least_common_color, flip_h, flip_v}`
- Budget:
  - `depth_limit`: **3** (pinned — the window is [3,3])
  - `max_arity`: 3 (`map_color` is ternary)
  - `max_pool`: TBD
- Engine options:
  - constant sources: `finite-enumerate` (r2/r3 take free COLOR params) — **the cost driver; see Notes**
  - function-hole fill: none
  - polymorphism: monomorphize
- Learn:
  - proposer: `AntiunifyPairs` (all demos full_solution)
  - governance: `GreedyMDL`
  - iterations: 6+

### Rung spine

Depths **machine-computed** (`compositional_depth` / `unfold_program`, 2026-07-19).

| i   | Rung          | Template (over `L_{i-1}`)                                                       | `d_i` | Inlined double-jump | Free params | Demo kinds    |
| --- | ------------- | ------------------------------------------------------------------------------- | ----- | ------------------- | ----------- | ------------- |
| 1   | swap_extremes | `map_color(map_color(g, most_common_color g, least_common_color g), least_common_color g, most_common_color g)` | 3 | 5 (skip r1) | 0 | full_solution |
| 2   | swap_mirror   | `map_color(flip_h(swap_extremes g), most_common_color g, c1)`                    | 3     | 5 (skip r2)         | 1 (COLOR)   | full_solution |
| 3   | swap_stack    | `map_color(flip_v(swap_mirror(g, c1)), most_common_color(flip_h g), c2)`         | 3     | —                   | 2 (COLOR)   | full_solution |

### Top Rung (goal layer — no abstraction is minted here)

- Reference solution: `flip_h(swap_stack(g, 2, 6))`
- `d_top` = 2 over `L_3` · `d_raw` = **8** · top-skip (over `L_2`) = 4

### Sandwich check

- Every `d_i` <= pinned `depth_limit`: 3, 3, 3 <= 3 — OK (no headroom)
- `d_top` <= `depth_limit`: 2 <= 3 — OK
- Every inlined double-jump > `depth_limit`: 5, 5 > 3 — OK
- Top-skip > `depth_limit`: 4 > 3 — OK
- `d_raw` > `depth_limit`: 8 > 3 — OK
- **Validity window: [3, 3]** (width 1)

### Per-rung detail

- **r1 `swap_extremes`** — param-free, two chained perceive-driven recolours.
  - Demos (>= 2): >= 2 train examples each with a **different most-common and least-common colour per example**, so no literal `map_color(g, k1, k2)` coincides (the E11 trap, directly).
- **r2 `swap_mirror`** — 1 free COLOR param `c1`.
  - `most_common_color(g)` (arg 2): derived → varies within task.
  - `c1`: free → fixed within task, varied across demonstrating tasks.
- **r3 `swap_stack`** — 2 free params `c1`, `c2`; same rule for both.
  - Note `c1` is threaded through to r2, so a demo task fixes both.
- `involves_lambda`? no (all rungs).

### Heldout split

- 1 task per level, with colour choices disjoint from train.

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- **The free-param / constant-heavy arm.** AL1 showed the vocabulary tax is almost entirely arity: its `b_eff` of 25-65 decomposes almost exactly into `map_color`'s two enumerated COLOR params contributing x100 per application. This ladder climbs three rungs with 0, 1 and 2 free params, so it measures how that tax compounds *under climbing* — which no run has done.
- Direct contrast with `al3` (param-free, no constant sources) at the opposite end of the cost axis.
- With `al6`, the height axis.

### Open problems

1. **Cost.** With `finite-enumerate` over 10 colours, a 2-free-param rung contributes x100 instantiations per application. At `depth_limit`=3 with a growing library this is the ladder most likely to wall. That is a legitimate measurement (and the user-accepted budget runs to millions of candidates), but it may need `max_pool` care, and if it walls, the wall's location *is* the result.
2. `swap_extremes` is not semantically a clean swap — the first `map_color` rewrites the background to the least-common colour, so the second recolour hits both the original least-common cells and the newly written ones. That is fine (the task is whatever the program computes), but **task generation must not assume swap semantics** — generate expected outputs by running the template, never by hand.
3. Window width 1 at `depth_limit`=3, and all three jumps sit exactly at the limit — zero headroom, so any library growth that pushes an effective depth up will break the climb rather than slow it.

### Dead ends / failed bisections

- **(2026-07-19, superseded design)** The original spine was `recolor_bg` (d=2, one free param) → a two-perceiver r2. It was abandoned for two reasons: the natural r2 (`recolor_bg(rot180 g, c)`) pulls `rot180` in as an independent sibling rung, which needs the sibling-level `LadderSpec` widening that does not exist; and d=2 jumps are below the height-3-to-6 / jump-3-to-5 target. The current spine keeps the free-param intent while reaching d=3 throughout by chaining perceivers inside each rung instead of across siblings.

### Notes

- Depths verified 2026-07-19 against the real registry; every template passes `make_abstraction` type-checking at its level.
- Minimality not verified — the certificate is the gate.

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/al5_perceiver.py`): **built** — registry key `al5-perceiver-chain`
- Generator / committed testbed: **built** — `taskgen al5-perceiver-chain` -> `testbeds/al5-perceiver-chain/` (template-driven, regenerates byte-identically)
- Generated artifacts (`spec.md` / `results.md` / `report.json`): — (written on first run)
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: — (lint passes; certificate pending first run)
