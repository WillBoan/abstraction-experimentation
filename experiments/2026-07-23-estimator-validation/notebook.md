# Does the RQ1 raw-cost estimator tell the truth? (2026-07-23)

**Goal.** Validate the extrapolated raw baseline that every ladder's headline RQ1 number rests on.

`ladders/report.py::_estimate_raw_cost` fits the per-round `composed` growth of the rounds a raw
search *did* complete and projects the missing `d_raw - depth_limit` rounds, returning a bracket
(geometric-mean ratio low, last-observed ratio high) with the stated claim **"the truth sits
between"**. That claim had never been checked, and al1's cited 78x-530x RQ1 headline depends on it
entirely. AL-PLAN Phase 1 item 8.

## Why the planned calibration ladder could not do this

The design doc's plan (§5.3) was a **calibration ladder** — height 2, tiny floor, raw cheap to
measure. al2-rot90-calibration was built for exactly that job, and it cannot do it:

```
al2 floor {flip_h, transpose}, measured:
  depth 2:  7 considered   composed = [1, 2, 4]
  depth 3: 11              composed = [1, 2, 4, 4]
  depth 4: 15              composed = [1, 2, 4, 4, 4]
  depth 5: 17              composed = [1, 2, 4, 4, 4, 2]
  depth 6: 17              composed = [1, 2, 4, 4, 4, 2, 0]
```

The floor generates the **8-element D4 group**. The composed counts are flat and the reachable
space is exhausted by depth 5. There is no growth regime, so there is nothing for a *growth fit*
to be right or wrong about — validating here would confirm nothing about the estimator's behaviour
on any ladder that matters. **al2 is retired as the calibration instrument.**

## What was run instead

One ladder at one point replaced by a sweep: four floors spanning the regimes the estimator is
actually asked to work in, and every depth gap it would be asked to bridge.

```
for each floor, for each observed depth L, for each d_raw in L+1 .. max:
    estimate from the L-run's completed rounds   vs   MEASURE the d_raw run outright
```

Pool freed to 200,000 (the estimator explicitly assumes a non-binding pool) with per-cell
saturation reporting, so no starved cell is scored — the frontier sweep's lesson, instrumented.
Guard 40M; a censored cell is not ground truth and is excluded. Two cells established the
measurable ceilings and were themselves censored: geometric depth 5 (670s) and layout+params depth
4 (693s).

The sweep also runs the head-to-head that became possible this week: the curve fit against
`execution/forecast_cost`, which is **structural** (typed census x the product law) rather than a
fit. Artifact: `artifacts/estimator_validation.py` (+`.out`).

## Result 1 — the bracket does not contain the truth

**2 of 10 cells.** The headline claim is false as stated.

| floor | observed | d_raw | measured | bracket | in bracket? |
| --- | --- | --- | --- | --- | --- |
| geometric | 2 | 3 | 2,521 | 480 – 845 | no (3-5x under) |
| geometric | 2 | 4 | 973,013 | 3,616 – 11,821 | no (**82-269x under**) |
| geometric | 3 | 4 | 973,013 | 35,729 – 110,585 | no (8.8-27x under) |
| layout+params | 2 | 3 | 3,712,560 | 57,394 – 220,345 | no (**17-65x under**) |
| colour (al1) | 2 | 3 | 191,057 | 169,512 – 437,693 | **YES** |
| d4-group | 2 | 3 | 11 | 15 – 15 | no (1.4x over) |
| d4-group | 2 | 4 | 15 | 31 – 31 | no (2.1x over) |
| d4-group | 2 | 5 | 17 | 63 – 63 | no (**3.7x over**) |
| d4-group | 3 | 4 | 15 | 15 – 17 | **YES** |
| d4-group | 3 | 5 | 17 | 19 – 27 | no (1.1-1.6x over) |

Three mechanisms, all visible:

- **Accelerating growth breaks both fits in the same direction.** The docstring assumed the low fit
  under-projects and the high fit over-projects, so the truth is between. But where primitives are
  binary and the pool is growing, each round takes a product of a larger pool — the growth *ratio
  itself rises*, so a ratio fitted on earlier rounds under-projects **both** ends. This is the
  regime every interesting ladder is in.
- **Finite spaces break it the other way.** Where the reachable function space is a group, growth is
  exponential only until exhaustion, and both fits over-project (up to 3.7x).
- **Error compounds per extrapolated round.** geometric at a 1-round gap: 0.19-0.34x. The same floor
  at a 2-round gap: **0.004-0.012x**. But it is not only gap size — at a 1-round gap the error still
  spans 0.015x (layout+params) to 1.4x (d4), so gap size alone does not bound it.

## Result 2 — the structural forecaster is tighter, but is not a drop-in replacement

