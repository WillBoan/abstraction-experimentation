# Micro-probe batteries — what actually makes a jump expensive? (2026-07-22)

**Goal.** Attribute jump cost to single factors, by construction rather than by inference.

The 2026-07-21 read-across ranked the factors by comparing ladders that differed in several ways
at once — the al4-proposer and shared-al5-floor confounds are the standing cautionary examples —
and the [frontier sweep](../2026-07-22-tractability-frontier/notebook.md) then showed that even a
clean two-factor sweep can measure the wrong thing (pool starvation reads as cheap depth). AL-PLAN
correction #4 is the response: *laws are reasoned, constants are measured; ladder batches validate,
micro-probes discover.* This is the discovery half.

**Method.** One task, one budget, one constant policy — held fixed — and exactly one factor moved
per cell. Two design choices make the numbers mean something:

- **The task is deliberately unsolvable from every floor here.** A solved search can stop early, so
  a cell that happened to solve would be cheap for a reason unrelated to the factor under test.
  Unsolvable means every cell pays the full depth: this is `cost_L(d)`, not cost-to-solution.
- **Every cell reports saturation and censoring**, using the instrument the frontier sweep's
  follow-up added. A saturated cell is measuring starvation and is excluded from comparison. No
  cell in any battery saturated.

Grids are 3x3, so `finite-enumerate` mints INT 0..3 (4 values) against COLOR 0..9 (10) — the two
type populations whose ratio does most of the work below. Pool 20,000, guard 2,000,000.

Artifacts: `artifacts/micro_probes.py` (+`.out`) — batteries A, A2, B, C, D;
`artifacts/hof_probe.py` (+`.out`) — battery E.

## Result 1 — the product law is not approximately right, it is exact

Round 1 is where the composition law is testable without survival entering: the pool is exactly the
round-0 leaves, so the prediction is arithmetic. Across **all 24 cells of batteries A/A2/B/C/D**,
`forecast_cost`'s predicted round-1 count equals the engine's actual count **exactly** — after two
bug fixes the batteries themselves produced (Result 5).

| floor | slots | predicted = actual |
| --- | --- | --- |
| base (3 unary) | `3 x grid(1)` | 3 |
| + `scale` | `+ grid(1) x int(4)` | 7 |
| + `translate` | `+ grid(1) x int(4) x int(4)` | 19 |
| + `set_cell` | `+ grid(1) x int(4) x int(4) x color(10)` | 163 |
| + `move_cell` | `+ grid(1) x int(4)^4` | 259 |

This matters beyond bookkeeping — but its scope needs stating precisely *(amended 2026-07-23 after
the estimator validation)*: what is computable from the floor's signature is the **round-1
composition count** and, more generally, each round's count *given its census*. Whole-cell cost is
that exact arithmetic times a survival term that is semantic (dedup = how many distinct functions
exist among the candidates), must be measured, and cannot be projected far: the one-round-ahead
projection ranged 0.04x–1.24x across floors. So the law supports *attribution and guards*, not
cost prediction — a rung's cost is known by running the cell, not by computing it.

## Result 2 — arity is not the driver; the product of type populations is

Battery A walks arity 1 -> 5 with one added GRID -> GRID primitive per cell. The naive reading
("cost grows with arity") fails outright at the top of the ladder:

| added primitive | arity | considered @ d=2 | @ d=3 |
| --- | --- | --- | --- |
| `identity` | 1 | 17 | 29 |
| `scale` | 2 | 47 | 131 |
| `translate` | 3 | 252 | 1,012 |
| `set_cell` | 4 | 15,174 | **632,944** |
| `move_cell` | 5 | 19,689 | **591,302** |

**Arity 4 costs MORE than arity 5** at depth 3. `set_cell` has a COLOR slot (10 members) where
`move_cell` has two extra INT ones (4 each): `1 x 4 x 4 x 10 = 160` against `1 x 4^4 = 256` at
round 1, and the composition of what survives reverses the order by depth 3.

Battery A2 pins arity at 3 and moves nothing but the slot types:

| added primitive | slots | considered @ d=2 | @ d=3 |
| --- | --- | --- | --- |
| `translate` | `int, int` | 252 | 1,012 |
| `pad` | `int, color` | 1,477 | 41,596 |
| `map_color` | `color, color` | 9,693 | **408,612** |

Identical arity, identical return bucket, **404x** apart at depth 3. The ratio at round 1 is exactly
`(10 x 10) / (4 x 4) = 6.25`, and depth compounds it. So the sentence "arity dominates depth" from
the 2026-07-21 read-across was directionally right for the wrong reason: what dominates is
`PROD(type populations)`, and arity is merely the *number of factors* in that product. A wide slot
costs more than an extra narrow one.

## Result 3 — the constant policy is a 19x lever, and the cheap option is not the narrow one

Battery B holds the library fixed (base + `translate`, two INT slots) and moves only the policy:

| constant source | leaves | considered @ d=2 | @ d=3 |
| --- | --- | --- | --- |
| none | 1 | 13 | 22 |
| `harvest-from-instance` | 2 | 22 | 34 |
| `finite-enumerate` | 5 | 252 | 1,012 |
| both | 6 (5 distinct) | 253 | 1,013 |

`harvest-from-instance` costs **1.5x** where `finite-enumerate` costs **46x**, on the same library
and the same task, because harvesting mints only the literals the grids actually contain (one, here)
while enumeration mints the whole typed range. Adding harvesting *on top of* enumeration is
near-free (253 vs 252) — its literals are already in the enumerated set and the pool dedupes them,
so only the duplicate leaf itself is paid for.

