# Configured compression and held-out enablement cases

**Date:** 2026-07-08 · **Machinery:** the F5 transfer-measurement layer (`learn/harness.py`, `learn/experiments.py`; MACHINERY.md F5) · **Frame:** [RESEARCH-2026-07-08.md](../../docs/archive/RESEARCH-2026-07-08.md) (the measurement-bottleneck thesis).

> **Reviewed interpretation (2026-08-12).** Logged historically in [EXPERIMENT_LOG.md](../../EXPERIMENT_LOG.md) (2026-07-08), anchored to commit `cda7c91`. These nine heterogeneous microworld points do not support a correlation estimate or a general statement that compression predicts—or fails to predict—reuse. E8's interpretable contrast changes the configured proposal set while holding the corpus, MDL selector, and consumer fixed; it is not selector-only. Held-out counts are budget-relative instance enablement. The historical analysis below is preserved with these limits.

## Reviewed question

Held-out instance enablement is measurable. The supported question is whether the instrument detects the configured E8 proposal-set contrast. The cross-experiment scatter remains descriptive because the tasks, held-out denominators, floors, proposal mechanisms, and budgets differ.

## Setup

- **Grade:** `heldout_transfer(base, aug, heldout_ids) = (aug.solved_ids − base.solved_ids) & heldout_ids`, measured at the **shallow enablement budget** (`enablement_search`). The point of the shallow budget: it's too tight to assemble the multi-step solution from scratch, so the abstraction only "counts" if it collapses depth enough to bring a held-out task into reach. (At the deep budget the base reaches them too, and transfer ≈ 0.)
- **Harness:** `compression_transfer_correlation` over the E1–E9 registry → [`artifacts/run_correlation.out`](artifacts/run_correlation.out).
- **Within-case contrast:** E8 with the **naive** `FrequentSubtree` proposal set vs. the registered **search-scoped** proposal set — same corpus, six held-out tasks, MDL selector, and consumer; proposals and the resulting minted abstraction differ.
- **Decomposition:** per experiment, held-out tasks the base (L1) vs. learned (L2) library solves at the shallow budget → [`artifacts/transfer_breakdown.out`](artifacts/transfer_breakdown.out).

## What ran & found

Scatter (compression = L1→L2 re-solve DL ratio; transfer shown as newly-enabled / held-out size):

| exp                    | compress    | transfer | tr_speedup  |
| ---------------------- | ----------- | -------- | ----------- |
| e1-rot90               | 1.30        | 1/4      | 1.58        |
| e2-swap-cells          | 6.42        | 2/2      | 104         |
| e3/e4-swap-cols        | 4.69 / 2.44 | 2/2      | ~90         |
| e5-rederive-rot90      | 0.99        | 2/2      | 1.00        |
| e6-rederive-d4 (naive) | 0.83        | 1/6      | 1.00        |
| e7-rederive-d4-safe    | **0.79**    | **6/6**  | 1.00        |
| e8 / e9-mirror-index   | 1.12        | 5/6      | 3.47 / 5.00 |

**Decision trail / dead-end.** The first cut computed the usefulness `speedup` from the _shallow_ enablement run → mostly < 1 (a larger library considers more nodes per depth; misleading). Fixed to the **deep-search** speedup restricted to train — now matches the canonical figures (E8 ×3.47, E9 ×5.00, E2 ×104). `harness.py::train_usefulness` now takes both the deep and the shallow run pairs (speedup from deep, enablement from shallow).

**Held-out decomposition** (`transfer = L2 solves − base solves`, on held-out):

- **E2–E5, E7:** base solves 0 (deep floor→target gap) → the abstraction unlocks all → transfer 100%.
- **E1:** base already solves **3/4** — rot90 is only 2 steps from `{flip_h, transpose}`, within the base's shallow reach → transfer 1 means _shallow gap_, **not** a bad abstraction.
- **E6:** base 0/6, but the **naive proposer's broken (scope-violating) abstractions** generalise to only 1/6.
- **E8/E9:** base solves **1** (`transpose` — the shallowest member, `read(g,$1,$0)`, no arithmetic) → the single learned `mirror_index` unlocks the other 5 → transfer 5/6.

## Historical findings, narrowed by the reviewed interpretation

1. **The heterogeneous scatter contains illustrative divergences, not a correlation result.** E7 has compression ×0.79 and held-out instance enablement 6/6, while E2 has ×6.42 and 2/2, but their tasks, denominators, floors, and mechanisms differ.
2. **The instrument reads the configured E8 proposal-set contrast:** naive proposals → 0/6 held-out instances newly enabled; search-scoped proposals → 5/6, with corpus, MDL selector, and consumer fixed. Because the proposal set changes, this is not a selector-only ablation.

Together these cases motivate explicit downstream estimands when proposal or governance mechanisms are compared. They do not establish a general compression/reuse relationship or a generally correct selector.

## Caveats / open

- **Not normalised.** Raw transfer counts are bounded by per-experiment held-out size (E1: 4, E2–E5: 2, D4: 6) and are budget-relative (E1's low count is base-reach, not abstraction quality). Cross- experiment integer comparison is rough; the **within-experiment** naive-vs-scoped contrast is the clean signal. → a normalised transfer (fraction of newly-reachable) is a TODO.
- **x-axis is full-corpus re-solve DL**, not the **train-DL** the greedy governance actually optimises. The divergence is sharper at the train-DL level (cf. the E8/E9 entry, where the naive read-bodies compress _train_ more). A train-DL-vs-transfer plot is the more pointed version.
- **Microworld scale (9 heterogeneous points):** illustrative, not a statistical correlation analysis. A future relationship study would need a common estimand, comparable units, and a pre-specified design.
