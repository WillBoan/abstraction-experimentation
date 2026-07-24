# CLAUDE.md

Operational guide for agents working in this repo. Human-facing overview is in [README.md](README.md); this file is the agent contract — conventions, gotchas, and recipes. Keep it lean and pointer-heavy (it loads every session).

## What this is

`arc-lab`: a sandbox for the ARC-AGI benchmarks and, more broadly, ML / program-synthesis / abstraction-formation experimentation. The load-bearing design decision: **machinery is data** — there are no solver classes; a run is a frozen, content-hashed `RunSpec = Config × Corpus`, and the execution layer (`program_search/execution/`) drives `Config` directly. The activity/call-stack model is **[EXECUTION.md](EXECUTION.md)**; the search-engine design is **[ARCHITECTURE.md](ARCHITECTURE.md)**.

> `_notes/` is the user's private notes — off-limits.

## The one command that matters

```
make check      # ruff + mypy --strict + FULL pytest (incl. slow locks, in parallel) — the gate
make test       # fast pytest only (`-m "not slow"`) — the dev inner loop (~seconds)
make format     # auto-fix ruff lint + format
```

`uv` runs everything (`uv run …`); deps live in `pyproject.toml`. Never invoke `python`/`pytest` bare.

**Two test tiers.** Fast unit/functionality tests run by default; heavy regression **locks** (dataset benchmarks, learning-loop runs) are `@pytest.mark.slow` — excluded from `make test`, run by `make check`. New search/learning tests should be *fast functionality* checks (tiny task + tight budget); mark genuinely heavy ones `slow`.

## Definition of done

1. `make check` is green (ruff clean, mypy `--strict` clean, all tests pass).
2. **Regression locks preserved.** The new-world locks pin exact solved task-id sets per preset on `arc1-train` in `tests/program_search/execution/test_locks.py` (the old-world locks in `tests/test_integration.py` guard the old tree until its deletion). A behavior-preserving change must not move them; a feature that changes them updates the lock deliberately.
3. For changes with runtime behavior, actually drive it: `uv run arc-lab search <preset> --corpus <corpus>`.

## Experiment log

When you run a meaningful experiment or reach a finding — **including dead ends** — append a terse, commit-anchored entry to [EXPERIMENTS.md](EXPERIMENTS.md). It's the shared human+AI record of what's been tried and what it meant. It's an *event log, not a state mirror* — read its header for the discipline before adding to it. The **active experimental program is the Abstraction Ladder Experiments** — plan of record `docs/abstraction_ladders/AL-PLAN-2026-07-23.md`, cross-cutting index `docs/TODO-2026-07-23.md`. [EXPERIMENT_QUEUE.md](EXPERIMENT_QUEUE.md) is now the drain-only **backlog of non-ladder / deferred experiments** (the single-task search-behavior line it began as is superseded; see its header).

For a **non-trivial investigation**, also keep a detailed lab notebook under [experiments/](experiments/) — the full write-up + the throwaway probe scripts and their outputs, which EXPERIMENTS.md (the curated abstract) points to. See [experiments/README.md](experiments/README.md).

## Mental model

