# Reading all 18 ladder reports — and what it retracted (2026-07-27)

The first cross-cutting analysis of the committed ladder reports. It was meant to produce the MVE's
quantitative core; it instead found a defect that invalidates part of it, and then a second defect
introduced by the fix.

Companion investigation (what built the ladders):
[2026-07-27-mve-ladder-cohorts](../2026-07-27-mve-ladder-cohorts/notebook.md).

## Goal

MVE-PLAN names the quantitative core as read-side and already-computed: "marginal rung value per
rung, the granularity curve, the loop-overhead factor, and recovery / junk / cascade per member."
We had produced the atoms (18 `report.json`) and never analysed them — every number quoted so far
was scraped from a `results.md` headline.

## Setup

`artifacts/load.py` loads every committed `docs/abstraction_ladders/ladders/*/report.json` and
labels each real (the 8 new MVE members) or synthetic (al1–al21). Each report carries `certificate`,
`climb_trace`, `cost_matrix` (task x library), `rung_recovery`, `shape`, a 17-key `cost` block, and
a `comparisons` block (`enablement`, `loop_overhead_factor`, per-rung `marginal_rung_value`).

## Log

### A1 — marginal rung value  ([`marginal.py`](artifacts/marginal.py))
46 rungs. Median **1.22x**, range 1.00x–1987.94x; **57% worth under 2x**. The report's own legend is
explicit that `own_tasks_speedup` (cost-to-first) is "the honest measure" and the layer-above ratio
is NOT a speedup — checked before using it, which is why the ratio column is not reported here.

Also **budget-dependent**: the same rung reads 1988x at pool 150 and 56x at pool 30.

### A2 — is value predicted by POSITION?  ([`structure.py`](artifacts/structure.py))
Medians separate strongly (top-fed 21.64x vs rung-fed 1.05x) but the bands **overlap** — best
rung-fed 31.10x beats the worst top-fed 1.00x. Position is not the driver.

### A3 — is it predicted by CONSTANT BINDING?  ([`constants.py`](artifacts/constants.py))
Better: rungs binding a large-battery constant (colour / offset / coord) median **34.61x** vs
structural rungs median **1.07x** — a 32x gap in medians. Still **overlapping** at both ends
(`pair` binds an offset and is worth 1.03x; `shift2` binds none and is worth 52x). A predictor, not
a law. The cleanest framing: a rung is worth roughly what its own step costs to REDISCOVER, and a
big constant battery is the commonest reason that is expensive.

### A4–A7 — aggregates  ([`aggregate.py`](artifacts/aggregate.py))
Loop overhead appeared to rise with rung count (1: 2.22x, 2: 2.78x, 3: 3.34x, 4: 3.41x); real vs
synthetic looked similar (2.85x vs 3.05x); **43/43 rungs recovered, 0 junk mints**.

*(The first two are retracted below. Only the third survived.)*

### A8 — the defect  ([`idle_and_census.py`](artifacts/idle_and_census.py))
Chasing "which rungs bought neither speed nor reachability" led into `cost_matrix`, and there:

**Six of the eight new real-task ladders never solve their TOP task** — `solved=False`,
**`censored=False`** at the full oracle library `L_k`. The search ran to EXHAUSTION and the top is
not there. Every synthetic ladder solves its top, so this was specific to the new set.

**Cause, measured** (`94f9d214-nor-recolor`'s top at `L_4`, depth 3): pool 30 -> unsolved (23,754
exhaustive) · pool 60 -> unsolved (702,470 exhaustive) · **pool 150 -> SOLVED**, `first_solution_index`
473,987. Reproduced on `dae9d2b5-split-halves-lean`. A depth-3 search must retain its depth-2
intermediates to compose them; a 30-entry pool evicts them.

**My error:** the pool calibration was validated on `dae9d2b5-split-recolor`, whose schedule is
all-depth-2, and then applied to ladders whose schedules end in a 3. Every broken member has a `3`
in its schedule; both intact ones do not. I never named "all-d2" as a precondition.

