# Plan: Abstraction Ladder Experiments — foundational machinery

## Context

We are building the **Abstraction Ladder Experiments** for `arc-lab` — a batch of LEARN experiments measuring whether, and by how much, learned abstractions convert one intractable search into a sequence of tractable ones. Full design: `docs/abstraction_ladders/ABSTRACTION-LADDERS-2026-07-16.md`.

A **Ladder** = a **Floor** (`L_0`, a starting `Library`), an ordered chain of **bridging Rungs** (`r_1..r_k`, each a _learnable_ abstraction over the previous cumulative library `L_{i-1}`), and a **Top Rung** — the goal layer: the hardest tasks, whose solutions _use_ the top bridging rung `r_k` as a fragment, but which are **not** minted as an abstraction (nothing is above them to learn them). A rung-tagged **Corpus** holds the demonstrating tasks. The experiment measures **raw cost** (Floor → Top, no learning; usually intractable) against **laddered cost** (Floor → Top via the bridging rungs, with learning), plus a matrix of derived metrics.

This plan covers the **foundational machinery** that must exist before the first ladder can be designed, linted, run, and analyzed. Exploration confirmed **no structural `unfold` exists** and **no ladder machinery exists**; everything here is new or additive, with two small behavior-preserving refactors and a set of deliberate correctness changes to the search return path (each isolated in its own commit).

---

## Settled design decisions

### Depth & unfold (substrate)

- **Delete the dead `Program.depth()`** (leaf = 1, grep-confirmed zero call sites in `src/` and `tests/`) and its mention in the `program.py` module docstring — leaving two off-by-one depth conventions is a foot-gun.
- `compositional_depth(program, *, lam_as_leaf=True)` in `analysis/depth.py` (NEW) is then the ONE depth function. **Leaf = 0** convention (leaves/`Param`/`Const`/`Input`/`Var`/`PrimRef` = 0; `Apply`/`If`/`AppFn`/`Lam` add 1) = the search's generation accounting. A depth-`d` program needs `budget.max_depth >= d + 1` (the E1-note `+1`). _(Post-completion, 2026-07-18: superseded by the `depth_limit` rework — `Budget.max_depth` was renamed and re-defined as `Budget.depth_limit`, the INCLUSIVE compositional-depth cap (old `max_depth=n` == new `depth_limit=n-1`); the lint states its checks as `d <= depth_limit` and the validity window is recorded inclusively in `depth_limit` units. Design doc §2.)_ `lam_as_leaf=True` (default) does not recurse into `Lam.body` (its cost is paid in a descended sub-search) → measures top-level generation depth. Detect HO via `any(isinstance(n, Lam) for n in program.walk())` → depth checks advisory. Prefer non-HO floors (`function_hole_fill_mode="none"`) for v1.
- `unfold_program(program, library, *, expand=None) -> Program` in `substrate/abstraction.py` (NEW, inverse of `make_abstraction`). Mechanic: recursively unfold each child/arg first; at an `Apply(name, args)` where `library.get(name).template is not None` **and** (`expand is None` or `name in expand`), `substitute_params` the unfolded args into a fresh copy of that template, then recurse on the result. Semantics that MUST be tested: `expand=None` recurses through substituted templates all the way to floor (`d_raw`); `expand={r_i}` expands exactly `r_i`'s call sites — `r_i`'s template's own references to `r_{i-1}` stay folded (this is precisely the inlined-double-jump form). Capture-avoidance is free (`Param`/`Var` namespaces disjoint); simultaneous substitution.
- `substitute_params(template, arg_programs) -> Program` — the reusable atom (structural analogue of `Program.evaluate` binding args into `Param` holes). **Free function in `abstraction.py`** (keeps `Program` lean; both rewrites co-located).

### Solution sink & the search-return correctness changes

The pool is keyed `(type, signature)` with strictly-cheaper-wins dedup, and every solution has `type == goal_type, sig == target` — so the pool holds **at most one** solution entry, ever. The sink captures every goal-matching candidate at absorption, before dedup collapses them. This unlocks correctness AND is RQ3's "top-K solution retention" enabler (that deferred item becomes nearly free once this lands — update its cost estimate).