This is the factor that also drives **collapse**, which makes it the sharpest design lever in the
batch. The `constant-subterm` lint's severity rule is exactly "does the beating literal exist in
this ladder's own search?" — al14's literal collapse and al4/al5/al6's perceiver collapse are all
`finite-enumerate` findings, and al8 (which mints no constants) carries the same constancy at *warn*
tier because no literal beats it. So the same knob that costs 46x in tractability is the one
manufacturing the collapses. **Ladders wanting a parameterised rung should prefer
`harvest-from-instance`**: cheaper and less collapse-prone, at the price of a narrower reachable set.

## Result 4 — two arity-2 primitives beat one arity-3, for the same expressible set

Battery D spells the same function two ways: `translate(g, dx, dy)` against
`translate_v(translate_h(g, dx), dy)`. Both floors express every translation within depth 2.

| floor | considered @ d=2 | @ d=3 |
| --- | --- | --- |
| arity-3 `translate` | 252 | 1,012 |
| arity-2 `translate_h` + `translate_v` | **104** (0.41x) | **379** (0.37x) |

Splitting a 2-parameter primitive across two rounds is **~2.6x cheaper** than fusing it into one
round, because `2 x (1 x 4) = 8` beats `1 x 4 x 4 = 16` and the saving compounds. A concrete
ladder-design rule falls out: **decompose parameters across rungs, not into slots** — which is also
what makes the resulting abstraction lower-arity, and low arity is what the sleep probe grades.

## Result 5 — the batteries found two forecaster bugs, on floors no ladder builds

Both surfaced as a `r1 prediction MISSED` flag and were diagnosable from the arithmetic alone:

1. **Overlapping constant sources double-counted.** `('finite-enumerate', 'harvest-from-instance')`
   yields `3` twice; the pool dedupes it, the model did not. Predicted 28 against an actual 19.
   Fixed by counting *distinct* leaves for the census while keeping the *raw* yield for round 0's
   considered count — the engine genuinely considers both and pools one.
2. **BOOL-typed `if` branches were excluded.** `if : (bool, a, a) -> a` instantiates at `a = bool`
   like any other type, and the engine composes those; `_branch_term` skipped them. On a floor whose
   only non-grid leaves are the two BOOL literals, predicted 3 against an actual 7.

After both fixes: 24/24 cells exact. **The 336-round backtest is byte-identical before and after** —
neither floor exists anywhere in the 20-ladder batch. That is correction #4 earning its keep:
these were reachable only by building floors on purpose, and no amount of ladder-batch running
would have found them.

## Result 6 — the if-tax is small, and the HOF tax is entirely about one knob

**Conditionals** (battery C) cost 2.0x–7.1x at these pool sizes — real but modest, and quadratic in
the pool rather than a product term, so it grows faster than a primitive would with depth.

**Higher-order primitives** (battery E) are the meta-grouping with no prior data at all, and the
answer is not what the framing predicted:

| cell | @ d=2 | @ d=3 |
| --- | --- | --- |
| plumbing only (no HOF) | 47 | 107 |
| `map`/`fold` @ `none` | 47 (1.0x) | 107 (1.0x) |
| any HOF @ `point-free` | 68–70 (1.4x) | 140–142 (1.3x) |
| `map` @ `lambda-synthesis` | 68 (1.4x) | 140 (1.3x) |
| `filter` @ `lambda-synthesis` | 103 (2.2x) | 464 (4.3x) |
| `fold` @ `lambda-synthesis` | 981 (**20.9x**) | 26,801 (**250x**) |

- A HOF whose holes can never be filled costs **exactly nothing** — `@ none` is byte-identical to
  the control, not "enumerated and failed" as I had assumed when writing the harness. Corrected.
- `point-free` fill is cheap and flat (~1.3x) for all three.
- `lambda-synthesis` spans **1.0x to 250x depending on which HOF**, so "the HOF tax" is not one
  number.

And the finding with the most consequence for Phase 2's planned HOF floors:

> **`map @ lambda-synthesis` is silently a no-op under the default config.** `map`'s hole return
> type is a free type variable (`(a) -> b`), and `unpinned_type_var_mode='reject'` — the default in
> every preset — skips synthesis for exactly that shape. Confirmed by re-running with
> `eager_grounding_over_universe`: `map` moves 140 -> 625 at depth 3, while `filter` and `fold`
> (whose hole returns are pinned) do not move at all.

A ladder built on a `map` floor with `lambda-synthesis` set would get point-free fill only, and
nothing in the run record would say so.

## Decisions

- Ladder cost should be reasoned about as `PROD(type populations)` per slot, never as arity or
  depth. The probe's dominant-factor string already prints exactly this product; it is the number
  to design against.
- Prefer `harvest-from-instance` for parameterised rungs: ~30x cheaper than enumeration on the same
  floor, and it removes the literal that manufactures collapse.
- Prefer splitting parameters across rungs over widening a rung's arity: cheaper, and it mints a
  lower-arity abstraction.
- Phase 2's HOF-floor cells must set `unpinned_type_var_mode` deliberately, and any `map`-floor
  result under the default is evidence about point-free fill only.

## Next

- The `map` synthesis gap is a config trap, not a bug — but it deserves a probe-level warning
  ("this floor's HOF holes cannot be synthesised under this config"), which is a cheap addition to
  the rung probe's existing flags.
- Estimator validation (Phase 1 item 8) is now the only open Phase 1 item: a calibration ladder at
  `d_raw - depth_limit ~ 3-4` with raw actually run. al1's 78x-530x headline stays unsupported
  until it exists.
