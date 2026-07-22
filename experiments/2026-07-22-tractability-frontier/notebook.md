# The tractability frontier — where is it actually? (2026-07-22)

**Goal.** Replace the ladder batch's depth folklore with a measurement.

Every ladder in the batch pins jump depth at 2 (al3/al4 at 4, al5/al6 at 3). The AL plan's first
correction says that convention was never measured: the `considered_limit=50000` guard that
produced the "intractable" verdicts arrived at the *end* of the 2026-07-20 batch, and al14's
diagnosis showed it was three orders of magnitude too small for the cell it killed. So: what does
enumerating to depth *d* actually cost, on real floors?

**Method.** For each floor, take one of its own tasks and run the real engine at
`depth_limit` 2..5, recording `considered`, wall-clock, and the forecaster's prediction for the
same cell. The engine calls `_enumerate` once for the whole `depth_limit` (there is no iterative
deepening), so the cost is depth-driven whether or not the task solves — this is `cost_L(d)`, not
cost-to-solution. Guard: 5M considered (~4 min at the measured throughput), `immediate` mode.

Four floors, chosen to span the axes the batch found mattered (arity and parameters, not depth):

| label | floor | why |
| --- | --- | --- |
| geometric | `concat_h, concat_v, flip_h, flip_v` (al7) | param-free, arity 2 — the cheapest shape |
| layout+params | `concat_v, translate, pad` (al17) | INT + COLOR parameters |
| colour | `flip_h, flip_v, map_color` (al1) | two COLOR params — the +282% vocabulary-tax shape |
| cell | `read, set_cell, sub` (al14) | arity 4 — the floor that "was intractable" |

Artifacts: `artifacts/frontier_sweep.py` (+`.out`), `artifacts/frontier_sweep_pool.py` (+`.out`).

## Result 1 — the sweep as first designed measured the wrong thing

`artifacts/frontier_sweep.out`, at each ladder's own `max_pool` (300-2000):

| floor | d=2 | d=3 | d=4 | d=5 |
| --- | --- | --- | --- | --- |
| geometric | 61 | 2,521 | 320,801 (4.6s) | 491,997 (7.1s) |
| layout+params | 3,587 | 170,627 (3.3s) | **170,627** | **170,627** |
| colour | 6,743 | 29,591 | 36,017 | **36,017** |
| cell | 143,467 (1.9s) | **5,000,000 — censored (269s)** | — | — |

The bolded repeats are the tell: those rounds composed **zero** candidates. Once `max_pool` binds
and nothing new survives dedup + eviction, the new-layer restriction makes every deeper round
empty — the search is not exploring, it is idling. So this table is mostly a measurement of **pool
starvation, not depth cost**, exactly as the design doc (§5.3) warns: "raising `depth_limit`
without raising `max_pool` measures pool starvation, not depth cost." Re-run with the pool freed.

## Result 2 — with the pool freed, the cost is real

`artifacts/frontier_sweep_pool.out`:

| floor | pool | d=2 | d=3 | d=4 | d=5 |
| --- | --- | --- | --- | --- | --- |
| geometric | 400 | 61 | 2,521 | 320,801 (4.8s) | 491,997 (7.3s) |
| geometric | 20,000 | 61 | 2,521 | 973,013 (14.3s) | **>5M censored (79s)** |
| layout+params | 400 | 3,587 | 170,627 (3.3s) | 170,627 *(saturated)* | 170,627 *(saturated)* |
| layout+params | 20,000 | 3,587 | 3,712,560 (63s) | **>5M censored (80s)** | — |
| colour | 400 | 6,743 | 39,791 | 46,217 | 46,217 *(saturated)* |
| colour | 20,000 | 6,743 | 191,057 (15s) | **aborted at >20 min** | — |

(The last cell was stopped after 20 minutes without reaching the guard. Under an `immediate`
guard its `considered` is predetermined — exactly 5,000,000, censored — so the only unmeasured
quantity was wall-clock, and ">20 min at ~4k candidates/s" is itself the frontier answer for that
cell. Recorded in the `.out` rather than left as a gap.)

**The finding: depth alone is not the cost driver — the `(depth x max_pool)` PAIR is.**

- At the batch's pool settings, depth 4-5 costs **seconds** on three of four floors. The
  depth-2 convention was never the binding constraint.
- But raising `depth_limit` alone buys almost nothing: the extra rounds are empty or near-empty
  because the frontier is truncated. Cheap *and* useless.
- Free the pool and the cost appears where it always was: layout+params goes from 170k at pool 400
  to **3.7M at pool 20,000** for the same depth 3 — a 22x swing from the pool knob alone, at
  fixed depth.
- The **cell floor is the genuine outlier**: depth 3 blew the 5M guard by itself (269s, censored),
  at the ladder's own small pool. Arity 4 x enumerated INT/COLOR constants, not depth.

This corroborates the batch's own cross-ladder reading (arity and parameters dominate depth) and
refines the AL plan's correction #1: the depth ceiling was indeed never measured, but the useful
knob is the pair, and "deep jumps" only mean something at a pool that can hold the frontier.

## Result 3 — where the forecaster holds, and where it does not

Predicted/actual from sweep 1's last column:

- **Exact pre-saturation**: geometric d=4 predicted **320,801** against an actual **320,801**
  (1.00x); layout+params 0.92-0.94x; geometric d=3 0.79x.
- **Degrades at saturation**: colour d=3..5 read 0.18x / 0.15x / 0.15x — the forecaster's census
  stops growing sooner than the engine's real pool does.
- **Over-predicts on the cell floor**: d=2 4.36x.

The failure mode is the approximation `forecast_cost`'s own docstring flags — `max_pool` modelled
as a proportional shrink across types where the engine cuts **cheapest-first**. It is a benign
direction (it under-predicts precisely where the true answer is "cheap and flat"), but the honest
statement is: **trust the forecaster in the growth regime, not at or past saturation.** The
backtest's 97%-within-2x was measured at the reference budgets, which sit in the growth regime.
*(Amended 2026-07-23: even that was too generous — the estimator-validation sweep found the
one-round-ahead projection 25x under on two of five floors at freed pools. The forecaster's
validated uses are attribution, saturation detection, and guard-setting; its cost numbers carry
wide error margins outside the narrow regime it was backtested in.)*

## Decisions

- Ladder budgets should be stated as a `(depth_limit, max_pool)` pair, and a jump described as
  "depth 3 at pool 20,000", never "depth 3" alone.
- A saturated round (composed == 0) should be surfaced by the probe: it means the cell is
  pool-starved and the depth setting is decorative. **Built 2026-07-22** (`probe.Saturation`,
  reported with the cell's *effective* depth; advisory, outside `ok` — starvation is a defect in
  what a cell measures, not in whether its jump is sound).
- The forecaster needs a saturation flag before it is used to price cells near the cap.
  **Built 2026-07-22** (`TaskForecast.saturated_at` + a flag naming the total as a lower bound).

One thing fell out of building the first of those, and it sharpens the finding above: al1's r1
probes clean at its reference depth of 2, but at `depth_limit` 5 its **top becomes reachable
straight from `L_0`** (`flip_h(flip_v(map_color(input, 1, 2)))`, depth 3) — the ladder stops being
a ladder. So depth is not a free design parameter even where it is cheap: raising it can open skip
paths, which is a *third* reason "just unlock deeper jumps" was never the move. Pinned as a test.

## Next

Micro-probe batteries (Phase 1 item 7): if-tax, constant-domain width, param count, arity trade —
single-factor attribution now that the (depth x pool) confound is understood and controlled.
