# Experiments — reviewed synthesis

> **Reviewed through 2026-08-12 at `449ec1bd0c13e502eb94f965c9df0ae6ac9d3fe4`.**

This document is the current scientific interpretation of the repository's evidence. [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) is the chronological working record and intentionally preserves claims as they were made, including claims later narrowed or retired.

## 1. Scope and evidence basis

This repository studies authored abstraction-learning trajectories with one deterministic typed bottom-up enumerator. A trajectory declares a primitive floor, intermediate routines, demonstrations, a held-out Top task, and the budgets under which each claim is evaluated. The purpose is to separate a learner failure from a trajectory that was never executable as designed.

The evidence is not homogeneous:

- **Recorded runs** carry immutable `RunSpec = Config × Corpus` identity and generated reports. These support claims about the exact recorded configuration.
- **Historically traceable experiments** have committed scripts, outputs, or notebooks but predate the modern run identity contract. They remain evidence for the described configuration, not newly provenance-complete runs.
- **Offline diagnostics** inspect a fixed search space, trace, or artifact. They explain that object but do not establish an intervention effect.
- **Reconstructed accounting** classifies work observed in completed traces. It is bookkeeping over those traces, not a replay of a different policy.

The strongest conclusions below are therefore configuration-relative. The real-task evidence comprises three related geometric ARC tasks, two expressing the same rule under different palettes. Authored-rung counts describe this constructed sample; they are not prevalence estimates for ARC or for learning trajectories generally.

## 2. Executable trajectory validity

The most durable result is methodological: an intended learning trajectory has to be tested as an executable object before learner outcomes are interpreted.

Eight of 20 early authored synthetic Ladders were structurally invalid under their configured checks. Witness programs showed that a Top or rung could be reached without the intended intermediate routine. Repeated composition, an overly capable perception primitive on the floor, and literals substituting for a computed parameter were recurring causes. This is a diagnostic count within an authored development set, not an estimate of how often trajectories fail in a wider population. [Batch analysis](experiments/2026-07-21-ladder-batch-analysis/notebook.md)

The repair sequence converted those failure modes into executable checks. It also exposed an instrumentation error: local rung admission did not guarantee that the oracle or learned chain reached the Top. Reports now represent rung admission, oracle Top reachability, and learned-climb Top reachability separately. A claim about a completed trajectory requires the relevant end-to-end result, not merely clean local certificates. [MVE completion](experiments/2026-07-27-mve-completion/notebook.md)

These checks are budget-relative. A found bypass is evidence that a rung was not load-bearing in that configuration; failure to find one does not prove that no longer or differently guided bypass exists.

## 3. Configured search cost and when Laddering helps

Search cost depends jointly on the task, floor, vocabulary, constants, enumeration order, engine, stopping rule, and budget. The evidence supports configured contrasts, not a universal residual-depth, rung-count, or cost law.

