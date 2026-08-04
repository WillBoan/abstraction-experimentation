# Filling the real-ARC gaps: two closed, three shown unfillable (2026-08-04)

A gap-filling session, not an exploration. The [batch of record](../2026-08-03-batch-of-record/notebook.md)
made the register traceable; this asked the next question — **which gaps in it can be closed by
running something we already have?** — enumerated the candidates, and ran all of them.

Two closed. Three turned out to be unfillable, and the reason is one measured fact that was not
known this morning: **a cell censors on the product of depth and pool, not on either alone.**

Cost of the day: **297,458,313 candidates considered, 74% of it censored** — more compute than the
program's entire prior history (289,304,962), for one free win and one confirmation.

## The candidates, and what happened

| | gap | outcome |
| --- | --- | --- |
| **A1** | `dae9d2b5` RQ1 anchored to a member outside its own comparable set | ✅ closed, **0 compute** |
| **A2** | `max_pool` 30 never validated on the NOR floor (inherited from `dae9d2b5`) | ✅ closed, confirms |
| **B** | `dae9d2b5-recolor-solo`, the 1-rung coarse endpoint, probed only at a 500k smoke guard | ❌ unfillable |
| **A3** | `dae9d2b5-halves-union`, the region-tier baseline, parked unrun | ❌ unfillable |
| **A4** | price what exhausting a censored cell would cost | dropped — answered three times over by the above |

## Log

### A1 — the RQ1 bound was anchored outside the set it describes

`dae9d2b5`'s published `>= 10x` comes from `split-recolor`, the `max_pool` 150 member — which is
excluded from every cross-member comparison precisely because pool is a cost-determining budget key.
So the cohort's headline amortization number was not on the same footing as the members it is quoted
alongside.

The raw arm frees `max_pool` to 200,000, so the raw search is pool-independent: the *same* recorded
arm re-anchored against the comparable 4-rung member is sound.

```
arc-lab run-ladder dae9d2b5-split-recolor-lean --raw-arm-k 10     # 1.0s
```

| | anchor member | laddered marginal | ratio |
| --- | --- | --- | --- |
| before | `split-recolor` (pool 150, excluded) | 2,500,789 | `>= 10.0x` |
| **after** | `split-recolor-lean` (pool 30, in-set) | 100,973 | **`>= 247.67x`** |

`reused_recorded_arm: true`, `sound: true`, spend 25,007,890 — all of it already paid. This is
`dominating_raw_arm()` doing exactly what it was built for: the recorded arm proves far more than
the `k` it was bought for.

### A2 — pool 30 on the NOR floor: validated, not inherited

`dae9d2b5` has a pool-calibration pair (150 -> 30, 32.9x cheaper at a byte-identical verdict). The
NOR cohorts had no such pair — they simply adopted 30. That is an assumption, and the register
could not tell you it was one.

```
arc-lab run-batch --only 94f9d214-nor-merged,fafffa47-nor-merged --set budget.max_pool=150 --no-raw-arms
```

| member | quantity | pool 30 | pool 150 | ratio |
| --- | --- | --- | --- | --- |
| `94f9d214-nor-merged` | to-first | 62,640 | 2,039,082 | **32.6x** |
| | exhaust | 144,085 | 4,280,529 | 29.7x |
| | loop overhead | 4.0011 | 4.1818 | |
| `fafffa47-nor-merged` | to-first | 70,698 | 2,039,198 | **28.8x** |
| | exhaust | 152,233 | 4,280,525 | 28.1x |
| | loop overhead | 4.0010 | 4.1818 | |

Both admitted, 5/5 rungs recovered, top reached in chain and climb at **both** pools. So the NOR
floor reproduces `dae9d2b5`'s pool result and pool 30 is a measured choice on this floor too.

**Unplanned, and the more interesting half.** At pool 30 the twins differ by **12.9%**
(62,640 vs 70,698); at pool 150 they differ by **4 candidates** (4,280,529 vs 4,280,525 at exhaust).
The twins are the same rule with a 3-colour vs 9-colour north palette, and the cohort-template claim
is that the second task's marginal cost is a constant. That gap was being read as a palette effect;
it is a **pool-starvation artefact**. Once the pool stops binding, the two tasks cost the same.

### B — the coarse endpoint, probed at the standard rather than the smoke guard

`dae9d2b5-recolor-solo` was excluded as "probe INCONCLUSIVE at a 500k smoke guard". Every other
INCONCLUSIVE member was probed *at* the cohort's 2M guard, so this one was excluded on a weaker
test than the rule requires. Re-probing at the standard is applying the rule, not chasing a verdict
with a bigger budget.

```
arc-lab probe-ladder dae9d2b5-recolor-solo --guard 2000000
```

Still INCONCLUSIVE: both wake probes censored at exactly 2,000,000, skip test inconclusive. The
exclusion stands, now on the same test as everything else.

The probe's own diagnostic is what makes this worth recording:

```
floor tax (recolored_west-00): pruned 21 vs full 2,000,000 = 95,238x [floor-too-broad]
  kept ['map_color', 'nth', 'split_h']; dropped ['overlay']
  full spend by primitive: __const__ 100.0%, map_color 100.0%, overlay 99.8%, split_h 5.6%, nth 5.6%
```

**The rung is sound; the floor is too broad.** Pruned, the cell costs 21 candidates. `overlay` is
the bill — and `overlay` is in the floor of *every* `dae9d2b5` and NOR member.

### A3 — the region-tier baseline is not measurable at its own guard

`dae9d2b5-halves-union` is the predecessor kept as the measured baseline: it names a half through
the region tier, and the `split_h` primitive is what removes that plumbing. LADDERS.md says the pair
"prices what the plumbing cost" — a price never actually paid.

