# Abstraction Ladder Experiments — design snapshot, 2026-07-16

**Status:** design, pre-run. A dated snapshot in the style of [RESEARCH-2026-07-08.md](RESEARCH-2026-07-08.md); supersede by re-issue into `docs/archive/`, don't edit in place once runs begin.

**What this is:** the design for a batch of LEARN experiments ("Abstraction Ladders") measuring how much a chain of learnable intermediate abstractions reduces the search cost of reaching a target program — and what that reduction costs in learning overhead and library bloat. It is the **source of truth for ladder terminology** (§2) and the **pre-registered predictions** (§3): queue rows, notebooks, and future sessions link here rather than redefining.

**What this is not:** a results log (runs go to [EXPERIMENTS.md](../../EXPERIMENTS.md) + `experiments/` notebooks), a machinery design (that lands in [EXECUTION.md](../EXECUTION.md)/[ARCHITECTURE.md](../ARCHITECTURE.md), tracked in MACHINERY.md), or a state mirror of the queue ([EXPERIMENT_QUEUE.md](../EXPERIMENT_QUEUE.md) holds what's next).

**Builds on:** E11 (perceive→transform: single-rung mint with a genuinely free parameter; the cheapest-wins corpus discipline), E12 (layered-abstraction: two-generation climb; first vocabulary-tax measurement), E13 (fundamental-floor grain contrast: measured per-round growth factors; censored-baseline reality) — all in [EXPERIMENTS.md](../../EXPERIMENTS.md). Precursor sketch: [task_specific/4093f84a-EXPRESSIBILITY-2026-07-15.md](4093f84a-EXPRESSIBILITY-2026-07-15.md) (a hand-derived ladder, before the concept was fleshed out; its Total-vs-Jump-only depth distinction survives here as inlined vs jump depth).

---

## 1. Motivation & prior findings

The phenomenon under study: sleep-minted abstractions amortize search. Bottom-up search cost grows geometrically with composition depth, so a target k jumps above the floor is unreachable raw but reachable as k affordable jumps — _if_ each intermediate abstraction is learnable from tasks that demonstrate it.

What is already established, and by which experiment:

- **A single rung can be minted with a genuinely free parameter**, given the right corpus discipline
  - (E11: `recolor_bg`, byte-identical to target, full held-out transfer; and the _cheapest-wins trap_ — WAKE retains only the cheapest solving program per task, so demonstrating programs must be the cheapest solution or they are silently never seen by sleep).
- **A second-generation rung can be built on a just-learned first**, within one LEARN run (E12: `abs1` minted on `abs0` after a second WAKE that needed `abs0` to reach its tasks at all).
  - First cost signal against scaling: the grown library (3 → 5 primitives) multiplied considered-count by ~3.9x on the same corpus — learned vocabulary is additive round-0 leaf load on _every_ task.
- **Raw baselines are mostly censored** (E13: per-round growth ~17-24x on `UNIVERSAL_FLOOR`/`MINIMAL_COMPLETE_FLOOR`; a depth-6 run was killed unfinished).
  - "Search could get there without learning, at high cost" is usually not a measurable number — it is a bound.

What is new here: **a scaling instrument and a quantification, not a new phenomenon.** Ladders extend the existing study shape (a `StudySpec` is a height-1 ladder; E12 was a height-2 climb) to controlled heights and shapes, with the measurement plan to fit the cost model rather than just observe enablement.

## 2. Concepts & definitions

Depth convention throughout: `depth(f(x1..xn)) = 1 + max(depth(xi))`; literals, params, and bound variables are depth 0.

### The ladder object

- **Ladder** — `(Floor, bridging rungs r_1..r_k, top task set T*)`, defined **relative to a wake budget** `B`. The budget is constitutive, not a free parameter: every jump must be affordable within `B`, and the raw route must not be (a budget large enough to solve `T*` from the Floor at iteration 0 dissolves the ladder).
- **Floor (`L_0`)** — the starting library of primitives.
- **Bridging rung (`r_i`)** — an abstraction intended to be minted by sleep: a closed template over `L_{i-1}` (a `TargetAbstraction`), together with its **demonstrating tasks** (>= 2) whose cheapest solutions exercise it.
- **Cumulative library (`L_i`)** — `L_0 ∪ {r_1..r_i}`.
- **Top task(s) (`T*`)** — the hardest task(s) in the corpus; their solution over `L_k` is the final jump. The top solution may or may not itself get minted (in E12 it did); minting it is incidental, not required.
- **Height** — the number of jumps: `k+1` (k bridging rungs + the top jump). E12 is height 2.
- **Oracle vs learned flavor** — every per-rung quantity exists in two flavors: under the **gifted** library `L_i^oracle` (intended rungs added by hand — the study grid's L3 generalized) and under `L_i^learned` (whatever sleep actually minted by iteration i). Divergence between flavors isolates learner imperfection from ladder quality.

### Depth & cost quantities

- **Design jump depth (`d_i`)** — compositional depth of rung i's template over `L_{i-1}`. Static; the designer's lever.
- **Inlined depth** — depth of a template after substituting called rungs' own templates (recursively, down to `L_0`). Jumps **compound by substitution, never add**: the double-jump depth of `r_{i+1}` over `L_{i-1}` is its inlined depth with `r_i` expanded, not `d_i + d_{i+1}`. Raw total depth `d_raw` = inlined depth of the top solution over `L_0`.
- **Solve generation** — the 0-indexed composition round at which the first accepted program appeared (`SearchStats.solved_at_generation`). For floors without lambda synthesis, solve generation = application depth of the found program. Two standing caveats: `Budget.max_depth` counts rounds _including_ the round-0 leaves (so a depth-d program needs `max_depth >= d+1`), and lambda synthesis breaks the generation↔syntactic-depth correspondence (bodies are built in a `descend()`ed sub-search).
- **Considered count** — candidates absorbed by the tracker (`SearchTracker.considered`); the cost currency. Three per-task costs, all without early stop (the engine runs to budget exhaustion; ACCEPTED resolves at extraction):
  - **cost-to-first-solution** — cumulative considered through the earliest accepted candidate (reconstructable from `candidate_index`).
  - **cost-to-cheapest-solution** — cumulative considered through `ranked[0]` (the program WAKE retains, hence _the cost of the demonstration sleep will see_). Can exceed cost-to-first: extraction ranks by node count, generations by depth, so a smaller-but-deeper program can arrive later.
  - **cost-paid-full** — total considered at budget exhaustion (what a wake actually pays).
- **Program size vs depth** — `size` = node count (`ProgramSize`); depth = composition rounds. **Generations read depth; retention (cheapest-wins) and MDL read size.** The E11 trap lives entirely in the size ordering.
- **Censoring** — a cost recorded as "unsolved within budget" is a lower bound, not a measurement. Censored cells are first-class data (they are what ladder validity _predicts_ for double jumps).

### The cost model

- **Effective branching factor (`b_eff`)** — per (library, budget) cell: the fitted per-generation growth rate of composed candidates. The working model: **cost-to-solve ≈ c · b_eff^d** for a target at depth d. Measured so far: ~18x/round (`UNIVERSAL_FLOOR`, depth 3→4), ~17-24x (`MINIMAL_COMPLETE_FLOOR`, depths 3→5) (E13); small floors are far cheaper per round (E12's 3-primitive floor: ~5.9k considered/task at depth 3).
- **Amortization law (the RQ1 hypothesis)** — raw ≈ c·b^(d_raw) vs laddered-marginal ≈ Σ_i c·b^(d_i): **the ladder converts a product into a sum.** Deviations are the interesting part (vocabulary tax, loop overhead, sleep cost).
- **Vocabulary tax** — cost inflation on a _fixed_ task set from extra library entries: cost(tasks | L_j) / cost(tasks | L_i), j > i, on tasks whose solutions use none of the extra rungs. First-order model: b_eff scales with effective library size, so tax per depth-d jump ≈ (|L_j|/|L_i|)^d. Calibration point (E12): predicted (5/3)^2 ≈ 2.8x vs measured ~3.9x — right order, under-predicts; refining this model is a Family-A deliverable.
- **Budget compression** — `d_raw` vs `max_i(d_i)`: the reduction in _required search depth_ the ladder buys. **Enablement** (tasks solvable under `L_i` but not `L_{i-1}` at fixed budget) is its binary shadow.

### Ladder validity

- **Tractability sandwich** — per jump i: (a) affordable with headroom — predicted cost fills <= ~half the budget, computed with `b_eff` _at the library size expected when the rung comes due_, not the Floor's; (b) the double jump (inlined `r_{i+1}` over `L_{i-1}`) clearly exceeds the budget.
- **Skip path** — any solving program for rung-(i+1) tasks reachable from `L_{i-1}` within budget that bypasses `r_i`. Not statically decidable (it is the search problem); _empirically certified_ by the oracle chain: the `L_{i-1}` column must solve zero rung-(i+1) tasks. (E13's transpose≡rot180 generator bug is the canonical skip-path failure, one level down.)
- **Demonstration health** — per rung: fraction of demonstrating tasks whose _retained cheapest_ solution structurally contains the rung template. The E11-trap detector; its early-warning signal is the **first-vs-cheapest gap** (cost/generation divergence between the two).

### Learning-side quantities

- **Climb trace** — per LEARN iteration: library size, mint events, newly-solved tasks by rung level, per-task costs; the LEARN run's headline artifact. **Stall iteration**: first iteration with no new solves and no mints.
- **Rung recovery grade** — per intended rung: **exact** (structurally identical mint, as E11 achieved) / **behavioral** (same function, different form — the study report's existing grading) / **specialized** (literal-bound mint; stalls the climb one level up, far from its cause) / **missed**.
- **False mint** — a minted abstraction matching no intended rung; record its MDL gain and whether later solutions _use_ it (`primitive_keys`). A used false mint is an alternative ladder; an unused one is pure tax.
- **Marginal rung value** — cost(rung-(i+1) tasks | L\_{i-1}) / cost(rung-(i+1) tasks | L_i): same tasks, libraries differing by exactly one rung — "what did r_i buy." Numerator usually censored ⇒ report as a lower bound.
- **Solution routing** — does the final top solution actually contain the rungs (`primitive_keys`), and how many? A top task solved while bypassing rung 2 is a different finding than a clean climb.

### Shape

- **Telescope** — the degenerate chain where each rung wraps the previous one exactly once (fan-in 1, d_i = 2 forever). Method-1 construction's attractor; a batch of telescopes silently overclaims.
- **Fan-in** — per rung: distinct lower rungs its template uses, with multiplicity. Recorded per ladder; the batch must span fan-in > 1.
- **Scope ruling:** v1 ladders are chains (level-ordered), with fan-in as the recorded DAG-ness measure; full DAG ladders are a later axis.

## 3. Research questions & predictions

Pre-registration stance: the numeric predictions below are stated before any ladder runs; per-ladder predictions get computed at design time in the ladder's notebook, _before_ its first run. Results never get backfilled into this doc.

### RQ1 — Quantify the amortization: raw vs laddered cost

**Hypothesis:** raw cost ≈ c·b^(d_raw); laddered-marginal cost ≈ Σ_i c·b^(d_i); laddered end-to-end adds loop overhead (every wake re-searches every task under `reset_programs_each_wake` — unsolved upper-rung tasks pay full budget each iteration until their rung arrives, plausibly the dominant term) plus sleep cost.

**Predictions:**

- For any ladder passing the validity sandwich, the oracle chain shows every jump solved within budget and every double jump censored.
- Laddered-marginal vs raw: for a height-3 ladder with d_i ≈ 2 on an E12-scale floor, marginal cost within small multiples of 3 × (single-jump cost), while the raw route (inlined depth >= 4-5) costs >= b^2 ≈ 1-2 orders of magnitude more — measurable only on calibration ladders, censored elsewhere.
- Vocabulary tax per mint: between the size-model floor ((|L_i|/|L_0|)^d) and ~1.5x its prediction (E12 calibration: 2.8x predicted, 3.9x measured). Height-3 prediction: end-of-climb tax on floor-level tasks in the 3-8x range for a 3-4 primitive floor gaining 2-3 rungs.
- **Falsifier / kill:** the _oracle_ chain shows no cost collapse (jumps not cheap, or double jumps not expensive) ⇒ the ladder concept itself is broken; no learner work proceeds (§9).

### RQ2 — Quantify effects of params/metaparams on the amortization

**Organizing decomposition: params move `b`; metaparams move the `d_i` profile.**

- Params (move b): `budget.max_depth` / `max_arity` / `max_pool`, `beam_width` (`BeamBottomUpSearchEngine`), `constant_sources`, `function_hole_fill_mode`, `polymorphism_instantiation`, `unpinned_type_var_mode`, `function_sample_size` — **plus the learning side, which the search-param list omits at its peril**: proposer (`AntiunifyPairs` / `FrequentSubtree(min_frequency)` / `TypeScopedFrequentSubtree` / `StitchProposer`), governance (`GreedyMDL` threshold), `LearnSpec.iterations`.
- Metaparams (move d_i / the corpus): Floor, Top Rung, rung count, raw total depth, average/max jump depth; tasks per rung, distinct demonstrating programs per rung, full-solution vs fragment demonstrations, top-task count, next-rung-only vs all-tasks corpus.
- **Design rule:** reference config + one-factor-at-a-time sweeps; a full cross is impossible and budget sweeps are confined to the ladder-validity window (§2, budget-constitutive).
- **Prediction:** b_eff responds most strongly to constant sources and library size (E13/census: constants dominated `synth`'s 2.7M considered), and to `max_pool` only once eviction binds (E13's open eviction question).

### RQ3 — What programs/fragments does AF get to see? (sequenced last)

Options, with the hidden structure made explicit — **the type of a rung determines which visibility option can capture it, which selects the proposer**:

| Demonstration shape | Learnable by |
| --- | --- |
| Solution _is_ the rung template, params varying across tasks | `AntiunifyPairs` (the proven E11/E12 path) |
| Rung embedded in solutions, occurrences identical | `FrequentSubtree` |
| Rung embedded, params varying across occurrences | Stitch |
| Rung never appears in any retained solution (non-Grid→Grid quantities) | nothing today — needs fragment visibility (options below) or probe tasks |

- OPTION 0-1 solutions/task (current) → OPTION top-K solutions/task → OPTION K non-solution Grid→Grid programs → OPTION K non-solution non-Grid→Grid programs → OPTION lambda-synthesis sub-programs.
- **The `Input()` problem:** any cheapness-ranked non-solution selector floods with trivia (`Input()`, `flip_h(Input())`, ...). The selection policy _is_ the experimental condition. Candidates: dumb filters + generosity (type filter, size floor, signature dedup — let the proposer do selection; shifts cost into sleep), or **partial credit** (fraction of matching train-output cells at extraction; seam-safe; selects near-misses). The `SampleSpec` reservoirs observe candidates at absorption — including later-EVICTED ones — so `max_pool` does not bound what a selector can see.
- **Governance warning:** feeding non-solutions to a compression learner makes "compresses well ≠ useful" likely (search residue is self-similar); expect these arms to force the deferred usefulness-governance question (EXPERIMENT_QUEUE backlog: reusable-idiom governance).
- **Sequencing:** top-K solutions first — smallest machinery change, and it directly relaxes the E11 cheapest-wins corpus burden everywhere else.

**Scope rulings (v1):** rungs are mintable abstractions only. Substrate-laddering — where parameter-passing shapes (`fold` + accumulator, per the 4093f84a doc's Ladder 3) deliver additive depth _without_ learning — is a named, deferred contrast arm, not part of the batch.

## 4. Ladder construction methodology

Two construction methods with asymmetric guarantees — **Method 2 is the primary generator**:

- **Method 2 — anchored bisection** (backward): fix Floor and Top first, recursively insert a mid-rung into the largest jump until the sandwich passes. Tops are _meaningful by construction_; each inserted rung's learnability must then be engineered (checklist below). Only Method 2 can connect a designated Floor to a designated Top.
- **Method 1 — forward extension**: grow upward from what's learnable (rungs learnable _by construction_, top arbitrary). Reserved for calibration ladders and controlled-shape synthetic families; its attractor is the telescope, so shape metadata is mandatory.

### The per-ladder checklist

1. **Anchor.** Pick Floor and Top Rung as a nameable competence — even for synthetic ladders. Real-ARC anchors get the 4093f84a-style hand-derivation.
2. **Bisect** the largest remaining jump until every jump passes the sandwich, computed on **inlined depths** with **headroom**: predicted jump cost <= ~half budget at b_eff(expected library size at due-iteration); double-jump inlined depth clearly over budget.
3. **Per-rung learnability discipline:**
   - full-solution demonstrations at the rung's own level (keeps mints on the `AntiunifyPairs` path; embedded use arrives via the level above); fragment-only demos are an RQ3 _condition_, not a default;
   - > = 2 demonstrating tasks, multi-example each;
   - an explicit **parameter variation plan** per rung parameter (fixed-within-task, varied-across-tasks — E11), else sleep mints a _specialized_ rung and the climb stalls one level up;
   - **MDL break-even check**: demonstration count × per-use savings clears the definition cost.
4. **Task derivation:** deterministic inputs (no RNG), enough examples to kill coincidences, and **collision checks** against the cheap end of the floor's space (the E13 lesson: verify against all cheap same-signature candidates before trusting a task).
5. **Static lint** (all computable pre-run): templates well-typed over `L_{i-1}`; sandwich on inlined depths; MDL break-even; variation plan present; raw total depth ≫ budget.
6. **Empirical certificate = the oracle chain** (§5): jump i solved under `L_{i-1}` within budget; **zero** rung-(i+1) tasks solved under `L_{i-1}` (no skip path — every rung necessary); demonstration health passes. Fail ⇒ back to 2-4.
7. **Admit and record shape metadata:** height, d_i profile, per-rung fan-in, tasks/rung, construction method, lint vs empirical certification status.

**Bisection failures are findings.** When no mid-rung exists for a jump after honest effort, log it (EXPERIMENTS.md + notebook) with the failure mode: _not-learnable-from-below_ vs _not-useful-for-above_ — these map different geometry. Some jumps are plausibly atomic (the fold-accumulator insight has no obvious midpoint); mapping them is part of the program's payoff.

## 5. Run plan per ladder

Wakes inside a LEARN run are **not** separately recorded runs (EXECUTION.md: wake i's library has no independently addressable identity — per-iteration telemetry lives in the LEARN run's trace). So the arms are:

| Arm | Runs | Yields |
| --- | --- | --- |
| **Climb** | 1 LEARN run (+ its 2-3 derived SEARCH runs: train-usefulness, transfer) | climb trace, learned-flavor jump costs, rung recovery, end-to-end cost |
| **Oracle chain** | k+1 SEARCH runs: `L_0 .. L_k` over the full corpus, same wake budget | the **cost matrix** — each column simultaneously gives: jump-i measurement (rung-i tasks), censored double-jump bounds (all higher tasks), vocabulary-tax readings (all lower tasks). `L_0` is also the raw-baseline column. |
| **Off-chain (optional, §10f)** | 1 SEARCH run: `L_0 ∪ {r*}` (top solution inlined into one gifted mega-primitive, no bridging rungs) | monolithic-vs-compositional library contrast: the top task collapses, bridging tasks don't |

Total: **1 LEARN + (k+1) oracle SEARCH + derived runs (+1 optional)** per (ladder × budget × learner) cell. Content-hashed caching makes every repeated cell free (study-grid property); budget sweeps multiply from here, confined to the validity window.

**Baseline strategy** (raw cost is usually censored, E13): (a) **calibration ladders** — height-2, raw route measurable at a deep budget (E12's shape) — anchor exact ratios; (b) **extrapolation** — fit per-generation growth on completed rounds, extrapolate to `d_raw`, flag the pool-eviction bend; (c) **censored bounds** reported as-is. All three, always labeled.

## 6. Measurement plan

**The rule: atoms recorded exhaustively at run time; every named metric is a read-side view** (`analyze_run` / report style — never requires re-running). The primary object is the cost matrix cost(task, library, budget); nearly everything below is a slice of it.

### Tier-0 atoms (per run × task), with instrument status

| Atom | Instrument | Status |
| --- | --- | --- |
| solved?, accepted program, solve generation | per-task row: `{considered, totals, by_primitive, solved_at_generation}` (`execute.py`) | ✅ landed |
| outcome partition, total + per-primitive | `SearchTracker` (`search/tracking.py`) | ✅ |
| per-generation funnel (composed/errored/pruned/deduped/entered_pool/displaced/evicted, pool sizes) | `GenerationTracker` | ⚠️ landed in-engine, feeds logging only — **not serialized into the run record** (gates b_eff fits + cost reconstruction) |
| cost-to-first / cost-to-cheapest | `candidate_index` of earliest ACCEPTED / of `ranked[0]` | ⚠️ derivable (indices exist on `PoolEntry`/capture) — **needs first-class per-task exposure** |
| sampled/captured programs incl. evicted | `SampleSpec` reservoirs / `TraceSpec` capture | ✅ opt-in |
| LEARN per-iteration trace (library, mints, solved sets) | LEARN run record trace | ✅ recorded — the climb-trace _report_ over it is the gap |
| sleep cost | — | ❌ no unit exists (§10c) |

### Views (all read-side; definitions in §2)

Per rung: jump cost (oracle + learned flavors) · double-jump censored bound · **marginal rung value** · vocabulary tax · demonstration health · first-vs-cheapest gap · recovery grade. Per ladder: budget compression · enablement per (library, budget) · b*eff per matrix column · climb trace + stall iteration · false mints + downstream usage · solution routing · **worth-it accounting**: laddered-marginal vs laddered-end-to-end (loop overhead separated) vs raw (labeled: measured/extrapolated/censored), plus **break-even horizon** — learning overhead ÷ per-task savings on \_heldout* top-level tasks (the existing eval-split machinery) = how many future tasks justify the ladder. Cross-analysis: by-primitive → category/provenance rollups (census machinery) — free, no design weight.

Currency discipline: headline ratios in **considered count** (or explicit log-cost); depth ratios reported but never averaged across rungs (depth is a log-scale quantity — a depth ratio of 9/12 is a ~b^3 cost ratio).

## 7. Batch design

- **Ladder #1: height-3 chain** (2 bridging rungs + top), Method 2 from a _synthetic_ anchor. The minimal genuinely-new datum beyond E12: does the ~4x vocabulary tax compound at generation 3? does greedy-MDL governance stay clean three generations deep? Also rehearses the bisection workflow the real-ARC anchors need.
- **Families, one axis each** (batch means over mixed axes are mush):
  - **A — height** {2,3,4,5}, fixed jump depth: climb scaling + tax compounding (RQ1).
  - **B — jump depth** {2,3,4}, fixed height: calibrates the b^d law (RQ1/RQ2).
  - **C — demonstration design** (tasks/rung, distinct programs/rung, full vs fragment): feeds RQ3.
- **Calibration ladders** (height 2, Method 1 fine): measurable raw baselines anchoring extrapolations.
- **Real-ARC anchors** (1-2): the external-validity bridge; expensive; may fail bisection in interesting places (log per §4).
- **Admission rule:** only ladders passing the empirical certificate count toward batch metrics; everything else is exploratory. Target 5-25 validated ladders total.

## 8. Machinery gaps & sequencing

Pointers only — design lands in EXECUTION.md/ARCHITECTURE.md, tracking in MACHINERY.md. Items marked ⚡ touch run identity (locks move deliberately).

**Phase 0 (gates ladder #1):**

1. Serialize the per-generation funnel into the run record (currently logging-only).
2. Expose accepted candidates' `candidate_index` per task (cost-to-first / cost-to-cheapest).
3. `LadderSpec` — generalizes `StudySpec`: leveled `TargetAbstraction`s, per-task rung annotation as solver-invisible meta (the `Split` pattern), the oracle-chain grid; plus the **static lint** (§4.5) as its validator.
4. Climb-trace report (read-side, over the LEARN trace + oracle-chain records).
5. Sleep-cost counters (unit pending §10c).
6. `taskgen` generators for ladder #1 (+ committed testbed).

**Deferred (later phases):** top-K solution retention ⚡ (RQ3 arm 1; also relaxes E11 corpus burden) · fragment selectors + partial-credit scoring (RQ3 arms 3-5) · `max_considered` budget cap ⚡ (exact cost-matched controls; sharper censored baselines) · early-stop `stop_after_solutions` ⚡ (policy experiment only — §10d).

## 9. Phasing & go/no-go gates

- **Phase 0 — machinery** (§8). Gate: `make check` green; atoms visible end-to-end on a smoke run.
- **Phase 1 — ladder #1** + full oracle chain. Gates: **(kill)** oracle chain shows no cost collapse ⇒ the ladder concept fails as designed — log and stop the program; **(pivot)** oracle collapses but the learner misses/specializes rungs under fully-engineered corpora ⇒ proposer/governance work before more ladders; **(proceed)** both rungs recovered at behavioral grade or better, climb completes.
- **Phase 2 — Families A + B** + calibration ladders. Gate: b^d model fits well enough (residuals systematic, not noise) to size Family C and the anchors.
- **Phase 3 — RQ3 arms + real-ARC anchors.** Expect the governance question (§3 RQ3) to activate here; **(pivot)** if vocabulary tax swamps jump savings by height 4-5 ⇒ governance/forgetting work (library curation) becomes the program.

Queue discipline: each phase's runs get EXPERIMENT_QUEUE.md rows referencing this doc; entries drain to EXPERIMENTS.md per the standing rules.

## 10. Open decisions

Marked open deliberately; to be settled by discussion, then this section re-issued.

- **(a) Method-1's "part of it, not all of it" demonstration condition.** Original intent unclear vs. the proposer matrix (§3): requiring embedded-fragment demos deselects `AntiunifyPairs`. _Proposed resolution:_ full-solution demos at each rung's own level; embedded use arrives automatically one level up. Confirm or state the intent it misses.
- **(b) Rung necessity: strict or permissive?** Strict = every consecutive double jump must be censored (clean amortization attribution; heavier design burden). Permissive = skippable rungs admitted with skippability as a recorded covariate. _Lean:_ strict for batch admission, permissive for exploratory singles.
- **(c) Sleep-cost unit.** Candidates: proposal count + antiunify-pair count (deterministic, O(n²) in solutions); wall-clock as telemetry only. _Lean:_ proposals + pairs; decide before ladder #1's LEARN run or "worth it" silently assumes sleep is free.
- **(d) Early stop.** Option 1: no early stop; track cost-to-first / cost-to-cheapest / cost-paid-full (preserves determinism, locks, and the first-vs-cheapest diagnostic). Option 2: implement `stop_after_solutions` ⚡ and track cost-to-first only. _Lean:_ Option 1; early stop later as a policy experiment.
- **(e) Fragment selection policy** for RQ3 arms 3-5: dumb-filters+generosity vs partial-credit ranking. _Lean:_ partial credit, built when Phase 3 starts, not before.
- **(f) Off-chain mega-primitive cell** (`L_0 ∪ {r*}`): per-ladder, or only ladder #1 + one family? _Lean:_ ladder #1 + Family A (it addresses monolithic-vs-compositional, which is a height question).
- **(g) Spec home:** extend `StudySpec` vs a new `LadderSpec` type. _Lean:_ new type sharing components (a study is a height-1 ladder; keeping both avoids retrofitting leveling onto existing locks).

## 11. Appendix — E12 re-read as the canonical height-2 ladder

The `layered-abstraction` study ([studies.py](../../src/arc_lab/program_search/execution/studies.py), EXPERIMENTS.md 2026-07-12), in this doc's vocabulary:

- **Floor** `L_0` = {flip_h, flip_v, map_color}; **wake budget** `max_depth=3` (two applications).
- **r_1** = `rot180 = flip_h(flip_v(g))`: d_1 = 2; 4 demonstrating tasks + 1 heldout; no free parameters (no variation plan needed); demonstrations full-solution at own level.
- **Top** = `recolor_flipped(g,a,b) = map_color(rot180(g),a,b)`: d_2 = 2 over `L_1`; **inlined depth 3 over `L_0`** — the sandwich held: jump (2) affordable at max_depth=3, inlined top (3) not.
- **Climb trace:** iteration 0 — rung-1 tasks solved raw, top tasks censored; sleep mints `abs0` (**exact** recovery). Iteration 1 — top tasks genuinely re-solved via `abs0`; sleep mints `abs1` (top minted incidentally; **exact**).
- **Enablement** at the learn budget: `L_0` 4/8 train, 1/2 eval → `L_2^learned` 8/8, 2/2. **Deep-budget control** (max_depth=4): `L_0` solves everything raw — the height-2 calibration measurement.
- **Vocabulary tax** (the finding this program scales up): considered 47,464 → 183,648 train (~3.9x) for 3 → 5 primitives; size-model predicts (5/3)^2 ≈ 2.8x.
- **What E12 lacked that this design adds:** the oracle chain (no gifted `L_1` column — learned-vs-oracle flavors not separable), per-generation cost atoms (b_eff unfittable), demonstration-health checks, sleep-cost accounting, and shape metadata (it is a telescope with fan-in 1 — exactly the degeneracy §7's batch must escape).
