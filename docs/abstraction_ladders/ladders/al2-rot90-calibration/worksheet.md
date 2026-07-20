# Ladder: al2-rot90-calibration

- **Status:** linted
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: quarter-turn rotation, as the batch's calibration instrument
- Construction method: (2) forward extension (retrofit of the `e1-rot90` testbed with a new goal layer)

### Reference config

- Floor (`L_0`): `{flip_h, transpose}`
- Budget:
  - `depth_limit`: 2 (candidate reference)
  - `max_arity`: 2
  - `max_pool`: TBD (small floor — generous is cheap)
- Engine options:
  - constant sources: none
  - function-hole fill: none
- Learn:
  - proposer: `AntiunifyPairs`
  - governance: `GreedyMDL`
  - iterations: 3+

### Rung spine

| i   | Rung  | Template (over `L_{i-1}`) | `d_i` | Inlined double-jump depth | Fan-in | Demo kinds    |
| --- | ----- | ------------------------- | ----- | ------------------------- | ------ | ------------- |
| 1   | rot90 | `flip_h(transpose(g))`    | 2     | - (k=1)                   | 0      | full_solution |

### Top Rung (goal layer — no abstraction is minted here)

- Candidate (probe-certified material): **rot180 tasks** — reference solution `rot90(rot90(g))`, d=2 over `L_1`; a self-composition top
- `d_raw`: 4 over `{flip_h, transpose}` (probe: rot180 is the *unique deepest* D4 member over this floor)

### Sandwich check

- Every `d_i` <= pinned `depth_limit`: 2 <= 2 — OK
- Top-skip (rot180 inlined to floor) > pinned `depth_limit`: 4 > 2 — OK
- Top `d_raw` > pinned `depth_limit`: 4 > 2 — OK
- Validity window (est.): [2, 3] — wider than AL1's
- Raw measurement cell: `depth_limit=4` in the budgets sweep (above-window ⇒ calibration/rung-necessity-probe arm, per the §7 rung-necessity resolution — a legitimate cell, not a ladder defect)

### Per-rung detail

#### r_1: rot90

- Params: none
- Demonstrating tasks (>= 2, full_solution): the existing `e1-rot90` tasks (non-square, asymmetric, size-varied — already shortcut-hardened)
- Collision risks: square/symmetric grids conflate D4 members — excluded by the existing generator's discipline; verify no depth-<=2 route to rot180 over `L_1` other than `rot90∘rot90` (the certificate checks this empirically anyway)
- `involves_lambda`? no

### Heldout split

- Reuse/extend the `e1-rot90` split; add heldout at the new top level

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- **Validation of the raw-cost estimator** — the batch's most load-bearing job. Since 2026-07-19 raw cost is *estimated by extrapolation* on every ladder (design doc §5.3), never measured: for a real ladder, running raw is intractable by construction. That estimator is now used everywhere and validated nowhere. This ladder is the one place where **both** numbers exist — 2 primitives, no constants, `d_raw`=4 → raw is genuinely cheap to measure — so it can answer: does the extrapolation match ground truth, and if not, by what factor does it need recalibrating?
- This is the **only** place we deliberately run raw. Everywhere else a deep raw cell is the wrong instrument.
- Also the `b_eff`-fitting substrate: per-generation funnels at several `depth_limit`s on a tiny floor, nearly free.
- ⚠ On the `depth_limit=4` cell, **raise `max_pool` enough that it does not bind** — otherwise it measures pool starvation, not depth cost, and may spuriously fail to solve. (AL1's floor already truncates 1,883 → 300 at its last round.)

### Open problems

1. Extend the `e1-rot90` testbed in place vs. mint a new `rot90-calibration` testbed reusing its generator functions? Likely the latter — `e1-rot90` feeds existing locks and should stay untouched.
2. Measure how far the `depth_limit=4` raw cell actually runs (2 primitives, no constants — should be cheap); if fast, add `max_pool` sweep cells for the eviction-regime read (§2.1) almost free.

### Dead ends / failed bisections

- (none yet)

### Notes

- Free design metaparameter (probe): FOUR interchangeable rung choices collapse rot180 d=4→2 (`rot90`/`rot270`/`flip_v`/`anti_transpose`) — a ready-made mini-family axis. `rot90` is the default (testbed exists).

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/<name>.py`): —
- Generator / committed testbed: — (predecessor: `testbeds/e1-rot90/` + its generator)
- Generated artifacts (`spec.md` / `results.md` / `report.json`): —
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: — (predecessor study: E1)
