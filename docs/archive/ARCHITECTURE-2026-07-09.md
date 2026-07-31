# ARCHITECTURE.md

> **SUPERSEDED (2026-07-11) by [EXECUTION.md](../EXECUTION.md).** This snapshot described the run/config/activity model as of 2026-07-09, over the *old* solver-based machinery. The execution overhaul replaced it wholesale: `Solver` is gone, `Config` holds live components (not name-strings), the activities are `run_search` / `run_search_learn` / `run_study` over a recorded-run core, and the run data model (SPECS vs RECORDS) lives in EXECUTION.md's "Run data model" section. Kept for the historical record only — do not build against it.

How a _run_ is specified, executed, and recorded. Sibling to the lever maps ([ONTOLOGY.md](../ONTOLOGY.md) = the primitives, [MACHINERY.md](../MACHINERY.md) = the mechanisms): this file is the **run/config/activity model** — the substrate the harness drives solvers over. It reflects the state after the `RunSpec × Config` refactor. Terms in **bold** are real types.

## Ontology at a glance

A run is pinned by a **`RunSpec` = `Config` × `Corpus`** — the content-addressed atom (`1 RunSpec = 1 run = 1 runs/ dir`). `Config` is the _machinery_ (how); `Corpus` is the _content_ (what). A **`StudySpec`** sits above: it generates several `RunSpec`s and reduces them.

```
StudySpec  (starting library · targets · tasks · search · enablement search · …)
   │  run_study(): generate runs, reduce them
   ├─▶ RunSpec = Config × Corpus  ──execute()──▶  runs/<dir>/{runspec,results,learned_library,trace}
   └─▶ reduce: compare + behavioural check vs targets + transfer grade
```

## Config — the machinery, as data

`solvers/dsl/config.py`. A frozen, hashable **`Config`** = `(library × search × cost)`, with the search _parameters_ carried as data (not welded into a solver subclass):

| field | meaning |
| --- | --- |
| `library: str` | a name resolved via `LIBRARIES` (`"d4"`, `"symmetry"`, `"atomic"`) |
| `search: SearchSpec` | `kind` (`single_apply`/`composite`/`enumerate`/`beam`) + params (`max_depth`, `beam_width`, `members`) |
| `cost: str` | a name resolved via `COSTS` (`"program-size"`) |

- `Config.with_param(max_depth=…, beam_width=…)` → a copy with search params overridden.
- `Config.to_dict()` → the canonical serialisation that feeds a run's `run_id`.
- **`PRESETS`** — the historical solvers as data: `dsl`, `dsl-sym`, `dsl-synth`, `dsl-beam`. `ProgramSearchSolver.from_config(config)` builds a live solver; the solver `REGISTRY` (`solvers/__init__.py`) is `{name: build PRESETS[name]}`.

There is exactly one solver class (`ProgramSearchSolver`); the config-as-subclass leaves are gone.

## Corpus — the content, provenance-agnostic

`core/dataset.py` + `core/annotation.py`. A **`Corpus`** (the renamed `Dataset`; the old names remain as aliases) is a named collection of **`AnnotatedTask`** = `{task: Task, meta: TaskMeta|None}`.

- The solver-facing surface (`__iter__`, `get`, `tasks`) yields the **pure `Task`** — solvers never see metadata (**blindness** is structural, enforced at the `Solver.predict` seam).
- **`TaskMeta`** = `{provenance, split, label}` — all core-clean (no DSL dependency). `provenance` is `Real(dataset)` | `Synthetic(generator)`; `real|synthetic|mixed` is _derived_. `label` is the ground-truth operation name (an observable, deliberately a string, not a DSL `Program`).
- **`SolvedTask`** = `{annotated, program}` (in `analysis/compression.py`) — a task + the program a run _found_ for it (distinct from `meta.label`, the oracle name).

## The activity tiers

