# CLAUDE.md

Operational guide for agents working in this repo. [README.md](README.md) is the research report (what this studies and what it found); [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) is the human-facing operational front door. This file is the agent contract — conventions, gotchas, and recipes. Keep it lean and pointer-heavy (it loads every session).

## What this is

`arc-lab`: a sandbox for the ARC-AGI benchmarks and, more broadly, ML / program-synthesis / abstraction-formation experimentation. The load-bearing design decision: **machinery is data** — there are no solver classes; a run is a frozen, content-hashed `RunSpec = Config × Corpus`, and the execution layer (`program_search/execution/`) drives `Config` directly. The activity/call-stack model is **[EXECUTION.md](docs/EXECUTION.md)**; the search-engine design is **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

> `_notes/` is the user's private notes — off-limits.

## The one command that matters

```
make check      # ruff + mypy --strict + FULL pytest (incl. slow locks, in parallel) — the gate
make test       # fast pytest only (`-m "not slow"`) — the dev inner loop (~seconds)
make format     # auto-fix ruff lint + format
```

`uv` runs everything (`uv run …`); deps live in `pyproject.toml`. Never invoke `python`/`pytest` bare.

**Two test tiers.** Fast unit/functionality tests run by default; heavy regression **locks** (dataset benchmarks, learning-loop runs) are `@pytest.mark.slow` — excluded from `make test`, run by `make check`. New search/learning tests should be _fast functionality_ checks (tiny task + tight budget); mark genuinely heavy ones `slow`.

## Definition of done

1. `make check` is green (ruff clean, mypy `--strict` clean, all tests pass).
2. **Regression locks preserved.** The locks pin exact solved task-id sets per preset on `arc1-train` in `tests/program_search/execution/test_locks.py`. A behavior-preserving change must not move them; a feature that changes them updates the lock deliberately.
3. For changes with runtime behavior, actually drive it: `uv run arc-lab search <preset> --corpus <corpus>`.

## Experiment log

When you run a meaningful experiment or reach a finding — **including dead ends** — append a terse, commit-anchored entry to [EXPERIMENTS.md](EXPERIMENTS.md). It's the shared human+AI record of what's been tried and what it meant. It's an _event log, not a state mirror_ — read its header for the discipline before adding to it. The experimental program to date is the **Abstraction Ladder Experiments**, whose results are written up in [README.md](README.md). Its plan lineage ran to completion and is archived; **there is no active plan of record**, so treat any multi-step experimental program as needing one written first (dated, in `docs/abstraction_ladders/`) rather than assuming one exists to consult. Live ladder docs are `docs/abstraction_ladders/` (start at its [README.md](docs/abstraction_ladders/README.md)); what has actually been run is the generated [BATCH-OF-RECORD.md](docs/abstraction_ladders/BATCH-OF-RECORD.md), never prose. [EXPERIMENT_QUEUE.md](docs/EXPERIMENT_QUEUE.md) is the drain-only **backlog of non-ladder / deferred experiments** (the single-task search-behavior line it began as is superseded; see its header).

For a **non-trivial investigation**, also keep a detailed lab notebook under [experiments/](experiments/) — the full write-up + the throwaway probe scripts and their outputs, which EXPERIMENTS.md (the curated abstract) points to. See [experiments/README.md](experiments/README.md).

## Mental model

