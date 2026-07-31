# Compression↔transfer correlation — the first experiment the measurement layer enables

**Date:** 2026-07-08 · **Machinery:** the F5 transfer-measurement layer (`learn/harness.py`, `learn/experiments.py`; MACHINERY.md F5) · **Frame:** [RESEARCH-2026-07-08.md](../../docs/archive/RESEARCH-2026-07-08.md) (the measurement-bottleneck thesis).

> logged in [EXPERIMENTS.md](../../EXPERIMENTS.md) (2026-07-08), anchored to commit `cda7c91`. Drains the queued **compression↔transfer correlation** row.

## Question

Held-out transfer is now measurable (the grade the disciplines rest on — previously an IOU). Two questions: (1) **does compression predict transfer** across E1–E9? (2) does the instrument read the **E8 compression/reusability divergence** — does the compression-greedy abstraction score _worse_ on transfer than the reusable one?

## Setup

- **Grade:** `heldout_transfer(base, aug, heldout_ids) = (aug.solved_ids − base.solved_ids) & heldout_ids`, measured at the **shallow enablement budget** (`enablement_search`). The point of the shallow budget: it's too tight to assemble the multi-step solution from scratch, so the abstraction only "counts" if it collapses depth enough to bring a held-out task into reach. (At the deep budget the base reaches them too, and transfer ≈ 0.)
- **Harness:** `compression_transfer_correlation` over the E1–E9 registry → [`artifacts/run_correlation.out`](artifacts/run_correlation.out).
- **Within-experiment control:** E8 with the **naive** `FrequentSubtree` proposer vs. the registered **search-scoped** one — same 6 held-out tasks, only the minted abstraction differs.
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

## Findings

1. **Compression does not predict transfer.** E7 is the star witness: _worst_ compression (×0.79 — six verbose-but-correct abstractions inflate the small train corpus's DL) yet _perfect_ transfer (6/6). E2: best compression (×6.42), transfer 2/2. Train-DL shrinkage and held-out enablement measure different things and can point opposite ways.
2. **The instrument reads the E8 divergence cleanly, within-experiment:** naive proposer → transfer **0**, search-scoped → transfer **5** (same 6 held-out tasks). The compression-greedy pick (two `COLOR` read-bodies) transfers to _nothing_; the reusable `mirror_index` transfers to 5.

Together: the empirical case for **selection-correct governance** (score candidates by usefulness/transfer, not train-DL node-count), and a validation of the measurement-bottleneck thesis — the grade had to exist before the governance objective could even be defined.

## Caveats / open

- **Not normalised.** Raw transfer counts are bounded by per-experiment held-out size (E1: 4, E2–E5: 2, D4: 6) and are budget-relative (E1's low count is base-reach, not abstraction quality). Cross- experiment integer comparison is rough; the **within-experiment** naive-vs-scoped contrast is the clean signal. → a normalised transfer (fraction of newly-reachable) is a TODO.
- **x-axis is full-corpus re-solve DL**, not the **train-DL** the greedy governance actually optimises. The divergence is sharper at the train-DL level (cf. the E8/E9 entry, where the naive read-bodies compress _train_ more). A train-DL-vs-transfer plot is the more pointed version.
- **Microworld scale (9 points):** illustrative, not statistical. The real correlation is a real-ARC job — which is exactly what the grade was built to make readable.
