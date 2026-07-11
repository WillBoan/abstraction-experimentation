# EXECUTION.md — the activity / call-stack model

How the three activities (**SEARCH**, **SEARCH + LEARN**, **STUDY**) are composed from the execution layer's primitives. Sibling to [ARCHITECTURE.md](ARCHITECTURE.md) (the search-engine design); code lands under `src/arc_lab/solvers/program_search/execution/`.

Status: agreed design, 2026-07-10. There is no `Solver` / `ProgramSearchSolver` class — the execution layer drives `Config` (`library × search_engine × constraints × cost × learn_engine?`) directly.

## Terminology

- **Within-task test** — each `Task`'s own held-out `test` examples. `SearchEngine.run` sees only `task.train`; `evaluate` always scores on the within-task test inputs. This never changes, in any flow, on any corpus.
- **Training / test corpus** — the _across-task_ split. The **training corpus** is the set of tasks the learning loop may see; the **test corpus** is tasks the learning **never saw**. This axis exists only because a learned library exists — it grades whether _the library_ transfers.
- **Recorded run** — `RunSpec = Config × Corpus` → content-hashed `run_id` → executed once, cached thereafter (`runspec.json` written first, `trace.jsonl` streamed, `results.json` written last; a present `results.json` is served from cache).

Where each corpus is touched:

| Phase | Training corpus | Test corpus |
| --- | --- | --- |
| Wake–sleep loop (search + learn) | ✅ searched & learned from | ❌ **never touched** |
| Final / grid evaluation runs | ✅ → measures **train-usefulness** | ✅ → measures **transfer** |

The two axes never substitute for each other: the corpus axis decides _which tasks_ get searched; the within-task axis decides _which grids_ the found programs are scored on.

## The primitives

- `SearchEngine.run(task, library, constraints, cost) → SearchResult` — the only entry point for searching one task. Sees `task.train` only.
- `evaluate(best_programs_per_task, corpus, library) → scored results` — **pure**: applies each task's best programs to its within-task test inputs and scores (ARC: either-of-2-attempts). The only function that touches test grids. Recording is owned by the _activity_, never by `evaluate`.
- `LearnEngine.run(library, all_wake_solutions) → grown library` — sleep. Consumes the whole corpus's wake solutions at once (cross-task compression needs the corpus in view).

---

## SEARCH — one corpus

_(No learned object exists → no across-task question → one corpus is fully sound.)_

1. `run_search_across_corpus` — for each task: `SearchEngine.run(task.train, …)`; collect best programs.
2. `evaluate` — pure: apply each task's best programs to its **within-task test inputs**; score.
3. Record to `runs/<run_id>/`. _(Recording is owned by the activity; the idempotency check happens before step 1.)_

## SEARCH + LEARN — training corpus, optional test corpus

Takes: **training corpus** (searched & learned from); optionally a **test corpus** (evaluation only — _never touched by the loop_).

1. **Wake–sleep loop** — on the _training corpus only_:
   1. Wake: `run_search_across_corpus` (fresh search each wake; reset-programs param, default True).
   2. Sleep: `LearnEngine.run(all wake solutions) → grown library`.
   3. Iterate per wake-sleep params; **ends with sleep** (the final wake is step 2 below, so no stale programs are ever evaluated — don't "fix" this back to ending with search).
   - Optional telemetry: `evaluate` after each wake (param, default False; never feeds back into learning).
   - Record `learned_library.json` + per-iteration trace.
2. **Final evaluation** — for the final library × each provided corpus, execute a **plain SEARCH recorded run** (search + evaluate + record, exactly as above):
   - × training corpus → **train-usefulness**.
   - × test corpus (if provided) → **transfer**.

## STUDY — search + learn + targets; two corpora required

Takes: **training corpus**, **test corpus**, **target abstraction(s)**.

1. **Set up** — libraries: **L1** = starting; **L2** = L1 + invented (produced by step 2); **L3** = L1 + target abstractions.
2. **Learn** — SEARCH + LEARN on the training corpus with L1 → yields L2. (Its final-evaluation runs are recorded runs; the grid below reuses them from cache.)
3. **Grid** — for each `(L1, L2, L3) × (budget₁, budget₂) × (training corpus, test corpus)`: execute a **plain SEARCH recorded run**. Cells already computed (e.g. by step 2) are served from cache by `run_id`.
4. **Reduce** — _pure read_ over the recorded runs (this is the analyze layer, not new execution):
   - behavioral check: invented L2 abstractions vs L3 targets (observables only — never a training signal);
   - solve-rate comparison across libraries × budgets × corpora;
   - **search-effort comparison** (`considered` from `SearchStats`): speedup is a distinct, often earlier signal than enablement;
   - transfer metrics (test-corpus cells vs training-corpus cells).

---

## Load-bearing properties

1. The test corpus appears **only** in evaluation cells, never inside the wake–sleep loop.
2. `evaluate` always means within-task test scoring; it is pure and reusable (by `analyze_run` and the Study reduce step).
3. Every final / grid evaluation is the _same_ recorded-run primitive — so STUDY inherits caching, and overlapping cells (step 2 vs step 3) cost nothing extra.
4. Wake is batched over the whole corpus before each sleep (cross-task compression signal; per-task interleaving would be order-dependent and starve antiunification).
5. Fresh search each wake (default): sleep must see solutions _re-expressed_ in the grown library, and search-effort is a measured signal — serving cached solutions would silently destroy both.
6. The reduce step is read-only over stored artifacts.
