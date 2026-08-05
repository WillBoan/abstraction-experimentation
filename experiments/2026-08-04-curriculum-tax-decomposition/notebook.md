# Curriculum-tax decomposition: what every climb actually spent, by class (2026-08-04)

A read-side investigation, zero new searches. The [tax-math notes](../../docs/abstraction_ladders/2026-07-29_chatgpt%20-%20tax%20math.md) formalized the curriculum tax as a lower-rung / current-rung / higher-rung (LR/CR/HR) decomposition with closed-form invocation counts. This asked: **what does that decomposition actually look like on the 21 recorded climbs** — and it had a puzzle to resolve, because two recorded facts made contradictory predictions about the split:

- per-iteration climb costs are nearly **flat** (`split-recolor-lean`: 32,665 / 32,837 / 33,009), suggesting iteration cost is dominated by one constant component;
- the 2026-07-23 **skip-solved** schedule arm saved **1.8–2.5x** by removing re-search of solved tasks, suggesting LR is roughly half the bill.

Both turn out to be right, and the resolution is one of the findings.

## Method — and what can count as a finding here

[`artifacts/curriculum_decomposition.py`](artifacts/curriculum_decomposition.py) — output: [`curriculum_decomposition.out`](artifacts/curriculum_decomposition.out) (summary tables) and [`curriculum_decomposition.json`](artifacts/curriculum_decomposition.json), which persists the **439 per-(task, wake) rows**; every aggregate below is a derivation from them.

For every batch member with a committed `report.json`, follow `provenance` to the `climb/learn` run dir and read `trace.jsonl`: per wake iteration, per task, `total.considered`, `solutions.first_index`, and the solved list. Classify each (task, wake) search by **realized** solve status: CR at its first-solve wake, HR before it, LR after it, **UN** if it never solves in the climb (kept separate from HR — a task unreachable at _every_ wake is a different defect from a task attempted prematurely). Cost under two accountings from the same records:

- **actual** = `considered` (what the run paid under its own stop mode);
- **to-first** = `first_index + 1` where the search solved, `considered` otherwise — the counterfactual stop-at-first bill, exact because `first_solution_index` is stop-independent.

**The evidential frame, stated before the numbers.** Every quantity here factors through three channels: **design** (authored geometry determines the class _counts_ exactly — the invocation identities are arithmetic: every task pays exactly R non-current runs), **settings** (stop mode + budgets determine the class _cost rules_: exhaustion pays the space, stop-first pays solution rank, an unreachable search pays min(space, guard) either way), and the **residual** (what neither predicts: actual space sizes under semantic dedup, growth under mints, where solutions sit in enumeration order, mint timing). The separation test for any number below: _could it have been computed from the `.ladder` file and config before the run?_ If yes, it is an artifact of our own decisions — at best a confirmation of the mechanism model. Findings are residuals from that null, or mechanism laws with stated scope; the sound claim shapes are **within-member contrasts** (settings varied, design held) and **license-matched comparisons** (design varied, task x floor held). Pooled aggregates vary everything at once and license nothing — they appear below only as store bookkeeping. (This is AL-PLAN-2026-08-04 decision 7.)

Further caveats: the classification is realized, not authored (an authored-rung join is also computed and reported separately); the CR denominator throughout is the **climb's own** current-rung compute — not the oracle chain's marginal, and not `C_optimal`, which requires a CR-only arm that has never run (Phase 1 item 6); the to-first counterfactual ignores generation-end granularity. All 21 members' cells are single-generation (the 2026-08-04 re-baseline). Data vintage: this describes the store as of 2026-08-04 — the register moved to uniform exhaustive accounting on 2026-08-05, so the stop-first segment below describes runs that remain recorded but are no longer any member's register configuration.

## Findings I — mode-conditional laws (settings varied within member, design held)

**Which class dominates is an accounting-mode artifact.**

| segment                                 | CR    | LR        | HR        |
| --------------------------------------- | ----- | --------- | --------- |
| 15 exhaustive-mode members, actual      | 33.2% | **42.7%** | 20.8%     |
| same members, to-first counterfactual   | 34.5% | 5.6%      | **56.0%** |
| 4 healthy stop-at-first members, actual | 10.1% | 7.4%      | **82.6%** |

Under generation-end accounting, a solved task's re-search still exhausts its depth-limited space — so every task pays roughly the same per wake regardless of class. That is why iterations are flat (cost ≈ n_tasks x per-task exhaustion, creeping ~0.5%/wake with mints), and why LR is the largest slice (~43%), which is exactly what skip-solved's 1.8–2.5x was collecting: the puzzle dissolves. Under stop-at-first, re-finds are nearly free and the split inverts to HR-dominated — the two `nor-recolor` members (5-wake, stop-first) measure **69.8% / 71.0% HR share**, the tax-math notes' worked example (70%) realized in the store. Any cross-member curriculum-tax comparison must therefore stratify by accounting mode.

