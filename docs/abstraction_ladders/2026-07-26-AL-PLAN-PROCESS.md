# Ladder process overhaul: machinery + a process doc (2026-07-26)

**STATUS: complete, 2026-07-26.** All three waves landed (`make check` green at 949 tests, from a 921 baseline, no regression lock moved). Three verification items were struck as mis-scoped rather than met — they asked for `dae9d2b5-halves-union`'s certificate, which is LADDER work; see Verification below. Next: the MVE build ([MVE-PLAN-2026-07-25.md](MVE-PLAN-2026-07-25.md)), and the dae9d2b5 ladders (`dae9d2b5-3-recolor-rungs`, and a d2-throughout variant needing a `split_h: (Grid) -> List[Grid]` producer) as a separate thread.

A dated plan for closing the process and machinery gaps that the first real-ARC ladder exposed. It does not supersede the experimental program — [MVE-PLAN-2026-07-25.md](MVE-PLAN-2026-07-25.md) remains the active execution plan for the experiment set, and this is the prerequisite work that unblocks it. Concepts it leans on: [CERTIFICATE-PROFILE-2026-07-24.md](CERTIFICATE-PROFILE-2026-07-24.md) (per-rung verdicts, the double-jump as a (rung, consumer) property), [BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md) (the two cost axes), [LADDER-FORMAT.md](LADDER-FORMAT.md) (the chosen/derived split), [LADDER-SET-DESIGN-2026-07-24.md](LADDER-SET-DESIGN-2026-07-24.md).

## Context

Authoring the first real-ARC ladder (`dae9d2b5-halves-union`, 2026-07-25/26) cost far more than it should have, and the post-mortem found the causes were mostly **process and machinery gaps, not hard problems**:

- **A 5.3-million-fold cost surprise went undiagnosed for hours.** Rung 1 costs 21,149,854 considered on the full floor and **4** optimally pruned. `by_primitive` attributes it to `map_color` / `overlay` / `__const__` — primitives and constants the rung never uses. That data was available from the start; nothing surfaced it, so mechanisms were asserted instead of measured.
- **Four sites carried a chain-adjacency assumption** (`rungs[level +/- 1]`), fixed reactively one at a time as each bit. **Two remain live in `certificate.py` and would spuriously fail the next `run-ladder`.**
- **The probe was used to prove a negative**, which its own design record says it cannot do ("the probe convicts, only the certificate acquits", EXPERIMENTS 2026-07-22). That contract is absent from CLAUDE.md and AL-PLAN, whose "~1s/rung" claims silently assume the default guard. Result: six escalating guard runs, >1h wasted.
- **Five ladder variants were overwritten through one filename**, against the repo's own discipline (LADDERS.md: a rejected ladder's file persists as the finding). Two had to be reconstructed rather than recovered.
- **The skip-free gate deformed the ladder design.** Natural rungs (`recolored_west` / `recolored_east`) were folded into the top purely to pass a gate that CERTIFICATE-PROFILE-2026-07-24 already says should be a verdict profile, not a gate.

Intended outcome: machinery that makes these failures impossible or immediately visible, plus a short process doc covering only what machinery cannot enforce.

**Guiding principle: prefer machinery over process.** A check that fires beats a rule to remember, and cannot rot. Keep the doc small to avoid the over-specify -> fail -> re-spec cycle.

## Execution: three waves

Each wave is independently valuable and independently verifiable; stop and reassess between them.

| Wave | Contents | Verified by |
| --- | --- | --- |
| **1** | A1 DAG sweep · A2 per-rung budgets | `run-ladder dae9d2b5-halves-union` reaches a certificate with non-zero rung-2 health; the degenerate `[4,2]` window becomes valid per-rung |
| **2** | A3 probe overhaul · A4 breadth census | Two probe cells/rung at the fixed guard in seconds, recorded, with the ~10^6 pruned/full ratio visible |
| **3** | A5 Compromise Options · A6 overwrite guard · A7 lint output · the process doc | `make check` green; doc cross-links resolve |

## Part A — Machinery

### A1. DAG sweep — finish it (do first; live bug)

`src/arc_lab/program_search/ladders/certificate.py` has two level-adjacent sites:

