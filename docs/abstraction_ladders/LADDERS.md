# Ladder register

One row per candidate Ladder for the Abstraction Ladder Experiments ([ABSTRACTION-LADDERS-2026-07-16.md](ABSTRACTION-LADDERS-2026-07-16.md) — the design doc; all terms per its §2). This is **state, not events**: rows advance status, get corrected, or get rejected — findings and run records never accumulate here (they go to `EXPERIMENTS.md` and the ladder's worksheet).

**Discipline:**

- **One folder per row** — `ladders/<name>/` holds the worksheet (`worksheet.md`, copied from [ladders/TEMPLATE.md](ladders/TEMPLATE.md)) plus the generated artifacts: `spec.md` (structure, from `LadderSpec.render()`), `results.md` + `report.json` (from the ladder report) — all written by `arc-lab run-ladder <name> --artifacts ladders/<name>/`. The worksheet holds design work and narrative; generated artifacts own structure and results; this file only indexes.
- **Names, not numbers.** Slug = the anchor competence (eg `count-markers-per-region`). E-numbers are minted at run time, in `EXPERIMENTS.md` — never here.
- **Source-of-truth handoff.** Once a ladder becomes code (`LadderSpec` + generator + testbed), the spec owns the structure — the worksheet keeps rationale + dead ends only. Sized-to-run → one EXPERIMENT_QUEUE.md row pointing at the worksheet. Run → EXPERIMENTS.md entry.
- **Rows persist after running** (a certified ladder + its testbed is a reusable asset). Delete a row only if the ladder is abandoned _and_ its worksheet records why.
- **Statuses:** `sketch` → `linted` (static checks pass) → `tasks-drafted` → `certified` (oracle-chain empirical checks pass) → `admitted` (in the batch) → `run`.
  - Terminal: `rejected` (reason in the worksheet; if the reason is itself a finding — eg a no-foothold gap — log it in `EXPERIMENTS.md` too).

| Ladder | Anchor competence | Floor | Height | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| [al1-mirror](ladders/al1-mirror/worksheet.md) | mirror-then-recolor composition | `{flip_h, flip_v, map_color}` | 3 | run | ADMITTED 2026-07-18 (EXPERIMENTS.md). Pure telescope — the shape-control arm. Considered-ratio still censored (raw calibration cell queued). Name predates the names-not-numbers rule; kept — the code registry + testbed own it. |
| [quad-symmetrize](ladders/quad-symmetrize/worksheet.md) | build the 4-fold symmetric completion | `{concat_h, concat_v, flip_h, flip_v}` | 3 | sketch | #1 pick for the next real ladder — first fan-in > 1 attempt. Probe-certified sandwich; OPEN: the r2 skip route (minimal witness is fan-in 1). |
| [mask-crop](ladders/mask-crop/worksheet.md) | normalize content position/extent | `MASK_MIN` (+ TBD) | 3 | sketch | Learned `Mask`-typed intermediate — construct AND consume. r2/top design open. |
| [perceiver-chain](ladders/perceiver-chain/worksheet.md) | recolor relative to perceived colors | `{map_color, most_common_color, least_common_color}` | 3 | sketch | Free-param rungs (variation plans under climbing); E11 discipline inside a ladder. r2/top design open. |
| [rot90-calibration](ladders/rot90-calibration/worksheet.md) | quarter-turn rotation (calibration instrument) | `{flip_h, transpose}` | 2 | sketch | Calibration arm: raw cost actually measurable (above-window cell) — anchors RQ1's considered-ratio. Retrofits the E1 testbed with a new goal layer. |
