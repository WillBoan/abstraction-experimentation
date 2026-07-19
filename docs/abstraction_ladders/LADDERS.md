# Ladder register

One row per candidate Ladder for the Abstraction Ladder Experiments ([ABSTRACTION-LADDERS-2026-07-16.md](ABSTRACTION-LADDERS-2026-07-16.md) — the design doc; all terms per its §2). This is **state, not events**: rows advance status, get corrected, or get rejected — findings and run records never accumulate here (they go to `EXPERIMENTS.md` and the ladder's worksheet).

**Discipline:**

- **One folder per row** — `ladders/<name>/` holds the worksheet (`worksheet.md`, copied from [ladders/TEMPLATE.md](ladders/TEMPLATE.md)) plus generated artifacts (the committed `LadderSpec.render()` output, notes). The worksheet is where the design work happens; this file only indexes it.
- **Names, not numbers.** Slug = the anchor competence (eg `count-markers-per-region`). E-numbers are minted at run time, in `EXPERIMENTS.md` — never here.
- **Source-of-truth handoff.** Once a ladder becomes code (`LadderSpec` + generator + testbed), the spec owns the structure — the worksheet keeps rationale + dead ends only. Sized-to-run → one EXPERIMENT_QUEUE.md row pointing at the worksheet. Run → EXPERIMENTS.md entry.
- **Rows persist after running** (a certified ladder + its testbed is a reusable asset). Delete a row only if the ladder is abandoned _and_ its worksheet records why.
- **Statuses:** `sketch` → `linted` (static checks pass) → `tasks-drafted` → `certified` (oracle-chain empirical checks pass) → `admitted` (in the batch) → `run`.
  - Terminal: `rejected` (reason in the worksheet; if the reason is itself a finding — eg a no-foothold gap — log it in `EXPERIMENTS.md` too).

| Ladder       | Anchor competence | Floor | Height | Status | Notes |
| ------------ | ----------------- | ----- | ------ | ------ | ----- |
| _(none yet)_ |                   |       |        |        |       |
