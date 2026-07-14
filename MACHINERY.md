# MACHINERY.md

A living catalog of the **machinery** — the mechanisms that search, score, match, and learn — that are, or might be, at play in this system. One of three lever maps: [ONTOLOGY.md](ONTOLOGY.md) maps the **primitives / abstractions** the system _knows_ (lever 1, the Floor); [SEARCH-SPACE.md](SEARCH-SPACE.md) maps the **expressibility-control** levers; this file maps _how the search-and-learning machinery works_ (lever 3, the Machinery). [EXPERIMENTS.md](EXPERIMENTS.md) logs what we tried, and [RESEARCH-2026-07-08.md](docs/RESEARCH-2026-07-08.md) is the frame all three are read against.

> **Grounding pass 2026-07-13:** every file/class/preset reference below re-verified against the post-overhaul tree (`src/arc_lab/program_search/` + the execution layer of [EXECUTION.md](EXECUTION.md)). The old `solvers/dsl/` names (bespoke search classes, `ProgramSearchSolver`, `Config.search.kind`) are gone from this doc; where a mechanism's _finding_ predates the overhaul, the finding stays and the mechanism's current home is named.

It exists because the machinery is not one thing. A flat label like "abstraction governance" hides **≥4 distinct mechanisms** (the E3 bloat had that many causes), and — the load-bearing fact — **machinery components gate each other**: objects need a beam search; real-corpus compression needs subtree-matching; the cell floor needs cost-guided search; the whole low-floor thesis needs a lambda binding. You can't see the critical path or the gaps without a map. This is the map.

## How to read / maintain this

- **One row = one mechanism.** Grouped into **families** (F0–F5) for readability; treat it as one logical table. Each family answers a distinct question (see Mental model).
- The **Interface** column is the most load-bearing attribute after Status: it's the _experiment surface_ — what you can swap and compare **today** (`ABC`/`param`) vs. what's welded shut (`baked`) or absent (`unbuilt`/`learned`).
- The **Gates** column is the point of the doc: what a mechanism blocks or enables. Most `🔜/⚪` rows are gated by exactly one other row — this is a dependency graph, not a flat catalog.
- Add rows as we imagine them; flip **Status** as they ship. Negative findings ("tried, not worth it") get a note here _and_ an entry in `EXPERIMENTS.md`.
- Deliberately **over-complete**: most rows are `⚪ cand` and may never be built. The gaps and the couplings matter more than any single row.

## Terminology (the words we're using)