- **Sink recording (Commit 2, dormant/telemetry):** record `(candidate_index, generation, cost, program)` for every candidate with `output_type == goal_type and signature == target`, gated to the top-level search (`track_generation is not None`). `signature == target` is plain tuple `==` (matches `extract()`, short-circuits). **Keep-cheapest-K** reservoir (ranked by `(cost, candidate_index)`) + an O(1) running `first_solution_index`. Cap + loud `truncated` flag → the cap is a **`TraceSpec`** telemetry field (outside run identity); when it binds, only the _count/all-solutions_ views degrade (cheapest and first stay exact). Commit 2 does NOT change `.solved`/`ranked_programs` — they stay pool-based, so Commit 2 is provably zero-behavior.
- **Ranking key = `(cost, candidate_index)`** — cheapest, then first-arrived. This reproduces the pool's dedup identity (first-arrived-among-cheapest), preserving _which_ equal-cost program is retained. NOT `(cost, size, str)` — that would change WAKE-retained programs on ties, hence which abstraction mints, moving study locks with no solve-count change.
- **Commit 3 — eviction-loss fix (behavior change, may move locks):** returned `ranked_programs`/`.solved`/`solved_at_generation`/indices become sink-based, but returning **only the sink-cheapest** (cardinality ≤ 1, preserving `attempts_per_test` parity). Effect: returns the true cheapest solution even if the pool later evicted it → only flips unsolved→solved (never the reverse). Outcome partition stays pool-based, unchanged (an evicted solution stays `EVICTED`; the `solved > accepted` gap becomes a measured eviction-loss signal). Lock movement here is eviction-loss only.
- **Commit 4 — `attempts_per_test` wakeup (separate behavior change, may move locks):** `ranked_programs` becomes the full cheapest-ordered sink ranking; `predict` now sees up to `attempts_per_test` solutions (the long-intended semantics). Two train-consistent solutions can disagree on test grids, so test scoring can flip wrong→right with zero eviction — a distinct correctness change, its own commit, its own lock analysis.
- **Verification for Commits 3 & 4 diffs mint identity, not just solve sets** — run the study locks and confirm the learned library is byte-identical except where a change is expected and explained. Any lock movement: confirm the cause, update deliberately, note in `EXPERIMENTS.md`, queue re-runs in `EXPERIMENT_QUEUE.md`.
- **Early stopping: NOT in this work** (changes run identity; wrong for measurement). Deferred.

### Per-generation funnel (search)

Surface `SearchTracker._generations` (already accumulated) into `SearchStats`, serialize in `execute.py::_search_stats`, keep OUT of `merge_search_stats` (per-task only, like `solved_at_generation`). Sole source for `b_eff` fitting and the vocabulary-tax view. Additive → Commit 2.

### Sleep-cost counters (learn)

Thread an optional mutable `SleepCounters` (defined in **`learn/`**, NOT `search/tracking.py` — keep the seam clean) through `LearnEngine.run → AbstractionSelector.select → AbstractionProposer.propose` (additive param, default `None`, mirrors `SearchTracker`). Increment `proposal_count` at the `propose(...)` call (selection.py:64-68) and `antiunify_pair_count` at the `itertools.combinations(counts, 2)` loops (antiunify.py:91-96, 154-156). Attach to `LearnOutcome` (learn_engine.py); serialize in the sleep trace row (execute.py). Telemetry only. Additive → Commit 2.

### Refactors (behavior-preserving, lock-safe)

- Lift the behavioral-equivalence checker (`_matches_target` + `_probe_values` + `_agree` + `_type_matched_permutations`) from `run_study.py` into `analysis/behavioral.py`; study + ladder reports import it.
- Shared oracle-chain `Library` builder used by `run_ladder`.
- Do NOT refactor `StudySpec`/`run_study` away — locks depend on them.

---

## Ladder data model

