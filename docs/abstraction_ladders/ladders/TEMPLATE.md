# Ladder: <slug>

<!-- Copy to ladders/<slug>/worksheet.md and add a row in ../LADDERS.md. Terms per the design doc
     §2-§3; the Structure checks mirror the Ladder Linter.

     TWO PARTS, kept strictly apart:
       1. STRUCTURE — the machine-checkable facts. This file owns them ONLY while the ladder is
          docs-side. Once a LadderSpec + generator exist, DELETE Part 1 entirely: the generated
          `spec.md` beside this file owns structure from then on (and `results.md` + `report.json`
          own results, once run) — all three written by `arc-lab run-ladder <name> --artifacts`.
          Never restate a fact that lives in a generated artifact.
       2. NARRATIVE — rationale, open problems, dead ends, side notes. Never generated; hand-written;
          lives here for the ladder's whole life. -->

- **Status:** sketch
- **Artifacts:** spec: — · results: — <!-- link spec.md / results.md once generated -->

---

## Part 1 — Structure (delete once spec.md exists)

### Identity

- Anchor competence (the named capability the top tasks embody — chosen FIRST):
- Construction method: (1) anchored bisection | (2) forward extension

### Reference config

- Floor (`L_0`):
- Budget:
  - `depth_limit`:
  - `max_arity`:
  - `max_pool`:
- Engine options:
  - constant sources:
  - function-hole fill:
  - polymorphism:
- Learn:
  - proposer:
  - governance:
  - iterations:

### Rung spine

| i   | Rung | Template (over `L_{i-1}`) | `d_i` | Inlined double-jump depth | Fan-in | Demo kinds |
| --- | ---- | ------------------------- | ----- | ------------------------- | ------ | ---------- |
| 1   |      |                           |       |                           |        |            |

### Top Rung (goal layer — no abstraction is minted here)

- Anchor task(s), in words:
- Reference solution per top task (over `L_k`):
- `d_raw` per top task (unfolded to `L_0`):

### Sandwich check

<!-- leaf = 0; `depth_limit` = the inclusive depth cap (design doc §2). Compute depths by
     enumeration (the derivability probe / compositional_depth), never by hand. -->

- Every `d_i` <= pinned `depth_limit`, with headroom:
- Every inlined double-jump > pinned `depth_limit`:
- Every top `d_raw` > pinned `depth_limit`:
- Validity window (est., inclusive, `depth_limit` units):

### Per-rung detail

<!-- repeat per rung -->

#### r_1: <name>

- Params — classify each, with its variation plan:
  - `<param>`: derived → varies within-task | free → fixed within-task, varied across demonstrating tasks
- Demonstrating tasks (>= 2), each tagged with its kind vs THIS rung's abstraction (v1 default `full_solution`; fragment kinds require the matching proposer — design doc §2):
  - <task sketch: inputs, examples per task, which variation kills which shortcut>
- MDL break-even: <template size x demo count vs definition cost>
- Collision risks: <shallower programs that could coincide on all examples; how the tasks rule them out>
- `involves_lambda`? <if yes: depth checks advisory>

### Heldout split

- <which tasks per rung level are heldout>

---

## Part 2 — Narrative (permanent)

### Why this ladder / role in the batch

- <what phenomenon it tests; which family/arm it belongs to>

### Open problems

-

### Dead ends / failed bisections

<!-- The most durable part of this file. For each: the gap, the candidate mid-rungs tried, and
     whether each failed as NOT-LEARNABLE-FROM-BELOW or NOT-USEFUL-FOR-ABOVE. Log genuine findings
     to EXPERIMENTS.md as well. -->

-

### Notes

<!-- side observations, cross-references, history — anything that is neither structure nor a
     decision; keep it out of the sections above -->

-

### Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/<name>.py`): —
- Generator / committed testbed: —
- Generated artifacts (`spec.md` / `results.md` / `report.json`, beside this worksheet): —
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: —
