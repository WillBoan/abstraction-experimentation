# Ladder-set experiment plan (2026-07-24)

The execution plan for building and running the experiment set of abstraction ladders. A dated plan; it extends the program of record ([AL-PLAN-2026-07-23.md](AL-PLAN-2026-07-23.md), whose "chosen direction" — the cfb2ce5a variant program — this generalizes into the full set). **Phase 0/1 execution is narrowed to a minimum viable set by [MVE-PLAN-2026-07-25.md](MVE-PLAN-2026-07-25.md)** (after the 2026-07-25 ground-truth audit); this file's goals, measurements, and Phase 2+ gates stand. Structure and vocabulary: [LADDER-SET-DESIGN-2026-07-24.md](../../abstraction_ladders/LADDER-SET-DESIGN-2026-07-24.md). Cost-model constraints and design disciplines: [BREADTH-AXIS-2026-07-24.md](../../abstraction_ladders/BREADTH-AXIS-2026-07-24.md). Comparison licenses: [LADDER-RELATIONSHIPS-2026-07-23.md](../../abstraction_ladders/LADDER-RELATIONSHIPS-2026-07-23.md).

## Goals

Get to a solid base experiment set — **~10-30 certified ladders, 3-5 ARC tasks, a few cohorts — and run it**, measuring:

1. **Certificate / collapse rates on real tasks** — the first-order Family-B question (does cheap perception erase real-task gaps, or do real ladders certify?). Either outcome is a headline.
2. **Granularity** — cost vs cut density within sub-cohorts (same skeleton, varying cuts; budget windows co-vary by necessity and that coupling IS the question).
3. **Decomposition strategy** — sibling sub-cohorts (different skeleton or parameterization = choice-binding placement) within one cohort.
4. **Floor power** — ablations across cohorts of one task (raw-delta = what the floor was worth), including bundle _type_ (high-level / lowered / HOF / conditional floors of the same task).

Non-goals for this plan: breadth-cashing machinery (weighting, normal-form pruning), neural guidance, type invention — Phase 2+/3 candidates recorded in BREADTH-AXIS; scale-by-generation beyond the propose-check loop.

## Strategy

- **Start simpler and tractable; expand only if the simple set runs well** (Phase 1 -> Phase 2).
- **Cohort economics shape the set**: raw cancels within a cohort, so skips/sub-cohorts are cheap; every cohort is a new raw arm, so cohorts and tasks are the paid dimensions. Few tasks, 1-2 cohorts each, 1-2 sub-cohorts per cohort, members populated by skips.
- **Spine-as-generator**: author one finest ladder (spine) per sub-cohort + cut-sets; derive coarser members; demos via the propose-check loop (Claude proposes; S-B law + `free-params-covary` + discriminating grids + `probe-ladder` check, seconds per iteration).
- **Everything gated before it runs**: `lint-ladder` -> `probe-ladder` -> `diff-ladder` (membership/equivalence) -> `taskgen` commit -> `run-ladder` + raw arm. EXPERIMENT_LOG.md entry per batch; a cohort is a report, not a folder.

### Design disciplines (from the 2026-07-24 findings; binding for Phase 1)

