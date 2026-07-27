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