```python
# ladders/spec.py

class DemonstrationKind(enum.Enum):          # relationship of a demo's solution to its rung's abstraction
    FULL_SOLUTION      = "full_solution"       # solution == template instantiated  -> AntiunifyPairs viable
    FRAGMENT_IDENTICAL = "fragment_identical"  # template is a subprogram, identical instantiation -> needs FrequentSubtree
    FRAGMENT_VARYING   = "fragment_varying"    # template is a subprogram, varying params -> needs StitchProposer

@dataclass(frozen=True, slots=True)
class Demonstration:
    task_id: str                 # body lives in the corpus; resolved by id
    kind: DemonstrationKind

@dataclass(frozen=True, slots=True, kw_only=True)
class Rung:                       # a BRIDGING rung — learnable
    level: int                                   # 1..k
    target_abstraction: TargetAbstraction        # (name, template over L_{level-1}); canonical form references r_{level-1}
    demonstrations: tuple[Demonstration, ...]    # >= 2; kinds vs THIS rung's abstraction

@dataclass(frozen=True, slots=True, kw_only=True)
class TopRung:                    # the goal layer — NO abstraction, nothing minted, solutions may differ
    task_ids: tuple[str, ...]
    reference_solutions: tuple[Program, ...]     # index-aligned, over L_k; for d_raw profile + routing check

@dataclass(frozen=True, slots=True, kw_only=True)
class LadderSpec:                # Floor = reference_config.library; height = len(rungs) + 1
    reference_config: Config     # LEARN config: .library=Floor(L_0), .budget=reference budget, .learn=wake-sleep params
    rungs: tuple[Rung, ...]      # bridging rungs, k >= 1
    top: TopRung
    train_corpus: Corpus         # rung-tagged (meta.label = rung name, meta.split), TRAIN
    heldout_corpus: Corpus       # HELDOUT — transfer / break-even
    budgets: tuple[Budget, ...]  # RQ2 sweep cells; reference budget must be one of them
    # methods: floor(), oracle_library(level), rung_tasks(level), lint() -> LadderShape, render() -> str,
    #          to_dict() (provenance, no from_dict — mirrors StudySpec)
```

```python
# ladders/shape.py  — the derived output of LadderSpec.lint()

@dataclass(frozen=True, slots=True)
class LintFinding:
    check: str; ok: bool; detail: str; severity: str   # severity in {"error","warn"}

@dataclass(frozen=True, slots=True)
class RungShape:
    level: int
    jump_depth: int                      # compositional_depth(target_abstraction.template)          over L_{i-1}
    double_jump_depth: int | None        # compositional_depth(unfold_program(r_{i+1}.template, expand={r_i}))
    fan_in: int                          # distinct lower rungs referenced (with multiplicity)
    demonstration_count: int
    kinds: tuple[DemonstrationKind, ...]
    mdl_break_even_margin: float
    involves_lambda: bool

@dataclass(frozen=True, slots=True)
class LadderShape:
    height: int
    raw_depth_profile: tuple[int, ...]   # per-top-task d_raw = compositional_depth(unfold_program(sol, expand=None))
    rungs: tuple[RungShape, ...]
    validity_window: tuple[int, int]     # (lower, upper) in max_depth coords
    findings: tuple[LintFinding, ...]
    ok: bool                             # no error-severity findings
```

- Rung tags ride on the testbed manifest as `label = <rung name>` + `split`; `DemonstrationKind` and `reference_solutions` live in the LadderSpec builder code (the testbed round-trip carries only `{task_id, label, split}`).
- `LadderSpec.render()` (and `__str__`): summary block (floor, height, `d_raw` profile, window, reference config) + per-rung table (level, name, `d_i`, double-jump depth, fan-in, demonstrations by kind). Doubles as the artifact in `docs/abstraction_ladders/ladders/<name>/`.

---

## Linting (`LadderSpec.lint() -> LadderShape`)