1. **Corpus production** — `taskgen` (synthetic) / `load_corpus` (real) → a `Corpus`.
2. **Execution** (produces runs) — one core, `analysis/runner.py::execute(solver, corpus, *, sleep)`:
   - `sleep is None` → **Eval** (wake only, fixed library).
   - `sleep=<strategy>` → **Synthesize** (grow the library on the train split via `wake_sleep`, then eval; writes `learned_library.json`).
3. **Analysis** (read-side) — `analysis/transfer.py`: `enablement_transfer` / `heldout_transfer` (the **grade**) / `train_usefulness` reduce stored `RunSummary`s. `arc-lab runs` is the trivial member (list artifacts).
4. **Composition** — `learn/experiments.py::run_study(StudySpec)`: TaskGen → Synthesize (L2) → Eval L1/L2/L3 at main + shallow budgets → compare + behavioural check vs targets + transfer.

## The run artifact (`runs/<solver>_<corpus>_<hash>/`)

`analysis/artifact.py`. `run_id = sha256(canonical RunSpec)[:16]`, hashing `solver × dataset × library × config` (commit recorded but **excluded**, so an unrelated commit doesn't bust the cache). Broadening the hash to include `config` is what stops two runs that differ only in a search _parameter_ from colliding on one directory.

| file | role | written |
| --- | --- | --- |
| `runspec.json` | identity / inputs (holds `run_id`) | first (survives a crash) |
| `results.json` | metrics + per-task rows | last |
| `learned_library.json` | the grown library (Synthesize only) | last |
| `trace.jsonl` | per-task records — a **gitignored, regenerable cache** | streamed |

Runs are idempotent (a present `results.json` is served from cache) and resumable (a partial `trace.jsonl` is continued). `runs/` is fully gitignored; the durable record is `testbeds/` + `EXPERIMENTS.md`.

## The library store

`substrate/store.py` + `substrate/registry.py` + `Library.from_dict`. A library round-trips to/from JSON: base primitives resolve **by name** against the substrate `registry` (their `impl` is code — never pickled), learned abstractions rebuild from their serialised `template` via `make_abstraction`. `save_library`/`load_library` give a content-addressed `libraries/<hash>.json` store.

## Configuring a run

- **Programmatic** (today): pick a `PRESETS[name]`, override with `.with_param(...)`; or build a `Config`/`ProgramSearchSolver` directly.
- **CLI** (today): `arc-lab eval <preset> --dataset <ds>`, `arc-lab analyze <preset> …`, `arc-lab study <name>`. Presets are corpus-independent, so one preset runs across datasets.
- **Precedence** (target): `dataclass defaults < named preset < config file < CLI --set`. Only the first two are wired; a config file and `--set` overrides are **not yet built**.

## Extending an axis

Add a search strategy → a `SearchSpec.kind` branch in `config.py` (+ the `Search` subclass). Add a library → an entry in `config.py::LIBRARIES`. Add a cost → `config.py::COSTS`. Add a proposer / sleep strategy / selector → subclass the ABC (`learn/antiunify.py`, `learn/sleep.py`, `learn/selection.py`) and wire it on a `StudySpec`. See [MACHINERY.md](../MACHINERY.md) for the full axis catalogue.

## Deferred (target model, not yet built)

- **`GeneratedTask` fold** — synthetic testbeds still produce `GeneratedTask`, not a `Corpus` of `AnnotatedTask`. Folding them needs `taskgen` changes + regenerating committed testbeds.
- **Enablement as a study-level `Config`** — `StudySpec.enablement_search` is still a second `Search` (correct: E8/E9 use a structurally different tighter search, not merely a shallower depth).
- **Sleep in the run identity** — a Synthesize run's `RunSpec` does not yet encode the sleep strategy; it will when the learn axes move into `Config`. Until then, don't Eval and Synthesize the same solver+corpus into the same `out_dir`.
- **CLI verb split** — `analyze` is currently the _execution_ CLI command (backed by `execute`); the read-side `analyze` / `synthesize` verbs and a config-file / `--set` surface are future work.