**The machinery gap is separate and worth its own fix:** admission is `tractable_jumps` +
`no_skip_paths`, both statements about RUNGS. A ladder can be ADMITTED, recover every rung, score
health 1.0, and be unable to reach its own goal at its own budget — with no check and no report line
saying so. `top-affordable-with-ladder` passes because it reasons about DEPTH and does not model
`max_pool`. The datum sits in `cost_matrix`; nothing surfaces it.

**A caution recorded because it nearly became a false finding:** the first reading of A8a was "8
rungs bought neither speed nor reachability". Checking `enablement`'s semantics before reporting
showed it indexes rung levels only, so the conclusion was ambiguous — and pursuing that ambiguity is
what led to the real defect. Do not report an `enablement`-based claim without checking what the
dict covers.

### The fix, and its cost split
Priorities were set from a measured cost split rather than intuition:

| | chain | climb | raw arm |
| --- | --- | --- | --- |
| `dae9d2b5-split-recolor-lean` | 504,935 (61%) | 302,961 (37%) | 20,077 (2%) |
| `94f9d214-nor-recolor` | 634,250 (57%) | 465,928 (42%) | 13,139 (1%) |

This **retracted an earlier claim** that the raw arm was 76% of a run — true at pool 150, but only
1–2% at the lean settings these ladders use, because its guard is `K x laddered marginal`. Cutting
`K` had been mis-ranked as a major lever; it is not.

