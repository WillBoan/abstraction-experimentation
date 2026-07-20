# Ladder: al6-mirror-tall

- **Status:** linted
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: normalize-and-mirror, stacked — the same competence as [al1-mirror](../al1-mirror/worksheet.md), climbed four rungs instead of two
- Construction method: (2) forward extension (AL1's floor + perceivers, extended upward)
- **Family:** shares its floor with [al5-perceiver-chain](../al5-perceiver-chain/worksheet.md). al5 is height 4, al6 is height 5 — the batch's **height axis**, everything else held constant. Siblings, not independent data points.

### Reference config

- Floor (`L_0`): `{flip_h, flip_v, map_color, most_common_color, least_common_color}`
  - AL1's floor `{flip_h, flip_v, map_color}` **plus the two perceivers** — the addition is what lets rungs be param-free enough to stack without the constant space exploding at every level.
- Budget:
  - `depth_limit`: **3** (pinned — the window is [3,3])
  - `max_arity`: 3 (`map_color` is ternary)
  - `max_pool`: TBD
- Engine options:
  - constant sources: `finite-enumerate`
  - function-hole fill: none
  - polymorphism: monomorphize
- Learn:
  - proposer: `AntiunifyPairs` (all demos full_solution)
  - governance: `GreedyMDL`
  - iterations: 7+ (height 5 needs >= 5 climbing wakes plus termination headroom)

### Rung spine

Depths **machine-computed** (`compositional_depth` / `unfold_program`, 2026-07-19).

| i   | Rung        | Template (over `L_{i-1}`)                                                              | `d_i` | Inlined double-jump | Free params | Demo kinds    |
| --- | ----------- | ---------------------------------------------------------------------------------------- | ----- | ------------------- | ----------- | ------------- |
| 1   | rot180      | `flip_h(flip_v g)` — AL1's own rung, unchanged                                              | **2** | 4 (skip r1)         | 0           | full_solution |
| 2   | norm_mirror | `map_color(flip_h(rot180 g), most_common_color g, c1)`                                    | 3     | 5 (skip r2)         | 1 (COLOR)   | full_solution |
| 3   | norm_stack  | `map_color(flip_v(norm_mirror(g, c1)), least_common_color(flip_h g), c2)`                  | 3     | 5 (skip r3)         | 2 (COLOR)   | full_solution |
| 4   | norm_quad   | `map_color(flip_h(norm_stack(g, c1, c2)), most_common_color(flip_v g), c3)`                 | 3     | —                   | 3 (COLOR)   | full_solution |

### Top Rung (goal layer — no abstraction is minted here)

- Reference solution: `flip_v(norm_quad(g, 1, 7, 4))`
- `d_top` = 2 over `L_4` · `d_raw` = **9** · top-skip (over `L_3`) = 4

### Sandwich check

- Every `d_i` <= pinned `depth_limit`: 2, 3, 3, 3 <= 3 — OK
- `d_top` <= `depth_limit`: 2 <= 3 — OK
- Every inlined double-jump > `depth_limit`: 4, 5, 5 > 3 — OK
- Top-skip > `depth_limit`: 4 > 3 — OK
- `d_raw` > `depth_limit`: 9 > 3 — OK
- **Validity window: [3, 3]** (width 1)

### Per-rung detail

- **r1 `rot180`** — param-free; AL1's own rung (`flip_h(flip_v g)`), shared with ladder #1.
  - Demos (>= 2): >= 2 train examples each with varied content, killing the literal-constant shortcut.
  - Collision risk: AL1's lesson — `flip_h ∘ flip_v` is `rot180`, so if `rot180` is ever added to this floor r1 collapses to depth 2. It is deliberately **not** on the floor. Do not "helpfully" add it.
- **r2 `norm_mirror`** — 1 free COLOR param `c1` (fixed within task, varied across demos).
- **r3 `norm_stack`** — 2 free params `c1`, `c2`.
- **r4 `norm_quad`** — 3 free params `c1`, `c2`, `c3`.
- `involves_lambda`? no (all rungs).

### Heldout split

- 1 task per level (5 tasks), colour choices disjoint from train.

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- **The tallest ladder in the batch (height 5)** and the height-axis partner to al5. Whether the wake-sleep loop climbs five rungs at all is the open question — AL1 climbed two, and nothing has been tried above that.
- It is deliberately the **expensive arm**: free params grow 0 → 1 → 2 → 3 up the ladder, so the vocabulary tax compounds at every level on top of a library that is also growing. If any ladder walls, this one walls first, and where it walls is the measurement.
- Same anchor competence as AL1 on a superset of AL1's floor, so AL1 is its natural shallow control.

### Open problems

1. **Cost, and it is the sharpest version of the problem.** r4 carries 3 free COLOR params; with `finite-enumerate` over 10 colours that is 1000 instantiations per application, before the library-growth tax. This may exceed even a millions-of-candidates budget. Mitigations in preference order: switch to `harvest` constants; cap the colour alphabet in the generator; accept a walled climb as the result.
2. **Greedy MDL over five rungs.** Every previous climb was two rungs, so the loop has never had the chance to mint a wrong-but-compressive abstraction early and be stuck with it. This is the first real test of governance under a long climb.
3. Zero depth headroom (all four jumps sit exactly at `depth_limit`=3) — a fragile configuration by construction.
4. `iterations` needs to be generous; with `early_stop` a quiet wake is required before convergence is declared, so budget >= 7.

### Dead ends / failed bisections

- **(2026-07-19)** First attempt kept AL1's `rot180` and the double-jump skipping it came out at **3**, not exceeding `depth_limit`=3 — ie the rung was free to skip. The first diagnosis was that *rung depths must be roughly uniform*, and r1 was deepened to a d=3 `norm180`. **That diagnosis was wrong** and the deepening was reverted. Machine-checked (holding `d_1`=2 and varying only the call site): the rule is about **call-site nesting**, not depth uniformity —

  > skipping `r_i` is forbidden iff `(nesting of the r_i call site inside r_{i+1}) + d_i > depth_limit`

  The original `r_2` called `rot180` at nesting 1 (1+2 = 3, not > 3); calling it at nesting 2 gives 2+2 = 4 > 3 and the shallow rung is unskippable. Working the algebra through, any rung with `d_i >= 2` can be made unskippable — which is just the proper-composition rule the lint already enforces. So r1 is AL1's `rot180`, unchanged, and this ladder is a true upward extension of ladder #1.
- **(2026-07-19)** An earlier variant kept AL1's floor exactly (no perceivers) and reached d=3 rungs by adding more free COLOR params per rung instead. Rejected: param counts reached 6 at the top rung (10^6 instantiations), which is unrunnable. Adding the two perceivers buys depth without buying constants.

### Notes

- Depths verified 2026-07-19 against the real registry; every template passes `make_abstraction` type-checking at its level.
- Minimality not verified — the certificate is the gate.

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/al6_mirror_tall.py`): **built** — registry key `al6-mirror-tall`
- Generator / committed testbed: **built** — `taskgen al6-mirror-tall` -> `testbeds/al6-mirror-tall/` (template-driven, regenerates byte-identically)
- Generated artifacts (`spec.md` / `results.md` / `report.json`): — (written on first run)
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: — (lint passes; certificate pending first run)
