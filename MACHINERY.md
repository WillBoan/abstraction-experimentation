# MACHINERY.md

A living catalog of the **machinery** — the mechanisms that search, score, match, and learn — that are, or might be, at play in this system. Sibling to [ONTOLOGY.md](ONTOLOGY.md): that file maps the **primitives / abstractions** the solver _knows_ (lever 1, the Floor); this file maps _how the solver works_ (lever 3, the Machinery). Together they cover the solver; [EXPERIMENTS.md](EXPERIMENTS.md) logs what we tried, and [RESEARCH-2026-07-08.md](RESEARCH-2026-07-08.md) is the frame both are read against.

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
  - `ABC` — behind an abstract base; swap a subclass and re-run (`Search`, `Cost`, `Constraint`, `AbstractionProposer`, `LearnTrigger`).
  - `param` — pluggable by parameterization (`CompressionMetric` takes a `Cost`; `TwoPartMDL` subclasses it).
  - `fn` — a plain module-level function: reusable, but not yet a formal plug point.
  - `baked` — hardcoded inside another component (e.g. observational-equivalence lives inside `Enumerate`).
  - `unbuilt` — catalogued, not built. `learned` — needs a trained model.
- **Gates** — the coupling: X _gates_ Y iff Y cannot land (or cannot scale) until X exists. The critical path is the transitive closure of this relation.
- **Confidence** — claims are tagged `[C]` committed · `[H]` working hypothesis · `[O]` open, per RESEARCH.

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

