# EXECUTION.md — the activity / call-stack model

How the three activities (**SEARCH**, **SEARCH + LEARN**, **STUDY**) are composed from the execution layer's primitives. Sibling to [ARCHITECTURE.md](ARCHITECTURE.md) (the search-engine design); code lands under `src/arc_lab/program_search/execution/` (the `solvers/program_search/` → `program_search/` rename is **done**; the old `solvers/dsl/` stays on disk until the end-of-overhaul audit — see _Implementation order_).

Status: agreed design, 2026-07-11. There is no `Solver` / `ProgramSearchSolver` class — the execution layer drives `Config` (`library × search_engine × constraints × cost × learn?`) directly.

## Terminology

Granularity levels (ARC's own terminology): **dataset ⊃ corpus ⊃ task ⊃ example**. A dataset holds two corpora (**train** / **eval**); a task holds **train examples** and **test examples**. So: _train vs eval_ at the corpus level, _train vs test_ at the example level.

- **Test examples (within-task)** — each `Task`'s own held-out `test` examples. The search sees only the train examples; scoring always happens on the test examples. This never changes, in any flow, on any corpus. _(Naming: the scorer is **`score`**, not "evaluate" — avoiding collision with both the **eval corpus** and `Program.evaluate`, which keeps its canonical interpreter meaning: apply a program to a grid.)_
- **Train / eval corpus** — the _across-task_ split. The **train corpus** is the set of tasks the learning loop may see; the **eval corpus** is tasks the learning **never saw**. This axis exists only because a learned library exists — it grades whether _the library_ transfers.
- **Recorded run** — `RunSpec = Config × Corpus` → content-hashed `run_id` → executed once, cached thereafter (`runspec.json` written first, `trace.jsonl` streamed, `results.json` written last; a present `results.json` is served from cache).

Where each corpus is touched:

| Phase | Train corpus | Eval corpus |
| --- | --- | --- |
| Wake–sleep loop (search + learn) | ✅ searched & learned from | ❌ **never touched** |
| Final / grid evaluation runs | ✅ → measures **train-usefulness** | ✅ → measures **transfer** |

The two axes never substitute for each other: the corpus axis decides _which tasks_ get searched; the within-task axis decides _which grids_ the found programs are scored on.

## The primitives

- `SearchEngine.run(train_examples, library, constraints, cost) → SearchResult` — the only entry point for searching one task. Takes the task's **train examples only** (not the full `Task`), so blindness to test examples is structural, not a promise. _(Agreed decision; the signature change lands with the engine work. `Cost.of` takes the same `train_examples` for the same reason; `task_id` for logging comes from the caller.)_
- `predict(programs, test_inputs, library) → attempts` — **pure**: select the best k programs (ARC: 2 attempts) and apply them to the test inputs via `Program.evaluate_grid`. The apply-to-test step formerly inside `Solver.predict` (the `Solver` class is gone; this function is its surviving functionality).
- `score(attempts, test_outputs) → TaskScore` — **pure**: grid comparison, either-of-2-attempts (essentially the existing `score_task`). `predict` + `score` are the only functions that touch test grids. Recording is owned by the _activity_, never by these.
- `LearnEngine.run(library, all_wake_solutions) → grown library` — sleep. Consumes the whole corpus's wake solutions at once (cross-task compression needs the corpus in view).

Comparison-to-expected exists in exactly two places, one per example level: the `target` signature / `Constraint.holds` (**train** examples, inside search) and `predict`+`score` (**test** examples, in the activity). `Program.evaluate` / `evaluate_grid` are the _interpreter_ (program × grid → value), not comparators, and keep their names.

---

## SEARCH — one corpus

_(No learned object exists → no across-task question → one corpus is fully sound.)_

1. `run_search_across_corpus` — for each task: `SearchEngine.run(task.train, …)`; collect best programs.
2. `predict` + `score` — pure: apply each task's best programs to its **test inputs**; score against test outputs.
3. Record to `runs/<run_id>/`. _(Recording is owned by the activity; the idempotency check happens before step 1.)_

## SEARCH + LEARN — train corpus, optional eval corpus

Takes: **train corpus** (searched & learned from); optionally an **eval corpus** (evaluation only — _never touched by the loop_).

1. **Wake–sleep loop** — on the _train corpus only_:
   1. Wake: `run_search_across_corpus` (fresh search each wake; reset-programs param, default True).
   2. Sleep: `LearnEngine.run(all wake solutions) → grown library`.
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
  │   ├─ search_engine: SearchEngine ↗       #   incl. its Budget + capability policies
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
  └─ run_id (derived) = hash(config × corpus.content_hash)    # commit recorded but EXCLUDED

StudySpec                                    # orchestration, not a run — generates RunSpecs
  ├─ base_config: Config                     #   library = L1, learn = LearnSpec; grid cells derive via
  ├─ budgets: tuple[Budget ↗, ...]           #   base_config.with_(library=Lᵢ, budget=bⱼ, learn=None)
  ├─ train_corpus: Corpus ↗
  ├─ eval_corpus: Corpus ↗
  └─ target_abstractions: tuple[(name, Program ↗), ...]   # templates over starting primitives → L3

── RECORDS (read side: what happened — derived, never hashed) ───────────────────

RunRecord                                    # the handle execute() returns; input to analyze_run / study report
  ├─ run_id
  ├─ artifact paths (runs/<run_id>/…)
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
                            ├─ runs/<run_id>/results.json present? → cached RunRecord (no execution)
                            ├─ config.learn is None  (SEARCH run):
                            │    for task in corpus:
                            │      SearchEngine.run(task.train_examples, library, constraints, cost)
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
│   ├── learn/               # sleep: learn_engine · proposers · governance (taskgen moves OUT)
│   └── execution/           # the layer THIS doc specifies
│       ├── model/           #   the run DATA MODEL (frozen, hashable specs + records)
│       │   ├── config.py · learn_spec.py · run_spec.py · study_spec.py
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

Two deliberate changes vs. the old CLI: **`analyze-run` is read-side only** (the old `analyze` _executed_; execution is `search`/`learn`'s job now, and idempotency makes run-if-missing trivial), and **`taskgen` is its own command** — corpus _generation_ (seeded, deterministic, rare, committed) is disentangled from corpus _consumption_; a study that regenerated corpora inline would silently mint new run identities whenever generation logic changed, killing cache reuse. Study _takes_ corpora, never makes them.

## Load-bearing properties

1. The eval corpus appears **only** in evaluation cells, never inside the wake–sleep loop.
2. Scoring (`predict`+`score`) always means within-task test scoring; both are pure and reusable (by `analyze_run` and `create_study_report`).
3. Every final / grid evaluation is the _same_ recorded-run primitive — so STUDY inherits caching, and overlapping cells (step 2 vs step 3) cost nothing extra.
4. Wake is batched over the whole corpus before each sleep (cross-task compression signal; per-task interleaving would be order-dependent and starve antiunification).
5. Fresh search each wake (default): sleep must see solutions _re-expressed_ in the grown library, and search-effort is a measured signal — serving cached solutions would silently destroy both.
6. The report/analyze step (`analyze_run`, `create_study_report`) is read-only over stored artifacts.

## Implementation order

Ordering principles: **leaf dependencies first** · **additive before destructive** (deletions/renames last, tree stays workable throughout) · **cross-fork contact only at named sync points** (the engine/substrate work proceeds in parallel; the forks never edit the same file bodies).

**Phase 0 — Foundations** _(pure, zero-collision)_
1. `core/hashing.py` — `canonical_json` + `hash_id`. Tests: stability, key-order invariance.
2. `Corpus.content_hash` in `core/dataset.py`. Tests: same content ⇒ same hash; content change ⇒ different; corpus *name* excluded (content-addressed: identical content under two names is the same corpus for caching).

**Phase 1 — The run data model** (`execution/model/`)
3. `results.py` — `TaskScore`, `TaskResult`.
4. The serialization contract, once: `kind` discriminator + params, base-class `from_dict` dispatch (mirrors `Program.from_dict`), generic frozen-dataclass↔dict helper.
5. `learn_spec.py`.
6. `config.py` rewrite — `attempts_per_test`, `learn: LearnSpec | None`, `with_(...)`, delegating `to_dict`/`from_dict`.
7. `run_spec.py` (`run_id`) + `run_record.py`.
8. Tests against **fake components**: round-trip, hash stability, identity properties (SEARCH/LEARN never collide; corpus content moves `run_id`; commit excluded).

> **🔗 Sync A:** `to_dict`/`from_dict` on the real `SearchEngine`/`Cost`/`Constraint`/`LearnEngine` (engine-fork files). Phase 1 completes against fakes; real wiring is a small follow-up.

**Phase 2 — Scoring + predict** _(mostly additive)_
9. `eval/scoring.py`: parameterize attempts (`k`, default 2, fed from `Config`); `Prediction` type moves in (additively; the `solvers/base` import path dies in Phase 6).
10. `execution/predict.py` + tests with hand-built programs.

**Phase 3 — The core: `execute`**
11. `execute.py` — artifact layout, `runspec.json` first, `trace.jsonl` streamed + resume, `results.json` last, idempotency, `record_run`, `RunRecord` return; SEARCH branch wired to `SearchEngine.run`.
12. End-to-end test: tiny task + tiny library → run → cache-hit → resume from partial trace.

> **🔗 Sync B:** the `run(train_examples, …)` signature (engine fork lands it; `execute` consumes it). **🔗 Sync C:** the `LearnEngine.run` interface (needed for step 14).

**Phase 4 — Activities**
13. `run_search.py` (thin).
14. `run_search_learn.py` — the loop (batch wake, ends with sleep, reset/telemetry params, per-iteration trace) + derived runs via `load_library`.
15. `analyze_run.py` — read-side basics.

**Phase 5 — Study**
16. `model/study_spec.py` + `run_study.py` (grid via `base_config.with_(...)`, execute-with-cache) + `create_study_report`.

**Phase 6 — Destructive cleanup** _(each its own commit)_
17. Delete `solvers/base.py` (`Solver`) + `eval/runner.py`; consumers of `TaskResult` move to `model/results.py`. _(The `solvers/` → `program_search/` rename is already done.)_
18. `taskgen/` moves out of `learn/`.
19. **Audit, then delete `solvers/dsl/`** — the old tree stays on disk until a dedicated comparison pass (old `dsl/` vs the new build: anything missed?) has run. Deleting it is the *last* destructive step, after that audit.

**Phase 7 — CLI + docs**
20. `cli/` — thin modules per command; presets registry replaces the solver `REGISTRY`.
21. Docs reconciliation: CLAUDE.md pointers, `ARCHITECTURE-2026-07-09.md` supersede-or-merge, EXPERIMENTS.md overhaul entry.
22. **Re-pin the behavior locks deliberately** (old locks reference old presets; re-pinning is an explicit, reviewed change) — `make check` green is the final gate.