Its first chain cell, at `depth_limit` 3 and derived pool 750, **censored at 150,000,000**
(5 tasks x its own 30M guard) with 4 of 5 tasks solved. Killed after that cell: each further cell
costs another ~150M to return the same non-answer.

The baseline can be recorded as a bound, not as a measurement. (LADDERS.md's 21,149,854 figure for
its rung 1 is a round-1 breadth census, a different quantity — but the direction is the one the whole
day showed.)

### The finding the three negatives share

All 34 search cells recorded today, grouped by the two budget knobs
([`pool_wall.py`](artifacts/pool_wall.py) · [`.out`](artifacts/pool_wall.out)):

| depth | pool | cells | censored | considered |
| --- | --- | --- | --- | --- |
| 2 | 30 | 7 | 0/7 | 81,995 .. 109,673 |
| 3 | 30 | 2 | 0/2 | 75,770 .. 98,592 |
| 2 | 150 | 18 | 0/18 | 2,923,962 .. 5,360,579 |
| **3** | **150** | 6 | **6/6** | 6,000,000 .. 18,000,000 |
| **3** | **750** | 1 | **1/1** | 150,000,000 |

Every censored cell stopped at **exactly** its guard.

Depth 3 is affordable (98k at pool 30). Pool 150 is affordable (5.4M at depth 2). **Depth 3 *and*
pool >= 150 is not affordable at any guard tried** — 6M, 8M, 10M, 14M, 18M and 150M all censor. Each
x5 pool step costs roughly 40x at fixed depth, so `pool_for_depth`'s `POOL_GROWTH_PER_ROUND = 5`
is what converts a depth-3 level into an unrunnable one.

This also retires a run from earlier the same day: an arm re-running the six `solution_limit = 1`
members exhaustively, to unify the register's accounting mode. All six of its depth-3 cells
censored. **The 2026-07-27 decision to add `solution_limit` was necessary, not a shortcut**, and the
accounting-mode gap is not closeable by re-running — it belongs with the censored ones.

### Machinery fix that fell out of it

The exhaustive arm could not be expressed at all: `--set budget.solution_limit=null` raised
`type mismatch: expected int, got None`. `_coerce` sees only a field's *current* value, so one
holding `1` looks like a plain `int` — meaning **`--set` could set any `Config` field except back to
`None`**, contradicting the module's own docstring. Fixed with `_admits_none`, which reads the
*declared* type; a required field still refuses. Pinned by a test.

## Findings

1. **`dae9d2b5`'s RQ1 is `>= 247.67x`, not `>= 10x`** — the bound was anchored to the one member
   excluded from the cohort's comparisons. No new compute; the recorded arm already proved it.
2. **Pool 30 is validated on the NOR floor** (28.8x-32.6x, byte-identical verdicts), and the 12.9%
   cost gap between the cohort twins is a **pool-starvation artefact**, not a palette effect — at
   pool 150 they differ by 4 candidates.
3. **A cell censors on depth x pool, not on either alone.** d3/pool30 costs 98k; d2/pool150 costs
   5.4M; d3/pool150 censors at every guard from 6M to 18M, and d3/pool750 at 150M.
4. **Three of the five gaps are bounded by floor breadth, not ladder structure.** The probe names
   the bill: pruning `overlay` takes a censoring cell from 2,000,000 to **21** considered.
5. **`--set` could not clear an optional `Config` field**, so no arm that removes a compromise was
   expressible. Fixed.

## Interpretation

The gap analysis that motivated the day assumed the remaining gaps were *unrun*. Most are
*unrunnable*, and for one reason that no amount of compute addresses: the cost wall is a property of
the **floor** and of `POOL_GROWTH_PER_ROUND`, not of the ladders. A ladder whose cut leaves a depth-3
residual jump is not expensive — it is unmeasurable at any budget this program will spend, and the
95,238x floor-tax figure says the leverage is in the floor rather than the guard.

Read against the register, that reframes what the granularity curves are. Their coarse ends are
missing on all three cohorts — `nor-halves` censored, `recolor-solo` inconclusive, `halves-union`
censored — and every one of those is a depth-3-or-worse residual. The curves are not partially
measured; they are measured exactly where the residual jump is depth 2, which is the regime where
cost is small. That is a sharper statement of the existing "cost is a step function in residual top-jump
depth" finding: the step is not steep, it is a cliff at the guard.

Methodologically the day repeats a pattern the last two notebooks both named, this time about my own
estimates. Three runs were launched with a stated cost expectation ("bounded by the 2M guard",
"moderate", "multi-hour") and two of the three were wrong by more than an order of magnitude, in the
same direction each time. The corrective was already available and unread: the store's own
depth/pool census, which takes seconds and is now committed as `pool_wall.py`.

## Next

1. **The gap table should be rewritten as unrunnable-vs-unauthored.** Of the five gap classes,
   four are closed by design or by cost; only "never authored" is addressable, and today predicts
   any authored cell with a depth-3 level hits the same wall — checkable by lint's breadth census
   before authoring, not after.
2. **`POOL_GROWTH_PER_ROUND = 5` is the untested lever**, and it is the one thing that would move
   the wall. It is in `Budget` -> `Config` -> `run_id`, so changing it re-baselines every cell in
   the repo — not an arm.
3. **Floor breadth is where the leverage is** (95,238x measured on one cell), and the register has
   no instrument for it beyond lint's round-1 breadth census.
4. Deliberately not done: nothing was written to the register. Both arms ran without `--artifacts`,
   so `BATCH-OF-RECORD` and every `report.json` are untouched.
