# Post-fill re-screen: what the commutative dedup reopened (2026-08-04)

Executes AL-PLAN-2026-08-04 **Phase 0 items 2 and 3**. The [canonical-order fill](../../EXPERIMENTS.md) (commit 69a5368) re-priced every `overlay`-carrying member 2.7–5.1x; two register claims were made under the old prices and flagged as possibly stale: the three `recolor-first` exclusions ("probe INCONCLUSIVE at the cohort guard") and the accounting-mode compromise on six members ("exhaust semantics unaffordable"). This session re-tested both, and re-ran the S13 cut-set screen under the post-fill boundary.

## Item 2a — the three `recolor-first` exclusions are all false post-fill

Re-probed at the unchanged cohort guard (2M), same pinned configs ([artifacts/probe-\*.out](artifacts/)):

| member | pre-fill probe | post-fill probe | skip search (was censored at 2M) |
| --- | --- | --- | --- |
| `dae9d2b5-recolor-first` | INCONCLUSIVE (wake ~2M guard-exhausted) | **2/2 rungs clean** | r1 10,819 · r2 **1,995,669** no-skip |
| `94f9d214-recolor-first` | INCONCLUSIVE (skip censored) | **2/2 rungs clean** | r1 1,788,899 · r2 1,737,296 no-skip |
| `fafffa47-recolor-first` | INCONCLUSIVE (skip censored) | **2/2 rungs clean** | r1 1,841,674 no-skip |

The d3-rung-level class — the exact class the affordability predicate excluded — is now **runnable at the cohort guard, at the guard's edge** (the widest skip exhaustion finishes 4,331 candidates under the 2M limit). Wake cells that were guard-exhausted now cost 10.7k–1.9M. Per the `recolor-solo` precedent, all three were removed from `EXCLUDED` (`batch.py`) and run in full; outcomes below.

## Item 2b — the static re-screen: the cohorts are NOT exhausted any more