- `constant_sources` stays **off** wherever a perceiver route exists — Phase-1 cohorts are clean _depth_ experiments (BREADTH-AXIS: the machinery cannot cash breadth savings; don't mix axes unwittingly).
- **No specialization-prelude arm** (struck: knowably measures ~zero under current machinery).
- Depth-1 rungs are not rungs (aliases/specializations; LADDER-SET-DESIGN §spines) — spines are all-d2 chains; granularity = nodes-per-rung.
- Parameterization is declared per sub-cohort and documented as the bind-early/bind-late choice it is; merged rungs' induced freezing is expected and probed, not a surprise.
- Budgets are derived from each member's validity window (default: the window minimum).

## Phases

### Phase 0 — prerequisites (in flight)

- Addressing tier landed; **all 6 cfb2ce5a percepts decompose over it** (EXPERIMENTS 2026-07-24; two are task-domain-equal rather than exact — the defensive-partiality flavor, safe for v5).
- **Next concrete step (already queued): probe ONE percept rung** — the source square, `crop_rect(g, head(filled_squares(g, 0)))`, d3 — off the addressing floor before authoring the full v5. `write_relative_tile`'s d8 decomposition warns some percept jumps may be too tall to certify in one leap; that is the granularity question arriving early, and the probe prices it in seconds. This is also the tier's first search-cost validation (correctness is proven; cost is not).

### Phase 1 — the simple, tractable set

1. **cfb2ce5a as anchor task.**
   - Cohort A (existing high floor): v1/v3 as two sub-cohorts (same term, different parameterization — bind-early vs bind-late); populate each with 1-2 skip members.
   - Cohort B (lowered/addressing floor): v5 — spine from the percept decompositions, cut-sets chosen off the probe results (the d8 warning), members derived.
2. **Add 2-4 more tasks** via the selection procedure (LADDER-SET-DESIGN §choosing-tasks): shortlist easy-to-medium; screen for raw-intractability of the top from 1-2 candidate floors (cheap probe; discard tasks that are too easy to host any ladder); pick for difficulty spread and hostability without overindexing. Per task: 1(-2) cohorts, one sub-cohort with a spine + 2-4 members.
3. **Run the grid**: certificate + climb + raw arm per member; schedules per the 2026-07-23 findings (curriculum = marginal exactly; skip-solved as the honest cheap mode, watching the frozen-param junk cases). Raw-arm K per TODO item 6 (⚑ steer, default K=10).
4. **Analyses**: the four goal measurements above; plus the loop-overhead and recovery accounting the al1-al20 batch established, now on real tasks.

**Exit criteria:** >=10 certified ladders across >=3 tasks; granularity curves for >=2 sub-cohorts; at least one full cohort-ablation (two floors of one task); a written report. If certification _fails_ broadly (Family-B confirmed on real tasks), that is a Phase-1 result, not a Phase-1 failure — it redirects Phase 2 toward laddering perception itself.

### Phase 2 — complex capabilities + the breadth axis (gated on Phase 1 running)

Entry gate, in order:

1. **Bidirectional literal typing** — do properly _before_ the first HOF ladder (~half a day; the `abs()` crutch corrupts d_i and produces spurious COLLAPSED probe verdicts on exactly the riskiest ladders).
2. **List constructor decision** (⚑ steer) — variadic is inexpressible (fixed `param_types`); `nil` has an unpinned type var under `reject` and nullary primitives are untested. Lean: fixed-arity `list2`/`list3`.
3. **HOF cohort** on cfb2ce5a (the v4 line — a third cohort of a known task, baselines already run): per-ladder `search_engine.function_hole_fill_mode='lambda-synthesis'` override (decided: default stays `'none'`), own `(depth, pool)` budget, probe-gated (battery E prices `fold @ lambda-synthesis` at ~250x; point-free ~1.3x).
4. **Conditional cohort** on a task whose condition genuinely varies (`if-condition-varies`).
5. **Expensive producers** (`squares`, O(n^3)) — admitted only with a probe-measured cost budget.
6. **Breadth items** (BREADTH-AXIS §approaches): the static breadth-sandwich lint leg (cheap, reuses `considered_limit`); optionally the abstraction-normal-form pruning experiment (the arc-lab-native cashing mechanism). The specialization-prelude arm returns **only if** a cashing mechanism exists.

### Phase 3 / horizon (recorded, not planned)

Weighted/probabilistic enumeration -> neural-guided search; type invention as a learnable artifact (pruning objective currently unscoreable); full generate-and-certify automation.

## Risks / open questions

- **Demo authorship cost is unquantified** — the propose-check loop is the one non-mechanical step; measure it on the first generated sub-cohort before assuming the set scales.
- **The addressing tier's search cost is unvalidated** until the Phase-0 probe (correctness != cost; quadratic Coord/Offset constant leaves are a known hazard if a ladder opts into constants).
- **Tall percept jumps** (the d8 warning) may force more granular percept spines than expected — which is informative, but changes v5's shape.
- **Spine alignment judgment** (2+3 vs 3+2 maximal cut-sets) is localized but real; document the choice per sub-cohort.
- ⚑ steer pending: raw-arm K policy; list-constructor shape.

## Instruments (pointers, not duplicates)

`lint-ladder` (incl. `--draft` structural tier) · `probe-ladder` (joint-budget, per-rung, seconds) · `diff-ladder` (static/observational equivalence; membership checks) · `run-ladder` / `run-study` · the checks register ([LINT-CHECKS.md](../../abstraction_ladders/LINT-CHECKS.md)) · EXPERIMENT_LOG.md discipline for every batch.