Static/cheap only — **never runs a search** (the empirical collision/skip-path guarantee is the certificate's job). Each check emits a `LintFinding`; `ok = no error-severity findings`. Checks:

1. **Structural (error):** `rungs` non-empty; `level`s contiguous `1..k`; every `Demonstration.task_id` and every `top.task_ids` entry exists in `train_corpus`; `len(top.task_ids) == len(top.reference_solutions)`; every bridging rung has `>= 2` demonstrations; every referenced task has `>= 2` train examples.
2. **Type well-formedness (error):** each `target_abstraction.template` type-checks over `L_{i-1}` — attempt `make_abstraction(name, template, L_{i-1})` and catch its `ValueError`/type errors (reuses its closed-template + contiguous-param validation); each `top.reference_solutions[j]` type-checks over `L_k`.
3. **Jump affordable (error):** for each bridging rung, `compositional_depth(target_abstraction.template) + 1 <= reference max_depth` (the `+1` budget offset).
4. **Raw intractable (error):** every `raw_depth_profile[j] + 1 > reference max_depth` (top solutions unreachable raw at the reference budget).
5. **Double-jump intractable (error):** for each consecutive bridging pair, `compositional_depth(unfold_program(r_{i+1}.template, expand={r_i})) + 1 > reference max_depth`; and the top over `L_{k-1}` (skip `r_k`) likewise intractable.
6. **Proposer compatibility (error):** each rung's demonstration kinds must be servable by `reference_config.learn.learn_engine.proposer`: all `FULL_SOLUTION` ⇒ `AntiunifyPairs` ok; any `FRAGMENT_IDENTICAL` ⇒ proposer must be `FrequentSubtree`/`TypeScopedFrequentSubtree`; any `FRAGMENT_VARYING` ⇒ must be `StitchProposer`.
7. **Parameter variation plan (warn — best-effort static):** for each `target_abstraction` param, classify derived-vs-free from the template; where the demonstrations' constructions are known to the builder, check free params vary across demos / fixed within task. Emits `warn` (not `error`) since full verification is empirical (the certificate + demonstration-health).
8. **MDL break-even (warn):** estimate `demonstration_count * per_use_saving - definition_cost > 0` from template size + count; warn if negative (the rung may not mint under GreedyMDL).
9. **Fan-in / telescope (warn):** compute `fan_in` per rung; warn if every rung has `fan_in == 1` (a degenerate all-telescope ladder).
10. **Lambda advisory (warn):** if any template `involves_lambda`, mark that rung's depth checks advisory.
11. **Validity window (recorded, not pass/fail):** compute `(lower, upper)` = (min `max_depth` where all jumps affordable, max `max_depth` where no inlined double-jump reachable).

---

## Confirmed API surface (reuse — do not reinvent)

- `PoolEntry(program, sig, cost, primitives=frozenset(), candidate_index=0, generation=0)`; `Pool.add_dedup(...) -> DedupOutcome(inserted, displaced)` (strictly-cheaper-wins; ties do NOT displace); `Pool.items_of_type`, `.cheapest(n) -> (Pool, dropped)`, `.entries()`. (`search/pool.py`)
- `Signature: TypeAlias = tuple[Value | Bottom, ...]` — plain tuple, value `==`, no cached hash. (`search/signature.py`)
- `extract(pool, goal_type, target, constraints, train_examples, library) -> Extraction(accepted, constraint_rejected)`; accepted ranked `(cost, program.size(), str(program))` — vacuous today (≤1 accepted). (`search/extraction.py`)
- `SearchStats(engine, considered, accepted, outcomes, by_primitive, solved_at_generation)` + `.solved` property. (`search/search_result.py`)
- `SearchTracker._generations: list[GenerationTracker]` (already populated). (`search/tracking.py`)
- `make_abstraction(name, template, library) -> Primitive`; `Library.extended(*, name, extra) -> Library` (kw-only, version+1); `Primitive{name, param_types, return_type, impl, variadic_param, template, body_sampler}` (`is_variadic` a property). (`substrate/abstraction.py`, `substrate/library.py`)
- `AbstractionProposer.propose(programs, library) -> list[Program]`; `GreedyMDL.select(corpus, library, proposer, metric) -> Program | None` (single `propose` call at selection.py:64-68); `GreedyMDLLearnEngine.run(library, solutions) -> LearnOutcome`; `LearnOutcome{library, added, rewritten, description_length}`. (`learn/`)
- `make_task(task_id, *, label, split, solution, train_inputs, test_inputs)`, `write_testbed(name, tasks, out_root, note)`, `GENERATORS`. `load_testbed(name) -> Corpus`, `Corpus{name, entries}`, `split_by_meta`. `TaskMeta{provenance, split, label}`. (`taskgen/`, `core/dataset.py`, `core/annotation.py`)
- CLI: register in `cli/main.py` via `app.command(name="run-ladder")(run_ladder.run_ladder_command)`; thin-wrapper pattern per `cli/run_study.py`.
- `run_search_learn(config, train_corpus, eval_corpus=None, ...) -> LearnActivityResult{learn, train_usefulness, transfer}`. (`execution/run_search_learn.py`)

---

## Run structure per ladder (k bridging rungs)

- **1 LEARN run** — the climb (`run_search_learn` on `reference_config` + `train_corpus`); its iteration-0 wake row = the **L_0 column** (read from the trace, not a separate run).
- **k oracle SEARCH runs** — `L_1..L_k` (each `= L_{i-1}.extended(make_abstraction(r_i.template, L_{i-1}))`), over the full `train_corpus`, at the reference wake budget. `L_1..L_{k-1}` measure bridging jumps 2..k; `L_k` measures the top jump. Each column also yields censored baselines (higher rungs) + vocabulary tax (lower rungs).
- **1 off-chain SEARCH run** — Floor + `{r_k}` only (r_k gifted onto the floor via `unfold_program` to floor form): does the top need the whole chain or only the top bridging rung?
- **Arms are positional in v1** (derived from `LadderResult` structure; amend the doc §3.5 accordingly — no first-class arm field yet).

---

## Folder structure

```
program_search/
  substrate/
    abstraction.py        EDIT  + unfold_program, substitute_params
    program.py            EDIT  DELETE Program.depth() + its docstring mention
  analysis/
    depth.py              NEW   compositional_depth(program, *, lam_as_leaf=True)
    behavioral.py         NEW   _matches_target & helpers, LIFTED from run_study.py (refactor)
  search/
    tracking.py           EDIT  solution sink (record; keep-cheapest-K + running first index); per-gen funnel already present
    search_engine.py      EDIT  thread target into _RunState; fire sink in _absorb_one; sink-based return (Commit 3/4); surface generations
    search_result.py      EDIT  SearchStats += generations, solutions(sink), first/cheapest indices; .solved sink-based (Commit 3)
    (extraction.py)       —     unchanged (partition stays pool-based)
  learn/
    learn_engine.py       EDIT  LearnOutcome += proposal_count, antiunify_pair_count
    engines.py            EDIT  thread SleepCounters through run
    selection.py          EDIT  thread SleepCounters through select
    antiunify.py          EDIT  increment at the combinations() loops
    telemetry.py          NEW?  SleepCounters (or co-locate in learn_engine.py) — lives in learn/, not search/
  execution/
    execute.py            EDIT  _search_stats serializes generations + sink; sleep row carries SleepCounters; TraceSpec sink cap
    model/trace_spec.py   EDIT  + solution-sink cap field
  ladders/                NEW PACKAGE
    __init__.py
    spec.py               NEW   LadderSpec, Rung, TopRung, Demonstration, DemonstrationKind
    shape.py              NEW   LadderShape, RungShape, LintFinding
    run.py                NEW   run_ladder, LadderResult
    certificate.py        NEW   certify, LadderCertificate
    report.py             NEW   create_ladder_report
    registry/             NEW SUBPACKAGE
      __init__.py         NEW   aggregates LADDERS + make_ladder
      <ladder-1>.py       NEW   ladder #1 (and/or family) builder
  taskgen/
    generators.py         EDIT  ladder #1 rung-tagged generators (+ committed testbeds/<ladder-1>/)
  cli/
    ladder.py             NEW   run-ladder command
    main.py               EDIT  register run-ladder
  run_study.py            EDIT  import lifted behavioral checker
docs/abstraction_ladders/
  ABSTRACTION-LADDERS-2026-07-16.md   EDIT  top-rung framing, sink/eviction, arms positional, canonical templates
  ladders/<name>/         artifacts (render() output, notes) — already started
tests/program_search/{substrate,analysis,search,ladders}/   NEW test modules
```

---

## Execution process (two blocks; the risky changes isolated per commit)

**Block 1 — engine/substrate layer (settle the locks here, before any ladder code):**

- **Commit 1** — substrate atoms: `unfold_program`, `substitute_params`, `compositional_depth`; delete `Program.depth()`. Tests use **purpose-built small fixtures** (rot180/recolor_flipped from studies.py: `d_1=2`, `d_2=2`, inlined double-jump `=3`), its _convention_ not the 4093f84a numbers; explicit `expand=None` vs `expand={r_i}` test. Lock-safe.
- **Commit 2** — additive telemetry: sink RECORDING (dormant), per-generation funnel serialization, sleep counters, index surfacing, `TraceSpec` sink cap. `.solved`/`ranked_programs` stay pool-based → provably zero-behavior; locks untouched.
- **Commit 3** — eviction-loss fix: return sink-_cheapest_ only (≤1). `make check`; diff mint identity + solve sets; explain/queue any lock movement (eviction-loss only).
- **Commit 4** — `attempts_per_test` wakeup: `ranked_programs` = full cheapest ranking; predict sees up to `attempts_per_test`. `make check`; separate lock analysis (test-score flips on multi-solution tasks).
- **→ checkpoint:** engine green, locks settled + explained.

**Block 2 — ladder layer:**

- **Design ladder #1 on paper first** (throwaway scratch using Commit-1 tools to verify the sandwich numerically) — CHECKPOINT with the user (Floor + rungs + top tasks + computed depth table) before building machinery.
- **Commit 5** — data model + linter + taskgen (Stage 3): `ladders/spec.py`, `shape.py`, taskgen generators + committed testbed; lint passes on the design.
- **Commit 6** — execution + read-side + CLI (Stage 4): `analysis/behavioral.py` (refactor), `ladders/run.py|certificate.py|report.py|registry/`, `cli/ladder.py` + `main.py`; run ladder #1 end-to-end; `EXPERIMENTS.md` entry + `experiments/<date>-abstraction-ladder-1/` notebook.
- **→ checkpoint:** first ladder result reviewed.

Principles: smallest reviewable commits, each risky change surgically alone; `make check` green between every commit; verify by driving the real CLI (repo DoD #3); done in the main loop sequentially (a lock-gated stateful build is a poor fit for parallel agents — delegate at most a well-scoped island like one test file); user checkpoints at ladder-#1 design, the first end-to-end run, and any lock movement in Commits 3/4.

---

## Verification

- **Per commit:** `make test` (fast tier) during; `make check` (ruff + mypy --strict + full pytest incl. slow locks) as the gate before moving on.
- **Commit 1:** `uv run pytest tests/program_search/substrate/test_unfold.py tests/program_search/analysis/test_depth.py` — `compositional_depth`/`unfold_program` reproduce hand-computed depths of the small fixtures; `expand=None` reaches floor, `expand={r_i}` keeps `r_{i-1}` folded.
- **Commits 3 & 4 gate:** `make check`; **diff learned-library/mint identity on the study locks, not just solve sets**; drive live — `uv run arc-lab search synth --corpus arc1-train` + `uv run arc-lab analyze-run <id>` to confirm per-generation funnel + sink fields appear in `results.json` and that any solve/mint change is the expected eviction-loss (Commit 3) or multi-attempt (Commit 4) cause.
- **Commit 5:** `uv run arc-lab taskgen <ladder-1>` regenerates the committed testbed byte-identically; `LadderSpec.lint()` returns `ok=True` with the intended depths/window; `print(spec.render())` matches the hand-authored table.
- **Commit 6 end-to-end:** `uv run arc-lab run-ladder <ladder-1> --out report.json`; confirm (a) oracle chain solves rung-`i` under `L_{i-1}` and zero rung-`(i+1)` (certificate `admitted=True`), (b) the LEARN run mints the bridging rungs (rung-recovery: exact/behavioral), (c) amortization computed in both accountings, (d) the L_0 column reads from the iter-0 wake. `make check` green.
- **Definition of done (repo contract):** `make check` green; regression locks preserved or deliberately + documentedly updated (with `EXPERIMENTS.md` note + `EXPERIMENT_QUEUE.md` re-runs); runtime behavior actually driven via the CLI.
