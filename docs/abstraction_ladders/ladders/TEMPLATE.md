# Ladder: <slug>

<!-- Copy to ladders/<slug>/worksheet.md and add a row in ../LADDERS.md. Terms per the design doc §2-§3; the checks below mirror the Ladder Linter (design doc §6; AL-machinery-plan). Once a LadderSpec + generator exist, THEY own the structure — the spine table is superseded by the committed `render()` artifact, and this file keeps only rationale, history, and dead ends. -->

- **Status:** sketch
- **Anchor competence:** <the named capability the top tasks embody — chosen FIRST>
- **Construction method:** <(1) anchored bisection | (2) forward extension>
- **Reference config:** <Floor (`L_0`) library · reference budget · learn params (proposer / governance / iterations)> — the anchor for every sandwich claim (design doc §3.1)
- **Validity window (est.):** <(lower, upper) in `max_depth` coords — computed + recorded by lint later>

## Top Rung (goal layer — no abstraction is minted here)

- Anchor task(s), in words:
- Reference solution sketch per top task (over `L_k`):
- `d_raw` per top task (unfolded to `L_0`):

## Rung spine (bridging rungs 1..k)

| i   | Rung | Template (over `L_{i-1}`) | `d_i` | Inlined double-jump depth | Fan-in | Demo kinds |
| --- | ---- | ------------------------- | ----- | ------------------------- | ------ | ---------- |
| 1   |      |                           |       |                           |        |            |

Sandwich check (leaf = 0; `max_generation = max_depth - 1`, design doc §2): every `d_i <=` reference `max_generation`, with headroom · every inlined double-jump `>` reference `max_generation` · every top `d_raw >` reference `max_generation`.

## Per-rung detail

### r_1: <name>

- Template:
- Params — classify each, with its variation plan:
  - `<param>`: derived → varies within-task | free → fixed within-task, varied across demonstrating tasks
- Demonstrating tasks (>= 2), each tagged with its kind vs THIS rung's abstraction (v1 default: `full_solution`; fragment kinds require the matching proposer — design doc §2):
  - <task sketch: inputs, examples per task, which variation kills which shortcut>
- MDL break-even: <template size x demo count vs definition cost>
- Collision risks: <shallower programs that could coincide on all examples; how the tasks rule them out>
- `involves_lambda`? <if yes: depth checks advisory>

<!-- repeat per rung -->

## Heldout split

- <which tasks per rung level are heldout>

## Open problems

-

## Failed bisections / dead ends

<!-- The most durable part of this file. For each: the gap, the candidate mid-rungs tried, and whether each failed as NOT-LEARNABLE-FROM-BELOW or NOT-USEFUL-FOR-ABOVE. Log genuine findings to EXPERIMENTS.md as well. -->

-

## Handoffs (fill in as they come to exist)

- `LadderSpec` (`ladders/registry/<name>.py`): —
- Generator / committed testbed: —
- `render()` artifact (committed beside this worksheet): —
- EXPERIMENT_QUEUE.md row: —
- Runs / EXPERIMENTS.md entries: —