# Curriculum accounting over recorded climbs (2026-08-04; reviewed 2026-08-12)

> **Current interpretation.** This was a read-side analysis: it ran zero searches and classified work already present in completed traces. Its 439 `(task, wake)` rows are nested within 21 authored climbs and still fewer task/floor families. The analysis supports same-trace accounting identities, diagnostics, and conditional predictions. It does not replay a different stopping or scheduling intervention, identify causal “deadweight,” or estimate a population of learning trajectories.

The source calculations and outputs are preserved in [`artifacts/curriculum_decomposition.py`](artifacts/curriculum_decomposition.py), [`curriculum_decomposition.out`](artifacts/curriculum_decomposition.out), and [`curriculum_decomposition.json`](artifacts/curriculum_decomposition.json). The current cross-repository interpretation is in [EXPERIMENTS.md](../../EXPERIMENTS.md).

## Question and unit of analysis

The original question was where recorded climb work fell relative to a task's first successful wake. For each completed trace row, the script labels the search:

- **CR**: the task's first successful wake;
- **LR**: a later re-search after the first success;
- **HR**: a pre-first-solve attempt; or
- **UN**: a task never solved anywhere in that recorded climb.

`HR` therefore means **pre-first-solve**, not “unreachable,” “useless,” or “deadweight.” `UN` means never solved in that finite recorded climb, not universally unreachable.

The observational units are not independent. There are 439 row-level classifications, but only 21 authored climbs, with repeated tasks, related configurations, and fewer underlying task/floor families. Pooled row shares are store-budget bookkeeping only.

## Two views of the same trace

For a solved search, the trace records both:

- `considered`: what that run paid under its configured stopping mode; and
- `first_index + 1`: the rank of the first solution in that same enumeration trace.

Using `first_index + 1` to relabel an exhaustive trace is an **oracle same-trace accounting estimate**. It answers how many candidates precede the already-observed first solution. It is not an executed stop-at-first arm.

Actually stopping earlier may change later caches, retained pools, learned libraries, wake count, proposal opportunities, and—for any future nondeterministic engine—RNG state. Consequently, differences between `considered` and `first_index + 1` are not automatically a removable compute bill.

## Identities and conditional predictions

The invocation-count relations are arithmetic consequences of the authored full-wake schedule. The script verified, to floating-point tolerance,

`M = 1 + τ_LR + τ_HR + τ_UN`.

Every recorded full-schedule climb attempted every task at every executed wake; early convergence shortened the number of wakes, not the task list within a wake. These are schedule identities, not empirical laws.

Conditional predictions follow from the same accounting:

- Under exhaustive generation-end search, a solved re-search may pay the whole configured space again, so LR can be large.
- Under stop-at-first accounting on the same trace, a previously found shallow program can make LR appear much smaller.
- A never-solved task pays `min(space, guard)` in its observed cell.

These statements explain what the configured accounting should do. Residual variation—semantic dedup, pool growth, solution rank, and mint timing—remains empirical within the recorded cells.

## Recorded descriptive results

The retained tables are descriptive summaries of this authored store:

| segment | CR | LR | HR |
| --- | ---: | ---: | ---: |
| 15 exhaustive-mode members, recorded `considered` | 33.2% | 42.7% | 20.8% |
| same members, oracle same-trace first-solution accounting | 34.5% | 5.6% | 56.0% |
| 4 healthy stop-at-first members, recorded `considered` | 10.1% | 7.4% | 82.6% |

Within 11 of 15 exhaustive members, the observed compute multiplier divided by the invocation multiplier was 1.00–1.04. That is a configured confirmation that per-search costs were similar in those cells, not a general `M ≈ H` law. Values outside that band—1.24–1.27 on small-pool synthetics and 1.31–16.4 on stop-first members—show why the equality must not be exported.

Observed LR-to-CR ratios also depended on stopping semantics: per-member medians were 1.0–1.2 under exhaustive accounting and 0.85–0.93 under stop-first accounting, reaching 0.47 at one recorded distance-four cell. These are conditional measurements, not a universal sign-flip law.

Other retained cell facts:

- Exhaustive cells showed about 0.5% per-wake cost growth in this store.
- Two tasks at one budget considered 3,889 and 5,777 candidates, demonstrating data-dependent semantic-dedup variation in that cell.
- Multi-mint behavior put realized first-solve labels ahead of the authored one-level-per-wake mapping on 140/439 rows across 12/21 members, and behind on none. The absence of behind rows is conditional on the finite set and its recovery behavior.
- Every one of the 21 recorded climbing members changed at least one retained solution after a mint. This is finite **solution churn in 21/21 authored climbs**, not a universal property.
- Exactly two recorded cells were guard-bound; the two `nor-halves` Top cells were space-bound below the guard.

## Pooled store-budget bookkeeping

Across the 21 climbs, 19,456,316 considered candidates were classified as CR 9.6%, LR 11.0%, HR 42.6%, and UN 36.8%. These compute-weighted shares are concentrated by known defective and expensive members. They describe where this store's recorded budget went; they do not estimate how common those classes are.

The historical calculation that a CR+LR plus first-solution accounting would be a median 7.7× smaller per member (range 1.9–1716×; pooled 9.1×) is retained only as an **oracle same-trace accounting estimate**. It assumes knowledge of the already-observed first-solve boundary and holds later traces fixed. It is neither a causal effect nor a principal/removable tax.

## Interpretation changes made in review

- “Higher-rung deadweight” is replaced by **pre-first-solve accounting**.
- “Unreachable” is replaced by **never solved in the recorded climb** unless an independent reachability proof exists.
- “Mode-conditional laws” are now **identities or conditional predictions plus configured observations**.
- Pooled shares and the 7.7× calculation are store bookkeeping, with concentration and nesting explicit.
- Medians remain useful summaries of heavy-tailed cells, but an estimand and unit of analysis are mandatory; “use medians” is not itself a scientific result.
- No claim is made that a CR+LR schedule would preserve mints. Testing that requires a new intervention with registered predictions.

## What a future intervention would need

A causal schedule experiment would pre-register the scheduling policy, stopping semantics, comparison unit, and estimand; run both arms rather than reconstruct one from the other's trace; and compare learned libraries, caches, wake counts, Top reachability, and compute. A frozen replay could answer a different question about direct accounting while explicitly disabling learning. Neither experiment has been executed here.

## Run provenance read by the script

The investigation resolved one `climb/learn` run per member through each committed report's provenance. The 21 members were:

`94f9d214-nor-halves`, `94f9d214-nor-merged`, `94f9d214-nor-recolor`, `al1-mirror`, `al12-unlearnable`, `al15-shift-frame`, `al16-layout-nest`, `al17-shift-frame-tall`, `al18-fanin-rotate`, `al19-fanin-recolor`, `al2-rot90-calibration`, `al20-recolor-telescope`, `al21-dag-siblings`, `dae9d2b5-half-param`, `dae9d2b5-split-asym-lean`, `dae9d2b5-split-halves-lean`, `dae9d2b5-split-recolor`, `dae9d2b5-split-recolor-lean`, `fafffa47-nor-halves`, `fafffa47-nor-merged`, and `fafffa47-nor-recolor`.

Exact run IDs, per-row classifications, aggregates, and calculation code remain in the committed artifacts linked above. This review did not alter those artifacts or create new run provenance.
