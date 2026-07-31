# Making abstraction-learning trajectories measurable

> **`arc-lab`** — setup, commands, and layout are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Summary

The question behind this project is simple: if an ARC solver succeeds using a rich domain-specific language, how much of that success came from the solver and how much came from the language it was given? To study acquisition rather than just performance, I fix and declare a starting primitive library, then measure the effort required to build useful routines above it.

In order to research and experiment with these questions, I did two main things:

1.  I engineered a deterministic program-synthesis system.
2.  I conducted research and experimentation into abstraction learning, and the dynamics of abstraction learning.
    - This led to me building a framework for working with _instances of abstraction learning trajectories_, called [**Abstraction Ladders**](docs/abstraction_ladders/ABSTRACTION-LADDERS.md).

An Abstraction Ladder makes an authored learning trajectory explicit: a primitive floor, a sequence of intermediate routines, demonstrations for learning them, and a held-out Top task. The framework has already produced several useful findings about library learning and search cost. Its most important contribution so far is methodological: it makes invalid trajectories, hidden priors, and misleading cost comparisons visible.

This is not yet a benchmark, a demonstration that the system discovers its own curriculum, or an evaluation of revision and pruning. It is a controlled substrate for making those later experiments meaningful.

## The instrument

The system uses typed bottom-up program enumeration and a wake-sleep library-learning loop. Search, library, proposal mechanism, governance objective, and budget are immutable run configuration. Runs are deterministic, content-hashed, cached, and recorded; the search engine never sees test examples, and withheld targets are used only for evaluation.

In a planted-ground-truth study, I author a target routine, a floor from which it is reachable, and demonstration tasks. The learner receives the demonstrations but not the target. Recovery is therefore blind at runtime, while the experiment remains explicitly target-authored.

An Abstraction Ladder adds the missing trajectory object. It declares:

- a **floor**: the initial primitive library;
- **rungs**: routines intended to be learned in sequence; and
- a **Top**: a harder held-out task expected to reuse the learned routines.

The key discipline is testing whether the proposed trajectory actually exists. A rung is admitted only if its demonstrations are reachable from the preceding library and no route bypasses it within the consumer's configured budget. That last condition is budget-relative: no detected skip is not a proof that no longer alternative route exists. End-to-end validity is stricter still: the Top must be reached both by an oracle chain and by the learned climb.

This separates a failed learner from a bad experiment. It also keeps the costs interpretable: all results are relative to a stated floor, engine, trajectory, and budget.

[ABSTRACTION-LADDERS.md](docs/abstraction_ladders/ABSTRACTION-LADDERS.md) gives a fuller account of Abstraction Ladders – the concept, validity discipline, cost views, Ladder relationships, and workflow.

## Some key findings

### 1. Most authored trajectories were not valid experiments

Of 20 early synthetic Ladders, 8 were rejected structurally: the Top could be reached without an intended rung, or a rung could be satisfied more cheaply than designed. Three recurring causes were repeated composition, an overly capable perception primitive on the floor, and literals substituting for a parameter that the rung was meant to compute. [Batch analysis](experiments/2026-07-21-ladder-batch-analysis/notebook.md)

Those failures were valuable. They became executable checks with witness programs, and six subsequent Ladders designed around them were rung-admitted on their first attempt. The instruments also caught their own failure modes: initial reports could admit all rungs while failing to reach the Top. Top reachability is now recorded separately from rung admission. [Validity repair](experiments/2026-07-27-mve-completion/notebook.md)

The lesson is not that the learner is strong. It is that a learning-trajectory experiment must establish that its intended intermediate routines are genuinely load-bearing before interpreting a result.

### 2. Compression and future usefulness can diverge

On a low-level geometric task family, an MDL-style selector preferred the routine that compressed the solved training programs most. That routine had a type and shape that the search could not compose into later programs. A smaller shared coordinate routine compressed less, but unlocked the later reflections.

With the same corpus, the larger train compressor enabled 0 held-out tasks; a search-scoped proposal set that exposed the reusable coordinate routine enabled 5. This is not a selector-only ablation, but it makes the proposal-governance interaction concrete. [E8/E9](experiments/2026-07-07-e8-e9-mirror-index-bootstrap/notebook.md) and the [Stitch spike](experiments/2026-07-08-stitch-spike/notebook.md) show that first-order Stitch over the raw corpus makes the same unfavorable choice. Higher-order invention can prevent the burial, while first-order library refactoring can recover the buried routine from library definitions.

This is a concrete governance problem: compression of past solutions does not by itself capture future search use. The possible remedies are search-aware selection, library refactoring, or more expressive abstraction formation.

### 3. Search cost is shaped by residual depth and vocabulary width