| floor | observed → d_raw | curve fit / actual | forecast / actual |
| --- | --- | --- | --- |
| geometric | 2 → 3 | 0.19 – 0.34x | **1.24x** |
| geometric | 2 → 4 | 0.004 – 0.012x | **0.33x** |
| geometric | 3 → 4 | 0.037 – 0.114x | **0.33x** |
| layout+params | 2 → 3 | 0.015 – 0.059x | 0.04x |
| colour (al1) | 2 → 3 | **0.89 – 2.29x** | 0.04x |
| d4-group (5 cells) | — | 1.1 – 3.7x over | **1.00 – 1.12x** |

Aggregate over the 10 scorable cells: curve fit spans **0.004x to 3.71x** (~900x spread);
forecaster **0.04x to 1.24x** (~30x spread), median 1.00x.

So the forecaster is roughly an order of magnitude tighter in the worst case and never
over-predicts by more than 1.24x — but it is **25x under on two cells, one of which is al1's own
floor**, the exact ladder whose headline is at stake. Swapping it in would fix the geometric and
d4 cells and make al1's worse. **Neither method is trustworthy enough to be called a measurement.**

## The consequence for RQ1

An RQ1 ratio is `raw_cost / laddered_cost`, and the numerator carries a multiplicative error of
somewhere between **0.004x and 3.7x** with no way to tell which from the outside. So:

> **RQ1 ratios as currently computed are uncertain by roughly three orders of magnitude, in an
> unknown direction.** al1's 78x-530x is not merely unvalidated — it is produced by a method that
> happened to bracket correctly on al1's own floor and is wrong by up to 269x on others.

The direction is not even consistently conservative, so "the true saving is at least N" is also
unavailable.

## What changed in code

Deliberately minimal — this measurement condemns one method without blessing the other, so nothing
was swapped:

- `_estimate_raw_cost`'s docstring carries a `.. warning::` recording that "the truth sits between"
  is measured-false (2/10), with the three mechanisms and the head-to-head numbers.
- The returned `caveats` — which ship inside every ladder report — now state the measured
  unreliability rather than the old "order-of-magnitude, not a measurement; validate on a
  calibration ladder" (that validation has now happened, and the answer is worse than the caveat
  implied). A `validated` field carries the date and the hit rate.
- A test pins the caveats, so a future consumer cannot read the bracket as containment without
  tripping it.

## Decisions and open questions

- **al2 is retired as the calibration ladder** — a finite-group floor cannot validate a growth fit.
  Anything replacing it needs a floor that genuinely grows *and* a `d_raw` that is measurable; the
  geometric floor is the one that fits (measurable to depth 4, >40M at depth 5).
- **RQ1 needs a decision, not a better fit.** Three options, none free:
  1. **Report RQ1 as a floor with a measured error band** and stop quoting point ratios.
  2. **Redefine RQ1 on measurable ground** — e.g. marginal rung value (cost of layer *i* under
     `L_{i-1}` vs under `L_i`), which is measured on both sides and needs no extrapolation at all.
     The report already computes this.
  3. **Keep extrapolating but only at a 1-round gap**, refusing to report beyond it. Costly: it
     forces `depth_limit = d_raw - 1`, which the frontier sweep says is affordable more often than
     the batch assumed.
  Option 2 looks strongest — it replaces an extrapolated number with a measured one — but it changes
  what the AL program claims, so it is a research decision rather than an engineering one.

## Next

- Take the RQ1 decision above, then re-derive the batch's headline numbers under it.
- If extrapolation survives in any form, the forecaster's two 0.04x cells are worth diagnosing:
  both are floors where the modelled census growth (`survivors = composed x rate`) lags the engine's
  real pool growth, which is a fixable modelling gap rather than an inherent limit.

## Addendum (2026-07-23) — decision taken

Recorded in [AL-PLAN-2026-07-23.md](../../docs/abstraction_ladders/AL-PLAN-2026-07-23.md). The
choice is none of the notebook's options 1–3 verbatim but the measured/bounded split option 2
gestured at, made concrete:

> RQ1 = `raw / (laddered + learning)` (design doc §4 — raw in the numerator, so > 1 means the
> ladder won). Run the raw arm deliberately (depth toward `d_raw`, pool freed, saturation-checked)
> with guard = **K x the measured laddered cost**. Solve ⇒ a *measured* ratio (<= K); censor ⇒ a
> *proven bound*: ratio >= K. Every bound reported with its `(depth, pool, spend)` conditions.

The extrapolated bracket is retired from results (advisory only, carrying its 2/10 caveats).
Estimation research is deferred, not abandoned — but nothing may depend on an estimator that has
not survived a validation of this kind. This session also corrected the framing this notebook's
sibling documents carried: prediction of rung cost without running it, and `b_eff` from early
rounds, failed for the same root reason raw extrapolation did (the survival/dedup term is semantic
and does not hold still), and the docs now say so plainly rather than scoping it as "reliable
within a regime".
