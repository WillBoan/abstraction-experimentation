# EXECUTION.md — the activity / call-stack model

How the three activities (**SEARCH**, **SEARCH + LEARN**, **STUDY**) are composed from the execution layer's primitives. Sibling to [ARCHITECTURE.md](ARCHITECTURE.md) (the search-engine design); the code lives under `src/arc_lab/program_search/execution/` (the old `solvers/dsl/` tree stays on disk until the end-of-overhaul audit — see _Implementation history_).

Status: agreed design, 2026-07-11. There is no `Solver` / `ProgramSearchSolver` class — the execution layer drives `Config` (`library × search_engine × budget × constraints × cost × learn?`) directly.

## Terminology

Granularity levels (ARC's own terminology): **dataset ⊃ corpus ⊃ task ⊃ example**. A dataset holds two corpora (**train** / **eval**); a task holds **train examples** and **test examples**. So: _train vs eval_ at the corpus level, _train vs test_ at the example level.

- **Test examples (within-task)** — each `Task`'s own held-out `test` examples. The search sees only the train examples; scoring always happens on the test examples. This never changes, in any flow, on any corpus. _(Naming: the scorer is **`score`**, not "evaluate" — avoiding collision with both the **eval corpus** and `Program.evaluate`, which keeps its canonical interpreter meaning: apply a program to a grid.)_
- **Train / eval corpus** — the _across-task_ split. The **train corpus** is the set of tasks the learning loop may see; the **eval corpus** is tasks the learning **never saw**. This axis exists only because a learned library exists — it grades whether _the library_ transfers.
- **Recorded run** — `RunSpec = Config × Corpus` → content-hashed `run_id` → executed once, cached thereafter (`runspec.json` written first, `trace.jsonl` streamed, `results.json` written last; a present `results.json` is served from cache). The `run_id` is the cache key `execute()` dedupes on, not the raw dirname: the on-disk dir is `runs/<started_at>_<run_id>/` (`model.run_record.find_run_dir` resolves by hash suffix) so `runs/` sorts and reads chronologically while the identity stays a pure function of `(config, corpus)`.

Where each corpus is touched:

| Phase | Train corpus | Eval corpus |
| --- | --- | --- |
| Wake–sleep loop (search + learn) | ✅ searched & learned from | ❌ **never touched** |
| Final / grid evaluation runs | ✅ → measures **train-usefulness** | ✅ → measures **transfer** |

The two axes never substitute for each other: the corpus axis decides _which tasks_ get searched; the within-task axis decides _which grids_ the found programs are scored on.

## The primitives

- `SearchEngine.run(train_examples, library, constraints, cost, budget) → SearchResult` — the only entry point for searching one task. Takes the task's **train examples only** (not the full `Task`; the `TrainExamples` alias in `core/task.py`), so blindness to test examples is structural, not a promise. `budget` is an *argument*, not an engine field: the engine is machinery (HOW — algorithm + capability policies); the budget is per-run data (HOW MUCH), varied independently (e.g. across a study grid) and living on `Config`. _(**Sync B: DONE.** `Cost.of`, `Constraint.holds`, `extract`, and `BodySampler` take the same `train_examples`; `task_id` for logging comes from the caller.)_
- `predict(programs, test_inputs, library) → attempts` — **pure**: select the best k programs (ARC: 2 attempts) and apply them to the test inputs via `Program.evaluate_grid`. The apply-to-test step formerly inside `Solver.predict` (the `Solver` class is gone; this function is its surviving functionality).
- `score(attempts, test_outputs) → TaskScore` — **pure**: grid comparison, either-of-2-attempts (essentially the existing `score_task`). `predict` + `score` are the only functions that touch test grids. Recording is owned by the _activity_, never by these.
- `LearnEngine.run(library, solutions: tuple[SolvedTask, ...]) → LearnOutcome` — sleep. Consumes the whole corpus's wake solutions at once (cross-task compression needs the corpus in view). `SolvedTask` = (annotated task, found program), in `analysis/compression.py`. `LearnOutcome` = grown `library` + `added` primitives + `rewritten` solutions + `description_length` (the MDL objective — deliberately **not** named "score": `score_task` is the unrelated test-example scorer), with a derived `converged` (nothing added) that drives `early_stop`. A `LearnEngine` is a frozen dataclass: it is run identity, hashed via the component serde.

Comparison-to-expected exists in exactly two places, one per example level: the `target` signature (**train** examples — the engine's goal test, `sig == target`; there is no `ConsistentWithTraining` constraint — deleted as a redundant, ⊥-incompatible reimplementation of the goal test) and `predict`+`score` (**test** examples, in the activity). A `Constraint` means only an _extra_ inductive-bias filter on goal-test survivors. `Program.evaluate` / `evaluate_grid` are the _interpreter_ (program × grid → value), not comparators, and keep their names.

---

## SEARCH — one corpus

_(No learned object exists → no across-task question → one corpus is fully sound.)_

1. `run_search_across_corpus` — for each task: `SearchEngine.run(task.train, …)`; collect best programs.
2. `predict` + `score` — pure: apply each task's best programs to its **test inputs**; score against test outputs.
3. Record to `runs/<started_at>_<run_id>/`. _(Recording is owned by the activity; the idempotency check happens before step 1.)_

## SEARCH + LEARN — train corpus, optional eval corpus

Takes: **train corpus** (searched & learned from); optionally an **eval corpus** (evaluation only — _never touched by the loop_).

1. **Wake–sleep loop** — on the _train corpus only_:
   1. Wake: `run_search_across_corpus` (fresh search each wake; reset-programs param, default True).
   2. Sleep: `LearnEngine.run(library, solutions) → LearnOutcome` (grown library + telemetry).
   3. Iterate per wake-sleep params; **ends with sleep** (the final wake is step 2 below, so no stale programs are ever evaluated — don't "fix" this back to ending with search).
   - Optional telemetry: `predict`+`score` after each wake (param, default False; never feeds back into learning).
   - Record `learned_library.json` + per-iteration trace.
2. **Final evaluation** — for the final library × each provided corpus, execute a **plain SEARCH recorded run** (search + predict/score + record, exactly as above):
   - × train corpus → **train-usefulness**.
   - × eval corpus (if provided) → **transfer**.

## STUDY — search + learn + targets; two corpora required

Takes: **train corpus**, **eval corpus**, **target abstraction(s)**.

1. **Set up** — libraries: **L1** = starting; **L2** = L1 + invented (produced by step 2); **L3** = L1 + target abstractions.
2. **Learn** — SEARCH + LEARN on the train corpus with L1 → yields L2. (Its final-evaluation runs are recorded runs; the grid below reuses them from cache.)
3. **Grid** — for each `(L1, L2, L3) × (budget₁, budget₂) × (train corpus, eval corpus)`: execute a **plain SEARCH recorded run**. Cells already computed (e.g. by step 2) are served from cache by `run_id`.
4. **Report** (`create_study_report`) — _pure read_ over the recorded runs (this is the analyze layer, not new execution):
   - behavioral check: invented L2 abstractions vs L3 targets (observables only — never a training signal);
   - solve-rate comparison across libraries × budgets × corpora;
   - **search-effort comparison** (`considered` from `SearchStats`): speedup is a distinct, often earlier signal than enablement;
   - transfer metrics (eval-corpus cells vs train-corpus cells).

---

## The run data model

Three kinds of type, one tree each. **Specs** are input identity (frozen, content-hashed); **records/results** are outputs (frozen, derived — never hashed into identity). Leaf types marked `↗` are defined elsewhere and appear here by reference only — this section deliberately does not re-document them (`Task`, `Grid`, `Program`, `Library`, `Corpus`, `SearchEngine`, `Budget`, … live in `core/` and `program_search/`).

```
── SPECS (write side: what to run — content-hashed) ─────────────────────────────

RunSpec                                      # the recorded-run atom — exactly ONE corpus
  ├─ config: Config                          # the machinery (HOW)
  │   ├─ library: Library ↗                  #   content-addressed; provenance (hand-written vs grown) is NOT identity
  │   ├─ search_engine: SearchEngine ↗       #   the machinery: algorithm + capability policies (HOW)
  │   ├─ budget: Budget ↗                    #   the resource caps (HOW MUCH) — per-run data, flows into run() as an arg
  │   ├─ constraints: tuple[Constraint ↗, ...]
  │   ├─ cost: Cost ↗
  │   ├─ attempts_per_test: int = 2          #   k programs tried per test input (official ARC: 2); flows to predict()
  │   └─ learn: LearnSpec | None             #   None ⇒ SEARCH run; set ⇒ LEARN run (the two can never collide on run_id)
  │       ├─ learn_engine: LearnEngine ↗     #   sleep's internal governance (MDL threshold, proposer) lives on the engine
  │       ├─ iterations: int                 #   max wake–sleep cycles (a cap, not a mandate)
  │       ├─ early_stop: bool = True         #   stop when sleep converges (library unchanged / no MDL gain)
  │       ├─ reset_programs_each_wake: bool = True
  │       └─ score_each_wake: bool = False   #   telemetry only; never feedback
  ├─ corpus: Corpus ↗                        # the content (WHAT)
  └─ run_id (derived) = hash(config × corpus.content_hash)    # commit + run_started_at recorded but EXCLUDED

StudySpec                                    # orchestration, not a run — generates RunSpecs
  ├─ base_config: Config                     #   library = L1, learn = LearnSpec; grid cells derive via
  ├─ budgets: tuple[Budget ↗, ...]           #   base_config.with_(library=Lᵢ, budget=bⱼ, learn=None)
  ├─ train_corpus: Corpus ↗
  ├─ eval_corpus: Corpus ↗
  └─ target_abstractions: tuple[(name, Program ↗), ...]   # templates over starting primitives → L3

── RECORDS (read side: what happened — derived, never hashed) ───────────────────

RunRecord                                    # the handle execute() returns; input to analyze_run / study report
  ├─ run_id                                  #   content-addressed identity (the cache key)
  ├─ artifact paths (runs/<started_at>_<run_id>/…)   # run_dir is resolved by run_id suffix, not joined directly
  └─ lazily loaded: results / learned_library / trace

TaskScore                                    # score_task's verdict for one task
  ├─ solved: bool                            #   ALL test inputs correct
  └─ per_test: tuple[bool, ...]              #   any-of-k-attempts, per test input

TaskResult                                   # one row of results.json (TaskScore + provenance)
  ├─ task_id · TaskScore · seconds · error
  └─ (moves here from the old eval/runner.py, which dies with Solver)
```

Run-count accounting:

- a LEARN activity = **one** recorded run (per-iteration telemetry lives in its trace; wakes are _not_ separate runs — wake _i_'s library only exists inside the loop's history, so it has no independently addressable identity) **plus** its derived SEARCH runs.
- `arc-lab learn` therefore produces **2–3 recorded runs**: the learn run + train-corpus evaluation (+ eval-corpus evaluation if provided). Train × eval final evaluation is always **2 separate runs** — different questions, different identities, independently cacheable.

## Tracing — capability sampling & full capture (outside run identity)

Every recorded run carries `SearchStats.outcomes`/`by_key` unconditionally — the outcome
partition (`search/tracking.py`: every candidate a `SearchEngine` considers resolves to exactly
one of `errored/pruned/deduped/displaced/evicted/goal_unmatched/constraint_rejected/accepted`,
broken down per primitive-name/node-kind key). That's free, no config, always on.

Beyond the counts, `TraceSpec` (`execution/model/trace_spec.py`) governs two further, opt-in
observations of a search, passed to `execute()` as a plain keyword (`trace: TraceSpec | None`)
— **never** a `Config` field:

- **Sampling** (`TraceSpec.samples`, on by default — a small deterministic `first_k` reservoir
  per `(key, outcome)` bucket) — a few example programs per primitive/node-kind × outcome,
  cheap enough to run unconditionally.
- **Full capture** (`TraceSpec.capture_all`, off by default) — every considered candidate,
  streamed to `capture/<task_id>.jsonl` (LEARN: `capture/iter-<n>/<task_id>.jsonl`), capped at
  `capture_all_max` — truncation is recorded loudly in `manifest.json`, never silently dropped.

Run-dir layout, extended:

```
runs/<started_at>_<run_id>/
├── runspec.json           # identity + provenance (written first)
├── trace.jsonl            # per-task/wake rows (resumable checkpoint)
├── results.json           # aggregate (written last — marks completion)
├── learned_library.json   # LEARN runs only
├── samples.json           # optional: TraceSpec.samples reservoirs, keyed by task_id
│                           #   (LEARN: "iter-<n>/<task_id>") — covers only the tasks THIS
│                           #   invocation actually ran; a resume's already-traced tasks
│                           #   aren't re-sampled (a diagnostic artifact, not run identity)
├── capture/                # optional: TraceSpec.capture_all's per-task JSONL streams
│   └── <task_id>.jsonl
└── manifest.json           # optional: capture settings + counts + truncation, per task
```

**Why `TraceSpec` is not part of `run_id`:** `Config` decides _what is computed_; `TraceSpec`
decides _what is recorded about_ that computation. Excluding it from the hash is sound
specifically because this codebase is deterministic (no RNG anywhere — CLAUDE.md's
"Immutable & deterministic" invariant): re-executing a cached run under a different `TraceSpec`
provably reproduces the identical search, so telemetry can always be safely (re)attached to an
existing run directory without risk that it describes a different execution than the one whose
`results.json` is already cached. `force_recapture=True` on `execute()` (CLI: `--force-recapture`)
exploits exactly this — it deletes `trace.jsonl`/`results.json` and re-executes from scratch
purely to repopulate tracing artifacts under a new `TraceSpec`, without changing the run's
identity or the substantive content of `results.json` (only wall-clock `seconds` and whatever
the new `TraceSpec` observes can differ).

## The call stack

`execute` is the **only writer of `runs/`**; the activities orchestrate it; the read side never executes.

```
CLI                       ACTIVITIES                            THE CORE
arc-lab search       ──▶  run_search(config, corpus)       ──▶  execute(RunSpec)
arc-lab learn        ──▶  run_search_learn(config,              │
                            train_corpus, eval_corpus?)     ──▶  │  1× execute(learn RunSpec)
                            └─ load_library(record)             │  then 1–2× execute(derived SEARCH RunSpecs)
arc-lab run-study    ──▶  run_study(study_spec)             ──▶  │  N× execute(grid RunSpecs) (cache hits free)
                            └─ create_study_report(records)     │
                                                                 ▼
                          execute(run_spec) → RunRecord
                            ├─ runs/<started_at>_<run_id>/results.json present? → cached RunRecord (no execution)
                            │    (an existing dir is located by its run_id suffix — find_run_dir; the
                            │     started_at prefix is only ever set once, at first execution)
                            ├─ config.learn is None  (SEARCH run):
                            │    for task in corpus:
                            │      SearchEngine.run(task.train_examples, library, constraints, cost, budget)
                            │      predict(programs, test_inputs, library, k=config.attempts_per_test)
                            │      score_task(attempts, test_outputs) → TaskScore
                            │      → TaskResult row → trace.jsonl (streamed; resumable)
                            └─ config.learn is set   (LEARN run):
                                 loop { wake: per-task SearchEngine.run · sleep: LearnEngine.run }
                                 → learned_library.json + per-iteration trace
                            └─ record_run(...) → runspec.json (first) · results.json (last)

READ SIDE (never executes)
arc-lab analyze-run  ──▶  analyze_run(run_id)     — RunRecord → derived metrics (MDL, effort, programs)
                          create_study_report     — RunRecords → behavioral check · comparisons · transfer
                          load_library            — substrate/store.py (existing) reads learned_library.json
```

Function inventory:

- `execute`
- Activities:
  - `run_search`
  - `run_search_learn`
  - `run_study`
  - `analyze_run`
- `predict`
- `score_task` (pure, per-task)
- `record_run` (artifact writing, called only by `execute`)
- `create_study_report`
- `load_library` (existing, `substrate/store.py`)

## File / folder structure (target)

```
src/arc_lab/
├── core/                    # domain-generic: grid · task · annotation · dataset (Corpus + content_hash) · hashing
├── eval/                    # ARC scoring RULES — paradigm-agnostic, stays put
│   └── scoring.py           #   score_test_input · score_task · Prediction (moves in from solvers/base)
│                            #   runner.py DIES with Solver (replaced by execute)
├── program_search/          # ← moved up from solvers/ (DONE, committed)
│   ├── substrate/           # the language: types · program · library · primitives/ · registry · store
│   ├── search/              # the wake proposer (SearchEngine + its parts)
│   │   └── tracking.py      #   capability tracking: Outcome partition · SearchTracker (sampling/capture)
│   ├── learn/               # sleep: learn_engine (ABC + LearnOutcome) · proposers · governance (taskgen moves OUT)
│   ├── analysis/            # read-side instrument: compression.py (SolvedTask · MDL metrics · ratios)
│   │                        #   capabilities.py (read-time category/provenance groupings over by_key)
│   └── execution/           # the layer THIS doc specifies — activities live HERE, not a commands/
│                            #   package (they ARE the execution layer; the CLI is the separate thin cli/)
│       ├── model/           #   the run DATA MODEL (frozen, hashable specs + records)
│       │   ├── config.py · learn_spec.py · run_spec.py · study_spec.py
│       │   ├── trace_spec.py   #   TraceSpec — sampling/capture config, deliberately OUTSIDE Config
│       │   └── run_record.py · results.py (TaskScore · TaskResult)
│       ├── execute.py       #   the recorded-run core (idempotency · trace · record_run)
│       ├── run_search.py    #   SEARCH activity
│       ├── run_search_learn.py  # LEARN activity (loop + derived runs)
│       ├── run_study.py     #   STUDY orchestration + create_study_report
│       ├── predict.py       #   predict (apply-to-test; the survivor of Solver.predict)
│       └── analyze_run.py   #   read-side
├── taskgen/                 # corpus GENERATION — own concern; writes testbeds/; consumes substrate
├── cli/                     # thin: arg-parse + dispatch only, one module per command
└── viz/
```

Layering rules:

- `model/` holds only frozen data (specs + records — importable by anything); behavior files import `model/`, never the reverse.
- `eval/` stays paradigm-neutral (grids in, booleans out) so a future non-search solver seam can reuse it unchanged.

## CLI

| Command | Function | What it does |
| --- | --- | --- |
| `arc-lab search <config> --corpus <c>` | `run_search` | execute one SEARCH recorded run |
| `arc-lab learn <config> --corpus <train> [--eval-corpus <eval>]` | `run_search_learn` | learn run + derived SEARCH runs (2–3 runs) |
| `arc-lab run-study <name>` | `run_study` | generate RunSpecs → execute (cached) → `create_study_report` |
| `arc-lab analyze-run <run_id>` | `analyze_run` | **read-only** over a completed run's artifacts (leaves room for a future `analyze-study`) |
| `arc-lab taskgen <generator>` | — | generate a synthetic corpus → committed testbed (`testbeds/`) |
| `arc-lab runs` / `configs` / `datasets` / `show` | — | utilities (`solvers` dies with `Solver`; `configs` lists presets) |

**Config precedence:** `dataclass defaults < named preset < config file < CLI --set`. The `<config>` argument to `search`/`learn` is a preset name or a JSON file `{"preset": "<name>", "set": {"<dotted.path>": <value>}}`; `--set path=value` (repeatable) applies last. Overrides are dotted paths into the frozen `Config` (`budget.max_depth=4`, `search_engine.beam_width=64`, `library=d4` by registry name, `learn.iterations=3` on a LEARN config) — `execution/overrides.py`; unknown fields and type mismatches fail loudly, and every override mints its own `run_id` (no cache collisions).

**Tracing flags** (`search`/`learn`, `cli/_trace.py`, see _Tracing_ above): `--sample k:mode` (repeatable; `mode` is `first_k` or `cheapest_k`) overrides the default sampler, `--track-all` turns on full capture (`--capture-max` caps it, default 100k), `--force-recapture` re-executes an already-completed run to (re)populate its tracing artifacts. None of these affect `run_id` — they can be added to a cached run after the fact.

Two deliberate changes vs. the old CLI: **`analyze-run` is read-side only** (the old `analyze` _executed_; execution is `search`/`learn`'s job now, and idempotency makes run-if-missing trivial), and **`taskgen` is its own command** — corpus _generation_ (seeded, deterministic, rare, committed) is disentangled from corpus _consumption_; a study that regenerated corpora inline would silently mint new run identities whenever generation logic changed, killing cache reuse. Study _takes_ corpora, never makes them.

## Load-bearing properties

1. The eval corpus appears **only** in evaluation cells, never inside the wake–sleep loop.
2. Scoring (`predict`+`score`) always means within-task test scoring; both are pure and reusable (by `analyze_run` and `create_study_report`).
3. Every final / grid evaluation is the _same_ recorded-run primitive — so STUDY inherits caching, and overlapping cells (step 2 vs step 3) cost nothing extra.
4. Wake is batched over the whole corpus before each sleep (cross-task compression signal; per-task interleaving would be order-dependent and starve antiunification).
5. Fresh search each wake (default): sleep must see solutions _re-expressed_ in the grown library, and search-effort is a measured signal — serving cached solutions would silently destroy both.
6. The report/analyze step (`analyze_run`, `create_study_report`) is read-only over stored artifacts.

## Implementation history

Built 2026-07-11 in seven phases (foundations → run data model → scoring/predict → `execute` → activities → study → CLI + docs), with three cross-fork sync points (component serde on the real engines; the `run(train_examples, …)` blindness seam; the `LearnEngine`/`LearnOutcome` port). The full phase plan and per-step notes are in this file's git history (pre-2026-07-13); the locks were re-pinned deliberately in `tests/program_search/execution/test_locks.py` (full numbers + interpretation: EXPERIMENTS.md 2026-07-11).

**One step remains open — audit, then delete the old tree.** `src/arc_lab/solvers/` (incl. `dsl/`, `base.py`, `baseline.py`), `eval/runner.py`, `cli_legacy.py`, and the old top-level `tests/test_*.py` stay on disk until a dedicated comparison pass (old `dsl/` vs the new build: anything missed?) has run; they then delete as ONE unit. Nothing under `program_search/`, `cli/`, or `tests/program_search/` imports them. The old locks in `tests/test_integration.py` guard the old tree until then. _(User-owned; the last destructive step.)_ The eight live-module test files formerly at `tests/test_*.py` were moved to `tests/{core,eval,taskgen}/` (2026-07-13) precisely so this deletion cannot sweep them.