_"What is a program, and how is it run?"_ The physics both loops run on (`substrate/`). Mostly `baked` — it's the ground, not a plug point. The load-bearing lambda-index binding row (the floor under the whole low-primitive direction) is now built as a Stitch-compatible De Bruijn lambda; what remains unbuilt in F0 are only search-holes (a top-down concern) — a `let` / shared-binding (CSE) is expressible as `Lam`-sugar over the shipped binder, so it's an optimization, not a substrate gap (deliberately not a row).

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Program AST (`Input`/`Const`/`Apply`/`Param`) | programs as typed, inspectable data (`program.py`) | `baked` | ✅ | everything |
| Evaluation / interpreter (`env`-threaded) | virtual-dispatch `evaluate(grid, library, env)` | `baked` | ✅ | — |
| Variable binding — `Param`/`env` | positional holes for abstraction args | `baked` | ✅ | learned abstractions |
| Variable binding — lambda-index (`build_grid`) | a bound index inside a function argument — built as a **De Bruijn** bound var (`Var` = Stitch's `$i`; `Param` = `#j`) + a `Lam` binder evaluating to a `Closure`; env-based interp, no index-shifting. Stitch-compatible representation | `baked` | ✅ | **size-general geometry from cells; pixels→D4** (search + experiment shipped: E5/E7/E8/E9) |
| Variable binding — search-holes | an unfilled node the search expands | `unbuilt` | ⚪ | top-down search (F1) |
| Type system (`BaseType` + `ArrowType`/`TypeVar`, HM `unify`) | GRID/COLOR/INT/FN base singletons; arrows + type vars; MASK/OBJECT reserved | `baked` | ✅ | search pruning |
| Library structure (`extended` / versioning) | the typed vocabulary as a first-class value | `baked` | ✅ | library learning (F4) |
| Leaf / constant mining (`_leaf_constants`, `coord_ints`) | which COLOR/INT literals enter search | `baked` | ✅ | **cell-floor tractability** (coord blow-up) |

## F1 — search

_"Which candidate programs do we consider?"_ (`search/`, behind the `Search` ABC.) A concrete search is a point in **four axes** — and only one corner of each is populated:

- **direction:** bottom-up ✅ · top-down ✗ · bidirectional ✗
- **frontier policy:** breadth-first ✅ · beam ✅ · A\* ✗ · MCTS ✗ · stochastic ✗
- **pruning:** observational-equivalence ✅ · type-directed ✅ · deductive ✗
- **guidance:** blind ✅ · heuristic ✗ · learned ✗

MCTS and beam are _frontier policies_, not paradigms; bottom-up/top-down is the _direction_ fork. The engine is bottom-up, so beam is a small tweak but MCTS implies switching to top-down first.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `SingleApply` / `Overlay` / `Tile` | bespoke depth-1 and combinator searches | `ABC` | ✅ | — |
| `Enumerate` | bottom-up, typed, obs-equiv dedup, `max_pool` cap | `ABC` | ✅ | — |
| `CompositeSearch` | run strategies in sequence, dedup | `ABC` | ✅ | — |
| Cost-guided **beam** (`BeamSearch`) | keep top-K grids by cost per round vs. the blind `max_grid_args` cut; overrides one `_grid_frontier` seam on `Enumerate` | `ABC` | ✅ | **objects (F4-scale), cell-floor at scale** — the first search to consume `Cost` (near-lossless on the atomic floor; payoff lands with a pool that explodes) |
| `BuildGridSearch` (open-term, **primitive-driven**) | bespoke: enumerate coordinate-lambda _bodies_ (`$i` seeded) by composing **every `INT^n→INT` primitive the library carries** (`sub`/`add`/`mul` + any _learned_ coordinate), cell-battery obs-equiv dedup, cost-beam, assemble + verify a `build_grid` program | `ABC` | ✅ | **pixels→D4** (E5/E7); its **beam cliff** is _dissolved_ by a learned `mirror_index` the search now reuses (E8/E9: speedup ×3.5–5, +20 tasks enabled). The affine grammar (`+add/mul`) widens the base search (~3× effort) — the honest cost of not narrowing to `sub` |
| Cost-ordered / priority enumeration | expand cheapest-first, anytime stop | `unbuilt` | ⚪ | anytime budgets |
| Top-down / A\* over holes | goal-directed refinement of partial programs | `unbuilt` | ⚪ | needs F0 search-holes |
| Bidirectional | grow bottom-up from inputs and top-down from the (known) output, meet in the middle — the target is given in ARC, so both ends are anchored | `unbuilt` | ⚪ | needs both the bottom-up engine (✅) _and_ F0 search-holes; high complexity (the axis lists it `bidirectional ✗` — this is that row) |
| MCTS | tree search + rollouts over program construction | `unbuilt` | ⚪ | learned guidance _or_ an MDL-guided refinement space (Ferré/MADIL runs MCTS over models, MDL-guided, no net) |
| Neurally-guided search | learned policy/value proposes expansions | `learned` | ⚪ | the bootstrap speedup at scale |

## F2 — scoring

_"How good is a program, or a library?"_ The objective functions: the **filter** (a hard predicate) and the **rank** (a soft cost), plus the corpus-level aggregate that is the governance objective. Note the ONTOLOGY point — _the library itself is a prior_ — so F2 and F0's library are entangled.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `ConsistentWithTraining` (filter) | the spec: matches every train pair | `ABC` | ✅ | — |
| `ProgramSize` (rank) | node count — the Occam prior | `ABC` | ✅ | — |
| Bit-weighted cost | real bits, not node count: each `Apply` costs `log2(len(lib))` | `unbuilt` | ⚪ | real DL units vs. node-count |
| Learned prior (−log P) | data-dependent ranking toward an MDL objective | `learned` | ⚪ | amortized guidance |
| `CompressionMetric` (flat two-part) | `DL = library_bits + Σ program_bits`, flat library term | `param` | ✅ | — |
| `TwoPartMDL` | charges each abstraction its _definition size_ | `param` | ✅ | **clean governance** (E4: 16→1) |

## F3 — matching / equivalence

_"When are two programs the same, or does this pattern apply?"_ One family that **cross-cuts** — the same question is behavioral dedup in F1, template rewriting in F4, and the behavioral checker in F5 — on a spectrum **exact-structural ↔ behavioral ↔ partial/soft**.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Observational equivalence | dedup by behavior-signature — over **train inputs** (`Enumerate`) or a **cell-battery** (`BuildGridSearch`); **two baked flavors, no shared seam** | `baked` (Enumerate, BuildGridSearch) | ✅ | search dedup, the checker |
| `EquivalenceOracle` plug point | lift obs-equiv behind an ABC so the signature source swaps: train-inputs · cell-battery · **k generated / random grids** (tune k for speed↔discrimination, mind out-of-distribution false splits) | `unbuilt` | ⚪ | soundness-tunable, pluggable dedup — two baked flavors already exist so the seam is latent; a small internal refactor, **≠ adopting egg** (strategy: obs-equivalence is fine for now) |
| Structural antiunify / match (LGG + var-sharing) | most-specific common template; shared subterm → shared `Param` | `fn` | ✅ | abstraction proposal (E3) |
| `rewrite_with` (root-match) | replace a whole program with an abstraction call | `fn` | ✅ | — |
| Subtree-match rewrite | fold any matching subtree — nested occurrences, **and inside `Lam` bodies** (the E8 fix) — not just the root | `fn` | ✅ | **compression on heterogeneous corpora; folding a coordinate idiom _under_ a binder** |
| Partial / soft match scoring | graded "how close" rather than exact | `unbuilt` | ⚪ | fuzzy reuse |

## F4 — abstraction learning

_"How does the vocabulary grow?"_ (`learn/`.) The wake–sleep loop: **invention** (propose candidates), **governance** (select which earn a name), **trigger** (when to sleep), and **library management**. Invention, trigger, and now **governance** (`AbstractionSelector`, `GreedyMDL` default — lifted out of `learn()` into `learn/selection.py` after E3 proved it's plural) are all `ABC`s; only library management stays `baked`.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `AntiunifyPairs` proposer (LGG, var-sharing; `bound_var_safe`) | mine recurring structure into closed templates; the safe variant refuses to hole a bound `$i` into a `#j` abstraction arg | `ABC` | ✅ | **sound abstraction over lambdas** (E6 breaks, E7 fixes — the flat-vs-fixed contrast) |
| `FrequentSubtree` proposer (naive) | mine recurring **proper subtrees** (Lam-free; sound Var-holing — the mirror image of `bound_var_safe`) into closed templates; invents cross-member idioms whole-program antiunify can't (`mirror_index`) | `ABC` | ✅ | cross-member idioms — but greedy MDL over train-DL prefers larger _unreusable_ `COLOR` read-body idioms: the **compression/reusability divergence** (E8) |
| Type/signature-scoped invention (`TypeScoped` / `SearchScopedFrequentSubtree`) | keep only candidates of the type the consumer composes — _declared_, or **derived from the search** (`composes_signature`); recovers `mirror_index` | `ABC` | ✅ (**stopgap**) | E8/E9 bootstrap — but _anti-open-ended_ (can't grow non-composable / new-type vocabulary); a labelled stopgap, not the general fix |
| Search-aware / selection-correct governance | a selector scoring candidates by a **train-side usefulness** signal (search-effort reduction at fixed budget), not train node-count — the goal is an _accurate_ useful/not-useful verdict (chase **false-negatives** like `mirror_index`), **not** minting everything invention-complete | `unbuilt` | 🔜 | the general, non-scoping fix to the E8 divergence (train-DL ≠ reusability); consumes the F5 usefulness score |
| Learned / guided _proposal_ | a learned prior over _which_ candidates to mine ("patterns of thinking": bias invention toward the antiunification shapes that paid off before) — the **proposer-side** analog of search-aware _selection_ above | `learned` | ⚪ | amortized invention — distinct from selection-time governance; **defer hard** (strategy category B: adopting a net kills determinism) |
| Invent-broad + prune-unused | mint top-K, let the search use what it can, GC the rest — open-ended, cheap cousin of search-aware governance | `unbuilt` | ⚪ | reusability without a type gag |
| Library refactoring / e-graph / version-space proposer | compress the **library**, not just the corpus: mine + rewrite abstraction _definitions_ to extract shared factors into a hierarchy — the missing half of iteration (once read-bodies absorb `mirror_index` into their defs, corpus-only mining can't recover it) | `unbuilt` | 🔜 **via Stitch** | the open-ended general fix — ≈ Stitch's core (3–4 orders faster than DreamCoder's version spaces); hand-rolling = "invention engine twice", so **adopt Stitch at real-ARC scale**, per MACHINERY-STRATEGY's "not yet" |
| Greedy-MDL selection | add the single best-compressing candidate, repeat | `baked` | ✅ | (bloat source under flat MDL) |
| Governance as a plug point (`AbstractionSelector` ABC) | selection lifted out of `learn()` (`GreedyMDL` default) so strategies swap/compare | `ABC` | ✅ | testable governance (E3 proved it's plural) |
| Library-dedup guard | never re-mint an existing primitive | `baked` | ✅ | anti-re-mint (E3 hardening) |
| DL-monotonicity stop | discard a generation that doesn't lower DL | `baked` | ✅ | convergence (E3 hardening) |
| Keep-smallest wake | `Enumerate` keeps the smallest, not first-considered, program per behavior | `baked` | ✅ | removes the latent bloat root cause |
| Beam / joint selection | non-greedy abstraction _sets_ | `unbuilt` | ⚪ | jointly-compressing abstractions |
| `LearnTrigger` (`EachGeneration` ✅; plateau / freq / online ⚪) | when to run the sleep step | `ABC` | ✅ | — |
| Library retirement / pruning | drop abstractions that stop paying | `unbuilt` | ⚪ | long-run library health |
| Wake–sleep orchestration (`learn()`) | solve → compress → extend → repeat | `fn` | ✅ | — |

## F5 — instrumentation / science

_"How do we know it's working?"_ (`analysis/`, `learn/harness.py`, `learn/taskgen.py`.) The machinery of _studying_ the machinery — orthogonal to solving. This is where the anti-teleological discipline is enforced: targets are observables here, never a training signal. And mind the split **[H]**: compression is _also_ the governance objective (F2/F4), so it's a **leading/process** signal, not the grade — the grade is held-out **transfer**. Never grade the optimizer by its own objective; watch whether compression _predicts_ transfer.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Compression / speedup ratios | `compression_ratio`, `speedup_ratio` over two runs | `fn` | ✅ | — |
| Transfer / enablement metric | `enablement_transfer` same-corpus (✅); the **held-out transfer grade** — the grade the disciplines rest on — is the **active build**: top priority _and_ the one workstream zero-overlap with the Stitch track (RESEARCH-08) | `fn` | 🔜 | the _grade_ (train↔held-out) |
| Per-abstraction usefulness score | a **train-side** proxy (search-effort reduction / enablement at fixed budget on _train_) that governance consumes _without_ contaminating the held-out grade | `fn` | 🔜 | selection-correct governance (F4) |
| Compression↔transfer correlation | the diagnostic that tests the MDL premise — _does compression predict transfer?_ plots `(compression_ratio, transfer)` across E1–E9 | `fn` | 🔜 | adjudicates governance-vs-gap-climbing next; quantifies the E8 divergence as a scatter |
| Behavioral checker | `check_abstractions`: learned∩/∖ target by signature | `fn` | ✅ | anti-teleological measurement |
| Run artifact | content-hashed, cached, resumable `analyze` run | `fn` | ✅ | reproducibility |
| Three-library compare | `compare_libraries`: L1 (start) / L2 (learned) / L3 (targets) | `fn` | ✅ | — |
| Testbed generator (`taskgen`) | deterministic synthetic tasks with known-reachable targets | `fn` | ✅ | controlled experiments |
| Curriculum generation | real / staged task distributions (lever-2-adjacent) | `unbuilt` | ⚪ | curriculum experiments |

---

## What the map shows

- **The critical path (what gates what) [H].** Cleared. All five mechanisms that gated the downstream have shipped:
  - **cost-guided beam** (F1, `BeamSearch`) → objects at scale, the cell floor on real grids — _done_; the first search to consume `Cost` (near-lossless on the atomic floor, `dsl-beam` = `dsl-synth` at 11/400).
  - **subtree-match rewrite** (F3) → real, measurable compression on any heterogeneous corpus — _done_.
  - **governance as a plug point + keep-smallest wake** (F4, `AbstractionSelector`/`GreedyMDL`) → testable governance, and the latent-bloat root cause removed — _done_ (behavior-preserving on E1–E4).
  - **two-part MDL + the two hardening guards** (F2/F4) → clean governance — _done_ (E4 + the E3 hardening), which is why the loop stays honest today.
  - **lambda-index binding** (F0) → size-general geometry from cells, the pixels→D4 keystone — _done_ (the Stitch-compatible De Bruijn `$i` / `Lam` / `Closure` substrate + the `build_grid`/`width`/`height`/`sub` clique). And **pixels→D4 is now achieved end-to-end and _compresses_**: `BuildGridSearch` (F1) + the loop re-derive the whole D4 group from the cell floor, blind (E5 rot90; E7 all six), after a bound-var soundness fix to antiunify (E6→E7); then a **`FrequentSubtree` proposer** (F4) invents `mirror_index` and — because `BuildGridSearch` is now _primitive-driven_ — the search **reuses** it, so the ladder compresses (E8/E9: DL ×1.12, inverting E7's ×0.79) and the beam cliff dissolves (speedup ×3.5–5, +20 tasks). The catch (E8): greedy MDL over train-DL prefers larger _unreusable_ read-body idioms; the reusable one is recovered by _scoping invention to the type the search composes_ — a knowingly-limited **stopgap**. The open-ended general fix is **library refactoring** (compress the library, not just the corpus) — deferred to Stitch adoption at real-ARC scale.
- **The experiment surface today** is the `ABC`/`param` rows: `Search` (incl. `BeamSearch`), `Cost`, `Constraint`, `AbstractionProposer`, `AbstractionSelector`, `LearnTrigger`, and the `CompressionMetric` family. That is where you can swap-and-compare _right now_.
- **`baked`-in that arguably should still be pluggable:** observational equivalence — now in **two** baked flavors (train-inputs in `Enumerate`, cell-battery in `BuildGridSearch`) with no shared seam, which sharpens the case for an `EquivalenceOracle` ABC (F3). Governance has now been lifted behind `AbstractionSelector`, so the E3 argument there is discharged.
- **Emptiest / highest-leverage families:** F0 is complete, the open-term `build_grid` search is primitive-driven, and a `FrequentSubtree` proposer now compresses the D4 ladder (E8/E9) — so the frontier the _findings_ point at is the **general fix to the compression/reusability divergence** (E8): _search-aware governance_ or _library refactoring_ (the latter ≈ Stitch's core, deferred to real-ARC scale), the current type-scoping being a labelled stopgap; plus the wider A\*/MCTS/stochastic corner, and — per the strategy — pointing the loop at real ARC tasks rather than another microworld.
- **The frame the map serves (RESEARCH-08) [H]:** the research object is **axis 2 — the search-cost graph** (how machinery reshapes the low→high mapping); expressive completeness and the F5 **transfer-measurement layer** are _prerequisites_, not goals. The near-term unblock is that measurement layer — the held-out grade + the compression↔transfer diagnostic — the one workstream both top-priority and zero-overlap with the concurrent Stitch build. F4 governance and F1/F3 search are the levers that reshape axis 2; F5 is how we'll know they did.
- **Build vs. adopt vs. defer:** which of these rows to build ourselves, adopt from a mature tool (Stitch/babble/egg), or defer until a real task demands them is a _strategy_ question, not a map question — see [MACHINERY-STRATEGY-2026-07-07.md](MACHINERY-STRATEGY-2026-07-07.md), read against [RESEARCH-2026-07-08.md](RESEARCH-2026-07-08.md).