Terminology (ARC's own): **dataset ⊃ corpus (train/eval) ⊃ task ⊃ example (train/test)**.

- **`Config`** = `library × search_engine × budget × constraints × cost × attempts_per_test × learn?` (`execution/model/config.py`) — frozen machinery-as-data. `learn: LearnSpec | None` discriminates SEARCH vs LEARN runs. Named presets: `execution/presets.py::PRESETS` (`d4`/`sym`/`synth`/`beam`).
- **`RunSpec = Config × Corpus`** → content-hashed `run_id` → executed once by `execute()` (the ONLY writer of `runs/`), cached, crash-safe, resumable. `runs/` is a gitignored regenerable cache.
- **Activities**: `run_search` (one SEARCH run) · `run_search_learn` (wake-sleep loop = ONE recorded LEARN run + derived SEARCH runs: train-usefulness + transfer) · `run_study` (learn L2, build L3 = L1 + targets, grid `(L1,L2,L3) × budgets × (train,eval)`) + read-side `analyze_run` / `create_study_report`.
- **Blindness seams**: solvers see pure `Task`s (never `TaskMeta`); `SearchEngine.run(train_examples=…)` structurally cannot see test examples; `predict` + `score_task` are the only functions touching test grids. Targets are observables, never a training signal.
- **Search** (`program_search/search/`): one generic typed bottom-up engine (`BottomUpSearchEngine`), capability policies as fields (function-hole fill, polymorphism instantiation, constant sources), `Budget` as a `run()` argument. Goal test is `sig == target`; a `Constraint` is only an *extra* inductive-bias filter; `Cost` (`ProgramSize`) is the Occam prior.
- **Programs are data**: `Program` ABC — `Input | Param | Const | Apply | If | Var | Lam | AppFn | PrimRef` (`substrate/program.py`). Every node kind must round-trip both codecs — enforced by `tests/program_search/learn/test_codec_completeness.py` (ARCHITECTURE.md §11.6).
- **Learning** (`program_search/learn/`): sleep = `LearnEngine.run(library, solutions) → LearnOutcome` (proposers: antiunify / frequent-subtree / Stitch; governance: greedy-MDL). Studies register in `execution/studies.py::STUDIES`; testbed generators in `taskgen/generators.py::GENERATORS`.

Layers: `core/` (grid·task·annotation·dataset·hashing) · `eval/` (scoring rules only) · `program_search/` (`substrate/` · `search/` · `learn/` · `analysis/` · `execution/`) · `taskgen/` · `cli/` (thin) · `viz/`.

## Key commands

```
uv run arc-lab configs | datasets | runs | show <id> --dataset <ds>
uv run arc-lab search <preset> --corpus <c>          # one SEARCH recorded run (cached)
uv run arc-lab learn <preset> --corpus <train> [--eval-corpus <eval>]   # 2-3 recorded runs
uv run arc-lab run-study <name> [--out report.json]  # study grid + report (cache hits free)
uv run arc-lab analyze-run <run_id>                  # READ-ONLY over a completed run
uv run arc-lab taskgen <generator>                   # (re)generate a committed testbed
uv run arc-lab -vv search ...                        # -v INFO / -vv DEBUG trace (stderr)
ARC_LAB_LOG=DEBUG uv run pytest -k <x>               # same trace under pytest
```

A `--corpus` is a dataset (`arc1-train`), a testbed (`e1-rot90`), or a testbed split (`e1-rot90:train` / `:heldout`). Config precedence: `defaults < preset < config file < --set` — `<config>` may be a JSON file `{"preset": ..., "set": {...}}`, and `--set budget.depth_limit=3` overrides any `Config` field by dotted path (`execution/overrides.py`).

## Conventions & gotchas

- **mypy** `python_version = "3.12"` is intentional — only so numpy 2.5's PEP-695 stubs parse; the runtime targets 3.11+. Keep `--strict` clean.
- **ruff** `E203` on numpy slices is `noqa`'d for ruff-format compatibility — don't "fix" it. No `×`/`–` glyphs in code/docstrings (RUF002/RUF003).
- **Datasets are git submodules** under `data/`; integration tests skip cleanly if absent (`git submodule update --init --recursive`).
- **Immutable & deterministic:** `Grid`, programs, and all spec types are frozen; no RNG anywhere — reproducibility is what makes content-hashed caching and the locks meaningful.
- **Logging** is silent by default; use `%s` lazy args and guard hot paths with `if debug:` (`logger.isEnabledFor`).
- **Don't commit or push unless asked.** Throwaway analysis scripts go in the session scratchpad, not the repo.

## Recipes

- **Add a primitive** → a typed `Primitive` in `program_search/substrate/primitives/*.py`; register it in `substrate/registry.py::BASE_PRIMITIVES` (so serialized libraries round-trip) and add it to a library in `execution/presets.py` if a preset should search over it.
- **Add a search engine** → subclass `SearchEngine` (`search/search_engine.py`, frozen dataclass; `run(train_examples, library, constraints, cost, budget)`); add it to `execution/model/config.py::default_registry` for serde.
- **Add a machinery preset** → a `Config` in `execution/presets.py::PRESETS`.
- **Add a ladder check** → a `LadderCheck` subclass in `program_search/ladders/checks/<family>.py` (code/category/stage/severity as `ClassVar`s, logic in `run(ctx)`; read derivations off `CheckContext`) + an instance in `checks/plan.py::CHECK_PLAN`, which IS the order. `skipped_checks` and tier gating follow from `stage`.
- **Add a constraint / cost / learn engine / proposer** → `search/constraints.py` / `search/cost.py` / `learn/engines.py` / `learn/antiunify.py`+`learn/stitch_shim.py`; frozen dataclasses, registered in `default_registry` (they are run identity).
- **Add a study** → a generator in `taskgen/generators.py` (committed testbed under `testbeds/`) + a `StudySpec` builder in `execution/studies.py::STUDIES`; drive with `uv run arc-lab run-study <name>`.
- **Add a ladder** → one `<name>.ladder` file in `program_search/ladders/registry/` (format spec: `docs/abstraction_ladders/LADDER-FORMAT.md`); there is nothing to register — the directory is scanned. Loop: `arc-lab ladder-seeds --variant N` for paste-ready input grids → `arc-lab lint-ladder <name>` (static, reads only; works before the testbed exists) → `arc-lab probe-ladder <name>` (drives the REAL engine per rung, seconds, records nothing — catches collapses, task collisions, skip paths and wrong mints before a run) → `arc-lab taskgen <name>` to commit the testbed → `run-ladder <name>` to drive it. The gate layering is `docs/abstraction_ladders/LADDER-CHECKS-2026-07-21.md`.
- **Add a CLI command** → a thin module in `cli/`, registered in `cli/main.py`.

## Sources of truth (don't duplicate — point here)

- Activity / call-stack / run data model (RunSpec · Config · activities · runs/ layout · CLI): `EXECUTION.md`
- Search-engine & substrate design (types · scopes · enumeration · deliberate limits register §11.6): `ARCHITECTURE.md` (the superseded run-model snapshot is `docs/archive/ARCHITECTURE-2026-07-09.md`)
- Preset registry: `src/arc_lab/program_search/execution/presets.py` · Study registry: `execution/studies.py` · Generator registry: `src/arc_lab/taskgen/generators.py`
- Behavior locks: `tests/program_search/execution/test_locks.py` (old-tree locks: `tests/test_integration.py`, until the deletion pass)
- Commands: `Makefile`
- Experiment history & findings: `EXPERIMENTS.md` · Active program: `docs/abstraction_ladders/AL-PLAN-2026-07-23.md` + cross-cutting index `docs/TODO-2026-07-23.md` · Non-ladder backlog: `EXPERIMENT_QUEUE.md`
- Ladder file format (`.ladder` = a ladder's single source of truth: spec, testbed, artifacts): `docs/abstraction_ladders/LADDER-FORMAT.md` · Ladder sources: `program_search/ladders/registry/*.ladder` · Ladder register: `docs/abstraction_ladders/LADDERS.md`
- Ladder checks (every load/lint/certificate check + current batch health; dated): `docs/abstraction_ladders/LADDER-CHECKS-2026-07-21.md` · Lint implementation: `program_search/ladders/checks/` (`LadderCheck` ABC + `CHECK_PLAN`)
- AL plan of record (corrections, pipeline, phased build/measure order; dated): `docs/abstraction_ladders/AL-PLAN-2026-07-23.md` (superseded: `AL-PLAN-2026-07-22.md`)
- Lever maps (primitives / machinery / expressibility control): `ONTOLOGY.md` / `MACHINERY.md` / `SEARCH-SPACE.md`
- Research frame (dated snapshot the maps are read against): `docs/RESEARCH-2026-07-08.md` (superseded snapshots live in `docs/archive/`)
- Machinery build strategy (build vs. adopt vs. defer; dated): `docs/MACHINERY-STRATEGY-2026-07-07.md`
- Config/param defaults review (every param: options, cost impact, default rationale; dated): `docs/CONFIG-DEFAULTS-2026-07-11.md`
