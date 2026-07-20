# Ladder: quad-symmetrize

- **Status:** sketch
- **Artifacts:** spec: — · results: —

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence: build the 4-fold symmetric completion
- Construction method: (2) forward extension

### Reference config

- Floor (`L_0`): `{concat_h, concat_v, flip_h, flip_v}`
- Budget:
  - `depth_limit`: 3 (candidate)
  - `max_arity`: 2
  - `max_pool`: TBD
- Engine options:
  - constant sources: none
  - function-hole fill: none
  - polymorphism: monomorphize
- Learn:
  - proposer: `AntiunifyPairs` (all demos full-solution)
  - governance: `GreedyMDL`
  - iterations: 5

### Rung spine

| i   | Rung            | Template (over `L_{i-1}`)                             | `d_i` | Inlined double-jump depth | Fan-in       | Demo kinds    |
| --- | --------------- | ----------------------------------------------------- | ----- | ------------------------- | ------------ | ------------- |
| 1   | mirror_pair     | `concat_h(g, flip_h(g))`                              | 2     | 4 (est.)                  | 0            | full_solution |
| 2   | quad_symmetrize | `concat_v(r1(g), flip_v(r1(g)))` — see open problem 1 | 3     | -                         | 2 (intended) | full_solution |

### Top Rung (goal layer — no abstraction is minted here)

- Anchor task(s), in words: apply the full 4-fold symmetrization, then one more independent step
- Reference solution (probe-certified option): `quad2 = r2(r2(g))` — self-composition, d=2 over `L_2`
- `d_raw` per top task: compute by `unfold_program` once specced (probe: raw quad already censored > tree-size 6)

### Sandwich check

- Every `d_i` <= pinned `depth_limit`: jumps 2, 3 <= 3 — OK, no headroom on r2
- Every inlined double-jump > pinned `depth_limit`: 4 > 3 — OK (probe-certified)
- Every top `d_raw` > pinned `depth_limit`: expected OK (probe: censored); recompute in `depth_limit` units
- Validity window (est.): [3, 3] — minimum width, like AL1's

### Per-rung detail

#### r_1: mirror_pair

- Params: none (param-free; var-sharing — `g` used twice)
- Demonstrating tasks (>= 2, full_solution): mirror-completion tasks on h-asymmetric inputs; within-task shape/content variation kills literal shortcuts
- MDL break-even: template size 3, 2+ demos — comfortably positive
- Collision risks: h-symmetric inputs or repeated columns make `concat_h(g,g)` / bare `flip_h` coincide — demos must be h-asymmetric with distinct columns
- `involves_lambda`? no

#### r_2: quad_symmetrize

- Params: none
- Demonstrating tasks (>= 2, full_solution): 4-fold-completion tasks; asymmetry discipline on both axes
- MDL break-even: positive if the minted form is size 3-4 with 2+ demos
- Collision risks: **the skip route — see open problem 1**
- `involves_lambda`? no

### Heldout split

- A few per level: 1 mirror_pair, 1 quad, 1 top (AL1's 1-per-level pattern or slightly wider)

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- The #1 pick for the next real ladder: first attempt to leave the pure-telescope regime (fan-in > 1 at r2), with real size-compounding in the inlined form.
- Family potential: +frame/recolor rung → height 4; deeper r1 motif → jump-depth variant; its certified top (`quad2`) doubles as the first rung of the self-composition-telescope family.

### Open problems

1. **The r2 skip route (blocking).** Probe-certified: the *minimal* r2 witness is `mirror_pair(concat_v(g, flip_v(g)))` — fan-in **1**, tree-size 3 vs the intended 4. Cheapest-wins retention keeps that form, so the fan-in-2 claim does not survive minimality (structural sibling of the E11 literal trap). Resolutions to pick before promoting to `linted`:
   1. accept the telescope-form mint (but then this ladder loses its distinguishing role vs AL1);
   2. find a target whose minimal form is genuinely fan-in > 1 (break the commutation — e.g. the two r1 uses act on different deriveds);
   3. redesign the floor so the commuted form costs more.
2. Verify `quad2` top inputs against the ARC 30-cap (grid-doubling saturates fast).
3. The probe's numbers are tree-application counts, not nesting depth — recompute everything via `compositional_depth` before pinning the reference budget.

### Dead ends / failed bisections

- (pre-adoption, probe 2026-07-17) The intended size-4 quad template is shadowed by the size-3 commuted form — designer-computed jump depths were wrong; only enumeration caught it. See EXPERIMENTS.md 2026-07-17.

### Notes

- Certified material from the derivability probe ([experiments/2026-07-17-derivability-dag/](../../../../experiments/2026-07-17-derivability-dag/)): jumps 2/3 confirmed; `quad2` d=2 over L2 while censored (> tree-size 6) over L1 — the double-jump holds with room.

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/<name>.py`): —
- Generator / committed testbed: —
- Generated artifacts (`spec.md` / `results.md` / `report.json`): —
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: —
