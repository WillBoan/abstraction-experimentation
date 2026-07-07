# MACHINERY.md

A living catalog of the **machinery** — the mechanisms that search, score, match, and learn — that are, or might be, at play in this system. Sibling to [ONTOLOGY.md](ONTOLOGY.md): that file maps the **primitives / abstractions** the solver _knows_ (lever 1, the Floor); this file maps _how the solver works_ (lever 3, the Machinery). Together they cover the solver; [EXPERIMENTS.md](EXPERIMENTS.md) logs what we tried, and [RESEARCH-2026-07-06.md](RESEARCH-2026-07-06.md) is the frame both are read against.

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
| F4 | abstraction learning | how does the vocabulary grow? | `ABC` (invention) + `baked` (governance) |
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

_"What is a program, and how is it run?"_ The physics both loops run on (`substrate/`). Mostly `baked` — it's the ground, not a plug point — which is why the one `unbuilt` binding row (lambda-index) is so load-bearing: it's the floor under the whole low-primitive direction.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Program AST (`Input`/`Const`/`Apply`/`Param`) | programs as typed, inspectable data (`program.py`) | `baked` | ✅ | everything |
| Evaluation / interpreter (`env`-threaded) | virtual-dispatch `evaluate(grid, library, env)` | `baked` | ✅ | — |
| Variable binding — `Param`/`env` | positional holes for abstraction args | `baked` | ✅ | learned abstractions |
| Variable binding — lambda-index (`build_grid`) | a bound index inside a function argument | `unbuilt` | 🔜 | **size-general geometry from cells; pixels→D4** |
| Variable binding — search-holes | an unfilled node the search expands | `unbuilt` | ⚪ | top-down search (F1) |
| Type system (`ValueType`, typed dispatch) | GRID/COLOR/INT tags; MASK/OBJECT reserved | `baked` | ✅ | search pruning |
| Library structure (`extended` / versioning) | the typed vocabulary as a first-class value | `baked` | ✅ | library learning (F4) |
| Leaf / constant mining (`_leaf_constants`, `coord_ints`) | which COLOR/INT literals enter search | `baked` | ✅ | **cell-floor tractability** (coord blow-up) |

## F1 — search

_"Which candidate programs do we consider?"_ (`search/`, behind the `Search` ABC.) A concrete search is a point in **four axes** — and only one corner of each is populated:

- **direction:** bottom-up ✅ · top-down ✗ · bidirectional ✗
- **frontier policy:** breadth-first ✅ · beam ✗ · A\* ✗ · MCTS ✗ · stochastic ✗
- **pruning:** observational-equivalence ✅ · type-directed ✅ · deductive ✗
- **guidance:** blind ✅ · heuristic ✗ · learned ✗

MCTS and beam are _frontier policies_, not paradigms; bottom-up/top-down is the _direction_ fork. The engine is bottom-up, so beam is a small tweak but MCTS implies switching to top-down first.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `SingleApply` / `Overlay` / `Tile` | bespoke depth-1 and combinator searches | `ABC` | ✅ | — |
| `Enumerate` | bottom-up, typed, obs-equiv dedup, `max_pool` cap | `ABC` | ✅ | — |
| `CompositeSearch` | run strategies in sequence, dedup | `ABC` | ✅ | — |
| Cost-guided **beam** | keep top-K by cost per round vs. the hard `max_pool` cut | `unbuilt` | 🔜 | **objects (F4-scale), cell-floor at scale**; needs `Cost` injected into `Search` |
| Cost-ordered / priority enumeration | expand cheapest-first, anytime stop | `unbuilt` | ⚪ | anytime budgets |
| Top-down / A\* over holes | goal-directed refinement of partial programs | `unbuilt` | ⚪ | needs F0 search-holes |
| MCTS | tree search + rollouts over program construction | `unbuilt` | ⚪ | needs learned guidance |
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
| Observational equivalence | dedup by behavior-signature over train inputs | `baked` (Enumerate) | ✅ | search dedup, the checker |
| Structural antiunify / match (LGG + var-sharing) | most-specific common template; shared subterm → shared `Param` | `fn` | ✅ | abstraction proposal (E3) |
| `rewrite_with` (root-match) | replace a whole program with an abstraction call | `fn` | ✅ | — |
| Subtree-match rewrite | rewrite any matching subtree, not just the root | `unbuilt` | 🔜 | **compression on heterogeneous / real corpora** |
| Partial / soft match scoring | graded "how close" rather than exact | `unbuilt` | ⚪ | fuzzy reuse |

## F4 — abstraction learning