Residual composition depth is expensive. Across three small real ARC task cohorts, cost-to-first-solution was roughly 36,000-71,000 candidates with a depth-2 Top jump, 288,000-524,000 at depth 3, and not found within 30 million candidates at depth 4. [Granularity analysis](experiments/2026-07-27-mve-completion/notebook.md)

At a fixed depth, vocabulary can matter just as much. Two otherwise comparable signatures differed by 404x because their argument types opened different pools of candidate programs. In the largest single contrast, a search over the full floor considered 21,149,854 candidates; an oracle-pruned floor containing only the three primitives used by the solution considered 4. Constants and retained-pool size have similarly large effects. [Micro-probes](experiments/2026-07-22-micro-probes/notebook.md) and [floor-lowering sweep](experiments/2026-07-25-v5-lowering-search-cost/notebook.md)

The practical implication is not simply "make Ladders finer." **More rungs reduce the deepest jump but widen later search spaces. Measured total costs are non-monotone in rung count.** The useful quantity is the cost profile of a particular trajectory, not the number of intermediates in isolation.

### 4. Laddering is conditionally useful

The benefit of a Ladder is not intrinsic. It depends on the configured task, floor, trajectory, curriculum, engine, and budget. Three fully measured cases had raw-to-laddered ratios of 3.59x, 1.19x, and 0.48x: in the last case, the curriculum cost more than raw search. Ten other cases establish only `>= 10x` lower bounds because the raw arm exhausted its guard without solving. [Clean-set re-run](experiments/2026-07-23-clean-set-rerun/notebook.md)

The setup also makes overhead visible. Across four fully valid, uncompromised real Ladders, the full wake schedule cost 3.00x, 3.08x, 4.00x, and 4.00x an oracle per-rung schedule. A separate schedule control found that avoiding re-search of solved tasks reduced cost but sometimes minted unintended routines. These are oracle-relative overheads, not a clean additive decomposition or a production cost model; they are unavailable when a solution-limit compromise truncates the relevant cells. [Loop-overhead experiment](experiments/2026-07-23-loop-overhead/notebook.md) and [validity repair](experiments/2026-07-27-mve-completion/notebook.md)

### 5. Held-out instance generalization, not cross-competence transfer

On the original `AntiunifyPairs` clean set, the learner recovered 43 of 43 intended routines with no spurious mints. On three real ARC tasks, the learned library solved held-out Tops on grids it had not seen, while the bare floor could not. [Recorded transfer check](experiments/2026-07-27-mve-completion/notebook.md)

This is generalization to unseen instances of authored competences, not cross-competence transfer. It is also not a general wake-sleep result: proposer swaps produced 0/4, 0/5, and 0/2 recovery where the relevant whole-program abstraction was structurally outside those proposers' candidate spaces, and a parameterized real Ladder recovered 2 of 3 intended routines when governance selected specialized alternatives. These named failure modes are more informative than a universal recovery claim. [Recovery boundaries](experiments/2026-07-27-mve-completion/notebook.md)

## What this does not establish

- A population-level claim about ARC: the real-task sample is three related geometric tasks, two with the same rule under different palettes.
- A result across search engines: every number comes from one deterministic bottom-up enumerator and one enumeration order.
- A benchmark result: intermediate routines and curricula are prescribed rather than discovered.
- A general learner result: the clean-set recovery result is specific to one proposer and demonstration convention; other proposer and governance regimes have measured failure modes.
- A full account of continual abstraction learning: revision, merging, pruning, retirement, and distractor-task behavior remain untested.
- A neural result: there is no neural guidance in this system.

## Next

The immediate scientific next step is to drop the prescribed rungs. A Ladder-shaped benchmark would declare a floor and a Top but require a system to discover its own useful intermediate routines. The existing validity checks would still be useful, but they would evaluate a discovered trajectory rather than certify an authored one.

The most promising system directions are search-aware library governance, library refactoring, and learned guidance over which primitives, constants, and tasks to consider. Revision and pruning belong after there is a trajectory that can demonstrably require them; otherwise an ablation cannot distinguish an unnecessary mechanism from an inadequate test stream.

## Evidence and code

The repository is the primary artifact. The concise record of every experiment, including dead ends and retractions, is [EXPERIMENTS.md](EXPERIMENTS.md). Detailed notebooks and raw outputs live in [experiments/](experiments/). The Ladder registry and its per-Ladder reports are documented in [LADDERS.md](docs/abstraction_ladders/LADDERS.md), and [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) explains how to run the system.

The key investigations behind this report are the [compression-versus-reuse experiment](experiments/2026-07-07-e8-e9-mirror-index-bootstrap/notebook.md), the [first Ladder batch analysis](experiments/2026-07-21-ladder-batch-analysis/notebook.md), and the [MVE completion notebook](experiments/2026-07-27-mve-completion/notebook.md).