- `certify` (~line 76): `next_ids = spec.rungs[i].demonstrations if i < k else top.task_ids` — the skip check reads the next rung **by level**. On a DAG that is a sibling, not a consumer.
- `_demonstration_health` (~line 104): `below_name = spec.rungs[level - 2].name` — "routes through the rung below" by level. On `dae9d2b5-halves-union`, rung 2 (`east`) never calls rung 1 (`west`), so health scores **0.0** and a correct ladder is rejected.

Both should read the consumer graph, reusing what exists: `CheckContext.consumer_targets` / `graph.consumer_programs` (`ladders/graph.py`). `_demonstration_health` should check the rung's **actual dependencies** (the rungs its template calls), not `rungs[level-2]`.

Then sweep every remaining `rungs[<index arithmetic>]` across `ladders/` and convert or justify each in a comment. Add `dae9d2b5-halves-union` to the batch fixtures so a chain-only assumption can never regress silently — it is the first DAG ladder in the registry.

### A2. Per-rung budgets (TODO item 29; gate has fired)

Replace the single global `depth_limit` with a per-rung schedule. **Everything needed is already derived** — `RungShape.jump_needs` (demo-sourced since `9bebedf`) and `double_jump_needs` (`ladders/shape.py`).

- **Derivation:** `L_j = rung_shapes[j].jump_needs` (level `j` serves rung `j+1`); `L_k` uses `min_depth_limit` of the top's reference solutions. Derived, not declared, so run identity stays deterministic from the `.ladder` file.
- **Regime, settled 2026-07-26.** The schedule is **purely derived and derived is the default**, with an explicit `ladder.depth_schedule: 'pinned'` opt-out (LADDER-FORMAT CFG-7). Treating the pinned value as a cap (`min`) or a floor (`max`) was tried and rejected: `max` preserves the batch byte-for-byte but fails on exactly the ladders this is for, which need levels **lowered**; `min` gives the same thing by a different route. One ladder opts out — `al10-skippable`, whose content IS the over-generous uniform budget. **Consequence to accept:** `jump-affordable` and `top-affordable-with-ladder` are satisfied by construction under `derived` (the budget is derived from the need they test), so they report rather than gate, and `double-jump-intractable` carries the sandwich.
- **Chain wiring** (`ladders/run.py:109-115`): the run at level `j` uses the budget of **rung `j+1`** (level `k` uses the top's). This makes every read land at the right budget: rung `c`'s own tractability and skip-of-anything-`c`-consumes are both read at level `c-1`, which carries `L_c`.
- **Touches:** `ladders/run.py` (chain loop), `ladders/spec.py` (schedule accessor), the depth checks (`checks/depth.py` — window becomes per-rung), `ladders/probe.py`.

**This subsumes the skip-freeness question.** Under per-rung budgets, skip-freeness is automatic for every `d >= 2` rung on its consumer's critical path: needing `d_c + d_r - 1 + k > d_c + k` reduces to `d_r >= 2`, exactly what `proper-composition` enforces (the wrapper depth `k` cancels). So **do not relax skip-freeness further** — leave it advisory in lint, gate in the certificate. Relaxation raises `L`, and cost is exponential in `L`.

Payoff: the natural 4-rung `dae9d2b5` becomes valid _and cheaper_ than the shipped 2-rung version.

### A3. Probe overhaul

`ladders/probe.py` + `cli/probe_ladder.py`:

- **Fixed 50k guard.** The guard is not a knob. Remove or rename `--considered-limit` so escalation is not the obvious move; if retained, it must warn that a raised guard cannot produce an acquittal.
- **Pruned-then-full, two cells per rung.** Cell 1: library filtered to the primitives the rung's unfolded demo target references, plus constant pruning. Cell 2: `L_{i-1}` as the climb will actually have it, under the ladder's declared constant policy. Diagnostic split: _cell 1 censors_ -> the rung's own search cost is too high (redesign the rung); _cell 1 clean, cell 2 censors_ -> the floor is too broad; _both clean_ -> proceed, and `full/pruned` is the floor-tax ratio worth recording.
- **Constant pruning needs a real seam** — an explicit value allowlist threaded into the search config, not a monkeypatch of `policy_constants` (`search/leaves.py:89`). Pin the definition as **value-level** allowlisting (see A4).
  - **Built 2026-07-26** as `BottomUpSearchEngine.constant_allowlist`. The stated blocker (a new engine field moves every `run_id`, since `to_data` emits all fields) was resolved rather than paid: `to_data` honours a `SERDE_OMIT_WHEN_NONE` marker, so an unset allowlist serialises to nothing and **all 446 recorded runs keep their ids** (verified, 0 mismatches). Both prunings are needed and neither subsumes the other — on al14's `move_cell_up`, library pruning changes round-1 width not at all (300 -> 300) while value pruning takes it to 12, so a library-only cell would have reported `ratio 1.0x, clean` on a rung whose battery is the whole cost.
- **Surface `by_primitive`** — top contributors with shares, in probe output and the ladder report. This is the single change that most directly prevents the 2026-07-25 mis-diagnosis.
- **Honest INCONCLUSIVE message** — state it is a non-result by design and that `run-ladder` is the authority, replacing wording that reads as a defect to fix.
- **Record via the run machinery** (decided: full integration, not a fallback). Route probe cells through `execute()` so they are cached, crash-safe and recorded like any run — which also closes the seam risk of two code paths driving the same engine (`probe.py::_search` currently calls `config.search_engine.run(...)` directly, while the climb goes through `execute()`; their agreement was validated once in 2026-07-22 and never since).
  - **The prerequisite:** probe cells search over synthesized position-separating grids (three deterministic layouts per corpus shape, added for the al14 collision separation) which are not a registered corpus. `RunSpec = Config x Corpus` needs content-hashed `Corpus` identity for them. They are deterministic and RNG-free, so hashing is straightforward — but this is the bulk of A3's work and should be built first.
  - **Curatorial guard:** probe cells are design-time scratch (dozens per authoring iteration, most on ladders that never ship). Namespace or tag them so `arc-lab runs` stays a usable ledger of experiment results rather than filling with probe noise.

### A4. Floor-breadth census in lint

New read-side analysis, surfaced per rung. **Exact, not estimated**, for the two tiers that are computable:

- **Constant battery, per type** — `policy_constants` is a pure function of `(grids, constant_sources, library)` and `_type_in_use` decides which types mint. Report e.g. `COLOR: 10 minted (map_color, overlay use Color) — this rung uses 0`.
- **Round-1 composition counts** — the typed leaf census, the one predictive fact AL-PLAN-2026-07-23 kept after retiring the estimator (24/24 cells exact).

Four pruning corners for round-1 counts (none / primitive / constant / both); **the battery has only 3 distinct values** — constant pruning is a value allowlist determined by the rung's program, so primitive pruning cannot shrink it further (any `Const(v,T)` in the program is an argument to a primitive that survives pruning, so `T` stays in use). Derive and present: `irreducible = both-pruned`, `primitive tax = full - prim-pruned`, `constant tax = full - const-pruned`, `joint = full - both-pruned`, noting `joint != primitive + constant` because the marginals overlap.

**Label it an indicator, never a prediction.** Round-1 is exact but **understates badly** — the tax compounds with depth (the round-1 ratio is far below the measured 5.3M x at depth 3). Its value is ranking and relative comparison.

### A5. Compromise Options registry

A named, uniform concept for "reduces cost, costs data". Each entry states: **what it saves · what it forfeits · when justified**. Initial entries:

| Option | Saves | Forfeits |
| --- | --- | --- |
| `solution_limit=1` on a real run | large, when solutions are found below `depth_limit` | `cheapest_solution_index`, cost-to-exhaust, full `by_primitive`. RQ1 survives — `first_solution_index` is exact either way |
| Optimally-pruned real run | makes an otherwise unrunnable ladder runnable | **all cost interpretation (RQ1 void)**; preserves learnability (recovery / junk / cascade) |
| `wake_schedule: skip-solved` / `curriculum` | existing | existing (already arm-labelled) |

**Results produced under any option must be labelled at every level they appear** — following the existing `wake_schedule` precedent, which labels every wake trace row and banners the report.

Default for real runs stays `solution_limit=None`: `SearchStats` already records `first_solution_index`, `cheapest_solution_index` and `considered`, so one exhaustive run yields three cost quantities. **No machinery change is needed for the RQ1 asymmetry — it was a matter of reading the right column.**

### A6. Generator overwrite guard

**Premise corrected 2026-07-26:** nothing in the repo writes `.ladder` files — `taskgen` READS one to build a testbed, and the five destroyed variants came from throwaway scratch scripts. So the guard could not be added to an existing generator; it is a supported PATH instead: `arc-lab new-ladder <name> [--from <existing>] [--registry] [--force]`, which refuses to overwrite and makes the next variant (copy + rename the header, original untouched) cheaper than reusing a name. It cannot stop a scratch script — nothing can — but there is now a path that cannot lose work.

A generator must **refuse to overwrite an existing `.ladder` unless explicitly forced**. A git-tracked-only guard would not have helped: none of the five destroyed variants was ever committed. Refusing outright forces a new name per iteration (preserving each variant), while `--force` keeps typo-fixing cheap.

### A7. Lint output

- **Depth (default table):** `jump_depth` · `jump_needs` · `template_depth` · `double_jump`. Every affordability claim is stated in `needs`, so that is primary; `template_needs` and `double_jump_depth` matter only for higher-order templates -> put the full six in the generated `spec.md`, where width is free.
- **Breadth (default table):** `b1` (full) · `b1_min` (both-pruned) · ratio. The four-corner decomposition and per-type battery go to `spec.md`/verbose.
- **Do not write measured costs into `.ladder` files.** LADDER-FORMAT §1 keeps chosen/derived separate; a stale cost comment is worse than none. Instead have `lint-ladder`/`probe-ladder` **print recorded numbers alongside the rung table**, read from the artifact — co-location without a second source of truth. **Exception:** a retired dead-end draft carries its verdict in its header, since the verdict is the reason the file exists (as the three recovered drafts already do). **First cleanup under this rule:** `registry/dae9d2b5-halves-union.ladder`'s header still asserts the refuted mechanism ("dominated by `overlay`'s quadratic grid product" — corrected by the 2026-07-26 optimal-pruning entry to floor breadth the rung never uses) and pins the 30M guard rationale; trim both when A2/A3 land.

## Part B — The process doc

New: `docs/abstraction_ladders/LADDER-PROCESS-2026-07-26.md`. Deliberately short — machinery does the enforcing. Sections:

1. **Instrument contracts** — what each instrument can and cannot prove. The probe convicts; only the certificate acquits; an INCONCLUSIVE probe is expected and is **not** a signal to raise the guard. Pruning is a bound, never a measurement. The breadth census is an indicator, never a prediction.
2. **The ladder development loop** — task selection -> spine design -> floor design -> demo plan -> lint -> probe -> taskgen -> run -> analyse, with a **decision table mapping each failure mode to its response** (the thing improvised throughout 2026-07-25). Two ordering principles the loop must state explicitly (settled in the 2026-07-26 discussion session):
   - **Design order: competences -> floor -> demos.** Name the rungs as competences off the verified solution term's natural cut-sets first; then choose the smallest floor that makes each cut d2-3 with perceived geometry; author demos last. The 2026-07-25 breadth walls all trace to the reverse order — floors inherited from authoring convenience, rungs then bent to fit.
   - **Cheapest-instrument ordering.** Every question has a cheapest instrument that can settle it; exhaust cheaper instruments before escalating: hand algebra -> lint (~1s) -> pruned probe cell (seconds) -> full probe cell -> `run-ladder`. The session's own contrast: `dae9d2b5-3-recolor-rungs` was killed by one lint with no probe, while the `map_color`/`overlay` skip path cost a 25-minute probe that hand algebra could have found. The instrument-contract section (1) says what each instrument proves; this says which to reach for first.
3. **Tractability triage** — read the run results (`by_primitive`, `first_solution_index`, `generations`, retained programs) -> ablate to the absolute minimum -> **ask the human**. With explicit triggers for the third step.
4. **Design taste** — heuristics, explicitly not rules: a rung should be a _nameable competence_; **never collapse a natural rung to satisfy a gate**; anticipate the constant battery when choosing floor primitives (perceived-over-computed geometry as one instance); watch for algebraic laws that make a rung redundant; depth-1 is not a rung. Additions from the 2026-07-26 discussion session:
   - **The algebraic skip-audit is a design step, not a background worry:** before any probe, actively try to prove each rung skippable by hand — is there a law letting consumers reroute around it (`map_color` over `overlay`)? does a sibling at the same depth from the floor exist (`4347f46a-1`'s four shift rungs, skippable by construction)? Both 2026-07-25 skip findings were hand-derivable.
   - **When a gate and a natural design disagree, the prior is that the gate measures the wrong thing** — an explicit ask-the-human trigger (section 3). The folded recolour rungs are the type case: the machinery was wrong, not the design, and A1/A2 make the natural form valid _and cheaper_.
   - **Declare withheld primitives per ladder.** A floor designed around a known solution manufactures raw-intractability — that is the method, not a flaw — but the declaration keeps every RQ1 bound readable as floor-relative rather than absolute.
5. **Compromise Options registry** (A5) + the labelling rule.
6. **Operational discipline** — never pipe long-running output through a buffering filter (`tail`/`head`/`sort` swallow until exit — hit three times in one session); write to a known file and read it; background long runs; **state an expected duration _before_ launching, computed from the cost you already know** — the estimate is a decision input, not a postscript, and a run whose cost you would not have approved is one you should not have started (2026-07-26: launched `dae9d2b5-halves-union`'s chain and only then read the run log to discover it was a 6-10 hour job, with the 21M-per-cell figure sitting in this document's own Context section); do not chain sleeps to poll.
   - Corollary, from the same case: **when a verification is expensive, ask whether a cheap permanent instrument buys the same evidence.** `al21-dag-siblings` certifies the DAG reading end-to-end in 0.26s inside `make check`, forever; the multi-hour real-task chain would have added only "and it also holds here", once.
7. **Artifacts & provenance** — one file per variant at creation; generators committed under `experiments/<date>-<topic>/artifacts/` with the `.ladder` authoritative and regeneration explicitly not the workflow; **when to create an experiments/ folder — read [experiments/README.md](../../experiments/README.md) first**.
8. **Verdict & metric glossary** — `as-intended` / `collision` / `collapsed` / `skippable` / `censored` / `inconclusive` / `recovered` / `junk` / `cascade`, currently scattered across four docs.
9. **Pointers** — link out at each relevant point rather than duplicating: LADDER-FORMAT, CERTIFICATE-PROFILE, BREADTH-AXIS, LADDER-SET-DESIGN, LADDER-SET-PLAN, MVE-PLAN, LINT-CHECKS, EXECUTION.md, ARCHITECTURE.md, experiments/README.md.

### Small doc updates alongside

- **CLAUDE.md** — correct the probe one-liner with the convict/acquit asymmetry; add the process doc to Sources of truth.
- **AL-PLAN-2026-07-23.md** — the pipeline line's "~1s/rung" needs the same caveat.
- **MVE-PLAN-2026-07-25.md** — rewrite the task-screen step per the corrected cost model (scope settled in the 2026-07-26 discussion session), and refresh the stale "no real-task ladder lints clean" table:
  - **Demote the engine screen from filter to candidate generator.** Solvability-under-a-budget is a property of the **(task, floor) pair** — "it was the floors, not the tasks" (2026-07-25) — so the unsolved remainder is not a verdict on anything; only the positive gen-2 hits are leads, and the family buckets (two-halves / region-recolor / denoise / symmetry-repair) are the durable output. The 28-task result is already stale (`halves_h`/`halves_v` and `finite-enumerate-scalars` landed after it); re-run only after wave 2, as a generator refresh, with the A4 census informing the screen floor.
  - **Ground-truth anchoring is the first hard gate:** the hand-authored solution term verified against all train + held-out tests and pinned as a test, before any floor/spine/demo work. It was the most solid validation of the whole 2026-07-25/26 arc, and everything downstream derives from the term.
  - **Leg 3 becomes static: per-rung depth window + the A4 breadth census** (both ~1s at lint time). Depth-only was the filter as written, but breadth was the variable that actually bit; the fixed-guard pruned/full probe is then confirmatory, not exploratory.
  - **Two selection criteria to add:** _demo-pool cheapness_ — rungs demonstrable with task-realizable full-solution Grid demos are the cheap case (demo authoring is the plan's own dominant cost centre); fragment-demoed rungs are a deliberate Cohort-B sample, never an accident — and _floor leverage_ — prefer families where one perceived-geometry producer unlocks several tasks (`panels` -> the six separator two-halves tasks).

## Verification

**Status 2026-07-26: the plan is complete.** `make check` green at **949** tests (baseline 921), no regression lock moved across all three waves.

1. ✅ `make check` green (ruff · mypy --strict · full pytest incl. slow locks).
2. ~~`run-ladder dae9d2b5-halves-union` must reach a certificate with non-zero rung-2 health~~ — **struck 2026-07-26: this is LADDER work, not process work.** The plan conflated "verify the machinery" with "finish the ladder that motivated it". The DAG reading is verified instead by [`al21-dag-siblings`](../../src/arc_lab/program_search/ladders/registry/al21-dag-siblings.ladder), a purpose-built cheap DAG that certifies end to end in **0.26s inside `make check`** — permanently, rather than once — and which the pre-fix code **rejects** (`no_skip_paths[1]=False`, `demonstration_health[2]=0.0`). `dae9d2b5-halves-union`'s own certificate is a multi-hour chain and belongs to the ladder thread.
3. ✅ `lint-ladder` on the four registry/draft ladders. `dae9d2b5-halves-union` clean; the breadth census flags `dae9d2b5-1-arith-halves`'s floor at **76-130x on all seven rungs** with `color: 10 minted / 0 used` throughout; `dae9d2b5-2-merge-rung` clean; `4347f46a-1-shift-rungs` fails `rewrite-shallow[interior]` with the witness printed. (The census works on drafts: it builds a corpus from the file's own inline tasks, so no committed testbed is needed.)
4. ✅ **Per-rung budgets:** `dae9d2b5-3-recolor-rungs` — the natural 4-rung form the global window rejected — lints **0 errors** at schedule `[3,3,2,2,2]`.
   - ~~re-lint `dae9d2b5-1-arith-halves`, whose global window is degenerate `[4,2]`; per-rung it should become valid~~ — **wrong, corrected 2026-07-26.** Three of that draft's rungs have `jump_needs == double_jump_needs` (a deep fragment wrapper inflates the rung's own cost to meet its consumer's inlined cost), and no budget schedule separates those. It is a retired draft, so nothing is lost.
5. ~~Two cells per rung on `dae9d2b5-halves-union` at the fixed guard, completing in seconds~~ — **struck: unachievable and mis-scoped.** That floor is ~21M considered per cell; "in seconds" was never possible there. Verified on `al21-dag-siblings` instead (cells record, re-probe is a cache hit, `by_primitive` and the pruned/full ratio print), plus `al14-cell-row-grid` for the value-pruning case.
6. ~~Probe/certificate agreement for `dae9d2b5-halves-union`~~ — **struck with item 2, and superseded by something stronger.** The seam is now closed structurally (a probe cell IS a recorded run through `execute()`), and pinned two ways in `tests/.../test_probe_seam.py`: a lossless field-by-field trace round trip, and one cell driven through both `probe_rung` and a real `execute()` run reporting the same funnel.
7. ✅ Regression locks unmoved. 14 of 22 ladders' run identity untouched; the 8 that moved did so deliberately (derived depth schedule). Adding `constant_allowlist` moved **no** `run_id` at all (446 verified, 0 mismatches).

## Out of scope (recorded, not planned)

- `map_color`-distributes-over-`overlay` as a `BASE_EQUATION` (TODO item 19) — conditional (breaks when the recolour target equals the overlay mask colour, and `overlay` takes the max non-mask value so recolouring can change which wins) and not depth-reducing in the abstract; needs `concat-interchange`-style behavioural confirmation.
- The unfold blowup on heavily-shared DAGs (`cfb2ce5a-5-lowered-full` does not terminate).
- The demo-pool selector; in-file floor definitions; a `panels` region producer; unit-shift primitives.
- Resuming the MVE build itself — this plan is the prerequisite, not the work.
