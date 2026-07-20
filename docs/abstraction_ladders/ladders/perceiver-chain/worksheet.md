# Ladder: perceiver-chain

- **Status:** sketch
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: recolor relative to perceived colors
- Construction method: (2) forward extension

### Reference config

- Floor (`L_0`): `{map_color, most_common_color, least_common_color}` — see open problem 2 on `least_common_color`
- Budget: TBD with r2/top
- Engine options:
  - constant sources: `finite-enumerate`
  - function-hole fill: none
- Learn:
  - proposer: `AntiunifyPairs`
  - governance: `GreedyMDL`
  - iterations: 5

### Rung spine

| i   | Rung       | Template (over `L_{i-1}`)               | `d_i`         | Inlined double-jump depth | Fan-in | Demo kinds    |
| --- | ---------- | --------------------------------------- | ------------- | ------------------------- | ------ | ------------- |
| 1   | recolor_bg | `map_color(g, most_common_color(g), c)` | 2 (certified) | TBD                       | 0      | full_solution |
| 2   | TBD        | a two-perceiver composite               | TBD           | -                         | TBD    | full_solution |

- r2 candidate: "recolor bg to 0, then recolor the dominant remaining color" (design open)

### Top Rung (goal layer — no abstraction is minted here)

- TBD — needs a step over r2 that is independent (a second perceiver read or an independent recolor, not a geometry wrapper a group law could shorten)

### Sandwich check

- TBD (blocked on r2/top)

### Per-rung detail

#### r_1: recolor_bg

- Params:
  - `most_common_color(g)` (arg 1): derived → varies within-task (backgrounds differ across train examples)
  - `c`: free → fixed within-task, varied across demonstrating tasks
- Demonstrating tasks (>= 2, full_solution): E11-style — per-task target color, per-example background variation
- Collision risks: constant within-task background lets the literal `map_color(g, k, c)` coincide — the E11 trap; within-task bg variation is mandatory
- `involves_lambda`? no

### Heldout split

- TBD with the corpus (a few per level)

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- First ladder with **free-param rungs**: exercises the variation-plan machinery (background-within / target-across) *under climbing*, not just in a single LEARN run — the E11 corpus discipline inside a ladder.
- Deliberately sequenced after quad-symmetrize (param-free), so param effects are isolated from the fan-in question.

### Open problems

1. **r2 and the Top Rung are undesigned.** The chain-shaped r2 is needed to stay v1-eligible; the certified alternative `recolor_bg_flipped(g,c) = recolor_bg(rot180(g), c)` pulls in `rot180` as an independent sibling rung → the diamond/DAG shape, blocked on sibling-level `LadderSpec` support.
2. Does `least_common_color` earn its floor slot? It widens round-0 leaves (vocabulary tax) without being used by r1; it exists only to make a two-perceiver r2 expressible. If r2 doesn't use it, drop it.

### Dead ends / failed bisections

- (none yet)

### Notes

- r1 is the proven E11 abstraction (mintable; certified d=2).

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/<name>.py`): —
- Generator / committed testbed: —
- Generated artifacts (`spec.md` / `results.md` / `report.json`): —
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: —
