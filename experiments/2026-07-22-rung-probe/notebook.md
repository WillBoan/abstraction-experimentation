# The rung probe — build + batch validation (2026-07-22)

**Goal.** Give ladder design a feedback loop whose unit is a *rung*, not a *ladder*. Before this, the only empirical answer came from `run_ladder` — a full LEARN climb plus the oracle chain, after the testbed and spec were already written. That economics produced the 2026-07-20 batch: 20 ladders built, 8 rejected, every rejection discovered at the end.

**Question.** Can the certificate's questions be asked rung-locally, at design time, cheaply enough to iterate — and if so, does the answer agree with what the recorded runs said?

## What was built

`src/arc_lab/program_search/ladders/probe.py` + `arc-lab probe-ladder`. Per rung `r_i`, under `L_{i-1}`, at the pinned budget, recording nothing:

| probe | question | verdicts |
| --- | --- | --- |
| wake | do the demos solve, and is what search RETAINS the intended program? | `as-intended` · `collapsed` · `collision` · `alternative` · `unsolved` · `censored` |
| skip | does anything one level up already solve from `L_{i-1}`? | `no-skip` · `skip-path` · `inconclusive` |
| sleep | fed what wake ACTUALLY retained, does governance mint the rung, at the right arity? | recovered/missed + arity |
| forecast | what does the cell cost? | `estimate_cost` static ceiling — *superseded the same day by the calibrated forecaster, below* |

This is the home of design-doc §6.4's **task-collision check** — the one planned check that could never live in `lint()`, because deciding it requires a search.

## The non-obvious ingredient: the probe grids

First implementation compared the retained program against the intended one on the **ladder's own** train/heldout grids. On al14's known collision (`-01` retains a program reading cell (0,2) to write (1,1)) it reported *no disagreement*. Investigating:

```
16 grids; cells (0,2) and (2,1) share a colour in 16 of them
example grid: [[4, 1, 3], [5, 2, 4], [1, 3, 5], [2, 4, 1]]
```

**al14's seed construction confounds those two cells in its entire grid population** — so the collision agrees with the intent everywhere in the corpus, *including on heldout*, since heldout comes from the same generator. This corrects the 2026-07-21 notebook's characterisation ("holds only because those cells share a colour in both examples"): it is not a two-example fluke, it is systemic, and no amount of extra tasks from that generator would expose it.

Fix: also compare on **deterministic position-separating grids** — three colour layouts per shape the ladder uses (`(r*w+c) % 10`, `(c*h+r) % 10`, `(r*7+c*3) % 10`), no RNG. Shapes come from the corpus so probes stay in the ladder's own input space. With them, al14 r1 separates cleanly:

- `move_cell_up-00` → **collapsed**: `set_cell(set_cell(input, 1, 0, 0), 0, 0, read(input, 1, 0))` — same function, depth 2 not 3.
- `move_cell_up-01` → **collision**: `set_cell(set_cell(input, 2, 1, 0), 1, 1, read(input, 0, 2))` — a *different* function that fits only the train support.

Sleep, fed those retained programs, mints `abs0` at **arity 5** against an intended 3 — the wrong abstraction the 2026-07-21 notebook derived by hand, now produced automatically. (The reference config's `considered_limit=50000` censors `-01` before it is found; the separation needs `--considered-limit 400000`, which is itself the notebook's "the guard was 3 orders too small" finding, reproduced.)

## Batch validation

`artifacts/probe_sweep.out` — every rung of all 20 ladders, ~100s total (vs the 245 recorded runs the 2026-07-20 certificate needed).

**The probe-clean set is exactly the certificate's admitted-with-full-recovery set:** al1, al2, al15, al16, al17, al18, al19, al20 (8/20, each ≤1s). The other 12 fail, and their findings restate their recorded verdicts with the programs printed:

| ladder | probe finds | matches the recorded verdict |
| --- | --- | --- |
| al3 | r3 collapse `quad(quad(input))`; skip path at top | "skip paths at r2, r3" |
| al7 / al9 / al11 | skip paths r3–r5: `stack2(stack2(input))`, `stack2(wide4(input))`, `stack2(tall4(input))` | "skip paths at r3, r4, r5" (al9/al11 inherit al7's spine) |
| al5 | skip paths at r1/r3, collisions, r1 collapse to `map_color(input, least_common_color(input), most_common_color(input))` | "skip paths at r1, r3; zero rung recovery" |
| al6 | skip paths r1–r3, r4 censored | "r4 intractable; skip paths at r1–r3" |
| al8 | skip paths at every rung, r1 collapses at depth 2 | "skip paths at every rung; not a ladder, kept as an ARM" |
| al13 | r1 skip path `overlay(0, flip_h(flip_v(input)), overlay(0, input, flip_h(input), flip_v(input)))`; r2 inconclusive; both mints missed | "skip path at r1; r2 inconclusive; zero recovery" |
| al10 | top reachable from `L_0` | rejected as designed ✓ |
| al12 | **clean wake, clean skip**, mint missed (one demo → nothing to antiunify) | "admitted; climb fails as designed" ✓ |
| al4 | collisions at r1/r2/r3 + skip paths | "r2 intractable; skip paths at r1, r3" |
| al14 | collapse + collision + arity-5 mint | (its 2026-07-20 certificate was fully censored — the probe is the first empirical verdict) |

Totals across the batch: **35 skip paths, 14 collapses, 9 collisions**.

**al12 is the sharpest validation.** The certificate deliberately separates "is this a ladder?" (admitted) from "did the loop climb it?" (recovery), and al12 is admitted with zero recovery. The probe reproduces exactly that split without being told about it: `wake_ok` and `skip_ok` pass, `mint_ok` fails. Read the three components separately, never just `ok`.

## Decisions / notes

- **The probe convicts; only the certificate acquits.** Clean rung-local probes do not imply admission — the climb pays each jump under a library inflated by earlier mints, and cross-rung interaction is invisible here. A dirty probe *is* proof of non-admission.
- Sleep is graded on what wake **retained**, never on the intended solutions. That is the only way al14's arity-5 mint appears: a collapsed wake feeds sleep the collapsed form.
- The forecast column uses `estimate_cost`'s worst-case ceiling and is loose by construction (al14: 6.4e13). The calibrated forecaster is the next instrument (AL-PLAN Phase 0 item 3).
- The probe grids are bounded by corpus shapes and three layouts — adversarial, not exhaustive. A collision only visible on shapes the ladder never uses is out of scope by design.

## Next

Forecaster (per-type censuses, new-layer factor, measured survival rates), backtested — so a cell's cost is known before it is paid. **Done the same day; see below.**

---

# The calibrated forecaster (same day)

**Goal.** The probe's fourth column was `estimate_cost`'s worst-case ceiling — honest but useless for planning (al14: 6.4e13). Replace it with a *prediction*, and do not trust it until it is backtested.

## The model

`execution/forecast_cost.py`, deliberately a sibling of `estimate_cost.py` rather than a replacement: a **ceiling** must never under-count, a **forecast** should be close. Three corrections over the ceiling, each mirroring what the engine does:

1. **Typed census** — the pool is bucketed by type, so `set_cell(Grid, Int, Int, Color)` costs `|grid| x |int| x |int| x |color|` (al14: 10,615 x 17 x 17 x 14 = 43M), not `pool**4` (1.6e13).
2. **New-layer restriction** — round `d` composes only tuples using an argument from the previous round: `PROD(census_d) - PROD(census_{d-1})` per primitive. This is `estimate_cost`'s own named "deliberate, unbuilt refinement".
3. **Measured survival** — next round's pool is what neither errored, nor was pruned, nor deduped. `survival_from(stats)` reads the rate per round off a real funnel.

## Backtest (`artifacts/forecast_backtest.py`, output `forecast_backtest.out`)

336 completed rounds across 54 rung cells; ground truth is the engine's own funnel (censored rounds excluded — a cut-short round is not a measurement).

| predictor | geomean predicted/actual | within 2x | worst |
| --- | --- | --- | --- |
| `ceiling` (`estimate_cost`) | **21.63x** | 60% | 1.22e9x over |
| `cold` (prior only) | **1.07x** | **97%** | 33.7x |
| `warm` (calibrated on first 2 rounds) | 1.17x | 92% | 95.1x |

Measured survival across the batch: **median 0.445**, mean 0.488 (n=265) — now `DEFAULT_SURVIVAL`.

**A bug the backtest caught.** The first run showed `cold=0` against actual 6,370 on al3 and al11. Cause: `int(count * rate)` truncated a small round's survivors to zero, which froze the census, which made the *next* round's new-layer term exactly zero — the forecast collapsed to 0 for every deeper round. Fixed by guaranteeing at least one survivor per composing primitive; `cold` went from 88% to **97%** within 2x. Worth stating plainly: without the backtest this would have shipped as confident arithmetic that silently returns zero on deep cells.

**A finding, not a bug.** `warm` is *worse* than `cold` at depth. Carrying an early survival rate forward over-predicts, because dedup rises with pool size — early rounds survive at ~1.0, late rounds far lower. So calibrating on the first two rounds and projecting is optimistic; the measured prior is better for deep projection. The probe therefore carries the *deepest* observed rate forward, and the docstring states the residual bias (over-stating cost — the safe direction for a budget).

## Wired into the probe

The probe's forecast column is now "what would one more round of depth cost here?", calibrated on the funnel the wake probe just produced, with the dominant factor named:

```
- one round deeper (depth_limit 3): ~159,752 considered, calibrated on this cell's funnel;
  dominated by concat_v: grid(397) x grid(397)
```

That is the deep-jump question priced per cell — and al17's answer (~160k considered for depth 3) is **affordable**, which is the first direct evidence for the plan's "the depth-2/3 ceiling was a design habit, never a measured limit" correction.

## Next

The frontier sweep (Phase 1): `cost_L(d)` tables over (floor x depth x arity x pool) on representative floors, using the forecaster to choose which cells to actually run.