[artifacts/cut_set_rescreen.py](artifacts/cut_set_rescreen.py) (S13's enumerator, reporting both boundaries) — [output](artifacts/cut_set_rescreen.out):

- **Pre-fill boundary** (rung levels ≤ 2, top ≤ 3 — fitted 9/9 to pre-dedup outcomes): 3 + 2 affordable, all built. This was the basis of "zero new affordable members exist."
- **Post-fill boundary** (all levels ≤ 3 — justified by the probes above; d4 levels stay dead, `recolor-solo`'s depth-4 chain level still censors): **6 + 9 affordable**, of which **8 are NEW and unexplored** — `dae9d2b5`: `west+recolored_east` [2,3,3], `west+recolored_west+recolored_east` [2,2,3,2]; NOR: `north+south+merged` [2,2,3,2], `north+recolored_north+recolored_south` [2,2,3,3], `north+recolored_south+merged` [2,3,3,2], `recolored_north+recolored_south+merged` [3,3,2,2], `north+south+recolored_north+merged` [2,2,2,3,2], `north+recolored_north+recolored_south+merged` [2,2,3,2,2].

So the 2026-07-27 "cut-set enumeration closes the granularity axis by proof" claim is now scoped: it closed the axis **under the pre-fill cost regime**. The fill moved the boundary, and the design space has 8 unexplored screen-eligible members again (demo blocks reusable verbatim; authoring cost is the template line). Whether to author them is a plan decision (they extend the granularity and decomposition-strategy curves), not part of Phase 0.

A boundary caveat that belongs in any predicate rewrite: "all levels ≤ 3" is a **guard-edge** boundary — the widest measured d3 exhaustion sits within 0.2% of the guard, so members it admits can flip back to censored under any cost regression, wider floor, or larger pool. The honest form of the predicate is the cost-based one (RQ-I): each level's forecast exhaustion must fit the guard.

## Item 2c — the three members, run in full: two admitted, one rejected at the same edge

`run-batch --only <three> --artifacts` (25.5 min, 0 raised, all single-generation):

| member | verdict | top (chain/climb) | rungs | marginal-to-first | note |
| --- | --- | --- | --- | --- | --- |
| `94f9d214-recolor-first` | **ADMITTED** | yes / yes | 2/2 recovered | 368,474 | inherits the cohort's `solution-limit` compromise |
| `fafffa47-recolor-first` | **ADMITTED** | yes / yes | 2/2 recovered | 368,968 | twin-consistent with its sibling to 0.13% |
| `dae9d2b5-recolor-first` | **REJECTED** | chain yes / climb n/a | — | 202,101 (chain) | `no_skip_paths: {1: None, 2: True}` — r1 necessity censored |

Three things worth keeping:

1. **The first decomposition-strategy members are in the batch, and the direction of the old registered prediction inverts on NOR.** The `dae9d2b5-recolor-first` header predicted recolor-first would be _more_ expensive than address-first at the same cut density. On NOR the comparison is licensed — same task, same Floor (the cohort relation), cut direction the only design change — and it flips sign entirely: the address-first 2-rung members (`nor-halves`) have a depth-4 top that censors at every budget ever tried, while recolor-first's schedule ([3,3,3]) keeps every level at d3 — so **recolor-first is the first NOR cut at density 2 whose Top is reachable at all**. Where the cut direction moves depth _across_ the guard boundary, it decides feasibility, not just cost — the standing cost law, now with a cut-direction corollary.
2. **The `dae9d2b5` rejection is the probe contract's designed asymmetry, exemplified.** The probe acquitted (2/2 clean; its r1 skip completed at 10,819 at the consumer's derived budget), but the chain — the admission authority — runs its L0/L1 cells at depth 3 / pool 150 (`pool_for_depth`), the exact regime the pool-wall analysis measured as censoring, and its r1 necessity search censored at the 2M guard. "The probe convicts; only the certificate acquits" — a clean probe never promised admission, and this is the first member where that gap decided a verdict. Possible instrument follow-up (not built): the probe could _warn_ when its skip budget differs from the chain's, since it knows both.
3. **"All levels ≤ 3" is eligibility, not certifiability.** `dae9d2b5-recolor-first` satisfies the post-fill boundary, probed clean, and still rejected on a censored necessity cell — the guard-edge caveat of §2b is a measured fact one hour later. The honest predicate is the cost-based one (RQ-I): each level's _forecast exhaustion_ — wake and skip, at the level's own derived budget including pool scaling — must fit the guard.

## Item 3 — the accounting-mode compromise is removable, and was removed

The arm: `run-batch --only <six carriers> --set budget.solution_limit=null --set budget.solution_limit_mode=generation-end` — every cell of the six `solution_limit: 1` members re-run to generation-end exhaustion at their **unchanged** 2M guards. Wall clock **3.9 h** (1,428s–4,186s per member; manifest in scratchpad, cells recorded under `runs/`).

**Answer: exhaust semantics now fit — and the identification is clean.** Settings were the only varied channel (same members, same designs, same guards; the stop mode alone changed), so the comparison against the record is a within-member contrast. All six members: admitted, rung recovery identical to the record (2/2, 4/4, 3/3, 2/2, 2/2, 4/4), verdict profiles identical, **compromises `[]`**, all single-generation. The `nor-halves` tops remain censored — that is their standing depth-4 broken-top status, not accounting. This **reverses the 2026-08-04 conclusion** ("the `solution_limit` decision was necessary, not a shortcut" — measured when all six exhaustive depth-3 cells censored at 6M–18M guards): the canonical fill's ~4.4x discount brings those exhaustions inside 2M.

**Adopted as the record:** the eight `.ladder` files carrying the pin (the six + both NOR `recolor-first` members, which inherited it from the cohort template) had their `solution_limit` lines removed with a dated note; the register re-baseline cache-hits the arm's own cells, so adoption cost ~nothing beyond the arm. Consequence: the batch's accounting-mode axis unifies on `exhaustive`, which removes the register's last named cross-member comparability wall inside cohorts — restoring the granularity curve as a committed artifact is now unblocked (listed as a follow-up, not done here).

**A cost misestimate, recorded because it repeats a recorded pattern.** I predicted "a few minutes" for this arm; it took 3.9 hours — the same >1-order-of-magnitude miss the pool-wall session logged for its own launches. The cause was derivable from this session's _own_ decomposition data: under exhaustive accounting every task re-exhausts every wake (the M ≈ H law), so a 5-wake, 9-task member with ~1–2M depth-3 cells bills ~50–90M considered — plus the two RQ1 purchasers re-bought raw arms (the arm guard couples to the now-larger exhaustive marginal). The lint-side **schedule census** (Phase 0 item 5) exists to price exactly this statically; this arm is its motivating exhibit.

## Runs

Recorded runs for this session are named in the members' regenerated `report.json` provenance blocks and the register; probe cells under `runs/` are namespaced (`arc-lab runs --probes`).
