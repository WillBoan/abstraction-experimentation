# Ladder: al1-mirror

<!-- Post-handoff worksheet: structure lives in the generated spec.md, results in results.md /
     report.json (all three written by `arc-lab run-ladder al1-mirror --artifacts`). This file is
     Narrative only — rationale, open problems, dead ends. -->

- **Status:** run (ADMITTED 2026-07-18)
- **Artifacts:** [spec.md](spec.md) · [results.md](results.md) · [report.json](report.json)

## Why this ladder / role in the batch

- **Machinery shakedown.** The rungs reuse E12's proven-mintable abstractions, so the ladder exercised the new machinery (oracle chain, certificate, climb trace, amortization accounting) with known-good learning material — what was under test was the harness, not the learning.
- **The shape-control arm.** It is a pure telescope (fan-in 1 throughout; the `not-all-telescope` lint warning is by design). Fan-in > 1 phenomena are deliberately absent — that is quad-symmetrize's job.
- It realizes the `e12-layered-retrofit` idea from LADDER-IDEAS (same floor and rung pair, plus the goal layer).

## Open problems

- **The amortization ratio is an ESTIMATE (78x–530x), not a measurement — and that is the method, not a shortfall.** Raw is unreachable at the pinned budget by construction (`d_raw`=4 > `depth_limit`=2), so the measured Floor number (6,743) is a failed full-budget search, not a raw cost. Rather than run it deeper — which does not scale, since any ladder worth building has an intractable raw search — raw is extrapolated from the completed rounds (design doc §5.3, `_estimate_raw_cost`): composed [11, 102, 6630] projected 2 rounds at 24.55x–65x growth → 4.2M–28.4M. The bracket is method uncertainty. Open: the estimator is unvalidated — `rot90-calibration` is queued to check it against a measurable ground truth.
- **Cost-paid-full can't show rung value on this ladder.** With no early stop every search enumerates the whole budgeted space, and since every task here is a 2x3 grid the cost matrix columns are near-constant (L_0 6,743 / L_1 6,912 / L_2 26,401 for every task). The marginal-rung-value ratios computed in that currency (0.98x, 0.26x) therefore measure vocabulary tax, not rung benefit. Read cost-to-first instead (laddered marginal 8,372 vs 53,711 paid-full) and treat enablement as the primary rung-value signal here. A real speedup ratio needs either early stop or the uncensored calibration cell.
- Only 1 top task in train (+1 heldout) — thin for per-task variance at the goal layer; widen if AL1 becomes a family baseline.
- **Still not computed** (see results.md "Not computed here"): the break-even horizon (needs the heldout transfer run's per-task costs read against learning overhead — the runs exist, the view doesn't) and the sleep→wake cost conversion (needs the batch-level calibration weight `w`, which is a per-batch declaration that doesn't exist yet). Vocabulary tax, enablement, `b_eff`, marginal rung value and the loop-overhead factor are now computed and in results.md.

## Dead ends / failed bisections

- **Top design #1 rejected by the certificate (the D4 algebraic collapse).** `flip_v(mirror_recolor(g,a,b))` collapses via `flip_v ∘ rot180 = flip_h` to a 2-application program over the Floor — the "intractable" raw top was solvable at L0, and the certificate correctly returned `no_skip_paths[2]=False`. The static lint cannot see this (it depths the *intended* solution; the collapse is behavioral). Fix: a second **independent** recolor as the top, which no group law shortens. Lesson: algebraically closed floors invite skip paths; the lint + certificate split is load-bearing. Logged in EXPERIMENTS.md 2026-07-18.

## Notes

- The name predates the register's names-not-numbers rule; kept because the code registry and committed testbed own it.

## Handoffs

- `LadderSpec`: `src/arc_lab/program_search/ladders/registry/al1_mirror.py` (registry key `al1-mirror`)
- Generator / committed testbed: `taskgen/generators.py::al1_mirror_tasks` → `testbeds/al1-mirror/`
- Generated artifacts: [spec.md](spec.md) · [results.md](results.md) · [report.json](report.json)
- EXPERIMENT_QUEUE.md row: "al1-mirror raw-cost calibration" (added 2026-07-19)
- Runs / EXPERIMENTS.md entries: 2026-07-18 — machinery built + AL1 admitted (regression lock: `tests/program_search/ladders/test_run.py`)
