# Making abstraction-learning trajectories measurable

> **`arc-lab`** — setup, commands, and layout are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). The rigor-reviewed findings are in [EXPERIMENTS.md](EXPERIMENTS.md); the chronological working record is [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md).

This repository studies a controlled question: given a declared primitive library, what does it cost a deterministic program-synthesis system to acquire and reuse intermediate routines? It provides a typed bottom-up enumerator, a wake-sleep library-learning loop, and **Abstraction Ladders**—authored trajectories with a floor, rungs, demonstrations, and a held-out Top task.

The system's modern execution layer freezes `RunSpec = Config × Corpus`, content-hashes runs, and records their outputs. Older experiments remain useful where their scripts and artifacts are traceable, but later documentation does not give them modern run provenance.

## Three conclusions

### 1. Trajectory validity must be executable

Eight of 20 early authored synthetic Ladders were invalid under their configured checks: a rung or Top could be reached without the intended intermediate routine. That count describes the constructed development set, not a population prevalence. The failure modes became witness-producing checks, and a later correction separated local rung admission from oracle and learned Top reachability.

The durable result is methodological: establish that the intended trajectory exists under the stated floor, engine, and budget before interpreting learner performance. “No bypass found” remains budget-relative, not a proof of universal necessity. [Batch analysis](experiments/2026-07-21-ladder-batch-analysis/notebook.md) · [validity repair](experiments/2026-07-27-mve-completion/notebook.md)

### 2. Acquisition cost is configured, not intrinsic

Candidate cost changes with typed pools, vocabulary, constants, enumeration order, stopping policy, and budget—not just nominal program depth. Controlled probes show exact identities for particular rounds and large contrasts under particular configurations, but do not establish a universal arity or residual-depth law. An oracle-pruned vocabulary can diagnose where cost arises without representing an achievable selection policy.

Laddering is likewise conditional. In one historical case, the idealized marginal ladder path was cheaper than raw Top search, while the observed end-to-end climb was not; other cases were more expensive or censored. Raw-to-marginal acquisition cost, end-to-end system cost, and oracle-relative loop overhead are different estimands and must not be interchanged. [Micro-probes](experiments/2026-07-22-micro-probes/notebook.md) · [clean-set rerun](experiments/2026-07-23-clean-set-rerun/notebook.md)

### 3. Recovery and reuse have measured boundaries

The original clean-set baseline recovered 43/43 authored routines under `AntiunifyPairs` and its configured governance, corpus, engine, and budget. Proposer swaps and a governance-sensitive real case failed in named ways, so this is not a universal learner result.

Learned libraries also solved held-out instances on three related real ARC tasks where the bare floor did not solve within budget. That is unseen-instance generalization for authored competences, not cross-competence transfer. The historical E8 case is supporting evidence that proposal formation, governance, and downstream reuse can interact; because its proposal set changed, it does not establish a general compression-versus-reusability law. [Recovery boundaries](experiments/2026-07-27-mve-completion/notebook.md) · [E8/E9](experiments/2026-07-07-e8-e9-mirror-index-bootstrap/notebook.md)

## What an Abstraction Ladder is

A Ladder declares:

- a **floor**, the initial primitive library;
- **rungs**, routines intended to be learned in sequence;
- **demonstrations** from which those routines may be acquired; and
- a **Top**, a harder held-out task expected to reuse them.

The learner sees demonstrations, not authored target routines. Static linting, real-engine probes, recorded climbs, and generated certificates distinguish rung affordability, budget-relative bypasses, recovery, and Top reachability.

[ABSTRACTION-LADDERS.md](docs/abstraction_ladders/ABSTRACTION-LADDERS.md) explains the object and [ABSTRACTION-LADDERS-SPEC.md](docs/abstraction_ladders/ABSTRACTION-LADDERS-SPEC.md) defines its metrics.

## Scope

This is not yet a discovery benchmark, a population study of ARC, a comparison across search engines, or a test of the full revision/pruning lifecycle. The real-task sample is three related geometric tasks. Curricula and intermediate routines are authored. All quantitative claims are relative to their recorded or historically traceable configuration.

There is no active multi-step experimental plan. [Open directions and current research state](docs/abstraction_ladders/AL-RESEARCH-STATE-2026-08-12.md) include controlled schedule/accounting arms, better-isolated cost studies, additional task/floor families, a discovery-shaped floor-plus-Top benchmark, and work on proposals, governance, refactoring, or guidance. None is selected.

## Evidence and code

- [EXPERIMENTS.md](EXPERIMENTS.md) — current rigor-reviewed synthesis and evidence index.
- [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) — chronological record, including dead ends and interpretations later corrected.
- [experiments/](experiments/) — detailed notebooks and committed investigation artifacts.
- [BATCH-OF-RECORD.md](docs/abstraction_ladders/BATCH-OF-RECORD.md) — generated register of executed Ladders.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — setup, commands, architecture, and document index.