**M ≈ H under exhaustion.** If per-search cost is class-independent, the compute multiplier equals the invocation multiplier by arithmetic — so the _finding_ is the measured deviation being small: M/H = 1.00–1.04 on 11 of 15 exhaustive members (per-class mean costs 8,979 / 10,217 / 8,170), i.e., space size is nearly task- and class-independent there. Where the deviation is not small (1.24–1.27, tiny-pool synthetics), that excess is residual signal — mints matter more when the space is small. Stop-first members deviate 1.31–16.4x (1,533 on the broken-top members): the deviation _measures_ class-cost inequality.

**ρ flips sign with the stop policy.** LR drift ρ (re-search cost / that task's own CR cost), median per member: exhaustive **1.0–1.2** — re-search costs slightly _more_ each wake as mints grow the space (up to 3.8 on tiny synthetic spaces), confirming BREADTH-AXIS C ("minting does not reduce search cost mid-climb") per-member; stop-first **0.85–0.93**, falling to **0.47** at distance 4 — re-finding beats the original solve because the mint made the solution shallower. Both opposing forces from the tax-math notes exist; **which wins is chosen by the stop policy, not by the library.**

## Findings II — residuals (what no static instrument currently predicts)

- **~0.5%/wake cost creep** under exhaustion — the vocabulary tax operating inside the loop.
- **Per-task cost spread at one budget**: 3,889 vs 5,777 considered for two tasks under the same library and budget — semantic dedup is data-dependent, and this heterogeneity is the hard part of any pool-aware predictor.
- **Multi-mint schedule compression**: sleep mints more than one rung per iteration on these demo corpora, so the realized climb runs AHEAD of the authored one-level-per-wake schedule on **140 of 439 rows (12 of 21 members) — and never behind**. The zero-behind half is _derivative_ of 100% rung recovery under the default metric (a mint lands every productive iteration), not independent evidence. The nine zero-mismatch members are exactly the one-rung-per-level synthetics.
- **Solution churn is universal**: every climbing member rewrites every acquired task's retained program at least once (post-mint re-compression); zero solve regressions anywhere.

## Findings III — per-cell facts (mostly derivable, and stated as such)

An unreachable search pays min(space, guard). Given that the full schedule attempts the top at wake 0 by design, the dramatic numbers follow: `split-asym-lean`'s wake-0 top attempt censors at exactly **2,000,000**; one wake later, post-mint, the same top solves for **64,178** (`split-halves-lean`: 2,000,000 vs 62,040) — one attempt at 31x the eventual useful work, putting those members' full-vs-CR multipliers at **13.4x / 32.9x** where all-d2 members sit at 3.0–4.0x (reproducing the recorded loop overheads, which were only ever measured on the schedule shape that minimizes them). The residual content in these cells is only "the space exceeds the guard there"; everything else is schedule design plus the cost rule.

Utilization, with the binding decision recorded per cell (`binding` ∈ guard / solution / space): exactly **2 guard-bound cells exist in the store** — the two premature-top censors (u = 1.0). The `nor-halves` unreachable tops are **space-bound** (exhausting at ~1.7–1.8M, below the 2M guard): raising the guard provably buys nothing there.

## Findings IV — instrument results

- **The UN share re-detects defects.** The two `climb-budget-covers-top` members are flagged by their UN mass alone (99.9% of their climbs) — the decomposition works as a per-member diagnostic independent of any sample claim.
- **Heavy tails are mode-dependent, so medians are mandatory**: stop-first CR mean 26,496 vs median **284** (93x apart — the mean is the d3-top solves, the median a demo re-find); LR mean 8,755 vs median 266. Exhaustive members are tail-light (means ≈ 2–3x medians).
- **Identities verified**: `M = 1 + tau_LR + tau_HR + tau_UN` holds to float noise (worst abs err 4.6e-13; the transcript's form without `tau_UN` suffices on 18/21). Invocation identities exact — every climb ran every task every wake; early-stop cuts wakes, never within-wake tasks. The authored-rung join is clean (0 unmapped tasks; top level = shape height on 21/21).

## Store bookkeeping (planning input — not findings)

Pooled, compute-weighted, across all 21 climbs (19,456,316 considered): **CR 9.6% / LR 11.0% / HR 42.6% / UN 36.8%**. This is a fact about where this repo's climb compute historically went — dominated by the two known-broken members and the pathological cells — and licenses nothing beyond planning (it is one reason the schedule census is worth building). The per-member view is in Findings I; the UN detail: each `nor-halves` member burns ~3.5M re-exhausting its unreachable depth-4 top every wake.

**The removable bill.** A CR+LR schedule with to-first stopping — keep re-searching solved tasks (the recurrence evidence), never attempt not-yet-reachable ones, stop when found — costs a **median ~7.7x less per member** (range 1.9x–1716x; the extremes are the broken-top members; pooled 9.1x, bookkeeping). Two caveats are part of the result: CR+LR requires knowing which tasks are reachable — an oracle privilege, so this prices the curriculum-order prior rather than promising a blind learner the discount — and to-first forfeits the exhaust-mode quantities.

## Scope — what generalizes, and why

The mode-conditional laws generalize to unseen ladders _run under this machinery_ because they are mechanism-backed (we can say why they happen), not because this sample represents any population — it is a designed convenience set. The residuals are empirical facts about these runs, candidates for laws only if they recur with a mechanism. The per-cell and bookkeeping numbers are scoped to their cells and to the store respectively. Operationalized going forward (plan decision 7 + the Phase 0 item 5 spec): the schedule census emits each member's _predicted_ class profile — counts from the invocation identities, costs from the mode rules x breadth-census space estimates — and the ladder report renders measured vs predicted, so a share matching its prediction displays as model confirmation and "finding" means a recurring residual.

## Decisions and follow-ups this sets up

1. **The CR+LR arm** is the obvious next new-runs experiment, with registered predictions: mints byte-identical to the full schedule (sleep consumes solutions only; HR contributes none), savings per the table above. A confirmation makes "HR is deadweight, LR is the evidence" a measured statement.
2. **Mode stratification** is a demonstrated comparability wall; any renderer adoption of these metrics carries it.
3. The **full-frozen replay cell** (full schedule against chain libraries, learning off) remains the missing cell for splitting overhead into direct tax vs learning effect — and hosts the deferred old-solution replay (`G_new_abstraction`).
4. Report metrics worth promoting: class shares (both accountings), M vs CR, ρ drift, churn, utilization/binding — rendered measured-vs-predicted per decision 7.

## Runs

One `climb/learn` run per member, resolved via each report's `provenance` (this investigation read them; it wrote nothing):

| member | mode | wakes | climb/learn run |
| --- | --- | --- | --- |
| `94f9d214-nor-halves` | stop-first | 2 | [`8e85f48b2b91`](../../runs/2026-08-04/20260804_203853_8e85f48b2b9165b2/) |
| `94f9d214-nor-merged` | exhaustive | 4 | [`086d1d688536`](../../runs/2026-08-04/20260804_204303_086d1d6885366c2f/) |
| `94f9d214-nor-recolor` | stop-first | 5 | [`0988e459b009`](../../runs/2026-08-04/20260804_204319_0988e459b009d2bf/) |
| `al1-mirror` | exhaustive | 3 | [`c7dfd456076f`](../../runs/2026-07-22/20260722_212625_c7dfd456076ff761/) |
| `al12-unlearnable` | exhaustive | 1 | [`89868769ca0f`](../../runs/2026-08-03/20260803_201507_89868769ca0f82a3/) |
| `al15-shift-frame` | exhaustive | 3 | [`551e05c8a268`](../../runs/2026-08-03/20260803_203101_551e05c8a2682815/) |
| `al16-layout-nest` | exhaustive | 3 | [`40f4b8b641c2`](../../runs/2026-08-03/20260803_203107_40f4b8b641c27ffe/) |
| `al17-shift-frame-tall` | exhaustive | 4 | [`0efac0e88832`](../../runs/2026-08-03/20260803_203110_0efac0e88832553c/) |
| `al18-fanin-rotate` | exhaustive | 3 | [`8b85d26c47cb`](../../runs/2026-08-03/20260803_203118_8b85d26c47cbb3bc/) |
| `al19-fanin-recolor` | exhaustive | 3 | [`df41a6982550`](../../runs/2026-08-03/20260803_203122_df41a6982550d948/) |
| `al2-rot90-calibration` | exhaustive | 2 | [`35afb03c8453`](../../runs/2026-07-22/20260722_212647_35afb03c8453bd6d/) |
| `al20-recolor-telescope` | exhaustive | 3 | [`9a84ca44c492`](../../runs/2026-08-03/20260803_203141_9a84ca44c49201a7/) |
| `al21-dag-siblings` | exhaustive | 2 | [`2394300fc190`](../../runs/2026-07-26/20260726_204628_2394300fc1908dd5/) |
| `dae9d2b5-half-param` | exhaustive | 3 | [`e4e4de51d57e`](../../runs/2026-08-04/20260804_204715_e4e4de51d57e92d0/) |
| `dae9d2b5-split-asym-lean` | stop-first | 2 | [`be4030ec02ca`](../../runs/2026-08-04/20260804_204726_be4030ec02ca0843/) |
| `dae9d2b5-split-halves-lean` | stop-first | 2 | [`5c799e43ffce`](../../runs/2026-08-04/20260804_205018_5c799e43ffceb15b/) |
| `dae9d2b5-split-recolor` | exhaustive | 3 | [`487c5429df52`](../../runs/2026-08-04/20260804_205445_487c5429df52813b/) |
| `dae9d2b5-split-recolor-lean` | exhaustive | 3 | [`73adf3163f43`](../../runs/2026-08-04/20260804_210335_73adf3163f43e703/) |
| `fafffa47-nor-halves` | stop-first | 2 | [`ec9a6c359f3b`](../../runs/2026-08-04/20260804_210543_ec9a6c359f3bee50/) |
| `fafffa47-nor-merged` | exhaustive | 4 | [`85a670b006cc`](../../runs/2026-08-04/20260804_211056_85a670b006cc8638/) |
| `fafffa47-nor-recolor` | stop-first | 5 | [`cdb04726cab1`](../../runs/2026-08-04/20260804_211116_cdb04726cab17892/) |
