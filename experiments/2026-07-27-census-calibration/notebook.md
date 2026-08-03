# Calibrating the breadth census against measured cost (2026-07-27)

The standing gap from [2026-07-27-mve-batch-analysis](../2026-07-27-mve-batch-analysis/notebook.md): "the breadth census has never been calibrated against measured cost — the join in `idle_and_census.py` (A8b) returned nothing and was left unfixed when the defect took over."

It was meant to test an instrument's documented claim. It found that instrument reporting a **9.24x over-count in the one quantity it documents as EXACT**, on every floor carrying a variadic primitive — including the floor whose census reading is the batch's headline breadth finding.

Read-side plus short direct engine drives; no recorded runs, no ladder re-runs.

## What the census claims

`ladders/breadth.py`, verbatim: "Two **exact** quantities per rung … round-1 composition counts"; "**An indicator, never a prediction.** Round 1 is exact, and it UNDERSTATES badly, because the tax compounds with depth … Read these numbers to **RANK** floors and to compare a ladder against itself." LADDER-PROCESS §3 and MVE-PLAN's screen leg 3 both lean on it. Three testable claims: round-1 exactness, useful ranking, and a stated blind spot at depth.

## Precursor, and why it needed redoing

A first pass exists as [`census_calibration.py`](../2026-07-27-mve-completion/artifacts/census_calibration.py) (reported pooled Spearman 0.881). Four defects, all fixed here:

1. **Target mismatch.** It used `cost.jump_costs[rung]`, which SUMS `considered` over all of a rung's demo tasks, while `CheckContext.rung_breadth` prices only `targets[0]` — a census built on one task compared against a cost summed over n.
2. **Confounded correlation.** Pooling all rungs mixes BETWEEN-ladder variation (b1 spans 3 orders of magnitude — the "rank floors" claim) with WITHIN-ladder variation (b1 rises by exactly +1 per rung — the "compare a ladder against itself" claim). Separate claims, separate stakes.
3. **A degenerate predictor.** It printed `spearman(b1**depth, ...)` beside `spearman(b1, ...)` as if a comparison; every uncensored row is depth 2, so the two are equal _by construction_ (0.881 = 0.881).
4. **No pool variable** — and the batch contains a controlled pair that isolates it exactly.

## Log

### C1-C4 — the corrected join ([`census_join.py`](artifacts/census_join.py) · [`.out`](artifacts/census_join.out))

39 usable rung cells from 14 uncompromised ladders (compromised reports excluded: an early stop truncates cost-paid-full; censored cells excluded: a truncated cost calibrates nothing).

- **Ranking, decomposed.** BETWEEN ladders (median per ladder, the "rank floors" claim): Spearman **+0.966** (n=14). WITHIN a ladder: median **+1.000** (n=6 with >=3 rungs). Pooled: +0.803 — the confounded number, reported only to show what it hides.
- **The blind spot, isolated by a controlled pair.** `dae9d2b5-split-recolor` (pool 150) and `-split-recolor-lean` (pool 30) are the same ladder, same floor, same rungs, same depth schedule — so their census readings are **byte-identical**. Measured cost differs **19.0x - 25.6x**, rung by rung, entirely from `max_pool`. The census cannot see it, and no amount of round-1 accuracy would help.

### C5 — is the full forecaster the fix? ([`forecaster_backtest.py`](artifacts/forecaster_backtest.py) · [`.out`](artifacts/forecaster_backtest.out))

`execution/forecast_cost` _does_ model the pool (`_capped`), the new-layer restriction and survival, so the sharper question is whether the gap needs a new instrument at all. Backtested statically (DEFAULT_SURVIVAL, the mode a lint could use) on the same cells: **no**. Ranking **+0.455** vs the census's +0.803, and a systematic under-reader — median **0.20x** of measured, 18/39 within 2x. Its own docstring names the mechanism (saturation), confirmed in C6.

### C6 — the funnel, and the thing nobody was looking for ([`saturation_diagnosis.py`](artifacts/saturation_diagnosis.py) · [`.out`](artifacts/saturation_diagnosis.out))

Drove the real engine on the controlled pair's `west` cell and put its per-generation funnel beside the modelled rounds. Saturation was confirmed at round 2 (engine composed 11,988 at pool 30 and 230,346 at pool 150; the model 27 and 619). But the round-1 line was the finding:

|                               | round 1 composed |
| ----------------------------- | ---------------- |
| ENGINE                        | **131**          |
| census `b1_full` / forecaster | **1,211**        |

The quantity documented as exact was off by 9.24x, and both static instruments were wrong together — they share `round_terms`.

### C7 — isolating it ([`round1_exactness.py`](artifacts/round1_exactness.py) · [`.out`](artifacts/round1_exactness.out))

Per primitive over an identical 20-leaf census: `split_h` 1, `nth` 0, `map_color` 100, and **`overlay` 1,110** against the engine's 30.

`forecast_cost._slot_types` builds a variadic primitive's argument tuples by replicating `param_types[-1]` — the last DECLARED parameter. But the repeated tail type is declared in its own field, `Primitive.variadic_param`:

```python
OVERLAY = Primitive(name="overlay", param_types=(COLOR,), return_type=GRID, variadic_param=GRID)
```

