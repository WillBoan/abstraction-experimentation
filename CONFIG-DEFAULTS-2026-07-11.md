# Config / parameter defaults review — 2026-07-11

A dated snapshot (the convention of `RESEARCH-*.md` / `MACHINERY-STRATEGY-*.md`): every `Config` parameter after the execution overhaul — where it lives, its options, the search-cost impact of each, its default, and whether that default is the lowest-cost option. Read against [EXECUTION.md](EXECUTION.md) (the activity/run model) and [ARCHITECTURE.md](ARCHITECTURE.md) (the engine design). Source of truth is the code (`execution/model/config.py`, `search/`, `learn/`); this file is the *review*, not the definition.

A structural note: several fields deliberately have **no default** (marked *required*) — the "no silent default" choices where a run must state its intent: `Config.library/search_engine/budget`, all three engine capability policies, `beam_width`, and `LearnSpec.learn_engine/iterations`.

## `Config` (`execution/model/config.py`)

| Param | Description | Options | Cost impact | Default | Lowest-cost? |
|---|---|---|---|---|---|
| `library` | The typed vocabulary searched over | any `Library` (`d4` 8 prims / `symmetry` 10 / `atomic` 10, or custom) | Pool growth is roughly polynomial in library size per round (degree ≈ depth); the single biggest lever after depth | *required* | — |
| `search_engine` | The machinery (algorithm + policies) | `BottomUpSearchEngine`, `BeamBottomUpSearchEngine` | Beam is strictly cheaper (truncates the frontier harder) at the cost of misses (measured: 9 vs 11 solved) | *required* | — |
| `budget` | Resource caps (see below) | any `Budget` | The dominant lever | *required* | — |
| `constraints` | *Extra* inductive-bias filters on goal-test survivors | any `Constraint` tuple | Each adds a per-survivor check; `()` skips entirely | `()` | **yes** |
| `cost` | Ranking / Occam prior | `ProgramSize` (only registered option) | O(nodes) per candidate, evaluated once & cached | `ProgramSize()` | yes (trivially) |
| `attempts_per_test` | k programs tried per test input | any int ≥ 1 | No search cost — prediction only | `2` | no (1 would be) — **deliberate: official ARC rule** |
| `learn` | SEARCH vs LEARN discriminator | `None` \| `LearnSpec` | `None` = one search pass; set = the whole wake–sleep loop | `None` | **yes** |

## `Budget` (`search/budget.py`) — all *required*, no defaults

| Param | Description | Cost impact |
|---|---|---|
| `max_depth` | Enumeration rounds **including round-0 leaves** (so old "single apply" = 2); strictly decrements into lambda bodies (the termination guarantee) | Exponential-ish: each round composes over the whole pool. The #1 lever |
| `max_arity` | Variadic fan-out cap | Combinations grow ~`pool_grids^arity` — measured wall at arity 4 × wide constants (the sym 6M-candidate task, EXPERIMENTS.md 2026-07-11) |
| `max_pool` | Per-round frontier cap (cheapest-first) | Linear-ish brake on everything downstream; too low silently drops solutions |

## `BottomUpSearchEngine` (`search/search_engine.py`)

| Param | Description | Options (cost order, cheap → expensive) | Default | Lowest-cost? |
|---|---|---|---|---|
| `constant_sources` | Which `Const` leaves are seeded | `()` → `("parameterize",)` (mints nothing) → `("harvest-from-instance",)` (colors present ≤10 + 2 dims) → `("finite-enumerate",)` (all 10 colors + INT 0..max-dim — up to ~43 leaves, **multiplicative** under variadics) | *required* | — (presets: `d4`=`()`, `sym`/`beam`=harvest, `synth`=finite) |
| `function_hole_fill_mode` | How arrow-typed holes are filled | `"none"` → `"point-free"` (adds `PrimRef` leaves + `AppFn` composition) → `"lambda-synthesis"` (recursive body enumeration per hole — most expensive) | *required* | — (all presets: `"none"` — dormant capability) |
| `polymorphism_instantiation` | How type-variable signatures instantiate | `"monomorphize"` → `"bounded"` (closes a monotype universe first) → `"unrestricted"` (free vars flow; widest pool) | *required* | — (all presets: `"monomorphize"`) |
| `function_sample_size` | Probe values per param when deduping *function values* by behavior (cost grows `size^arity`) | any int ≥ 1 | `4` | **no** — deliberate: smaller batteries were measured **unsound** (the height-collapse bug, EXPERIMENTS.md 2026-07 review); 4 buys dedup soundness-in-practice |
| `beam_width` (Beam subclass) | Keep only k cheapest per round | any int | *required* | — (gotcha, documented in `presets.py`: must exceed the leaf-constant count or constants starve the GRID type — the beam-16 = 0/400 finding) |

