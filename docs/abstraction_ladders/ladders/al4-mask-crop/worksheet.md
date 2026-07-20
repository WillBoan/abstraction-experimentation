# Ladder: mask-crop

- **Status:** sketch
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: normalize content position/extent (via a learned `Mask`-typed intermediate)
- Construction method: (2) forward extension

### Reference config

- Floor (`L_0`): `MASK_MIN` (`nonbg_mask`, `crop_to_mask`) + additions TBD by the r2 choice (`flip_h`/`transpose` for crop_flip; `map_color` + finite-enumerate if recolor joins)
- Budget: TBD with r2/top
- Engine options:
  - constant sources: none (± `finite-enumerate` if recolor joins)
  - function-hole fill: none
- Learn:
  - proposer: `AntiunifyPairs`
  - governance: `GreedyMDL`
  - iterations: 5

### Rung spine

| i   | Rung            | Template (over `L_{i-1}`)        | `d_i`         | Inlined double-jump depth | Fan-in | Demo kinds    |
| --- | --------------- | -------------------------------- | ------------- | ------------------------- | ------ | ------------- |
| 1   | crop_to_content | `crop_to_mask(g, nonbg_mask(g))` | 2 (certified) | TBD                       | 0      | full_solution |
| 2   | TBD             | compose on the normalized grid   | TBD           | -                         | TBD    | full_solution |

- r2 certified option: `crop_flip(g) = flip_h(crop_to_content(g))` — d=2 over `L_1`, raw d=3; needs `flip_h`/`transpose` on the floor

### Top Rung (goal layer — no abstraction is minted here)

- TBD — the main design gap. Candidate: crop-then-X with X independent of the mask domain

### Sandwich check

- TBD (blocked on r2/top). Note `crop_flip`'s raw d=3 is shallow — may not clear a useful window.

### Per-rung detail

#### r_1: crop_to_content

- Params: none (param-free; var-sharing — `g` used twice)
- Demonstrating tasks (>= 2, full_solution): content-off-center inputs with varying background margins; within-task margin variation kills fixed-crop shortcuts
- Collision risks: content touching the border makes crop a no-op — demos keep nonzero margins that VARY
- `involves_lambda`? no

### Heldout split

- TBD with the corpus (a few per level)

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- The deepest gap-climbing phenomenon on the docket: sleep must mint an abstraction that **constructs AND consumes a learned `Mask`-typed intermediate** — a type the Floor's Grid-to-Grid surface doesn't advertise.
- `crop_to_content` is already gifted in `MASK_BASIC`, so the gen/full contrast is ready-made.
- Running it drains the EXPERIMENT_QUEUE.md "learned intermediate type" row.

### Open problems

1. **r2 and the Top Rung are undesigned** — the blocking gap. A height-3 with genuinely intractable raw likely needs a third domain joined, which risks turning this into cross-domain-normalize (blocked on sibling-level `LadderSpec` support).
2. Whatever floor addition r2 needs (`flip_h` or `map_color`): re-run the derivability probe on the final floor before linting — additions can open shortcuts to lower rungs.

### Dead ends / failed bisections

- (none yet)

### Notes

- Probe route note: the minimal `crop_flip` witness *commutes* — `crop_to_content(flip_h(g))` — so task design must not assume operand order, and recovery grading must treat the two forms as behavioral equals.

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/<name>.py`): —
- Generator / committed testbed: —
- Generated artifacts (`spec.md` / `results.md` / `report.json`): —
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: —