_"How does the vocabulary grow?"_ (`learn/`.) The wake–sleep loop: **invention** (propose candidates), **governance** (select which earn a name), **trigger** (when to sleep), and **library management**. Invention and trigger are `ABC`s; **governance is still `baked` into `learn()`** — the E3 finding proved it's plural, and it isn't a plug point yet.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| `AntiunifyPairs` proposer (LGG, var-sharing) | mine recurring structure into closed templates | `ABC` | ✅ | — |
| Frequent-subtree / e-graph / version-space proposer | DreamCoder-grade invention | `unbuilt` | ⚪ | richer abstractions |
| Greedy-MDL selection | add the single best-compressing candidate, repeat | `baked` | ✅ | (bloat source under flat MDL) |
| Governance as a plug point (`AbstractionSelector` ABC) | lift selection out of `learn()` so strategies swap/compare | `unbuilt` | 🔜 | testable governance (E3 proved it's plural) |
| Library-dedup guard | never re-mint an existing primitive | `baked` | ✅ | anti-re-mint (E3 hardening) |
| DL-monotonicity stop | discard a generation that doesn't lower DL | `baked` | ✅ | convergence (E3 hardening) |
| Keep-smallest wake | `Enumerate` returns smallest, not first-considered, per behavior | `unbuilt` | 🔜 | removes the latent bloat root cause |
| Beam / joint selection | non-greedy abstraction _sets_ | `unbuilt` | ⚪ | jointly-compressing abstractions |
| `LearnTrigger` (`EachGeneration` ✅; plateau / freq / online ⚪) | when to run the sleep step | `ABC` | ✅ | — |
| Library retirement / pruning | drop abstractions that stop paying | `unbuilt` | ⚪ | long-run library health |
| Wake–sleep orchestration (`learn()`) | solve → compress → extend → repeat | `fn` | ✅ | — |

## F5 — instrumentation / science

_"How do we know it's working?"_ (`analysis/`, `learn/harness.py`, `learn/taskgen.py`.) The machinery of _studying_ the machinery — orthogonal to solving. This is where the anti-teleological discipline is enforced: targets are observables here, never a training signal. And mind the split **[H]**: compression is _also_ the governance objective (F2/F4), so it's a **leading/process** signal, not the grade — the grade is held-out **transfer**. Never grade the optimizer by its own objective; watch whether compression _predicts_ transfer.

| Mechanism | What | Interface | Status | Gates |
| --- | --- | --- | --- | --- |
| Compression / speedup ratios | `compression_ratio`, `speedup_ratio` over two runs | `fn` | ✅ | — |
| Transfer / enablement metric | `enablement_transfer`: what the learned lib solves that the base can't — same-corpus today; the held-out split is the unbuilt half | `fn` | ✅ | the _grade_ (train↔held-out) |
| Behavioral checker | `check_abstractions`: learned∩/∖ target by signature | `fn` | ✅ | anti-teleological measurement |
| Run artifact | content-hashed, cached, resumable `analyze` run | `fn` | ✅ | reproducibility |
| Three-library compare | `compare_libraries`: L1 (start) / L2 (learned) / L3 (targets) | `fn` | ✅ | — |
| Testbed generator (`taskgen`) | deterministic synthetic tasks with known-reachable targets | `fn` | ✅ | controlled experiments |
| Curriculum generation | real / staged task distributions (lever-2-adjacent) | `unbuilt` | ⚪ | curriculum experiments |

---

## What the map shows

- **The critical path (what gates what) [H].** Four `unbuilt` mechanisms gate almost everything downstream:
  - **cost-guided beam** (F1) → objects at scale, and the cell floor on real (non-toy) grids.
  - **subtree-match rewrite** (F3) → real, measurable compression on any heterogeneous corpus.
  - **lambda-index binding** (F0) → size-general geometry from cells, i.e. the pixels→D4 keystone — the experiment that would actually test the low-floor thesis.
  - **two-part MDL + the two hardening guards** (F2/F4) → clean governance — _already done_ (E4 + the E3 hardening), which is why the loop stays honest today.
- **The experiment surface today** is the `ABC`/`param` rows: `Search`, `Cost`, `Constraint`, `AbstractionProposer`, `LearnTrigger`, and the `CompressionMetric` family. That is where you can swap-and-compare _right now_.
- **`baked`-in that arguably should be pluggable:** observational equivalence (inside `Enumerate`, F3) and the whole **governance/selection** step (inside `learn()`, F4) — the E3 finding is the argument for lifting governance behind an ABC so its knobs are testable in isolation.
- **Emptiest / highest-leverage families:** F1 frontier policies (only breadth-first exists — three of four axes are one-corner) and F0 lambda-binding (a single `unbuilt` row under the entire low-floor thesis).