So `overlay : (Color, Grid...) -> Grid` was modelled as composing **colour** tuples (10 + 10² + 10³ = 1,110) where the engine composes 3 arities x 10 colours x 1 grid = 30. The two coincide only when a variadic primitive's last fixed parameter happens to share the tail's type, which is why 21 of 42 cells were accidentally correct and the defect survived.

### C8 — the fix, verified against the engine ([`variadic_fix.py`](artifacts/variadic_fix.py) · [`.out`](artifacts/variadic_fix.out))

One line: read `variadic_param`. Verified by driving the engine at `depth_limit=1` with the pool raised so nothing truncates, on every uncompromised rung cell:

- **EXACT before: 21/42. EXACT after: 42/42.** Worst over-count 9.24x -> 1.00x.
- The 21 unaffected cells are **unmoved** — the fix is a correction, not a re-tuning.
- Affected: every `dae9d2b5` / NOR floor (`overlay`), 5.60x - 9.24x.

Shipped in `execution/forecast_cost.py` with a regression test pinning engine agreement AND the structural precondition (`overlay.param_types[-1] != overlay.variadic_param`), so the test fails if someone "simplifies" the fix back.

## Findings

1. **The census's exactness claim was false, and is now true.** Round-1 width was over-counted up to 9.24x on any floor with a variadic primitive taking a differently-typed fixed parameter first. Verified exact on 42/42 cells post-fix.
2. **`dae9d2b5-halves-union`'s headline breadth tax is 131x, not 1,211x** — the number quoted in LADDER-PROCESS, MVE-PLAN, `breadth.py`'s own docstring and ~20 generated `spec.md` files.
3. **The ranking claim holds, and is now measured rather than asserted**: +0.966 between ladders, +1.000 median within. This is the claim the instrument is actually used for (screen leg 3).
4. **The census is blind to `max_pool`, which is first-order** — 19-26x on a byte-identical reading. `b1` ranks floors; it can never be converted to an absolute cost.
5. **The full forecaster is not a drop-in replacement** — worse at ranking (+0.455), under-reads ~5x (median 0.20x), because `_capped` freezes the modelled census at `max_pool` and the new-layer restriction then makes deeper rounds structurally zero.
6. **Nothing the census DIAGNOSED moves.** Responsible primitives, wasted batteries, and the fat/lean floor separation are all unchanged; only magnitudes were wrong. The 2026-07-26 attribution of `dae9d2b5-halves-union` stands.

## What this changes

- `forecast_cost._slot_types` fixed; regression test added; `test_breadth.py`'s calibration case re-pinned to the exact engine-verified 131 (it asserted `> 1000` — a threshold that _encoded_ the defect, which is why no test caught it).
- The `spec.md` boilerplate is corrected at its source (`ladders/spec.py`) and now also states the measured ranking figure and the `max_pool` blindness; committed `spec.md` files carry the old text until each is regenerated.
- Dated corrections in LADDER-PROCESS §3 and MVE-PLAN screen leg 3.

## Open / handed forward

- **A pool-aware static predictor is the real gap.** Neither instrument forecasts absolute cost; the mechanism (round 2 composes over a pool-sized census, so cost ~ b1 + g(pool, library)) is measured in C4/C6 but not modelled. Fixing `_capped`'s saturation is the concrete lead: the modelled census stops GROWING while its CONTENT still turns over, so the new-layer term should be computed against what the pool now holds, not against its size.
- **Committed `spec.md` artifacts carry stale census numbers** until regenerated (mechanical, but it re-runs lint per ladder).
- **Depth is untested.** Every usable cell is depth 2 (the only depth-3 rows in the batch are al5's, all censored), so the "understates badly at depth" half of the claim is still uncalibrated — the ~40,000-fold gap on `halves-union` is one point, not a curve.

## Artifacts

Each script is paired with its captured output by matched basename.

| script | what it showed |
| --- | --- |
| [`census_join.py`](artifacts/census_join.py) · [`.out`](artifacts/census_join.out) | C1-C4 — corrected join; ranking +0.966 between / +1.000 within; the pool-blind controlled pair (19-26x) |
| [`forecaster_backtest.py`](artifacts/forecaster_backtest.py) · [`.out`](artifacts/forecaster_backtest.out) | C5 — the full forecaster ranks worse (+0.455) and under-reads (median 0.20x) |
| [`saturation_diagnosis.py`](artifacts/saturation_diagnosis.py) · [`.out`](artifacts/saturation_diagnosis.out) | C6 — engine funnel vs modelled rounds; saturation confirmed, and round 1 off by 9.24x |
| [`round1_exactness.py`](artifacts/round1_exactness.py) · [`.out`](artifacts/round1_exactness.out) | C7 — isolated to `overlay`: 1,110 modelled vs 30 composed |
| [`variadic_fix.py`](artifacts/variadic_fix.py) · [`.out`](artifacts/variadic_fix.out) | C8 — the one-line fix: 21/42 -> **42/42** exact, unaffected cells unmoved |

**Runs.** No recorded runs. C6/C7/C8 drive `search_engine.run` directly for diagnosis (the pattern the batch analysis's `pool_vs_top_reachability.py` established); the measured targets are read from committed `docs/abstraction_ladders/ladders/*/report.json`.
