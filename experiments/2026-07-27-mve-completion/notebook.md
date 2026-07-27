# Completing the MVE: validity inventory, curve semantics, and the report (2026-07-27)

Picks up the gaps handed forward by [2026-07-27-mve-batch-analysis](../2026-07-27-mve-batch-analysis/notebook.md): no valid granularity curve, only 2 measurement-valid real ladders, no `top-reachable` check, no written report. Goal: reach the MVE's exit criteria (MVE-PLAN-2026-07-25) today, on proven numbers only.

## Log

### S1 — full validity inventory of the 8 real members ([`status_inventory.py`](artifacts/status_inventory.py))

Read-side only. For every member: stop mode, chain-top and CLIMB-top reachability, which cost quantities are valid under which semantics, and the per-cohort cost-to-first numbers (`first_solution_index` is exact under either stop mode, so to-first quantities are licensed across mixed-mode cohorts — the same fact the solution-limit Compromise Option's registry entry rests on).

Output: [`status_inventory.out`](artifacts/status_inventory.out). Summary:

| member | rungs | stop | chain top | climb top | marginal-to-first |
| --- | --- | --- | --- | --- | --- |
| dae9d2b5-split-halves-lean | 2 | immediate | solved (287,530) | solved (iter 1) | 288,174 |
| dae9d2b5-split-asym-lean | 3 | immediate | solved (312,319) | **NEVER** | 330,279 |
| dae9d2b5-split-recolor-lean | 4 | exhaustive | solved (320) | solved | **35,778** |
| 94f9d214-nor-halves | 2 | immediate | **censored 2M** | never | — |
| 94f9d214-nor-recolor | 4 | immediate | solved (473,987) | solved | 523,165 |
| fafffa47-nor-halves | 2 | immediate | **censored 2M** | never | — |
| fafffa47-nor-recolor | 4 | immediate | solved (474,420) | solved | 523,718 |
| dae9d2b5-split-recolor (ref, pool 150) | 4 | exhaustive | solved (600) | solved | 1,176,600 |

RQ1: all four raw arms are sound `>= 10x` lower bounds (censored at guard, unsolved, `sound: true`).

### S2 — NEW DEFECT FOUND: `dae9d2b5-split-asym-lean`'s climb never solves the top

Its climb converged at iteration 2 **without ever solving the top** (`off_chain_top_solved: False`; `dae9d2b5` absent from every `wake_solved`), while its own chain reaches the top (312,319 to-first at L_3). The batch analysis's "4 of 6 fixed" is really **3 of 6 fully fixed** — its validity filter read top-reachability off the CHAIN only, so the climb side never entered it.

**Diagnosis, corrected after a first wrong reading.** First hypothesis was a stale climb (report generated before `run.py`'s climb-side pool fix). The real cause is in the `.ladder` itself: `budget.depth_limit: 2` — but the top's jump is depth 3. The chain is immune (it runs the DERIVED per-level schedule `[2,2,2,3]`), while the climb searches at the pinned reference `depth_limit`, so a depth-3 top was **structurally inexpressible to the climb at any budget**. The siblings pin 3 (`split-halves-lean`, both `nor` 4-rung members), which is why only asym broke. The wake totals (39,543 / 38,231 / 21,035) are depth-2 exhaustions, not pool starvation.

**The same defect class sits latent in both `nor-halves` members**: they pin `depth_limit: 3` against a depth-**4** top — their climbs are cut off below the top independently of the 2M censoring that already blocks their chains.

Consequence for any `top-reachable` machinery: it must assert BOTH stages — the chain's `solved` at `L_k` AND the climb's top solution — and the pinned `depth_limit`-vs-top-depth consistency is statically lintable.

**Fix applied and verified**: `dae9d2b5-split-asym-lean.ladder` `depth_limit` 2 -> 3 with an
in-file note; lint 0 errors, derived schedule unchanged `[2,2,2,3]`; re-run with `--raw-arm-k 0`
(cohort convention — raw arm cited from `split-recolor-lean`). Chain cells cache-hit exactly
(identical `first_idx` 312,319, to-first marginal unchanged 330,279), and the climb now **solves
the top at iteration 1** (iter 0: 3 mints, all rungs; iter 1: top at 313,100 considered).
Still ADMITTED, 3/3 recovered, still `solution-limit`-compromised like its curve siblings — so it
is now exactly as valid as they are: to-first semantics, both stages reaching the top.

### S3 — what is claimable today with zero new runs

- RQ1 `>= 10x` per cohort, 3/3 cohorts, sound.
- Learned-vs-oracle rung gap exactly zero: 43/43 recovered, 0 junk (26/26 on valid runs).
- 8/8 rung-level certificates admitted (tractable, skip-free, health 1.0).
- Marginal rung value concentrated: median 3.17x on valid runs, 50% of rungs under 2x, max 1988x.
- A licensed **cost-to-first** granularity curve on `dae9d2b5` (3 points: 288,174 / 330,279 / 35,778 — finest is ~8x cheaper, driven by the top jump: 320 vs ~290-312k, because only the finest cut keeps the top at depth 2) and bounded 2-point curves on both NOR cohorts (523k measured vs top-not-found-within-2M). **Direction consistent across all three tasks: the coarse cut pays at the top jump, to the point of unaffordability at d4.** This REVERSES the retracted "coarser is cheaper" reading, which was an artifact of coarse members never reaching their tops.
- Loop overhead only where exhaust semantics exist: 3.00x / 3.08x (n=2, same task+cut).

_(Assessment presented to the user for run decisions; execution continues below.)_

### S4 — the batch-analysis numbers reproduce

Before citing them anywhere: re-ran `marginal.py`, `aggregate.py`, `uncompromised.py`,
`valid_only.py` from [2026-07-27-mve-batch-analysis](../2026-07-27-mve-batch-analysis/notebook.md)
against the reports as committed today — all four outputs **byte-identical** to the committed
`.out` files. The median-3.17x / 50%-under-2x / validity-filter numbers are safe to cite.

### S5 — pricing the open decisions (decision-INFORMING probes, launched while decisions pend)

Two direct engine drives (same pattern as the batch analysis's reachability probe; not recorded
runs), each turning an "unknown cost" in the options table into a number:

- [`price_d4_top.py`](artifacts/price_d4_top.py) — is the NOR depth-4 top (`94f9d214-nor-halves`,
  schedule `[2,2,4]`, pool 750) findable within a 30M guard, and at what cost-to-first? Prices
  "fix the `-halves` members with budget" vs "report them as censored-by-design bounds".
  **RESULT: not found within 30M** (censored, `first_idx None`, ~40 min wall) — 15x the cohort's
  2M budget and still no solution. "Fix with budget" has an unknown and >= 30M price per cell;
  the members are honestly reported only as **censored-by-design bounds**. Read as RQ2 data, the
  bound is itself the finding: coarsening 4 rungs -> 2 moves the top's cost-to-first from ~474k
  to `> 30M` — a `>= 63x` penalty, minimum, for pushing the top jump from depth 3 to depth 4.
- [`price_d3_exhaust.py`](artifacts/price_d3_exhaust.py) — what does
  `dae9d2b5-split-halves-lean`'s depth-3 top cell cost to EXHAUST (no stop limit, 10M guard)?
  ~The marginal cost of an uncompromised re-run, i.e. the price of the exhaust-semantics curve.
  **RESULT: does not exhaust at 10M** (solved at `first_idx` 287,530 — byte-consistent with the
  recorded run — then censored at the guard, ~13 min wall). A single d3 top cell costs `> 10M` to
  exhaust at its schedule pool, and an uncompromised member would pay that in the chain AND per
  climb iteration. **The exhaust-semantics curve is not affordable today at any rigor worth
  having; cost-to-first is the only curve currency the budget supports.** (It also means the
  recorded immediate-stop runs forfeited nothing that 10M would have bought back.)

Also fixed in [LADDERS.md](../../docs/abstraction_ladders/LADDERS.md) while runs execute: the NOR
section still asserted the retracted "both cohorts reproduce the curve's shape / monotone" claim
below the file's own retraction banner — struck with a dated retraction, and the NOR cost columns
bannered as retracted first-run numbers.

### S6 — the S2 defect class, enumerated across the whole registry
([`depth_limit_consistency.py`](artifacts/depth_limit_consistency.py) · [`.out`](artifacts/depth_limit_consistency.out))

Static sweep of all 31 registry ladders for `pinned depth_limit < max(derived schedule)` — the
condition under which the climb is structurally cut off from its own top. **Affected: exactly 2**
(`94f9d214-nor-halves`, `fafffa47-nor-halves`, both `pinned=3` vs top depth 4). All 21 synthetics
and every other real member are consistent (asym reads clean post-fix). The class is fully
enumerated; nothing else is latent — and the check is a natural lint candidate (it is purely
static).

### S7 — the licensed granularity curves, extracted
([`tofirst_curves.py`](artifacts/tofirst_curves.py) · [`.out`](artifacts/tofirst_curves.out))

Cost-to-first per cohort, committed reports only, validity asserted per member (admitted + chain
top found + climb top solved; otherwise a censored bound):

| cohort | 2 rungs | 3 rungs | 4 rungs |
| --- | --- | --- | --- |
| `dae9d2b5` (marginal-to-first) | 288,174 (d3 top) | 330,279 (d3 top) | **35,778** (d2 top) |
| `94f9d214` (top-to-first) | > 30,000,000 (d4 top, bound) | — | 473,988 (d3 top) |
| `fafffa47` (top-to-first) | > 30,000,000 (d4 top, bound) | — | 474,421 (d3 top) |

**The curve is a step function in TOP-JUMP DEPTH, not rung count.** The two `dae9d2b5` d3-top
members cost ~288k and ~330k whether they have 2 or 3 rungs; the d2-top member costs 36k; the
d4 tops are unfindable within 30M. Within equal top depth the direction mildly REVERSES (the
3-rung member costs ~15% more than the 2-rung — its larger `L_3` library widens the base). So:
depth of the residual top jump dominates by orders of magnitude; library breadth adds a small
opposite-signed second-order term. This supersedes both the retracted "coarser is cheaper" claim
(an artifact of unreached tops) and my earlier "finer is cheaper" summary (true only across
depth boundaries).

### S8 — the 5-rung NOR member, and a registered prediction REFUTED by the probe

`94f9d214-nor-merged` (drafted via `new-ladder --from 94f9d214-nor-recolor`): adds a `merged` rung
(`overlay(0, recolored_north(g), recolored_south(g))` — the grid-level OR, pre-swap) so the top
drops to `swap_colors(merged(input), 0, 2)` at depth 2. Schedule `[2,2,2,2,2,2]` — all-d2, the
NOR analogue of `dae9d2b5-split-recolor-lean`. Lint 119 checks, 0 errors. Demo grids reuse the
4-rung member's recolored-rung inputs (the family generator's asserted properties are inherited).

**The registered prediction was WRONG, instructively.** The in-file prediction (written before
lint or probe) expected the skip instrument to convict rung 5, on the model that the skip search
runs at the INLINED depth (consumer 2 + rung 2 - 1 = 3), where the 4-rung member's own top route
is affordable (~474k << 2M). The probe instead reads `skip 94f9d214 no-skip` at **13,179**
considered — the skip search runs at the CONSUMER'S derived budget (d2 here), where no route
exists without the rung. Reconciles with `dae9d2b5-split-halves`' "skip test must reach d4" note:
there the consumer (top) runs at d3 and the skipped form needs d4, so proving no-skip means
exhausting d3 — the search never runs deeper than the consumer's budget. **So `no_skip_paths` is
a BUDGET-RELATIVE necessity claim**: "no rung is bypassable at this ladder's own per-level
budgets," not "the rung is unnecessary at the guard." Both facts are simultaneously true here:
the 4-rung route to the top is affordable (474k, measured), AND the 5-rung member's rung 5 is
unskippable at d2 (probed). An instrument-contract fact worth stating wherever no-skip is quoted,
and my wrong prediction is kept in the `.ladder` header with a dated correction.

Probe: 5/5 rungs clean — every wake as-intended at depth 2/2, sleep recovers each rung at intended
arity 1. Promoted to `registry/`, testbed committed (`taskgen`), run with `--raw-arm-k 0`.

**Both 5-rung members ran and are ADMITTED** (~2 min each, `fafffa47-nor-merged` authored from the
template for a colour constant, per the cohort-template claim):

| member | certificate | recovery | climb top | chain top-to-first | marginal-to-first | off-chain |
| --- | --- | --- | --- | --- | --- | --- |
| `94f9d214-nor-merged` | admitted, 5/5 all axes | 5/5, distinct mints | iter 3 | 12,647 | **62,640** | True (as predicted) |
| `fafffa47-nor-merged` | admitted, 5/5 all axes | 5/5 | converged, solved | 20,585 | **70,698** | True |

With these, **all three cohorts carry a measured multi-point curve** (S7 regenerated;
[`tofirst_curves.out`](artifacts/tofirst_curves.out)): the NOR cohorts read 5-rung 62-71k (d2 top)
· 4-rung 523k (d3 top) · 2-rung `> 30M` (d4 top). The step-function reading sharpens across
tasks: d2-top members 36-71k, d3-top members 288-524k, d4-top `> 30M` — roughly an order of
magnitude per level of residual top depth, on three independent real tasks. The MVE exit
criterion "granularity curves for >= 2 sub-cohorts" is now met with measured curves on all three,
under cost-to-first semantics.

### S9 — the validity guards, built (surface-only; gating stays an open decision)

Three shipped instances of "admitted, every rung clean, goal unreachable" (S2) earned machinery.
Deliberately **surfacing, not gating** — whether goal-reachability should move `admitted` is the
open design decision the fork discussion owns; nothing here changes any ladder's verdict:

1. **`top_reachable` in every report** (`report.py`): `{chain, climb}` — the oracle `L_k` search
   (tri-state, censored-unsolved is `None` like `no_skip_paths`) and the learned wakes (the stage
   that actually broke on asym). Rendered beside the certificate; a loud banner fires when a run's
   own goal is not provably reached, instructing that its numbers be read as censored bounds.
2. **Loop-overhead enforcement** (`report.py`): the factor is `None` (with
   `loop_overhead_forfeited_by` naming the codes) whenever an active Compromise Option forfeits
   it — the report now enforces what `compromise.py`'s registry entry states, instead of leaving
   an invalid 0.30x for a reader to quote.
3. **New static check `climb-budget-covers-top`** (`checks/depth.py`, warn severity): pinned
   `depth_limit` below the derived schedule's max = the climb structurally cut off from the goal.
   Fires today on exactly the two `nor-halves` members (S6's sweep); trivially clean under
   `PINNED` mode (al10 untouched). `LINT-CHECKS.md` regenerated.

Tests: `test_climb_budget_check.py` (fires on `94f9d214-nor-halves`, clean on
`split-recolor-lean` and `al10`), renderer tests for the reach line/banner/forfeit line, and two
end-to-end assertions on `al1-mirror` (uncompromised: reach True/True, factor present; under
`solution_limit=1`: factor `None`, forfeited-by `solution-limit`). **`make check` green: 994
tests, ruff + mypy --strict clean.**

### S10 — the breadth census calibrated against measured cost (the abandoned A8b join, finished)
([`census_calibration.py`](artifacts/census_calibration.py) · [`.out`](artifacts/census_calibration.out))

The census's own claim ("an INDICATOR for ranking, never a forecast") had never been tested against
measured cost. Join: per rung, the static `b1_full` / tax ratio vs the report's measured
`jump_costs`, over every UNCOMPROMISED committed report (an early stop truncates cost-paid-full),
excluding censored rung cells. Final state (both `nor-merged` members uncompromised): 39 rungs,
36 usable.

**Spearman(b1_full, measured) = 0.88** (0.92 before the second `nor-merged` joined). The tax-ratio
variant reads 0.81; the census ranks the batch essentially correctly from statics alone. Caveats,
stated because they bound the claim:
(1) every usable rung is depth-2 — the only d3 rungs (al5) were guard-censored — so the
depth-compounding behaviour ("understates ~4,000x at depth 3") stays uncalibrated; `b1^d` is
indistinguishable from `b1` at fixed depth. (2) `max_pool` is a confound the census does not
model: the pool-150/pool-30 twins share a census and differ 25x in measured cost — ranking
survives because the batch shares its pool regime, and a mixed-pool batch would need the pool
held fixed before reading the census.

### S11 — the 5-rung members re-run UNCOMPROMISED (the early stop was buying nothing)

The `nor-merged` members inherited `solution_limit: 1` from the 4-rung template, where a d3 top
makes exhaustion unaffordable. On their all-d2 schedule the early stop saves ~nothing (the
2026-07-27 calibration: every cell solves in its last generation) while its Compromise Option
forfeits the loop-overhead factor. Removed from both `.ladder` files (with the reason in-file,
mirroring `dae9d2b5-split-recolor-lean`), re-run (~3 min each):

| member | compromises | top_reachable | marginal (exhaust / to-first) | loop-overhead |
| --- | --- | --- | --- | --- |
| `94f9d214-nor-merged` | **[]** | chain True, climb True | 144,085 / 62,640 | **4.00x** (valid) |
| `fafffa47-nor-merged` | **[]** | chain True, climb True | 152,233 / 70,698 | **4.00x** (valid) |

Three things this buys: (1) both members are now **fully valid** (uncompromised + admitted + top
reached both stages) — 4 fully-valid real ladders total; (2) `laddered_marginal_to_first` is
byte-identical to the compromised runs (62,640 / 70,698) — the to-first invariance the curve
semantics rests on, now confirmed on real reruns rather than argued; (3) **valid loop-overhead
moves from n=2 (one task, one cut) to n=4 (three tasks, two cut densities)**: 3.00x / 3.08x
(4-rung dae9d2b5) and 4.00x / 4.00x (5-rung NOR). Caution: that pattern is suggestive of overhead
scaling with climb iteration count (2 vs 4 iterations), which the earlier RETRACTED
rising-with-rung-count trend makes exactly the claim NOT to re-adopt at n=4 — recorded as a
question, not a finding. The new `top_reachable` report field and the loop-overhead enforcement
are both visible working on real runs here.

### S10 — the base-width tax, measured from cells already on disk
([`base_width_tax.py`](artifacts/base_width_tax.py) · [`.out`](artifacts/base_width_tax.out))

Prompted by the critical-review question "is the 2-rung-vs-3-rung top-cell gap (+8.6%) really a
base-width effect, or order luck?" — the answer did not need new runs. In an exhaustive all-d2
member, every cost-matrix cell at `L_i` is a depth-2 EXHAUSTIVE enumeration over floor + `i`
rungs, so reading one task's `considered` across `L_0..L_k` measures d2 space size as a function
of library size — order-independent, many cells.

- **`dae9d2b5` floor at pool 150** (`split-recolor`): 230,497 -> 341,629 over 4 added rungs =
  **+10-11% per rung**, `b_eff` 107.3 -> 130.7 (~+5%/rung).
- **Same floor at pool 30** (`split-recolor-lean`): 12,139 -> 12,179 = **+0.08% per rung** — the
  pool binds and the tax all but vanishes.
- **Synthetics**: unary rungs +3-5%/rung (al15/17/19/20), +17-21% (al16/18), +40-49% (al21, tiny
  base) — and al1's 2-param rung **+282% (3.82x)**, reconfirming the registered "vocabulary tax
  is almost all arity" finding from the exhaustive side.
- **Cross-check that upgrades the 2v3 reading:** the observed +8.6% between the two d3 tops
  (287,530 vs 312,319, both pool 150, one library entry apart) matches the independently measured
  +10-11%/rung growth rate on this exact floor at this exact pool. Consistent, though the
  specific pair stays suggestive (different target terms, shared enumeration order).
- **Structural answer:** at fixed depth+pool the gradient is always >= 0 (space is monotone in
  the library), but its magnitude spans 0.08% -> 282% per rung, driven by arity, pool binding and
  floor breadth. "Mild" is not a law.
- **Matched-pool depth de-confound** (for the depth-dominance claim): at pool 150 on the same
  task, the d2 top costs **600** to-first over the LARGER library (`L_4`) vs **287,530/312,319**
  at d3 over smaller ones — **~480x per depth level**, conservative because the base tax biases
  the other way.

Config parity across the seven lean members, verified from the `.ladder` files: identical
`max_arity` 3 / pool 30 / guard 2M / `finite-enumerate-scalars`; differing ONLY in stop mode
(`recolor-lean` exhaustive vs `solution_limit: 1 immediate` elsewhere — invisible to to-first,
fatal to e2e comparability) and pinned `depth_limit` (2 vs 3; plus the S6 class on the
`nor-halves` pair). The derived per-level depth/pool schedules differ by design — they ARE the
treatment, and the pool-travels-with-depth policy means "the cost of depth d" deliberately
includes "the pool depth d needs".

### S11 — claim-strengthening pass: what the existing data can add to each report claim
([`claim_strengthening.py`](artifacts/claim_strengthening.py) · [`.out`](artifacts/claim_strengthening.out))

Read-side only, prompted by "can the claims be supported or refuted further from data we already
have?" Four investigations:

- **T1 — constants dominate the considered stream, universally.** Across all **385** cells carrying
  `by_primitive`: the `__const__` containment share is **>= 0.9675 in every cell** (median 0.9988;
  > 0.99 in 295/385). Semantics verified against `report.py::_by_primitive` before citing
  (`share = count/total` over per-primitive considered counts): this is *"fraction of considered
  programs containing a constant leaf"*, NOT a cost split — the enablement lesson applied.
- **T2 — the base-width tax vs the added rung's shape, 36 points** (exhaustive uncompromised
  reports, growth `L_(i-1) -> L_i` at fixed depth): median **1.03x** for arity-1 mints (n=24),
  **1.05x** arity-2 (n=11), **3.82x** for the single arity-3 point (al1's 2-value-param rung).
  Relative growth is larger on tiny bases (al2 1.86x, al21 1.40-1.49x). So: mild for unary/binary
  on real floors, arity is the escape hatch to large — consistent with the micro-probe product law,
  now shown on whole recorded chains.
- **T3 — predictor shoot-out on marginal rung value, 56 rungs** (set grew with the `nor-merged`
  members): big-battery constant **34.61x vs 1.05x** medians (32.9x separation) · top-fed
  **17.04x vs 1.05x** (16.2x) · minted arity >= 2 **no signal** (1.0x) · "binds any constant"
  **inverted** (0.3x — small-int constants sit in cheap rungs). All splits overlap. Sharpens B3:
  the predictor is battery SIZE specifically, not constant-binding per se; arity predicts the
  rung's COST (T2), not its VALUE (T3) — two different quantities, cleanly separated.
- **T4 — every raw arm on disk (13):** all `sound: true`. THREE measured exceptions to `>= 10x`,
  not two: al1 **3.59x** (d_raw 4) · al2 **0.48x** (d_raw 4, finite group) · **al21 1.19x**
  (d_raw 3) — newly noticed. Every `>= 10x` bound sits at d_raw 4-6 over designed-withheld floors;
  every measured sub-10x case is shallow-d_raw/lean-floor, ratios 0.48-3.59x, i.e. at or below the
  ~3x loop overhead. C3's "amortization tracks raw-intractability" now has 3 measured points + 10
  bounds.

Not further strengthenable read-side (needs new runs or out of scope): A5 depth-steps beyond the
existing pairs (mixed-schedule committed artifacts are stale pre-schedule), B4 loop-overhead vs
rung count (uncompromised climbs unaffordable per S5), D3 stressing the learner (wave-2 arm). The
big worthwhile deeper join: **census-vs-measured calibration** (breadth census b1 per rung vs
recorded cell costs; `runs/` trace.jsonl has per-generation data) — ~half a day, upgrades A9/B1
from ranking to validated forecast; recorded as the standing wave-2 analysis item.

### S12 — decomposition-strategy siblings: the wave-2 axis MVE-PLAN deferred, sampled for the first time

*(Numbering note: this section continues from a separate concurrent pass in this same notebook
that independently used S10/S11 for different content — base-width tax and claim-strengthening.
Not renumbered here to avoid touching that work; S12 is simply the next number after this
session's own S9/S10/S11 above it.)*

MVE-PLAN wave 2 item 2 ("second sub-cohorts / decomposition-strategy") has never been sampled —
every member so far cuts the SAME way (address-first: name the raw half, then recolor it). This
investigates the orthogonal cut: name the RECOLOURED half directly as the rung, folding addressing
into the rung's own template instead of the top's. Same task, same floor, same already-paid raw
arm per cohort — the cheapest axis to add, per LADDER-PROCESS discipline (draft -> lint -> probe
before any run; the probe convicts, only the certificate acquits).

**Candidates and registered predictions**, written before any lint or probe:

1. `dae9d2b5-recolor-first` (2-rung: `{recolored_west, recolored_east}`, top d2). Predicted MORE
   expensive overall than `split-halves-lean` despite the shallower top: each rung's own jump
   needs d3 from the bare floor (vs d2 for `west`/`east`), with no reuse between the two branches
   the way a shared top reuses both branches' work. Two independent d3 jumps vs one d3 top fed by
   two cheap d2 rungs.
2. `94f9d214-recolor-first`, `fafffa47-recolor-first` — same move on the NOR cohorts, doubling the
   sample for the same prediction once one probes clean.
3. A coarsest-possible 1-rung endpoint (`dae9d2b5`, single rung = `recolored_west`, everything
   else inlined -> d4 top): predicted to CENSOR or fail `raw-intractable` (barely distinguishable
   from raw at that point) — draft/lint/probe only, per the earlier d4 pricing (S5: NOR's d4 top
   unfindable within 30M).
4. NOR 1-rung endpoint and NOR 3-rung asym siblings (`{north,south,recolored_north}`, predicted to
   land at a d4 top like `nor-halves`): explicitly SKIPPED, not drafted — the d4 wall is already
   conclusively priced (S5), so these would only reconfirm it at the cost of new demo authoring
   with no new information. Recorded as a deliberate scope cut, not an oversight.

Log continues below with lint/probe results per candidate.

### S12a — TWO probe-machinery defects found while probing the first candidate

`dae9d2b5-recolor-first`'s first probe attempt was silently wrong before it was informative:

**Defect A — `probe_rung` didn't scale `max_pool` with the per-level derived depth.** The 2026-07-27
fix that scales the pool with depth (`run.py::pool_for_depth`) landed on the CHAIN only; `probe.py`
still derived `depth_limit` per level but left `max_pool` at the ladder's flat configured value.
Every prior schedule puts depth >= 3 ONLY at the top-serving level, which a rung's own probe never
searches at directly — so this was invisible until the first ladder with a depth-3 **rung**
(`recolor-first`'s rung 1). First symptom: "SATURATED: round 3 composed nothing at max_pool 30 —
this cell's effective depth is 2, not 3" alongside "UNSOLVED" — the tell (a genuinely intractable
jump exhausts; a starved one saturates). Fixed: `probe_rung` now computes
`pool_for_depth(configured_pool, depth)` exactly like the chain (`probe.py`), pinned by a new
regression test asserting `probe.saturation.max_pool == 150` for this exact ladder.

**Defect B, larger — the CLI never exercised the per-level derivation at all.** `probe-ladder`'s
command always built one explicit `Budget` from the ladder's PINNED config and passed it to every
probed rung — which skips `probe_rung`'s entire `if effective is None` branch (the per-level depth
+ pool derivation lives ONLY there; an explicit `budget` means "measure this exact cell", by
design). So the CLI has silently probed every non-uniform-schedule ladder at ONE flat depth+pool
for every level, not the schedule's actual per-level values — correct only by coincidence on
uniform-schedule ladders (the majority) or where the pinned value happens to equal the schedule's
max (asym-lean and both nor-halves members, both fixed earlier this session for the SAME reason on
the climb side). Confirmed by re-probing after Defect A's fix alone: byte-identical output to
before — the fix was never being reached. Fixed by removing the CLI's full-budget construction
entirely; `probe_rung`/`probe_ladder` gained a narrow `guard: int | None` parameter that overrides
only `considered_limit` on top of whichever budget (explicit or per-level-derived) was chosen,
which is all `--guard` ever needed.

**Consequence, scoped**: no CERTIFIED ladder's admission verdict is wrong — `run_ladder`'s CHAIN
(the actual admission authority) has always used the correct per-level derivation independent of
the probe. What was compromised is the probe's OWN diagnostic value on any non-uniform-schedule
ladder probed since the depth-schedule feature landed (2026-07-26) — an advisory pre-run tool, not
a certificate. Full regression suite (`test_probe.py`, `test_probe_seam.py`, whole
`tests/program_search/ladders/`) green after both fixes; a third regression test pins the CLI-level
symptom would have shown (identical to Defect A's, since the CLI now delegates to the same path).

### S12b — the candidates, probed under the fixed machinery

**`dae9d2b5-recolor-first`** (schedule `[3,3,2]`, correctly pool-scaled to 150 at rung level):
both rungs WAKE-solve — "alternative" verdict (a valid but non-canonical program, same behavioral
class, found at the intended depth 3/3) — but each hits the 2M guard essentially exhausted
(considered lands at exactly 2,000,000). The SKIP test for each censors at 2M too (`inconclusive`,
not `no-skip`). Floor tax: pruned 21 vs full 2,000,000 = **95,238x** [floor-too-broad] — the rung
itself is fine; the un-pruned floor at depth 3 is what costs. **Verdict: INCONCLUSIVE at the
cohort's standard budget, matching the registered prediction's direction** — recolor-first is
measurably more expensive than address-first at the same cut density, confirmed rather than
merely predicted. Not run (LADDER-PROCESS: an inconclusive probe is a non-result, not a defect to
chase with a bigger guard); kept in `registry/` with a committed testbed as a finding, same
precedent as `dae9d2b5-halves-union`.

**`94f9d214-recolor-first`** (same shape, NOR floor): a REFINEMENT of the prediction, not a
repeat. The WAKE searches are cheap here — 314,298 / 344,925 considered, well inside the 2M guard,
both solving at the intended depth 3/3. Only the SKIP test censors at 2M. So the expensive part on
this floor is specifically **proving no bypass exists**, not finding the rung itself — a sharper
and more precise finding than dae9d2b5's (where wake itself looked guard-bound too). Floor tax
18,488x-20,290x [clean] — the rung's own search is cleanly attributed, unlike dae9d2b5's
[floor-too-broad] reading. **`fafffa47-recolor-first`** probed for cohort symmetry; result below
once it lands.

**`dae9d2b5-recolor-solo`** (1-rung endpoint, schedule `[3,4]` — a rung AND a d4 top): lints clean
(0 errors) — the static `raw-intractable` check does NOT reject it, refuting my own prediction
that it might fail statically; `climb-budget-covers-top` warns as expected (pinned 3 < schedule
max 4, left uncorrected since this candidate is not being run). Probed at a lowered 500k smoke
guard (rung 1 is byte-identical to `recolor-first`'s rung 1, so wake result is a cache-consistent
confirmation, not new information): same INCONCLUSIVE pattern, floor tax 23,810x. Not run.
Confirms the earlier NOR d4 pricing (S5) generalises: the far coarse end of BOTH families' curves
is bounded by cost at the cohort's standard budget, not by any structural defect.

**`fafffa47-recolor-first`**, probed after the above for cohort symmetry: considered counts
**byte-identical** to `94f9d214-recolor-first`'s (314,298/314,340 and 344,925/344,901) — the
cohort-template claim confirmed exactly, not just structurally, on the recolor-first axis too.

### S12c — closeout

All four candidates kept in `registry/` with committed testbeds (`taskgen`), none run (all
INCONCLUSIVE at the cohort's standard 2M guard; per LADDER-PROCESS an inconclusive probe is a
non-result, not chased with a bigger guard). LADDERS.md gained a "Decomposition-strategy siblings"
section; EXPERIMENTS.md carries the full entry (defects + findings). **`make check` green: 1003
tests** (994 -> 1003, +9: three new `test_probe.py` cases pinning both machinery fixes, plus the
suite picking up the four new registry ladders' batch-wide checks), ruff + mypy `--strict` clean.

**Net finding of the whole decomposition-strategy pass**: cost tracks the depth of whichever
search is left carrying the deepest jump — and that search can be the WAKE or the SKIP, sitting at
the RUNG or the TOP, depending on how the cut falls. Address-first happens to put the deep jump at
the top (already established); recolor-first puts it at the rungs, and specifically — on the NOR
floor — at the rungs' SKIP tests rather than their wakes. Same underlying law, different surface
location; not a new axis of variation so much as the SAME axis read from the other side.

### S13 — cut-set enumeration: the granularity axis is PROVABLY exhausted, and the cost law sharpens
([`cut_set_enumeration.py`](artifacts/cut_set_enumeration.py) · [`.out`](artifacts/cut_set_enumeration.out))

The first of the systematic methods (now recorded in
[LADDER-IDEAS.md](../../docs/abstraction_ladders/LADDER-IDEAS.md)). A spine's intermediate terms are
a finite set, so its cut-sets are `2^n` — enumerate them ALL, render a draft `.ladder` each, lint
in-process, read the derived depth schedule, filter. Demo blocks are reusable **verbatim** across
cut-sets (a rung's demonstrating tasks are a property of the FUNCTION, not of which lower terms are
named), so only the template line changes — which is what makes the screen run *before* demo
authoring, the plan's dominant cost centre. 46 candidates, milliseconds each, no testbeds.

**First: the affordability predicate had to be derived, not assumed.** "All-d2" (the working
heuristic from S7) is too STRICT — it rejects `split-halves-lean`, `split-asym-lean` and
`nor-recolor`, all of which ran and certified. "max <= 3" is too LOOSE — it admits both
`recolor-first` members, which probe INCONCLUSIVE. The predicate that separates all nine
measured-or-probed outcomes **9/9** is:

> `max(schedule[:-1]) <= 2 and schedule[-1] <= 3` — every RUNG-serving level at depth 2, the TOP
> level allowed depth 3.

**And the asymmetry is structural, not empirical.** A rung-serving level pays an expensive wake AND
an expensive SKIP search — and the skip search must run to **exhaustion**, because it must NOT
solve (that is exactly what `no_skip_paths` asserts), so it can never stop early. The top level
carries no skip obligation, so one deep level there costs a single search. That is why a `3` in the
last position is affordable and a `3` anywhere earlier is not — and it explains the recolor-first
inconclusiveness (schedules `[3,3,2]` / `[3,3,3]`: the 3s sit at rung levels) structurally rather
than just observing it.

**Second: quotient by the spine's own symmetry.** On a two-branch DAG the branches are
interchangeable (already noted in `split-asym-lean`'s header), so a mirror-image cut-set is the
SAME experiment. Empirically supported: `94f9d214` and `fafffa47` differ only by palette and
produced byte-identical considered counts, so colour does not move cost.

**Result — both cohorts are exhausted:**

| cohort | cut-sets | lint-clean | distinct up to symmetry | affordable | **new & affordable** |
| --- | --- | --- | --- | --- | --- |
| `dae9d2b5` | 15 | 15 | 9 | 3 | **0** |
| NOR (`94f9d214`/`fafffa47`) | 31 | 31 | 19 | 2 | **0** |

Every affordable cut-set is already built: `split-halves-lean` `[2,2,3]`, `split-asym-lean`
`[2,2,2,3]`, `split-recolor(-lean)` `[2,2,2,2,2]`; `nor-recolor` `[2,2,2,2,3]`, `nor-merged`
`[2,2,2,2,2,2]`. **The granularity/cut-set axis is closed by enumeration, not by running out of
ideas** — and the screen retrodicted all 9 known outcomes before delivering the negative, which is
what licenses trusting it on the 37 candidates nobody has run.

**What this does NOT close, and the argument is now sharp.** The enumeration ranges over *subsets of
existing intermediate terms*. Three kinds of variation are outside that space by construction, so
the exhaustiveness result leaves them untouched — and they are now the only remaining headroom:

- **parameterization** — `half(g, i)` is a different FUNCTION (arity 2), not a subset of
  `{west, east, ...}`, so no cut-set can express it. All-d2 by construction, hence affordable.
- **demonstration plan** — same cut-set, different demo grids.
- **distractors** — same cut-set, extra off-spine tasks.

That is a stronger case for the `half-param` idea than I could make before: it is not merely the
next thing to try, it is the *only* cheap structural variation the cohorts still admit.

### S14 — TRANSFER: the recorded run nobody had ever read
([`transfer.py`](artifacts/transfer.py) · [`.out`](artifacts/transfer.out) ·
[`transfer_baseline.py`](artifacts/transfer_baseline.py) · [`.out`](artifacts/transfer_baseline.out))

`run_ladder` -> `run_search_learn(config, train_corpus, heldout_corpus)` produces THREE recorded
runs: the LEARN run, a `train_usefulness` search, and a **`transfer`** search over the HELDOUT
corpus with the grown library. The report says so itself, under "Not computed here": *"needs the
heldout transfer run's per-task costs ... the runs exist, the view does not yet."* So every claim
the program has made — 43/43 rungs recovered, 0 junk, every cost curve — has been about the TRAIN
corpus. Same species of gap as `top_reachable` (S2/S9): a datum recorded, never surfaced.

**Step 1, read-side (cached, no new search): transfer is 100%.** Every heldout task solved, on
every member, including the heldout top. **And on its own that is nearly vacuous** — the heldout
corpus holds held-out INSTANCES of the same competences (`west-heldout` is new grids for the same
`west`), and the learned library contains abstractions that ARE those competences, so each rung
heldout is a depth-1 application. Of course it solves. A number that cannot come out low is not
evidence.

**Step 2, the baseline that makes it mean something:** the same heldout corpus over the BARE FLOOR
at the same budget, so the only thing differing between the columns is the library.

**Result — 7/7 members: the heldout TOP is `floor=NO, learned=YES`.**

| member | rung heldouts | heldout TOP |
| --- | --- | --- |
| `dae9d2b5-split-recolor-lean` (pinned d2) | `west`/`east` free at floor; both `recolored_*` **learned only** | floor **NO** · learned yes |
| `dae9d2b5-split-halves-lean` (d3) | both free at floor | floor **NO** · learned yes |
| `dae9d2b5-split-asym-lean` (d3) | all three free at floor | floor **NO** · learned yes |
| `94f9d214-nor-recolor` (d3) | all four free at floor | floor **NO** · learned yes |
| `94f9d214-nor-merged` (d2) | `north`/`south` free; `recolored_*` + `merged` **learned only** | floor **NO** · learned yes |
| `fafffa47-nor-recolor` (d3) | all four free at floor | floor **NO** · learned yes |
| `fafffa47-nor-merged` (d2) | `north`/`south` free; `recolored_*` + `merged` **learned only** | floor **NO** · learned yes |

**What is now claimable, scoped precisely:** the learned library reaches the task's GOAL on grids it
never saw, where the bare floor cannot — unanimously, on three independent real ARC tasks. That is
the first transfer measurement the program has made, and it is the closest thing yet to the actual
research question, since an abstraction's value *is* its reuse.

**What is NOT claimable:** this is generalisation to unseen INSTANCES, not to unseen COMPETENCES.
No claim about a different task is licensed.

**And the rung-level value is BUDGET-RELATIVE, not intrinsic.** The "free at the floor" / "learned
only" split correlates perfectly with each member's pinned `depth_limit`: members pinned at 2 have
their d3 rungs read "learned only", members pinned at 3 have the same rungs read "free at the
floor". The TOP is the exception that carries the result — it is d4+ from the floor and therefore
out of reach at *every* budget in this batch. Same shape as the `no_skip_paths` lesson (S8): a
necessity claim is relative to the budget the ladder itself runs at, and only a claim that holds
across all of them is structural.


### S15 — the first honest NONZERO learned-vs-oracle gap: the zero gap was one proposer's property
([`proposer_swap.py`](artifacts/proposer_swap.py) · [`.out`](artifacts/proposer_swap.out))

Every real-task result to date — 43/43 rungs recovered, 0 junk mints — was produced with
`AntiunifyPairs` and nothing else, which makes "the learned-vs-oracle gap is exactly zero" a claim
about ONE PROPOSER rather than about wake-sleep. The program's own recorded gap says we cannot
distinguish "the loop is robust" from "nothing we have built can fail it". This settles it.

**Cheap, and the cheapness is verified not assumed.** The oracle chain builds its configs with
`learn=None` (`run.py::run_ladder_chain`), so a learn-side change is not part of any chain cell's
run identity: the whole chain cache-hits and only the climb re-runs. The script asserts the
certificate is byte-identical across arms — if a chain cell had re-run, that is where it would show.

| member | proposer | recovered | mints | iters | end-to-end |
| --- | --- | --- | --- | --- | --- |
| `dae9d2b5-split-recolor-lean` | AntiunifyPairs | **4/4** | 4 | 3 | 302,961 |
| | FrequentSubtree | **0/4** | 0 | 1 | 100,815 |
| | TypeScopedFrequentSubtree[GRID] | **0/4** | 0 | 1 | 100,815 |
| | StitchProposer | **0/4** | 0 | 1 | 100,815 |
| `94f9d214-nor-merged` | AntiunifyPairs | **5/5** | 5 | 4 | 576,512 |
| | the other three | **0/5** | 0 | 1 | 143,831 |
| `al1-mirror` (synthetic) | AntiunifyPairs | **2/2** | 2 | 3 | 200,280 |
| | FrequentSubtree / TypeScoped | **0/2** | 0 | 1 | 33,715 |
| | StitchProposer | **1/2** | 1 | 2 | 68,275 |

**It is not a wiring failure, and the mechanism is exact.** Three checks:
1. Identical costs across three proposers are *expected* under 0 mints — nothing is minted, so the
   library never changes, iteration 0's wake is the same search, and `early_stop` fires at 1.
2. `StitchProposer` recovers **1/2 on al1**, different cost, 2 iterations — so the swap genuinely
   reaches the proposer; a blanket zero would have been the suspicious result.
3. The trace shows the material WAS there: on `split-recolor-lean` iteration 0, wake **solved all
   four** demo tasks, the proposer offered exactly **1** proposal, and governance minted **0**.

The cause is structural and visible in the source: `FrequentSubtree.propose` builds its candidates
from `list(program.walk())[1:]` — **each program's own root excluded** (its docstring: "Lam-free
proper subtrees (each program's own root excluded)"). Every rung in these ladders is Grid-valued
and demoed as a FULL SOLUTION, so the abstraction the ladder needs *is the whole retained program*,
which root-exclusion makes structurally invisible. The single proposal it does offer is the only
recurring proper subtree left — `split_h(input)` — and a depth-1 wrapper does not compress, so
GreedyMDL rejects it. `AntiunifyPairs` mints precisely because it counts WHOLE programs
(`Counter(programs)`: "a program that recurs verbatim is itself an abstraction once its input is
lifted").

**The reframe, which is the actual result.** This is the **first nonzero learned-vs-oracle gap the
program has produced** — 0/4, 0/5, 0/2. But it is a *capability boundary with a named mechanism*,
not a defect: it is the exact mirror image of the E7 finding, which showed `AntiunifyPairs`
structurally unable to surface an idiom recurring *inside* larger programs and thereby motivated
`FrequentSubtree`'s existence. So:

> "The learned-vs-oracle gap is exactly zero" was never a property of wake-sleep. It is a property
> of **`AntiunifyPairs` + this program's demo convention** (Grid-valued rungs demoed as full
> solutions). The claim is falsifiable, and swapping the proposer falsifies it.

**Design consequence.** The ladder method as practised is coupled to one proposer by its demo
convention: a full-solution demo puts the target in `AntiunifyPairs`' regime *by construction* and
outside `FrequentSubtree`'s. Proposer-agnostic claims need either fragment-demoed (non-Grid-valued)
rungs — which is exactly what cfb2ce5a Cohort B was for — or an explicit proposer portfolio. That
retroactively sharpens why Cohort B was the one arm flagged as stressing the climb rather than
confirming it.

### S16 — `half-param`: a SECOND nonzero gap, from governance rather than proposer reach
([`gen_half_param.py`](artifacts/gen_half_param.py) · [`half_param_sleep.py`](artifacts/half_param_sleep.py) · [`.out`](artifacts/half_param_sleep.out))

The parameterization axis MVE-PLAN declares per sub-cohort and nothing had sampled: one arity-2
rung `half(g, i) = nth(split_h(g), i)` replacing the two monomorphic siblings `west`/`east`. Same
task, floor, budget and (already-paid) raw arm as `dae9d2b5-split-recolor-lean` — only the binding
moves. It is also the only cheap structural variation the cohorts still admit, since S13's cut-set
enumeration ranges over subsets of existing terms and `half` is a different FUNCTION.

Lint: 89 checks, 0 errors, schedule `[2,2,2,2]` — the all-d2 cheap regime, as predicted. **And the
static census already priced the arity tax before any run:** `half` grows the round-1 base
**1,211 -> 1,220 (+9)** where the arity-1 `west` grew it **+1**.

**Prediction 1 (cost) — resolved: it is a WASH.** to-first 35,987 vs the sibling's 35,778 (+0.6%),
exhaust 101,297 vs 100,973 (+0.3%), loop-overhead 2.99 vs 3.00. The wider entry and the fewer
entries very nearly cancel. Note *where* the difference sits: entirely in the CHAIN, which searches
the oracle library that actually contains the arity-2 `half` — the same +9-vs-+1 base-width signal
the census predicted statically.

**Prediction 2 (learnability) — REFUTED, and that is the finding.** I predicted GreedyMDL would
prefer one arity-2 entry covering four programs over two arity-1 entries covering two each. The
probe convicted rung 1 instead: wake **as-intended on all four** demos, **no skip path** on all four
consumers, then `sleep: MISSED; minted ['abs0','abs1'] at arity 1 (intended 2)`.

**The mechanism, separated rather than assumed** ([`half_param_sleep.py`](artifacts/half_param_sleep.py)).
Two very different causes produce that symptom, so I pulled the retained programs off the probe and
inspected the proposer's candidates directly:

```
PROPOSER (AntiunifyPairs) offered 3 candidates:
  arity 1  matches-target=False  nth(split_h(#0), 0)
  arity 1  matches-target=False  nth(split_h(#0), 1)
  arity 2  matches-target=True   nth(split_h(#0), #1)   <- the intended `half`, OFFERED
GOVERNANCE (GreedyMDL) kept 2:  abs0 arity 1, abs1 arity 1
```

So this is **GOVERNANCE, not proposer reach** — a different mechanism from S15, where
`FrequentSubtree` structurally could not propose the target at all. Here the right abstraction was
proposed and the selector discarded it.

**Why MDL prefers specialisation, and when it would not.** A parameterized abstraction saves LESS
per call site than a specialised one, because the argument still has to be written: `abs0(input)`
is 2 nodes against `half(input, 0)`'s 3, where the un-abstracted term is 4. With only TWO distinct
parameter values each specialised variant recurs often enough to pay its own library entry, so
2 entries x 2-nodes-saved beats 1 entry x 1-node-saved. The bias is therefore not unconditional —
it should invert once the parameter takes enough distinct values, which is a sharp, cheap follow-up.

**The ladder was run anyway** (all-d2, ~2 min), deliberately, because the conviction IS the result
rather than a defect to fix — the al9-al12 control precedent. Outcome: **ADMITTED**, top reached in
chain and climb, **rung recovery 2/3** (`half` missed; both recolour rungs recovered). That makes it
the first real-task ladder carrying a MEASURED nonzero recovery in a committed artifact.

**The sharpest part: the bind-late ladder COLLAPSES INTO the bind-early one under learning.** The
two members' per-iteration climb costs are byte-identical (`[100815, 100987, 101159]`, e2e 302,961
both). That is not coincidence — sleep's two specialised mints ARE `west` and `east`, so after
iteration 0 the learned libraries are behaviorally identical and every subsequent search matches
exactly. The learner does not merely fail to mint `half`; it actively **reconstructs the
decomposition the other member declares**.

**Interpretation, and it composes with a standing finding.** The recorded "vocabulary tax is almost
all arity" result says SEARCH is biased against parameterized abstractions (+2.5% param-free vs
+282% for a 2-param rung). Now governance is shown biased against them too. **Both halves of the
system push away from exactly the abstractions that generalise** — which is a coherent and somewhat
uncomfortable story for a program whose thesis is that reusable abstraction is what buys tractability.

### S17 — the governance boundary, characterised: S16 landed in the ONE cell that specialises
([`mdl_inversion.py`](artifacts/mdl_inversion.py) · [`.out`](artifacts/mdl_inversion.out))

S16 left a mechanical prediction: specialisation wins at few distinct parameter values and must lose
as they multiply, since V specialised entries grow linearly while their per-call-site advantage does
not. S16 only ever observed the V=2 corner. This sweeps V (distinct parameter values) x M
(occurrences each) — a pure SELECTOR experiment, no search, no ladder, no testbed, milliseconds,
on `map_color(input, c, 6)` (same shape as the real case, but colours give up to 10 values where a
half-index gives 2).

| V | M=1 | M=2 | M=3 |
| --- | --- | --- | --- |
| **2** | generalises\* | **SPECIALISES [1,1]** | **SPECIALISES [1,1]** |
| 3 | generalises\* | keeps [1,1,1,**2**] | keeps [1,1,1,**2**] |
| 4-8 | generalises\* | keeps [1...1,**2**] | keeps [1...1,**2**] |

\* the M=1 rows are NOT evidence of preference: with no verbatim repetition `Counter(programs)`
offers nothing, so the antiunified form is the *only* candidate and is kept by default.

**Two findings, and the second was not predicted.**

1. **The boundary is exactly V=2, and S16's real case sits precisely in it.** `dae9d2b5-half-param`
   has two half-indices with two demos each — V=2, M=2, the single cell in this table where the
   offered generalisation is actively DISCARDED. So the S16 failure is not a broad bias against
   parameterization; it is a narrow corner that the real experiment happened to land in exactly.
   Worth stating plainly because the S16 write-up's "both halves of the system push away from
   abstractions that generalise" is too strong as a general claim, and this is the correction.
2. **From V>=3 the selector does not choose the generalisation — it keeps EVERYTHING.** The kept
   sets read `[1,1,1,2]`, `[1,1,1,1,2]`, ... : the arity-2 form *plus* every specialisation, i.e.
   **V+1 entries where 1 would do.** Greedy-MDL adds while each addition improves description
   length, and it never revisits. So the V>=3 regime is not "correct behaviour" either — it trades a
   missed generalisation for LIBRARY BLOAT, which the standing vocabulary-tax finding says is paid
   again at every subsequent search.

**So governance has two distinct pathologies either side of V=2**, and neither is the right answer
(keep the generalisation, drop the specialisations it subsumes). The honest version of S16's
interpretation is therefore narrower and sharper: not "the system is biased against parameterized
abstractions", but **"greedy-MDL over program size never prunes a specialisation its own
generalisation subsumes — below V=3 that shows up as specialising instead of generalising, above it
as doing both."**

### S18 — a SECOND task family, anchored: `a740d043` (crop-and-recolour)
([`anchor_a740d043.py`](artifacts/anchor_a740d043.py) · [`.out`](artifacts/anchor_a740d043.out))

Every real-task ladder in the batch is two-halves geometry — split + combine, fixed colour
constants, one spine shape — which is why the honest claim has been "an existence result over a
deliberately narrow sample, not a rate". This opens a second family, starting where LADDER-PROCESS
says to start: the anchoring gate, before any floor, spine or demo work.

**The task.** `a740d043`: the background is the most common colour; the answer is the bounding box
of the non-background content with the background recoloured to 0. Structurally unlike the existing
family, and it routes the background through a **perceiver** (`most_common_color`) rather than a
literal.

**All four candidate terms anchor 4/4** (3 train + 1 held-out test):

| term | verdict |
| --- | --- |
| `map_color(crop_to_content(g), 1, 0)` | anchored — **but see the trap** |
| `map_color(crop_to_content(g), most_common_color(g), 0)` | anchored — the honest form |
| `map_color(crop_to_mask(g, nonbg_mask(g)), mcc(g), 0)` | anchored |
| `map_color(crop_to_mask(g, mask_complement(mask_by_color(g, mcc(g)))), mcc(g), 0)` | anchored |

**The literal form is a trap, and testing the cheap readings first is what caught it.** Every
example in this corpus happens to have background 1, so `map_color(..., 1, 0)` passes ground truth
while computing the wrong function — precisely what the `constancy` check exists to catch. The
perceiver form is the anchor; both are pinned, and a test asserts they agree on every example so the
withheld route provably computes the same competence.

Pinned permanently as `tests/program_search/ladders/test_a740d043_anchor.py` — deliberately NOT in
`test_real_arc_anchoring.py`, which is keyed by ladder name and so cannot cover a task that has no
ladder yet. This is the anchor-before-ladder case the process asks for.

**The ladder this affords, designed but not built.** `d_raw` is only 2 with `crop_to_content`
gifted, which would fail `raw-intractable` outright — so the floor must withhold it, and that is
what makes the task laddered rather than trivial:

- **Cheap variant (1 rung, all-Grid, all-d2).** Floor `{crop_to_mask, nonbg_mask, map_color,
  most_common_color}`; r1 `crop_to_content(g) = crop_to_mask(g, nonbg_mask(g))` (d2, Grid-valued,
  full-solution demos); top d2 over L_1; `d_raw` 3. Lands in the cheap regime by S13's predicate
  (rung levels d2, top d2). Thin at one rung, but it is the ready-made gen/full contrast the rung
  register already names for `crop_to_content`.
- **The valuable variant (2 rungs) is Cohort-B-shaped.** Withhold `nonbg_mask` too: r1
  `nonbg_mask(g) = mask_complement(mask_by_color(g, most_common_color(g)))` is **Mask-valued**, so
  it cannot be demoed as a full solution (a task solution must produce a Grid) and needs a wrapper —
  the demo-affordability law, costing a depth level. That is exactly the fragment-demo shape
  cfb2ce5a Cohort B was for, and the one arm-shape S15 identified as necessary for
  proposer-agnostic claims, since a full-solution demo puts the target in `AntiunifyPairs`' regime
  by construction.

**Stopping here deliberately.** The gate is passed and pinned, which is the durable result; the
2-rung variant's wrapper demos are the known-expensive authoring case and deserve a clean run at it
rather than a rushed one. Design recorded in [LADDER-IDEAS.md](../../docs/abstraction_ladders/LADDER-IDEAS.md).

---

### S19 — the `a740d043` ladder: a lint defect found on the way, and a conviction that generalises

Picking up S18's explicit next step (build the ladder). Two results, one machinery and one
scientific; the second is the more important and it is **negative**.

#### S19a — `proposer-compat`'s capability table was wrong, and it passed unlearnable ladders

Designing the rung set needed the answer to "which proposer can serve which demonstration kind",
so I read the table rather than trusting it. `checks/learnability.py::_PROPOSER_CAPABILITIES`
credited the `FrequentSubtree` family with `FULL_SOLUTION`. It cannot serve it:
`antiunify.py:168` mines `list(program.walk())[1:]` — **each program's own root excluded** — so a
rung demonstrated as a whole solution is precisely the one template it can never offer. That is the
same mechanism S15 measured (0/4, 0/5 recovery) but stated at the level of the *checker*: the lint
would PASS a ladder no configured machinery could climb, and the stall would only surface as
unrecovered rungs after a full run.

Measured every entry rather than extrapolating
([`proposer_compat_defect.py`](artifacts/proposer_compat_defect.py)):

| proposer | `full_solution` | `fragment_identical` | table said | verdict |
| --- | --- | --- | --- | --- |
| `AntiunifyPairs` | **yes** | no | `{full}` | correct |
| `FrequentSubtree` | **no** | yes | `{full, fragment}` | **`full` wrong** |
| `TypeScopedFrequentSubtree` | **no** | yes | `{full, fragment}` | **`full` wrong** |
| `SearchScopedFrequentSubtree` | **no** | yes | `{full, fragment}` | **`full` wrong** |
| `StitchProposer` | **yes** | **yes** | all kinds | correct |

**The two miners are complementary, not nested** — the table modelled `FrequentSubtree` as a
superset of `AntiunifyPairs`; each is in fact blind exactly where the other sees. Only Stitch spans
both. The direct consequence for design: **a single-proposer ladder cannot mix demonstration kinds
across its rungs**, which is a much stronger constraint than the table implied.

**A false start, recorded because it nearly shipped.** My first fixture gave Stitch two *identical*
wrappers, and Stitch offered the wrapper instead of the fragment — which read as "Stitch can't serve
`fragment_identical`" and would have been a wrong correction to a shipped check. With identical
wrappers the whole root *is* the best compressor; `fragment_identical` means the fragment recurs
across **distinct** solutions, so distinct wrappers are the faithful fixture. With those, Stitch
offers the target exactly. The table's Stitch row is fine.

**Retrodiction, exact.** `al4-mask-crop` is the batch's only `FrequentSubtree` ladder. Corrected
check flags r2 `flatten_content` and r3 `stamp` (both `full_solution`) and clears r1 `nonbg_mask`
(`fragment_identical`). The register records of its real run: *"Rung recovery: r1 only."* The
corrected check would have predicted that statically, in ~1s, before the run.

Fixed, with the mechanism documented at the table. Blast radius swept across the whole registry:
**al4 alone**, already retired-rejected. Pinned by
`tests/program_search/ladders/test_proposer_capabilities.py`, which drives the real proposers rather
than restating the table (the drift mode is precisely a table that stops matching its machinery).

#### S19b — the ladder: lint-clean, probe-convicted in ~2 seconds

Built `a740d043-crop-normalize` per LADDER-PROCESS. Terms verified against the evaluator before
authoring ([`gen_a740d043_ladder.py`](artifacts/gen_a740d043_ladder.out)): the floor withholds the
whole crop tier (`crop_to_content`, `crop_to_mask`, `bbox_mask`), leaving the **Rect** route
`crop_rect(g, bbox(nonbg_mask(g)))`, which agrees with S18's anchored term on all examples. One
Grid-valued rung `content_box`; top `map_color(content_box(input), 1, 0)`.

Two design decisions worth their reasons:

- **The literal `1`, not `most_common_color(input)`.** Every a740d043 example has background 1, so
  the perceiver form is a train-constant subterm beaten by an enumerated literal and
  `constant-subterm` rejects it — correctly. The ladder therefore claims the **crop** abstraction
  only, and makes no perceiver claim. (S18 flagged exactly this trap; here it bites for real.)
- **Exactly one rung**, because S19a's corrected table forbids mixing demo kinds: the finer cuts sit
  at the `Mask` and `Rect` intermediates, which cannot be demoed as whole solutions, and
  all-wrapper demos is `al4-mask-crop`'s retired shape.

Depths asserted in both units (`compositional_depth` == `min_depth_limit`; every term is
first-order, so they must coincide, and if they ever diverged the stated jumps would not be the
budgets the levels actually need): `d_raw` 4, jumps [3, 2]. Lint: **OK, 0 errors**, `b1` 101.

**The probe convicted r1 in ~2 seconds:**

```
! skip a740d043: SKIP PATH -- L_0 solves it:
    crop_rect(map_color(input, 1, 0), bbox(nonbg_mask(input)))
```

Verified independently: depth **3**, correct on all four examples including the held-out test.

**My hand skip-audit was wrong, and how it was wrong is the finding.** It argued no floor route
reaches the *content box* in under 3 steps — true, and irrelevant. A skip search does not have to
build the rung; it has to solve the **top**, by any route. `crop_rect(grid, rect)` takes its two
arguments independently, so a grid-side transformation hoists past it: a pointwise recolour and a
subrectangle selection touch disjoint aspects of a grid and therefore **commute**. Pushing the
recolour inside drops the top from the authored depth 4 to an actual depth 3 — exactly the rung's
own jump, so the rung buys nothing and the level that can afford it can already finish.

**The law this makes explicit:**

> A competence that factors into **commuting** operations cannot be laddered by cutting between
> them — the skip search simply reorders them.

For `a740d043` that exhausts the design space, so the task admits **no** ladder over this substrate:
cut between crop and recolour → skip path (proved); cut inside the crop → `Mask`/`Rect`-valued rungs
→ wrapper demos → al4's retired shape; cut nowhere → the rung is the task. Kept in the registry as
a recorded conviction with its testbed, the wrong audit corrected in the file itself.

It also explains **retroactively why the two-halves family ladders at all**: its spine
(split → recolour → merge → invert) does **not** commute — you cannot invert before merging. That
reframes the batch's task choice as load-bearing rather than incidental, and it is the same
algebraic law that convicted the `dae9d2b5` merge rung earlier, now stated generally instead of as
a one-off.

**A limitation of the static gate, stated plainly.** The linted `d_raw` (4) is the depth of the
**authored** route inlined; it is an **upper bound** on the true raw depth (3), because nothing
static searches for a cheaper algebraically-equivalent route. Only the probe finds it. No machinery
gap here — this is the "the probe convicts; only the certificate acquits" layering working exactly
as designed, for ~2 seconds against the cost of a full run. Worth recording because a reader of
`spec.md` could otherwise take `d_raw` as measured rather than authored.

**Designed, not built:** a synthetic **non-commuting twin** of this task (make the recolour's colour
depend on the crop) is the control the law predicts should become admissible. It is the cleanest
available test of the law and the natural next build.