`solution_limit` had also been dismissed too fast ("saves nothing — every cell solves in its last
generation"). That reasoned about *generations* without looking at *indices*. The option is right;
the default **mode** neutralises it:

| cell | config | considered | first_idx |
| --- | --- | --- | --- |
| `94f9d214` top (d3, pool 150) | exhaustive | 9,242,001 | 473,987 |
| same | `limit=1`, `generation-end` | 9,242,001 | 473,987 |
| same | `limit=1`, **`immediate`** | **473,988** | 473,987 |
| `dae9d2b5` top (d2, pool 30) | exhaustive | 20,125 | 320 |
| same | `limit=1`, **`immediate`** | **321** | 320 |

Shipped: **per-level `max_pool`** (`run.py::pool_for_depth`, travelling with the depth schedule for
the same reason the schedule exists, and preserving cache validity for unchanged levels), plus the
immediate stop limit on the six. Validated as a PAIR against the certified reference first —
identical certificate, identical rung recovery, compromise auto-detected.

Result: **4 of 6 fixed.** The two NOR `-halves` members have a **depth-4** top (schedule `[2,2,4]` —
the coarse cut inlines both recolours *and* the swap), and censor at the pinned 2M `considered_limit`.

### DEFECT 2 — the compromise silently invalidated a metric
Loop-overhead factors moved from 2.16–3.88x to **0.30x–10.52x**, including `dae9d2b5-split-asym-lean`
at **0.30x** — end-to-end (98,809) *below* marginal (330,286), impossible for a quantity defined as
re-search overhead. Cause: `laddered_marginal` is read off the CHAIN, `laddered_end_to_end` off the
CLIMB, and an early stop truncates the two at different points.

**This forfeit was not in the Compromise Option's declared list**, which named
`cheapest_solution_index`, cost-to-exhaust and complete `by_primitive`, and said "RQ1 SURVIVES".
Added to `ladders/compromise.py`, with the note that it was found by measurement, not review.

### The validity filter  ([`uncompromised.py`](artifacts/uncompromised.py), [`valid_only.py`](artifacts/valid_only.py))
A run's numbers mean what the metric claims only if it is **uncompromised**, **admitted**, and
**reached its top**. That leaves **11 of 18** ladders — and only **2 real**.

## Findings

**Survives.** The learned-vs-oracle gap is **exactly zero**: 26/26 rungs recovered, **0 junk mints**,
on valid runs (43/43, 0 junk across all admitted). This is the most robust result in the set and the
one that most needs stressing — no arm has ever made the learner fail.

**Survives, weakened.** Marginal rung value is hugely non-uniform: median **3.17x** on valid runs
(1.22x across all), **50% of rungs worth under 2x**, range 1.00x–1988x. The concentration is real;
MVE-PLAN's registered outcome "certifies, but marginal values are small" is better read as
*concentrated* than as *small*.

**Survives, thin.** Real vs synthetic loop overhead: 3.04x (n=2) vs 3.05x (n=9) — agreement, but
n=2 on the real side.

**RETRACTED — loop overhead rising with rung count.** On valid runs: 2 rungs **3.03x** (n=7),
4 rungs **3.04x** (n=2). Flat. The apparent monotone trend came entirely from broken and compromised
runs. Valid band: 2.18x–4.04x, median 3.03x, with no demonstrated dependence on rung count.

**RETRACTED — all three granularity curves.** Valid members: `dae9d2b5` **1 of 3**, `94f9d214`
**0 of 2**, `fafffa47` **0 of 2**. **There is currently no valid granularity curve at all** — which
is the MVE's designated RQ2 axis.

## Decisions

1. Loop overhead is quoted only from uncompromised, goal-reaching runs.
2. `solution-limit`'s forfeit list now names the loop-overhead factor.
3. The per-level pool ships; `POOL_GROWTH_PER_ROUND` is documented as fitted to two measured points
   and extrapolated geometrically — a heuristic, safe in the direction that matters.

## Gaps (what we cannot currently claim)

- **No valid granularity curve** — RQ2 needs uncompromised, top-reaching runs for every member of a
  cohort at a shared budget. None exists.
- **Only 2 real ladders are measurement-valid.** "8 ladders across 3 real tasks" is a statement about
  anchoring and certification, not about measured cost.
- **The two d4-top members censor** at 2M and need either a larger limit or to be recorded as
  censored-by-design.
- **The breadth census has never been calibrated against measured cost** — the join in
  `idle_and_census.py` (A8b) returned nothing and was left unfixed when the defect took over.
- **`top-reachable` is not a check.** The datum exists in `cost_matrix`; nothing gates or reports it.
- **The zero learned-vs-oracle gap is unexplained.** We cannot distinguish "wake-sleep is robust"
  from "nothing we have built can fail it."

## Artifacts

Each script is paired with its captured output by matched basename. [`load.py`](artifacts/load.py)
is the shared loader (no output of its own).

| script | what it showed |
| --- | --- |
| [`marginal.py`](artifacts/marginal.py) · [`.out`](artifacts/marginal.out) | A1 — 46 rungs, median 1.22x, 57% under 2x, range to 1988x |
| [`structure.py`](artifacts/structure.py) · [`.out`](artifacts/structure.out) | A2 — position separates medians but the bands overlap |
| [`constants.py`](artifacts/constants.py) · [`.out`](artifacts/constants.out) | A3 — constant-binding: medians 34.61x vs 1.07x, still overlapping |
| [`aggregate.py`](artifacts/aggregate.py) · [`.out`](artifacts/aggregate.out) | A4–A7 — loop overhead, enablement, real-vs-synthetic, 43/43 recovery |
| [`idle_and_census.py`](artifacts/idle_and_census.py) · [`.out`](artifacts/idle_and_census.out) | A8 — the `enablement` ambiguity that led to the defect (census join left unfixed) |
| [`pool_vs_top_reachability.py`](artifacts/pool_vs_top_reachability.py) · [`.out`](artifacts/pool_vs_top_reachability.out) | DEFECT 1 cause: pool 30/60 unsolved, 150 solved |
| [`stop_limit_modes.py`](artifacts/stop_limit_modes.py) · [`.out`](artifacts/stop_limit_modes.out) | `immediate` vs `generation-end`: 19.5x and 63x, `first_idx` identical |
| [`joint_validation.py`](artifacts/joint_validation.py) · [`.out`](artifacts/joint_validation.out) | per-level pool + immediate stop reproduce the certified profile |
| [`uncompromised.py`](artifacts/uncompromised.py) · [`.out`](artifacts/uncompromised.out) | loop overhead on valid runs only — the monotone trend disappears |
| [`valid_only.py`](artifacts/valid_only.py) · [`.out`](artifacts/valid_only.out) | which findings survive the validity filter; the curves that do not |

**Runs.** All cells are content-hashed recorded runs under `runs/` (gitignored); the durable
per-ladder record is `docs/abstraction_ladders/ladders/<name>/report.json`, which is what every
script here reads.