- **Family** — a machinery component's _role in the pipeline_: what question it answers (F0–F5 below). Orthogonal to Interface and Status.
- **Interface** — a component's _pluggability_, i.e. how you'd experiment on it:
  - `ABC` — behind an abstract base; swap a subclass and re-run (`SearchEngine`, `Cost`, `Constraint`, `LearnEngine`, `AbstractionProposer`, `AbstractionSelector`).
  - `param` — pluggable by parameterization: a field on a frozen component (`CompressionMetric` takes a `Cost`; the engine's capability **policies** — `constant_sources`, `function_hole_fill_mode`, … — are `param` rows), overridable by dotted path via `--set` (`execution/overrides.py`).
  - `fn` — a plain module-level function: reusable, but not yet a formal plug point.
  - `baked` — hardcoded inside another component (e.g. observational-equivalence lives inside `BottomUpSearchEngine`'s absorb/dedup path).
  - `unbuilt` — catalogued, not built. `learned` — needs a trained model.
- **Gates** — the coupling: X _gates_ Y iff Y cannot land (or cannot scale) until X exists. The critical path is the transitive closure of this relation.
- **Confidence** — claims are tagged `[C]` committed · `[H]` working hypothesis · `[O]` open, per RESEARCH.

## Configuring the machinery (data, not subclasses)

A run's machinery is a frozen, content-hashed **`Config`** value
(`program_search/execution/model/config.py`): `library × search_engine × budget × constraints ×
cost × attempts_per_test × learn?` — `learn: LearnSpec | None` discriminates SEARCH vs LEARN runs.
There are **no solver classes**: the execution layer drives `Config` directly (the activity model is
[EXECUTION.md](EXECUTION.md); the engine design is [ARCHITECTURE.md](ARCHITECTURE.md)). The pluggable
axes and where each is selected **today**:

| Axis | Interface | Selected via |
| --- | --- | --- |
| library (Floor) | value | `Config.library` (named libraries: `execution/presets.py::LIBRARIES`) |
| search engine (F1) | `ABC` | `Config.search_engine` — `BottomUpSearchEngine` or `BeamBottomUpSearchEngine` (`search/search_engine.py`), serde-registered in `model/config.py::default_registry` |
| engine capability policies (F1) | `param` | fields on the engine: `constant_sources` · `function_hole_fill_mode` · `polymorphism_instantiation` · `unpinned_type_var_mode` · `function_sample_size` · `beam_width` (Beam only) |
| budget (F1) | value | `Config.budget` (`Budget`: `max_depth` · `max_arity` · `max_pool`) — per-run *data*, passed to `run()`, varied across a study grid while the engine stays fixed |
| cost (F2) | `ABC` | `Config.cost` (default `ProgramSize`, `search/cost.py`) |
| constraint (F2) | `ABC` | `Config.constraints` (default `()` — *extra* filters only; consistency-with-training is the engine's goal test, not a constraint) |
| sleep engine · proposer · selector · metric (F4) | `ABC` | `Config.learn` → `LearnSpec.learn_engine` (`GreedyMDLLearnEngine` / `RefactoringLearnEngine`), whose fields hold the proposer/selector/metric |
| wake-sleep loop params (F4) | value | `LearnSpec`: `iterations` · `early_stop` · `reset_programs_each_wake` · `score_each_wake` |

Every scalar **knob** is data on one of those frozen components, overridable by dotted path —
`--set budget.max_depth=4`, `--set search_engine.beam_width=64` (`execution/overrides.py`;
precedence `defaults < preset < config file < --set`). Representative knobs: `budget.max_depth` ·
`search_engine.beam_width` (32 in the `beam` preset) · `learn.iterations` (5 in the registered
studies) · the `FrequentSubtree` proposer's `min_frequency` (default 2).

Named `PRESETS` (`d4`/`sym`/`synth`/`beam`, `execution/presets.py::PRESETS`) are the historical
solvers as data — one generic engine, presets differing only in library, budget, and policies.
Studies register in `execution/studies.py::STUDIES`. The rest of this file is the catalogue of
mechanisms and their couplings.

## Mental model

Two axes organize everything below.

**Family** — the pipeline spine. Each family answers one question:

| Code | Family | The question it answers | Dominant interface today |
| --- | --- | --- | --- |
| F0 | substrate / representation | what _is_ a program, and how is it run? | `baked` (the physics) |
| F1 | search | which candidate programs do we consider? | `ABC` |
| F2 | scoring | how good is a program / a library? | `ABC` / `param` |
| F3 | matching / equivalence | when are two programs "the same" / does a pattern apply? | `fn` / `baked` |
| F4 | abstraction learning | how does the vocabulary grow? | `ABC` (invention + governance) |
| F5 | instrumentation / science | how do we know it's working? | `fn` |

**Coupling — the doc's real content [H].** Unlike ONTOLOGY, whose primitives are mostly _independent_ rows on a Level spine (you can add `crop_to_content` without touching `rot90`), machinery components **gate each other**, and every recent finding lives in that coupling. So the **Gates column is where the value is**, and the closing section reads the critical path off it.

### Legend

- **Status:**
  - `✅ done` shipped
  - `🔜 next` proposed & prioritized
  - `⚪ cand` catalogued, not prioritized
- **Interface:**
  - `ABC` · `param` · `fn` · `baked` · `unbuilt` · `learned` (defined above).
- **Gates:**
  - `—` means it gates nothing catalogued yet (a leaf).
  - **bold** marks a gate on the critical path.

---

## F0 — substrate / representation

_"What is a program, and how is it run?"_ The physics both loops run on (`program_search/substrate/`). Mostly `baked` — it's the ground, not a plug point. The load-bearing lambda-index binding row (the floor under the whole low-primitive direction) is now built as a Stitch-compatible De Bruijn lambda; what remains unbuilt in F0 are only search-holes (a top-down concern) — a `let` / shared-binding (CSE) is expressible as `Lam`-sugar over the shipped binder, so it's an optimization, not a substrate gap (deliberately not a row).

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Program AST (`Input`/`Param`/`Const`/`Apply`/`If`/`Var`/`Lam`/`AppFn`/`PrimRef`) | programs as typed, inspectable data (`substrate/program.py`); every node kind round-trips both codecs (enforced: `tests/program_search/learn/test_codec_completeness.py`) | `baked` | ✅ | everything |
| Evaluation / interpreter (dual-channel) | virtual-dispatch `evaluate(grid, library, env, scope)` — `env` binds abstraction args (`#j`), `scope` the De Bruijn lambda stack (`$i`), kept distinct so a `build_grid` program becomes a learned abstraction cleanly | `baked` | ✅ | — |
| Variable binding — `Param`/`env` | positional holes for abstraction args | `baked` | ✅ | learned abstractions |
| Variable binding — lambda-index (`build_grid`) | a bound index inside a function argument — built as a **De Bruijn** bound var (`Var` = Stitch's `$i`; `Param` = `#j`) + a `Lam` binder evaluating to a `Closure`; environment-based interp (the `scope` channel), no index-shifting. Stitch-compatible representation | `baked` | ✅ | **size-general geometry from cells; pixels→D4** (search + experiment shipped: E5/E7/E8/E9) |
| Variable binding — search-holes | an unfilled node the search expands | `unbuilt` | ⚪ | top-down search (F1) |
| Type system (`TypeCon` + `ArrowType`/`TypeVar`, HM `unify`) | GRID/COLOR/INT/BOOL/FN/MASK base `TypeCon`s (`substrate/types.py`); arrows + type vars, first-order polymorphism resolved by the F1 instantiation policy. **No OBJECT type** — the Object pathway (segment/render) is entirely unbuilt | `baked` | ✅ | search pruning |
| Library structure (`extended` / versioning / content-addressed store) | the typed vocabulary as a first-class, hashable value (`substrate/library.py`, `store.py`) | `baked` | ✅ | library learning (F4) |
| Leaf / constant seeding (`constant_sources` policy, `search/leaves.py`) | which COLOR/INT/BOOL literals enter round 0: `finite-enumerate` (bounded typed set) / `harvest-from-instance` (literals present in the inputs) / `parameterize` (reserved — mints nothing here, realized in `learn/`); an engine field, never derived from outputs | `param` | ✅ | **cell-floor tractability** (constant blow-up: `finite-enumerate` measured at ~6M candidates on one 30x30 `sym` task) |

## F1 — search

_"Which candidate programs do we consider?"_ (`program_search/search/`, behind the `SearchEngine` ABC.) The overhaul dissolved the old zoo of bespoke search classes (`SingleApply`/`Overlay`/`Tile`/`Enumerate`/`CompositeSearch`/`BeamSearch`/`BuildGridSearch`/`BuildGridBodySearch`) into **two engines** — `BottomUpSearchEngine` and its `BeamBottomUpSearchEngine` subclass — whose *capabilities are policy fields*, and a `Budget` passed to `run()` as per-run data. A concrete search is a point in **four axes** — and only one corner of each is populated:

- **direction:** bottom-up ✅ · top-down ✗ · bidirectional ✗
- **frontier policy:** breadth-first ✅ · beam ✅ · A\* ✗ · MCTS ✗ · stochastic ✗
- **pruning:** observational-equivalence ✅ · type-directed ✅ · deductive ✗
- **guidance:** blind ✅ · heuristic ✗ · learned ✗

MCTS and beam are _frontier policies_, not paradigms; bottom-up/top-down is the _direction_ fork. The engine is bottom-up, so beam is a small tweak but MCTS implies switching to top-down first.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `BottomUpSearchEngine` | THE generic engine (`search/search_engine.py`): typed bottom-up rounds, obs-equiv dedup, per-round `max_pool` cheapest-cut, short-circuit `If` branching (summoned by the library's `if` token), memoized recursive sub-searches, goal test `sig == target` at extraction. Subsumes the old bespoke searches as (preset, budget, policy) points: single-apply ≈ `d4` at `max_depth=2`; composite/enumerate ≈ `synth` at `max_depth=3` | `ABC` | ✅ | — |
| Variadic composition (overlay / tile) | a generic engine capability, not a bespoke search: variadic primitives compose up to `Budget.max_arity` (the `sym` preset: arity 4 ≈ 2x2 tilings). Mosaic-scale tilings are a *budget/vocabulary* choice — `sym`'s 9 lost tile tasks vs the old bespoke `Tile` are a pinned, explained limit (3x3 = nine args; see EXPERIMENTS 2026-07-11) | `baked` | ✅ | mosaic-scale tilings (a budget/capability question on one engine, never a bespoke search again) |
| Variadic commutative-argument dedup (canonical-order fill) | `composition.py`'s `_fill` enumerates a variadic slot as ordered permutations-with-repetition over the pool (`candidates^k`); for a primitive whose variadic argument is provably order-/multiplicity-invariant (`overlay`: elementwise `max` over a stack, `substrate/primitives/combinators.py`), that mints `k!`-redundant candidates that immediately dedupe away. Measured on a `d4+combinators` run: `overlay` alone was **62% of the run's total considered candidates** (298,550/482,315), 99.9% deduped at arity 4, 100% at arity 1 (2026-07-14 investigation, `runs/2026-07-14/20260714_005712_e693f88791aff9fa`). Same shape as the `eq` reflexive/symmetric pruning idea two rows below (a `Primitive.commutative`-style flag), applied to the variadic-fill path instead of the polymorphic-floor pairwise path — the two should probably share one flag | `unbuilt` | ⚪ | **`overlay` / any future commutative combinator at scale** — the single largest measured search-cost contributor on a combinator-bearing library found so far |
| Cost-guided **beam** (`BeamBottomUpSearchEngine`) | keep only the cheapest `beam_width` per round instead of the `max_pool` cut — the search that consumes `Cost` round-by-round. The truncation's cost is visible and locked: `beam` 9/400 vs `synth` 11/400 on `arc1-train`; a 16-wide beam fills with size-1 constants and starves GRID entirely (measured 0/400 → width 32 + harvest constants) | `ABC` | ✅ | **objects (F4-scale), cell-floor at scale** (payoff lands with a pool that explodes) |
| `constant_sources` policy | see the F0 leaf-seeding row — the same field, viewed from search | `param` | ✅ | cell-floor tractability |
| `function_hole_fill_mode` policy (`none` / `point-free` / `lambda-synthesis`) | how arrow-typed holes get filled. `point-free`: pooled function values (`PrimRef`/`AppFn`, deduped by sampled-argument signatures, `function_sample_size`). `lambda-synthesis`: recursive body search per hole — binders from the hole's peeled arrow, body contexts + local targets from the primitive's `body_sampler`, goal-directed via `EnclosingTarget` propagation, terminating by `Budget.descend()`. This is the old `BuildGridSearch`/`BuildGridBodySearch` pair, generalized: the body grammar is just the library (every `INT^n→INT` primitive incl. a *learned* `mirror_index` — the E8/E9 reuse that dissolved the beam cliff: speedup ×3.5–5, +20 tasks), and the per-cell **decision** floor (`eq`/`if`/BOOL, `primitives/control.py`) composes uniformly in the body | `param` | ✅ | **pixels→D4** (E5/E7); per-cell decision language (mask / conditional recolor) beyond geometric transforms |
| `polymorphism_instantiation` policy (`monomorphize` / `bounded` / `unrestricted`) | what happens to a composed result type's free type vars: reject; ground over the bounded task-reachable monotype universe; or pool canonicalized polymorphic entries re-instantiated per round (`search/polymorphism.py`) | `param` | ✅ | higher-order / polymorphic vocabulary in search |
| `unpinned_type_var_mode` (`reject` / `eager_grounding_over_universe` / `lazy_synthesis`) | the *binder-type* analog for lambda holes no sibling pins (e.g. `map`'s `a→b`): skip, or ground eagerly over the universe (each grounding triggers a full recursive body search — measured cost-vs-depth in EXPERIMENTS 2026-07-11). `lazy_synthesis` (true deferred resolution) is **unbuilt — constructing the engine with it raises** | `param` | ✅ (`lazy_synthesis` unbuilt, raises) | `map`-style HOFs without hand-pinned types |
| Goal-type derivation (`derive_goal_type`) | derive the run's goal type from the task instead of the hardwired `GRID` default — **unbuilt, raises**; nothing else is derivable until `Task`/`Example` become generic over output type (a foundational change). The gap is named in code, not silent | `unbuilt` | ⚪ | non-GRID goals (COLOR/INT answers, Object outputs) |
| Polymorphic-floor search-cost control | the polymorphic control floor makes each round ~O(pool²) — `eq(a,a)` ranges over every same-typed pair — so cost today is bounded only by `max_pool`/`beam_width`. Two deliberate reductions remain unbuilt: **(a)** reflexive/symmetric pruning via a `Primitive.commutative` flag (skip `eq(x,x)` and `eq(b,a)` duplicates, ~2×); **(b)** a **cost-bounded per-round candidate budget** — expand cheapest-first to a hard cap so a polymorphic op can't emit O(pool²) unbounded | `unbuilt` | ⚪ | **`eq`/`if` at scale** (the honest scaling fix for the control floor; a design change, done deliberately) |
| Cost-ordered / priority enumeration | expand cheapest-first, anytime stop | `unbuilt` | ⚪ | anytime budgets |
| Iterative deepening at the driver (early stop) | `run()` calls `_enumerate` once for the *entire* `budget.max_depth`, never checking whether a shallower round already satisfied the goal before paying for deeper ones. ARCHITECTURE.md §5 already names the resolution ("call `_enumerate` with increasing `max_depth`, extracting after each; the §9 cache makes the shared prefix free") but `run()` doesn't do it (grepped: zero hits). Measured on `rot90-*` under `d4+combinators`: 37K-74K considered / up to ~4s per task to reach a program findable in 9 candidates / <1ms under plain `d4` (2026-07-14 investigation, `runs/2026-07-14/20260714_005712_e693f88791aff9fa` vs `...5a12f4f22a40a895`). Sound whenever `Cost` is non-decreasing under composition (true of `ProgramSize`) — provably wouldn't change any `ranked_programs[0]` or lock assertions, since bottom-up rounds only grow cost | `unbuilt` | ⚪ | cheap, safe win on any task solvable well under `max_depth` — compounds with the variadic-commutative-dedup row above (both fire on every round up to `max_depth`) |
| Cross-run depth checkpoint/resume (warm-start `max_depth`) | **to do soon.** `max_depth` is content-hashed into `RunSpec`, so a `max_depth=3` run and a `max_depth=4` run are today two fully independent runs — the deeper one silently re-enumerates rounds 1-3 from scratch, even though `_select_frontier` (`search_engine.py:744-752`) is a pure function of `(pool, max_pool)` only, so the round-3 `Pool` is a sound warm-start seed for round 4. Distinct from the row above: that's automatic single-process early-stop sharing the §9 recursive-sub-search memo (keyed *with* `budget`, so it can't cross depths either); this is user-controlled, cross-process resumption — run shallow, inspect `results.json`, go deeper cheaply — via a new opt-in checkpoint cache keyed on everything *except* `max_depth`, sitting outside run identity the same way `Pool` itself already is (`pool.py:8`: "never hashed, never part of the run identity"). Full design: [docs/CHECKPOINT-RESUME-2026-07-14.md](docs/CHECKPOINT-RESUME-2026-07-14.md) | `unbuilt` | ⚪ | the "how long will this run take" problem — start shallow and cheaply deepen instead of guessing a `max_depth` up front |
| Top-down / A\* over holes | goal-directed refinement of partial programs | `unbuilt` | ⚪ | needs F0 search-holes |
| Bidirectional / inverse semantics | grow bottom-up from inputs and top-down from the (known) output, meet in the middle — the target is given in ARC, so both ends are anchored. The engine carries the named gap: `inverse_semantics_propagation=True` **raises `NotImplementedError`** at construction (a goal-seeded pass needing an `inverse_semantics` primitive capability — distinct from the shipped `EnclosingTarget` propagation) | `unbuilt` | ⚪ | needs the bottom-up engine (✅) _and_ inverse primitive semantics; high complexity (the axis lists it `bidirectional ✗` — this is that row) |
| MCTS | tree search + rollouts over program construction | `unbuilt` | ⚪ | learned guidance _or_ an MDL-guided refinement space (Ferré/MADIL runs MCTS over models, MDL-guided, no net) |
| Neurally-guided search | learned policy/value proposes expansions | `learned` | ⚪ | the bootstrap speedup at scale |

## F2 — scoring

_"How good is a program, or a library?"_ The objective functions: the **filter** (a hard predicate) and the **rank** (a soft cost), plus the corpus-level aggregate that is the governance objective. Note the ONTOLOGY point — _the library itself is a prior_ — so F2 and F0's library are entangled.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Goal test (`sig == target`) | the spec: the pool's cached behaviour signature equals the training outputs (`search/extraction.py`) — the *definition* of a solution, not a pluggable filter. The old `ConsistentWithTraining` constraint class is gone: consistency is the engine's own goal test now | `baked` | ✅ | — |
| `Constraint` (extra filter) | genuinely *extra* inductive-bias predicates on goal-test survivors (`search/constraints.py`; e.g. a shape prior). The seam is live in `Config.constraints` (run identity) but default-empty — **zero concrete constraints shipped** | `ABC` | ✅ (seam; no concrete instances) | inductive-bias experiments |
| `ProgramSize` (rank) | node count — the Occam prior (`search/cost.py`; costs compose by summation, see the module docstring's MDL framing) | `ABC` | ✅ | — |
| Bit-weighted cost | real bits, not node count: each `Apply` costs `log2(len(lib))` | `unbuilt` | ⚪ | real DL units vs. node-count |
| Learned prior (−log P) | data-dependent ranking toward an MDL objective | `learned` | ⚪ | amortized guidance |
| `CompressionMetric` (flat two-part) | `DL = library_bits + Σ program_bits`, flat library term (`analysis/compression.py`; parameterized by a `Cost`) | `param` | ✅ | — |
| `TwoPartMDL` | charges each learned abstraction its _definition size_ (`analysis/compression.py`) | `param` | ✅ | **clean governance** (E4: 16→1) |

## F3 — matching / equivalence

_"When are two programs the same, or does this pattern apply?"_ One family that **cross-cuts** — the same question is behavioral dedup in F1, template rewriting in F4, and the behavioral checker in F5 — on a spectrum **exact-structural ↔ behavioral ↔ partial/soft**.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Observational equivalence | dedup by behavior-signature (`search/signature.py` + `Pool.add_dedup`) — **the overhaul unified the old two baked flavors into one path**: value programs sign over the train contexts, lambda bodies over the `body_sampler`'s contexts (the old cell-battery, now just a recursive sub-search's contexts), function values over sampled argument tuples (`function_sample_size`). Partial signatures (⊥ on some contexts) stay pooled — what makes domain-splitting `If` work | `baked` (inside the engine's absorb path) | ✅ | search dedup, the checker |
| `EquivalenceOracle` plug point | lift the signature *source* behind an ABC so it swaps: train-inputs · **k generated / random grids** (tune k for speed↔discrimination, mind out-of-distribution false splits). The old two-flavors-no-seam argument is discharged by the unification above; what remains is making the probe source pluggable — still **≠ adopting egg** (strategy: obs-equivalence is fine for now) | `unbuilt` | ⚪ | soundness-tunable, pluggable dedup |
| Structural antiunify / match (LGG + var-sharing) | most-specific common template (`learn/antiunify.py::_antiunify`); the same differing pair recurring at several positions reuses **one** `Param` (the memo — the E3 `swap_cells` requirement, built); antiunifies through `If` and under same-typed `Lam` binders | `fn` | ✅ | abstraction proposal (E3) |
| `rewrite_with` (subtree fold) | fold **every** subtree matching a template into an abstraction call — nested occurrences, **and inside `Lam` bodies** (the E8 fix) — root-only rewriting is the degenerate case, no longer a separate mechanism (`learn/antiunify.py::rewrite_with`/`match`) | `fn` | ✅ | **compression on heterogeneous corpora; folding a coordinate idiom _under_ a binder** |
| Partial / soft match scoring | graded "how close" rather than exact | `unbuilt` | ⚪ | fuzzy reuse |

## F4 — abstraction learning

_"How does the vocabulary grow?"_ (`program_search/learn/`.) The wake–sleep loop: **invention** (propose candidates), **governance** (select which earn a name), **the loop policy** (when/how long to sleep), and **library management**. One sleep is `LearnEngine.run(library, solutions) → LearnOutcome` (`learn/learn_engine.py`, an `ABC`; concrete: `GreedyMDLLearnEngine` and `RefactoringLearnEngine` in `learn/engines.py`), composing an `AbstractionProposer` (invention) with an `AbstractionSelector` (governance, `GreedyMDL` default — lifted into `learn/selection.py` after E3 proved it's plural) under a `CompressionMetric`. The loop around sleep is **data, not a class**: `LearnSpec` params in the run identity (`iterations` / `early_stop` / `reset_programs_each_wake` / `score_each_wake`). Only library management (extend / fold / rename) stays `baked` inside the engines.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `AntiunifyPairs` proposer (LGG, var-sharing; `bound_var_safe`) | mine recurring whole-program structure into closed templates (`learn/antiunify.py`); the safe variant refuses to hole a bound `$i` into a `#j` abstraction arg | `ABC` | ✅ | **sound abstraction over lambdas** (E6 breaks, E7 fixes — the flat-vs-fixed contrast) |
| `FrequentSubtree` proposer (naive) | mine recurring **proper subtrees** (Lam-free; sound Var-holing — the mirror image of `bound_var_safe`; `min_frequency` gate; `If`-rooted subtrees minable too) into closed templates; invents cross-member idioms whole-program antiunify can't (`mirror_index`) | `ABC` | ✅ | cross-member idioms — but greedy MDL over train-DL prefers larger _unreusable_ `COLOR` read-body idioms: the **compression/reusability divergence** (E8) |
| Type/signature-scoped invention (`TypeScopedFrequentSubtree` / `SearchScopedFrequentSubtree`) | keep only candidates of the type/signature the consumer composes — _declared_ (`result_type`), or **derived from the search** (a `composes` callable); recovers `mirror_index`. `SearchScoped`'s callable can't serialise, so it is **programmatic-only** (deliberately absent from `default_registry` — never a preset ingredient) | `ABC` | ✅ (**stopgap**) | E8/E9 bootstrap — but _anti-open-ended_ (can't grow non-composable / new-type vocabulary); a labelled stopgap, not the general fix |
| Search-aware / selection-correct governance | a selector scoring candidates by a **train-side usefulness** signal (search-effort reduction at fixed budget), not train node-count — the goal is an _accurate_ useful/not-useful verdict (chase **false-negatives** like `mirror_index`), **not** minting everything invention-complete. The 2026-07-08 correlation read (compression does NOT predict transfer; naive 0 vs scoped 5 on the same held-out) is its empirical mandate | `unbuilt` | 🔜 | the general, non-scoping fix to the E8 divergence (train-DL ≠ reusability); consumes the F5 usefulness score |
| Learned / guided _proposal_ | a learned prior over _which_ candidates to mine ("patterns of thinking": bias invention toward the antiunification shapes that paid off before) — the **proposer-side** analog of search-aware _selection_ above | `learned` | ⚪ | amortized invention — distinct from selection-time governance; **defer hard** (strategy category B: adopting a net kills determinism) |
| Invent-broad + prune-unused | mint top-K, let the search use what it can, GC the rest — open-ended, cheap cousin of search-aware governance | `unbuilt` | ⚪ | reusability without a type gag |
| Library refactoring (`RefactoringLearnEngine` + `StitchProposer`) | compress the **library**, not just the corpus: `rewrite_library_definitions` folds a shared factor into the minted _definitions_ (`learn/engines.py`), with Stitch (`learn/stitch_shim.py` — the sole `stitch_core` boundary; invention only, our metric governs) as the refactor proposer. E10: recovers a composable `mirror_index` first-order, no type gag. **A labelled first-order stopgap**: single-pass "Stitch mines the corpus" is real but emits the *higher-order* idiom (perceiver as a function arg); the two-phase split is superseded once higher-order Stitch mines the corpus in one pass | `ABC` | ✅ (**first-order stopgap**) | the open-ended general fix to the E8 divergence — sibling of selection-correct governance |
| Greedy-MDL selection (`GreedyMDL`) | add the single candidate that most lowers two-part DL, repeat until dry — the default `AbstractionSelector` (`learn/selection.py`) | `ABC` | ✅ | (bloat source under flat MDL; myopic — see Beam / joint selection) |
| Governance as a plug point (`AbstractionSelector` ABC) | selection behind an ABC on the learn engine so strategies swap/compare — and hash into the run identity | `ABC` | ✅ | testable governance (E3 proved it's plural) |
| Library-dedup guard | never re-mint a template already a primitive (`GreedyMDL.select`'s existing-template filter) | `baked` | ✅ | anti-re-mint (E3 hardening) |
| DL-monotonicity stop | a candidate mints only if it *strictly lowers* DL (`GreedyMDL` returns `None` otherwise) and the loop's `early_stop` halts on a converged sleep (`LearnOutcome.converged`) | `baked` | ✅ | convergence (E3 hardening) |
| Keep-cheapest wake | the pool keeps the cheapest, not first-considered, program per behavior (`Pool.add_dedup`), and extraction ranks solutions cheapest-first | `baked` | ✅ | removes the latent bloat root cause |
| Beam / joint selection | non-greedy abstraction _sets_ | `unbuilt` | ⚪ | jointly-compressing abstractions |
| Wake-sleep loop policy (`LearnSpec` params ✅; plateau / freq / online triggers ⚪) | when/how long to sleep is now **data in the run identity**, not a `LearnTrigger` class: `iterations` (cap) + `early_stop` (converged sleep) + `reset_programs_each_wake` ≈ the old each-generation trigger; adaptive triggers (plateau / frequency / online) would be new `LearnSpec` policy | value | ✅ | — |
| Library retirement / pruning | drop abstractions that stop paying | `unbuilt` | ⚪ | long-run library health |
| Wake–sleep orchestration | solve → compress → extend → repeat: the LEARN branch of `execute()` (`execution/execute.py`) — ONE recorded run, checkpointed at iteration grain (each sleep row carries the library), crash-safe and resumable; the final wake is the derived SEARCH run (`run_search_learn`) | `baked` (execution layer) | ✅ | — |

## F5 — instrumentation / science

_"How do we know it's working?"_ (`program_search/analysis/`, the read-side activities `execution/analyze_run.py` and `execution/run_study.py::create_study_report`, and `taskgen/`.) The machinery of _studying_ the machinery — orthogonal to solving. This is where the anti-teleological discipline is enforced: targets are observables here, never a training signal (structurally: nothing on the execution path reads `StudySpec.target_abstractions`). And mind the split **[H]**: compression is _also_ the governance objective (F2/F4), so it's a **leading/process** signal, not the grade — the grade is held-out **transfer**. Never grade the optimizer by its own objective; watch whether compression _predicts_ transfer (measured 2026-07-08: **it doesn't** — see the correlation row).

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Compression / speedup ratios | derived read-side from stored observations — the artifact stores DL / `considered_total` only, never a ratio; the study report computes per-cell effort + `speedup_vs_L1` (`create_study_report::_effort_comparison`), and `analyze_run` summarizes per-task effort / the learn trajectory | `fn` | ✅ | — |
| Unreachable-primitive diagnostic | flag (at run end, or folded into `search_stats`) any library primitive that appears in **zero** candidates all run — silently possible today: `overlay`/`tile` require an `INT`/`COLOR` leaf that only a `constant_sources` entry can supply (`search/leaves.py`), so setting `constant_sources=()` on `d4+combinators` makes both combinators structurally unreachable while the run still reports its library as `d4+combinators` — confirmed 2026-07-14 (`runs/2026-07-14/20260714_021804_9eca4fa0709d64f5`, zero `overlay`/`tile` entries in `by_primitive`, vs `...e693f88791aff9fa` with the same library and `constant_sources` set). `by_primitive` (`search/tracking.py`) already has the data this needs; it's a read-side check away | `unbuilt` | ⚪ | config legibility — catches "this run doesn't test what its library name suggests" silently |
| Transfer / enablement metric | **the held-out grade is built**: every learn activity runs the grown library on train (**train-usefulness**) and, if provided, on an eval corpus the loop never touches (**transfer**) as ordinary recorded runs (`run_search_learn`); the study report reads train↔eval solve rates per (library, budget) (`_transfer_metrics`). First readings: E1 4/4 on the new stack; E1–E9 pre-overhaul via the old tree's `heldout_transfer` | `fn` | ✅ | the _grade_ (train↔held-out) — what selection-correct governance is judged against |
| Per-abstraction usefulness score | a **train-side** proxy (search-effort reduction / enablement at fixed budget on _train_) that governance consumes _without_ contaminating the held-out grade. Built pre-overhaul (`Usefulness`, old tree, cda7c91) — **not yet re-landed on the execution layer**, which is what F4's selection-correct governance needs | `fn` | 🔜 | selection-correct governance (F4) |
| Compression↔transfer correlation | the diagnostic that tests the MDL premise — _does compression predict transfer?_ **Ran across E1–E9 (2026-07-08): it does not.** E7: worst compression (×0.79), perfect transfer (6/6); within-experiment, the compression-greedy pick transfers 0 vs the scoped pick's 5 on the same held-out. The harness lives in the old tree (port pending, like the usefulness score) — the *finding* stands and mandates F4's selection-correct governance | `fn` | ✅ (first read done; harness port pending) | adjudicated governance-vs-gap-climbing; quantified the E8 divergence |
| Behavioral checker | the study report's behavioral check (`run_study.py::_matches_target`): invented vs target primitives by **behavior** — identical templates, else probe-based semantic equivalence over type-matched argument permutations, capped at `MAX_PROBE_COMBOS=512` (the cap recorded, never silent) | `fn` | ✅ | anti-teleological measurement |
| Run artifact | the whole execution layer: `RunSpec = Config × Corpus` → content-hashed `run_id`, executed once by `execute()` (the ONLY writer of `runs/`), cached, crash-safe, resumable; `runs/` a gitignored regenerable cache | `baked` (execution layer) | ✅ | reproducibility — and free cache hits across a study grid |
| Three-library compare | the study grid: **L1** (start) / **L2** (learned) / **L3** (L1 + targets) × budgets × (train, eval) as plain recorded runs (`run_study`) | `fn` | ✅ | — |
| Testbed generator (`taskgen`) | deterministic synthetic tasks with known-reachable targets and solver-invisible train/heldout split metadata — `taskgen/generators.py::GENERATORS`, committed under `testbeds/`, regenerated via `arc-lab taskgen <name>` | `fn` | ✅ | controlled experiments |
| Curriculum generation | real / staged task distributions (lever-2-adjacent) | `unbuilt` | ⚪ | curriculum experiments |

---

## What the map shows

- **The critical path (what gates what) [H].** Cleared. All five mechanisms that gated the downstream have shipped:
  - **cost-guided beam** (F1, `BeamBottomUpSearchEngine`) → objects at scale, the cell floor on real grids — _done_; the search that consumes `Cost` (on the new engine the truncation's cost is locked and visible: `beam` 9/400 vs `synth` 11/400).
  - **subtree-match rewrite** (F3) → real, measurable compression on any heterogeneous corpus — _done_.
  - **governance as a plug point + keep-cheapest wake** (F4, `AbstractionSelector`/`GreedyMDL`) → testable governance, and the latent-bloat root cause removed — _done_ (behavior-preserving on E1–E4).
  - **two-part MDL + the two hardening guards** (F2/F4) → clean governance — _done_ (E4 + the E3 hardening), which is why the loop stays honest today.
  - **lambda-index binding** (F0) → size-general geometry from cells, the pixels→D4 keystone — _done_ (the Stitch-compatible De Bruijn `$i` / `Lam` / `Closure` substrate + the `build_grid`/`width`/`height`/`sub` clique). And **pixels→D4 is now achieved end-to-end and _compresses_**: open-term lambda synthesis (F1, then the bespoke `BuildGridSearch`, since dissolved into the engine's `lambda-synthesis` fill mode) + the loop re-derive the whole D4 group from the cell floor, blind (E5 rot90; E7 all six), after a bound-var soundness fix to antiunify (E6→E7); then a **`FrequentSubtree` proposer** (F4) invents `mirror_index` and — because the body grammar is _primitive-driven_ (just the library) — the search **reuses** it, so the ladder compresses (E8/E9: DL ×1.12, inverting E7's ×0.79) and the beam cliff dissolves (speedup ×3.5–5, +20 tasks). The catch (E8): greedy MDL over train-DL prefers larger _unreusable_ read-body idioms; the reusable one is recovered by _scoping invention to what the search composes_ — a knowingly-limited **stopgap**. The open-ended general fix, **library refactoring**, has since shipped too (`RefactoringLearnEngine` + Stitch, E10) — itself a labelled *first-order* stopgap until higher-order Stitch mines the corpus in one pass.
  - Since then the **whole machinery became data**: the `RunSpec × Config` refactor + execution overhaul (2026-07-09/11) dissolved the bespoke search classes into the two generic engines and made every mechanism above a frozen, content-hashed, `--set`-overridable `Config` component. The locks were deliberately re-pinned on the new engine (`d4` 7 = old, `synth` 11 = old, `sym` 10 vs old 19 — the tile gap explained as budget/vocabulary, `beam` 9 newly locked).
- **The experiment surface today** is the `ABC`/`param` rows: `SearchEngine` (`BottomUpSearchEngine`/`BeamBottomUpSearchEngine` + their capability-policy fields), `Cost`, `Constraint`, `LearnEngine` (`GreedyMDLLearnEngine`/`RefactoringLearnEngine`), `AbstractionProposer`, `AbstractionSelector`, the `CompressionMetric` family, and every scalar knob via `--set` dotted paths. That is where you can swap-and-compare _right now_ — with cache-hit reruns free.
- **`baked`-in that arguably should still be pluggable:** observational equivalence — the overhaul *unified* the old two baked flavors into one absorb/signature path inside the engine, discharging the "no shared seam" complaint; what remains of the `EquivalenceOracle` case (F3) is making the probe *source* pluggable (k generated/random grids). Governance was lifted behind `AbstractionSelector` long ago, so the E3 argument there is discharged too.
- **Emptiest / highest-leverage families:** F0 is complete (through higher-order: `Lam`/`AppFn`/`PrimRef` + polymorphism policies), and **both** general fixes to the E8 compression/reusability divergence now have machinery — library refactoring shipped (E10, first-order stopgap); _selection-correct governance_ remains the unbuilt 🔜, gated on porting the F5 usefulness score to the execution layer. Beyond that: the wider A\*/MCTS/stochastic corner, recalibrating the E2–E10 environments onto the generic engine (queued), and — per the strategy — pointing the loop at real ARC tasks rather than another microworld.
- **The frame the map serves (RESEARCH-08) [H]:** the research object is **axis 2 — the search-cost graph** (how machinery reshapes the low→high mapping); expressive completeness and the F5 **transfer-measurement layer** are _prerequisites_, not goals. That measurement layer has since landed (the held-out grade; the study grid) and its first read is in: **compression does not predict transfer** (E1–E9, 2026-07-08) — which adjudicates the next lever as F4 selection-correct governance. F4 governance and F1/F3 search are the levers that reshape axis 2; F5 is how we know they did.
- **Build vs. adopt vs. defer:** which of these rows to build ourselves, adopt from a mature tool (Stitch/babble/egg), or defer until a real task demands them is a _strategy_ question, not a map question — see [MACHINERY-STRATEGY-2026-07-07.md](docs/MACHINERY-STRATEGY-2026-07-07.md), read against [RESEARCH-2026-07-08.md](docs/RESEARCH-2026-07-08.md).