One controlled round-1 composition probe gives an exact accounting identity for that enumerator. In a representative synthetic cell, changing the available typed pools changed considered candidates from 1,012 to 408,612 at the same nominal depth — a 404× contrast. This isolates configured branching in that probe; it is not a general arity formula. An [oracle-pruned diagnostic](EXPERIMENT_LOG.md#2026-07-26-optimal-pruning) produced the more extreme contrast 21,149,854 versus 4 candidates, but the smaller vocabulary was selected with knowledge of the solution and is therefore explanatory, not a deployable baseline. [Micro-probes](experiments/2026-07-22-micro-probes/notebook.md) and [floor-lowering diagnostics](experiments/2026-07-25-v5-lowering-search-cost/notebook.md)

Across the three related real-task cases, observed Top searches were in the tens of thousands of considered candidates for configured depth-2 jumps, hundreds of thousands for depth-3 jumps, and exceeded a 30-million guard for depth-4 jumps. Depth co-varied with vocabulary and pool growth, so these cases show a useful configured pattern rather than an isolated causal effect of depth. [MVE completion](experiments/2026-07-27-mve-completion/notebook.md)

Laddering can help, fail to help, or remain censored. In one fully measured historical case, raw search to the Top considered 192,865 candidates while the idealized marginal ladder path considered 53,711, a 3.59× configured ratio; the observed end-to-end ladder run considered 200,280, so the acquisition advantage did not survive loop overhead. Other completed cases include a ladder that cost more than raw search, while censored cases provide only lower bounds. These estimands must remain separate: raw-to-marginal acquisition cost is not raw-to-end-to-end system cost. [Clean-set rerun](experiments/2026-07-23-clean-set-rerun/notebook.md)

Four fully valid, uncompromised real cases had end-to-end-to-oracle loop-overhead ratios of 3.00, 3.08, 4.00, and 4.00. Those four descriptive values reflect their schedules and stopping rules; they are not an additive tax decomposition or a population estimate. [Loop-overhead analysis](experiments/2026-07-23-loop-overhead/notebook.md)

The curriculum decomposition is narrower still. Its 439 rows are nested observations from 21 authored climbs, not 439 independent trajectories. `considered` and `first_index + 1` are two views of the same completed trace. Relabeling trace work under a hypothetical earlier stop gives an **oracle same-trace accounting estimate**; actually stopping earlier could change caches, learned libraries, pool contents, wake order, and any stochastic state in a future engine. Invocation-count identities and conditional predictions from this analysis are useful for instrument design, but are not empirical laws of curriculum cost. [Curriculum accounting](experiments/2026-08-04-curriculum-tax-decomposition/notebook.md)

## 4. Recovery, reuse, and their boundaries

On the original clean set under the configured `AntiunifyPairs` proposer and governance, the learner recovered 43 of 43 authored routines without spurious mints. This is a baseline for that proposer, corpus construction, governance, engine, and budget. `FrequentSubtree` and `TypeScopedFrequentSubtree` each recovered 0/4, 0/5, and 0/2 across the three tested Ladders; their root-exclusion design placed the required whole-program abstractions outside their candidate spaces. `StitchProposer` recovered 0/4, 0/5, and 1/2, demonstrating a different capability boundary rather than the same blanket-zero mechanism. One parameterized real Ladder recovered 2/3 intended routines after governance selected specialized alternatives. Recovery is therefore proposal- and governance-dependent. [MVE completion](experiments/2026-07-27-mve-completion/notebook.md)

On three related real tasks, learned libraries solved held-out **instances** of authored competences that the bare floor did not solve within the configured budget. This is held-out instance generalization, not evidence of unseen-competence transfer.

The E8/E9 mirror-index case is retained as a historically traceable configured example. With the corpus, MDL selector, and consumer held fixed, changing the proposal set changed which library fragment was exposed: the training-compressing proposal enabled 0/6 held-out tasks, while the coordinate-oriented proposal enabled 5/6. Because the proposal set changed, this is not a selector-only ablation and does not establish a general compression-versus-reusability law. It demonstrates a concrete interaction among proposal formation, governance, and downstream composition. [E8/E9 notebook](experiments/2026-07-07-e8-e9-mirror-index-bootstrap/notebook.md)

The associated Stitch spike also needs an arity qualification. First-order Stitch output over the raw corpus was not callable as a valid unary AE transform. Valid historical probes were definition refactoring and higher-order invention, which preserved or exposed the reusable coordinate structure. The raw first-order output is not evidence of an AE-consumable abstraction. [Stitch notebook](experiments/2026-07-08-stitch-spike/notebook.md)

## 5. Material corrections and retired claims

| Earlier presentation | Reviewed status |
| --- | --- |
| Compression and future usefulness generally diverge | **Retired as a general law.** E8 is a configured proposal-set contrast with selector and consumer fixed. |
| Raw first-order Stitch independently confirms the E8 choice | **Corrected.** Its raw output is arity-invalid for the unary AE consumer; only the valid refactoring/higher-order probes remain interpretable. |
| Search cost follows a universal arity/residual-depth formula | **Retired.** Exact identities hold only for specified rounds and pools; broader results are configured observations. |
| More or fewer rungs has a general monotone effect | **Retired.** The measured tradeoff is trajectory- and configuration-specific. |
| The oracle-pruned 21,149,854-versus-4 contrast is an achievable method | **Narrowed.** It is an explanatory diagnostic selected with solution knowledge. |
| The four loop-overhead values define a general overhead factor | **Narrowed.** They are descriptive values for four related configured cases. |
| `AntiunifyPairs` recovers authored abstractions generally | **Narrowed.** The 43/43 result is a configured baseline; proposer and governance failures are part of the result. |
| Held-out Top results demonstrate new competence | **Corrected.** They demonstrate unseen instances of authored competences on three related tasks. |
| Curriculum rows identify causal “deadweight” or a removable bill | **Retired.** They support same-trace accounting classes and conditional estimands, not a replayed intervention. |
| Pooling 439 rows or 21 climbs estimates trajectory prevalence | **Retired.** Observations are nested within a small authored set with still fewer task/floor families. |
| Historical experiments inherit modern `RunSpec` provenance | **Rejected.** Later documentation can clarify provenance but cannot create it retroactively. |

The previously foregrounded 78–530× cost-law range is not a current finding. “Class B” is not used as an unexplained public label: the retained E8 evidence is described directly as a historically traceable proposal-set contrast.

## 6. What remains open

There is no selected active multi-step experimental plan. The current state and the partially executed 2026-08-04 plan are recorded in [AL-RESEARCH-STATE-2026-08-12.md](docs/abstraction_ladders/AL-RESEARCH-STATE-2026-08-12.md).

Open directions include:

- Controlled schedule and accounting arms.
- Experiments that isolate search-cost factors more cleanly.
- Additional task and floor families.
- A discovery-shaped floor-plus-Top benchmark with no prescribed rungs.
- Work on proposal formation, governance, library refactoring, or guidance.

These are candidates, not commitments. Any resumed program should begin with a new dated, prediction-first plan and explicit estimands.

The current evidence does _not_ establish:

- Population claims about ARC
- Results across search engines
- Autonomous curriculum discovery
- Cross-competence transfer
- The full lifecycle of abstraction revision, merging, pruning, and retirement

## 7. Evidence index and working record

<a id="2026-07-07--pixelsd4-compresses-a-frequent-subtree-proposer--primitive-driven-search-e8e9"></a>

- **Legacy E8/E9 fragment:** [reviewed interpretation](#4-recovery-reuse-and-their-boundaries) · [historical event](EXPERIMENT_LOG.md#2026-07-07--pixelsd4-compresses-a-frequent-subtree-proposer--primitive-driven-search-e8e9) · [notebook](experiments/2026-07-07-e8-e9-mirror-index-bootstrap/notebook.md)

<a id="2026-07-27--mve-completion-the-curves-re-bought-in-cost-to-first-a-fourth-defect-two-5-rung-members-and-the-goal-reachability-guards"></a>

- **Legacy MVE-completion fragment:** reviewed [validity](#2-executable-trajectory-validity), [cost](#3-configured-search-cost-and-when-laddering-helps), and [recovery](#4-recovery-reuse-and-their-boundaries) · [historical event](EXPERIMENT_LOG.md#2026-07-27--mve-completion-the-curves-re-bought-in-cost-to-first-a-fourth-defect-two-5-rung-members-and-the-goal-reachability-guards) · [notebook](experiments/2026-07-27-mve-completion/notebook.md)

The legacy fragments above have explicit reviewed, historical, and notebook destinations; the general evidence index follows.

- [Chronological working record](EXPERIMENT_LOG.md) — all 84 original dated events plus the 2026-08-12 documentation-review event; historical interpretations are preserved in place.
- [First Ladder batch analysis](experiments/2026-07-21-ladder-batch-analysis/notebook.md) — map from the early authored set to later validity corrections.
- [Micro-probes](experiments/2026-07-22-micro-probes/notebook.md) — exact configured identities and diagnostic contrasts.
- [Clean-set rerun](experiments/2026-07-23-clean-set-rerun/notebook.md) — raw, marginal, and end-to-end estimands.
- [Loop-overhead analysis](experiments/2026-07-23-loop-overhead/notebook.md) — four configured overhead observations.
- [MVE completion](experiments/2026-07-27-mve-completion/notebook.md) — Top-reachability correction, recovery boundaries, and real-task cases.
- [Run-store census](experiments/2026-08-03-run-store-census/notebook.md) — provenance and generated-state audit.
- [Curriculum accounting](experiments/2026-08-04-curriculum-tax-decomposition/notebook.md) and [post-fill rescreen](experiments/2026-08-04-postfill-rescreen/notebook.md) — reconstructed accounting and its later rescreen.

For reproducible state, prefer a committed `RunSpec`, generated report, and the source `.ladder` file over prose. The generated [batch of record](docs/abstraction_ladders/BATCH-OF-RECORD.md) is the current register of executed Ladders.