Terminology (ARC's own): **dataset ⊃ corpus (train/eval) ⊃ task ⊃ example (train/test)**.

- **`Config`** = `library × search_engine × budget × constraints × cost × attempts_per_test × learn?` (`execution/model/config.py`) — frozen machinery-as-data. `learn: LearnSpec | None` discriminates SEARCH vs LEARN runs. Named presets: `execution/presets.py::PRESETS` — four ARC-benchmark machineries (`d4`/`sym`/`synth`/`beam`) + three floor-grain contrast floors (`geom`/`universal-floor`/`minimal-complete-floor`).
- **`RunSpec = Config × Corpus`** → content-hashed `run_id` → executed once by `execute()` (the ONLY writer of `runs/`), cached, crash-safe, resumable. `runs/` is a gitignored regenerable cache.
- **Activities**: `run_search` (one SEARCH run) · `run_search_learn` (wake-sleep loop = ONE recorded LEARN run + derived SEARCH runs: train-usefulness + transfer) · `run_study` (learn L2, build L3 = L1 + targets, grid `(L1,L2,L3) × budgets × (train,eval)`) + read-side `analyze_run` / `create_study_report`.
- **Blindness seams**: solvers see pure `Task`s (never `TaskMeta`); `SearchEngine.run(train_examples=…)` structurally cannot see test examples; `predict` + `score_task` are the only functions touching test grids. Targets are observables, never a training signal.
- **Search** (`program_search/search/`): one generic typed bottom-up engine (`BottomUpSearchEngine`), capability policies as fields (function-hole fill, polymorphism instantiation, constant sources), `Budget` as a `run()` argument. Goal test is `sig == target`; a `Constraint` is only an _extra_ inductive-bias filter; `Cost` (`ProgramSize`) is the Occam prior.
- **Programs are data**: `Program` ABC — `Input | Param | Const | Apply | If | Var | Lam | AppFn | PrimRef` (`substrate/program.py`). Every node kind must round-trip both codecs — enforced by `tests/program_search/learn/test_codec_completeness.py` (ARCHITECTURE.md §11.6).
- **Learning** (`program_search/learn/`): sleep = `LearnEngine.run(library, solutions) → LearnOutcome` (proposers: antiunify / frequent-subtree / Stitch; governance: greedy-MDL). Studies register in `execution/studies.py::STUDIES`; testbed generators in `taskgen/generators.py::GENERATORS`.

- **Ladders** (`program_search/ladders/`): the active experimental instrument — the `.ladder` language (`lang/`), the lint checks (`checks/`), the per-rung probe, and the certificate. A Ladder is one authored learning trajectory (floor → rungs → Top) made testable; see the "Add a ladder" recipe below.

Layers: `core/` (grid·task·annotation·dataset·hashing) · `eval/` (scoring rules only) · `program_search/` (`substrate/` · `search/` · `learn/` · `analysis/` · `execution/` · `ladders/`) · `taskgen/` · `cli/` (thin) · `viz/`.

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

# the ladder loop (cheapest gate first) — see the "Add a ladder" recipe
uv run arc-lab lint-ladder <name>                    # static, ~1s, no search (works pre-testbed)
uv run arc-lab probe-ladder <name>                   # REAL engine per rung: collapses, skip paths
uv run arc-lab run-ladder <name> [--artifacts <dir>] # full climb + oracle chain + certificate
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
- **Add a ladder check** → a `LadderCheck` subclass in `program_search/ladders/checks/<family>.py` (code/category/stage/severity as `ClassVar`s, logic in `run(ctx)`; read derivations off `CheckContext`) + an instance in `checks/plan.py::CHECK_PLAN`, which IS the order. `skipped_checks` and tier gating follow from `stage`; regenerate the register with `arc-lab lint-checks --out docs/abstraction_ladders/LINT-CHECKS.md` (a test pins it).
- **Add a constraint / cost / learn engine / proposer** → `search/constraints.py` / `search/cost.py` / `learn/engines.py` / `learn/antiunify.py`+`learn/stitch_shim.py`; frozen dataclasses, registered in `default_registry` (they are run identity).
- **Add a study** → a generator in `taskgen/generators.py` (committed testbed under `testbeds/`) + a `StudySpec` builder in `execution/studies.py::STUDIES`; drive with `uv run arc-lab run-study <name>`.
- **Add a ladder** → `uv run arc-lab new-ladder <name> [--from <existing>] [--registry]` (drafts by default; **refuses to overwrite** — that is how variants survive). One `<name>.ladder` file in `program_search/ladders/registry/` is all a batch member is (format spec: `docs/abstraction_ladders/LADDER-FORMAT.md`); there is nothing to register — the directory is scanned.
  - Loop: `arc-lab ladder-seeds --variant N` for paste-ready input grids → `arc-lab lint-ladder <name>` (static, reads only; works before the testbed exists) → `arc-lab probe-ladder <name>` (drives the REAL engine per rung — catches collapses, task collisions, skip paths and wrong mints before a ladder run) → `arc-lab taskgen <name>` to commit the testbed → `run-ladder <name>` to drive it. The gate layering is `docs/archive/abstraction_ladders/LADDER-CHECKS-2026-07-21.md`.
  - **The probe convicts; only the certificate acquits.** A skip path / collapse / collision it finds is a real defect; INCONCLUSIVE is a _non-result by design_, not a defect to tune away — raising `--guard` buys a longer search, never a verdict. Lint first: it settles statically, in ~1s, everything it can see, **including the round-1 breadth census** (`ladders/breadth.py`), which usually explains an expensive cell before it is ever run.
  - Probe cells are ordinary recorded runs (cached, resumable), namespaced and hidden from `arc-lab runs` unless you pass `--probes`. So a re-probe of an unchanged rung is free, and its cost is only ever paid once — but the FIRST probe of a fat floor still costs what the enumeration costs.
- **Add a CLI command** → a thin module in `cli/`, registered in `cli/main.py`.

## Sources of truth (don't duplicate — point here)

- Activity / call-stack / run data model (RunSpec · Config · activities · runs/ layout · CLI): `docs/EXECUTION.md`
- Search-engine & substrate design (types · scopes · enumeration · deliberate limits register §11.6): `docs/ARCHITECTURE.md` (the superseded run-model snapshot is `docs/archive/ARCHITECTURE-2026-07-09.md`)
- Preset registry: `src/arc_lab/program_search/execution/presets.py` · Study registry: `execution/studies.py` · Generator registry: `src/arc_lab/taskgen/generators.py`
- Behavior locks: `tests/program_search/execution/test_locks.py`
- Commands: `Makefile`
- Experiment history & findings: `EXPERIMENTS.md` (event log) + `experiments/` (notebooks) · Non-ladder backlog: `docs/EXPERIMENT_QUEUE.md`
- **Ladder docs index** (read this first — it states the naming convention): `docs/abstraction_ladders/README.md`
  - Concept explainer (the short read): `ABSTRACTION-LADDERS.md` · **canonical spec — cite it for terms, quantities and metrics: `ABSTRACTION-LADDERS-SPEC.md`** (its §5.3 estimation decision was reversed 2026-07-23; everything else stands)
  - Process (instrument contracts · the failure→response table · tractability triage · design taste · Compromise Options · operational discipline · glossary): `LADDER-PROCESS.md`
  - File format (`.ladder` = a ladder's single source of truth: spec, testbed, artifacts, AND the finding if it was rejected): `LADDER-FORMAT.md` · Ladder sources: `program_search/ladders/registry/*.ladder`
  - **The register is generated: `BATCH-OF-RECORD.md`** (`arc-lab run-batch`) — per-member verdicts, what the set samples on each axis, which cohorts license which comparisons. There is no hand-maintained register; `LADDERS.md` was deleted 2026-08-03 as triple-covered by this, the `.ladder` files, and `EXPERIMENTS.md`.
  - Generated per-check register: `LINT-CHECKS.md` (`arc-lab lint-checks --out …`; a test pins it — never hand-edit) · Lint implementation: `program_search/ladders/checks/` (`LadderCheck` ABC + `CHECK_PLAN`)
  - Concept snapshots (dated, still cited): set structure `LADDER-SET-DESIGN-2026-07-24.md` · the two cost axes (depth vs breadth) `BREADTH-AXIS-2026-07-24.md` · certificate = per-rung verdict profile (not a sandwich gate) `CERTIFICATE-PROFILE-2026-07-24.md` · comparison licenses `LADDER-RELATIONSHIPS-2026-07-23.md`
- Research report (what this studies, what it found, what it does not establish): `README.md` · Operational front door (setup · commands · layout · doc index): `docs/DEVELOPMENT.md`
- Lever maps (primitives / machinery / expressibility control): `docs/ONTOLOGY.md` / `docs/MACHINERY.md` / `docs/SEARCH-SPACE.md`
- **Everything dated is in `docs/archive/`** — superseded research frames, completed plan lineages, the config-defaults review, the dated check inventory. Indexed by `docs/DEVELOPMENT.md`; go there when you need the history behind a decision. Deliberately not enumerated here: this file loads every session, and an archive pointer in it reads as a live source of truth.