## `LearnSpec` (`execution/model/learn_spec.py`)

| Param | Description | Options | Cost impact | Default | Lowest-cost? |
|---|---|---|---|---|---|
| `learn_engine` | The sleep machinery | `GreedyMDLLearnEngine`, `RefactoringLearnEngine` | Refactoring adds a second (library-definition) mining phase | *required* | — |
| `iterations` | Max wake–sleep cycles (cap, not mandate) | int ≥ 1 | Each iteration = a full corpus search + a sleep | *required* | — |
| `early_stop` | Stop when sleep converges | bool | `True` skips dead iterations | `True` | **yes** |
| `reset_programs_each_wake` | Fresh search every wake vs carrying solutions | bool | `True` is the **expensive** option (re-search everything each wake) | `True` | **no** — deliberate: sleep must see solutions *re-expressed* in the grown library, and search-effort is a measured signal (EXECUTION.md property 5); `False` would silently corrupt both |
| `score_each_wake` | Per-wake test scoring (telemetry only) | bool | Adds predict+score per task per wake | `False` | **yes** |

## Sleep internals (`learn/engines.py` · `learn/antiunify.py` · `learn/stitch_shim.py` · `analysis/compression.py`)

| Param | Where | Description / options | Cost impact | Default | Lowest-cost? |
|---|---|---|---|---|---|
| `proposer` | `GreedyMDLLearnEngine` | `AntiunifyPairs` (O(n²) pairwise) · `FrequentSubtree` (walks all subtrees) · `TypeScopedFrequentSubtree` · `StitchProposer` (external engine) | Sleep-side only — dwarfed by wake search in practice | *required* | — |
| `bound_var_safe` | `AntiunifyPairs` | Refuse to hole subterms containing a bound `$i` | Marginally cheaper OFF | `False` | yes on cost — **but it's the E6-unsound option**; E7 showed `True` is needed near lambdas. Flagged for reconsideration (below) |
| `min_frequency` | `FrequentSubtree` | Recurrence threshold | Higher = fewer candidates scored | `2` | no (higher would be) — 2 is the minimum meaningful recurrence |
| `selector` | `GreedyMDLLearnEngine` | `GreedyMDL` (only option): re-scores corpus DL per candidate per greedy round | O(candidates × corpus) per round | `GreedyMDL()` | trivially |
| `metric` | selector/engine | `CompressionMetric` (flat, `bits_per_primitive=1.0`) vs `TwoPartMDL` (also charges definition sizes) | Two-part slightly costlier; flat causes **library bloat** (the E3/E4 finding) | `CompressionMetric()` | **yes** — but E4 says two-part is the *better* default scientifically. Flagged (below) |
| `StitchProposer.*` | stitch | `first_order=True`, `iterations=5`, `max_arity=3`, `threads=1` | `threads=1` is the slow-but-deterministic choice (the locks depend on it) | as listed | `threads`: yes (deliberately); others: middle |

## Summary judgment

The defaults follow a consistent philosophy — **capabilities dormant until summoned, cheapest option where the choice is free** — with exactly four deliberate exceptions where the default is *not* lowest-cost, each with a documented reason:

1. `attempts_per_test=2` — ARC's official rule.
2. `function_sample_size=4` — dedup soundness (smaller batteries measured unsound).
3. `reset_programs_each_wake=True` — compression-signal integrity.
4. `StitchProposer.threads=1` — determinism, which the locks depend on.

Two defaults **flagged for reconsideration** — both currently "cheapest" but arguably wrong-side-of-history given the experiment log; neither changes any current lock (E1 mints correctly under both), so flipping either is a deliberate, cheap change:

- `AntiunifyPairs.bound_var_safe=False` — E7 established the safe proposer as the sound one near lambdas; the unsafe default re-creates E6's failure mode for anyone who doesn't know the history.
- `metric=CompressionMetric` (flat) — E4 established two-part MDL as the anti-bloat governance.