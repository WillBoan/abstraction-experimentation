# Abstraction Ladder Experiments — design (2026-07-16)

The design snapshot for the **Abstraction Ladder Experiments**: a batch of LEARN experiments measuring whether — and by how much — learned abstractions convert an intractable search into a sequence of tractable ones. This document is the merged output of the 2026-07-16 design sessions; it records the concept, the metrics, the ladder-construction methodology, the run structure, and the open decisions. It is a _design_ doc, not a log: runs land in [EXPERIMENTS.md](../EXPERIMENTS.md) with notebooks under [experiments/](../experiments/), and next-run sizing lands as [EXPERIMENT_QUEUE.md](../EXPERIMENT_QUEUE.md) rows when each run is specced.

Prior work this builds on directly: E11 (cheapest-wins trap, free-parameter corpus discipline), E12 (2-rung climb works end to end; first vocabulary-cost signal, ~4x), E13 (per-round growth b ≈ 17–24x; raw deep search is censored in practice, not just expensive). A `StudySpec` is the degenerate 1-rung ladder; E12's `layered-abstraction` was a 2-rung ladder. This direction is a **scaling instrument** for that phenomenon, not a new phenomenon.

An early hand-worked precursor (before the concept was fleshed out): [task_specific/4093f84a-EXPRESSIBILITY-2026-07-15.md](task_specific/4093f84a-EXPRESSIBILITY-2026-07-15.md) — its Total-vs-Jump-only depth distinction and "depth compounds by re-embedding" observation survive into this design; its rungs-as-quantities framing is superseded (see §2 scope note).

---

## 1. Concept and definitions

- **Ladder** — a Floor + an ordered sequence of intended abstractions (Rungs) + a corpus demonstrating them. Terminology: a ladder is _data_ (floor, rung templates, tasks, annotations); runs are made against it.
- **Floor** — the starting `Library`.
- **Rung i** — an intended abstraction, defined as a closed template over **L\_{i-1}** (see below). The **Top Rung** (rung R) is the abstraction whose task(s) anchor the ladder — the hardest competence in the corpus.
- **Bridging Rungs** — rungs 1..R-1. Each rung has ≥ 2 demonstrating tasks; the Top Rung has ≥ 1.
- **Library chain** — `L_0 = Floor`; `L_i = Floor ∪ {rung_1 .. rung_i}`. Every library-relative quantity states which flavor it uses:
  - **oracle** — `L_i` with the _intended_ rungs gifted;
  - **learned** — whatever sleep actually minted by wake-iteration i. These diverge exactly when learning is imperfect; the divergence is a primary observable, not noise.
- **Jump i** — the step from L\_{i-1} to rung i. Two distinct quantities, never conflated:
  - **design jump depth** `d_i` — compositional depth of rung i's template over L\_{i-1} (static, a lever);
  - **measured jump cost** `c_i` — considered count to solve rung-i tasks under L\_{i-1} (observable, an outcome).
- **A Ladder is defined relative to a wake budget.** The budget is constitutive, not a free parameter: every jump must fit inside it and the raw total must exceed it. Sweeping the budget past the raw total depth dissolves the ladder (everything solves at iteration 0).

**Scope (v1):** rungs are _mintable abstractions_ — subtrees promotable to library primitives by the existing proposers. Substrate-based laddering (e.g. `fold`'s parameter-passing shape achieving additive depth without any learning pass — the 4093f84a doc's Ladder 3) is a distinct mechanism producing the same cost profile; it is **out of scope for v1** and registered as a future named contrast arm (learning-based vs substrate-based laddering).

## 2. Core hypothesis

Abstraction learning turns a **product into a sum**:

> raw cost ≈ b^(d_raw) vs laddered cost ≈ Σ_i b^(d_i) + learning overhead + vocabulary tax

where `b` is the effective per-round growth factor (E13: ~17–24x for the floors measured). This is falsifiable and _numerically predictive before running_: `b` is measurable per (floor, params) cell, the `d_i` are static. Per-rung residuals (measured `c_i` ÷ predicted `b^(d_i)`) are the interesting object — vocabulary tax and pool-eviction effects live in the residuals.

Depth caveats baked into all uses of "depth": `max_depth` counts rounds _including_ round-0 leaves (the studies.py E1 off-by-one note); on floors with lambda synthesis the generation↔syntactic-depth correspondence breaks (`descend()`ed sub-searches), so solve generation = application depth only for `function_hole_fill_mode="none"` floors — state the convention per floor.

## 3. Research questions

**Q1 — Quantify the amortization: raw cost vs laddered cost.** Including: does the climb _scale with height_, or stall when the library gets fat (E12's ~4x tax, compounding)? Pre-run estimates live in **cost space** (`b^d` model, §2), never as sums/ratios of depths — a sum of jump depths is bookkeeping, not a depth, and depth ratios are log-scale quantities.

**Q2 — Quantify the effects of params and metaparams on the amortization.** Clean decomposition: **params move `b`** (the base), **metaparams move the `d_i` profile** (the exponents).

- Search params: `budget.max_depth` / `max_arity` / `max_pool`, `beam_width`, `constant_sources`, `function_hole_fill_mode`, `polymorphism_instantiation`, `unpinned_type_var_mode`, `function_sample_size`.
- Learn params (as consequential as the search params): proposer (`AntiunifyPairs` / `FrequentSubtree(min_frequency)` / `TypeScopedFrequentSubtree` / `StitchProposer`), governance (`GreedyMDL` + threshold), `LearnSpec.iterations`.
- Core metaparams: Floor identity, Top Rung identity, rung count, raw total depth, average/max jump depth.
- Corpus metaparams: programs per rung, tasks per rung, full-solution vs fragment-only demonstrations (NB: this metaparam is secretly a _proposer selector_ — §5.3), programs/tasks at the Top Rung, next-rung-tasks-only vs all-tasks corpus.
- Constraint: no full cross exists even in principle (budget is constitutive, §1) — reference config + one-factor sweeps, budget sweeps confined to the window where the ladder property holds.

**Q3 — Quantify the effect of what programs/fragments AF sees** (EVENTUAL; machinery-gated). Options, in build order: (a) 0–1 cheapest solution per task (today); (b) top-K solutions per task — smallest change, directly attacks the E11 cheapest-wins trap and relaxes corpus-engineering burden everywhere, sequence it first; (c) up to K non-solution Grid→Grid programs; (d) up to K non-solution non-Grid→Grid programs; (e) solution sub-programs from lambda synthesis. Known issues for (c)–(e): any cheapness-ranked selector floods with trivia (`Input()`, `flip_h(Input())` — the cheapest well-typed pool members _by construction_); the selection policy does all the work. Candidate policies: dumb filters (type, size floor, signature-dedup) + generosity, letting the proposer do recurrence detection; or **partial credit** (fraction of matching train-output cells, computed at extraction — seam-safe, selects near-misses; recommended first). The `SampleSpec` reservoirs observe candidates at absorption _including later-evicted ones_, so `max_pool` truncation does not bound what a selector can see. Governance warning: compression-driven learning over non-solutions makes "compresses well ≠ useful" likely (search residue is self-similar) — the fragment arms are expected to force the deferred usefulness-governance question (F4/F5).

The type of a rung determines which visibility option can capture it: Grid→Grid whole-solution rungs — learnable today; rungs embedded in solutions — `FrequentSubtree`/Stitch; non-Grid→Grid rungs never appearing inside retained solutions — only via (d)/(e), or via **probe tasks** that reify the quantity as a grid (works today; is explicit curriculum supervision — a weaker claim; keep both as contrast conditions).

## 4. Metrics

### 4.1 Organizing principle: atoms vs views

The primary measured object per ladder is the **cost matrix**: cost(task, library, budget) over the oracle-chain columns + the learned trajectory's iterations. Nearly every named metric is a slice or ratio of its cells. Discipline: **tier-0 atoms are recorded exhaustively at run time; every named metric is a read-side view** (`analyze_run` / report style) — a new metric never requires re-running.

Tier-0 atoms per (run × task), with instruments:

| Atom | Instrument | Status |
| --- | --- | --- |
| solved?, solve generation | `solved_at_generation` | landing (working tree, 2026-07-16) |
| per-generation funnel (composed/errored/pruned/deduped/entered_pool/displaced/evicted; pool sizes) | `GenerationTracker` | landing (working tree) |
| outcome partition, total + per-primitive | `SearchTracker.totals` / `by_primitive` | shipped |
| cost-to-first / cost-to-cheapest | `candidate_index` of earliest ACCEPTED / of `ranked[0]` | derivable; needs run-record exposure |
| accepted program + `primitive_keys` | extraction + tracker | shipped |
| sampled/captured programs (incl. evicted) | `SampleSpec` reservoirs / capture | shipped |
| per-iteration LEARN trace (library before/after, mints + MDL gain, solved-task set) | LEARN run record | partial — climb-trace report is the main gap |
| sleep cost | — | **gap** (§4.5) |

### 4.2 Static vs observed quantities

- **Compositional depth** — depth of a template over a stated library (static). Convention: `depth(f(x1..xn)) = 1 + max(depth(x_i))`, literals/params depth 0.
- **Program size** — node count. Distinct role from depth: generations are organized by _depth_ (predicts when found); extraction/dedup/MDL rank by _size_ (predicts what is retained and what sleep sees). The E11 trap lives entirely in the size ordering.
- **Solve generation** — the round where a solving program is first composed (observable). **Not merged with compositional depth**; their relation is a diagnostic:
  - equal — healthy;
  - observed < design — a shortcut program exists (skip path / E11–E13 trap class);
  - observed > design or unsolved — the intended program was reachable in principle but not built: eviction (`max_pool`), missing constant source, or type-gating — isolates the non-exhaustiveness mechanisms.
- **Considered count** — the cost currency. **Headline comparisons are in considered count (or explicit log-cost), never averaged depth ratios.**

### 4.3 Cost accounting (decided)

Track **all three**, no early stop:

- **cost-to-first-solution** — cumulative considered through the first ACCEPTED candidate (the cost of _solving_);
- **cost-to-cheapest-solution** — through `ranked[0]` (the cost of _the demonstration AF sees_; cheapest-wins retention). Genuinely different from first (a smaller-but-deeper program can arrive a later generation); the gap is a per-task E11-trap indicator, free on every run;
- **cost-paid-full** — full-budget cost (what end-to-end accounting needs; the engine has no early stop — ACCEPTED resolves at whole-run extraction).

Early stop (`stop_after_solutions`) is rejected for measurement: it changes run identity (locks), sharpens order-sensitivity, and destroys the first-vs-cheapest observable. It remains a candidate _policy experiment_ later. All costs reported per-task and aggregated per-rung as **sum** (per-task retained for variance).

### 4.4 Named views (search side)

- **Jump cost(i)** = cost(rung-i tasks | L\_{i-1}) — oracle and learned flavors.
- **Double-jump cost(i)** = cost(rung-(i+1) tasks | L\_{i-1}) — skipping rung i. By ladder validity this is _censored_ (unsolved at budget); record as a bound.
- **Marginal rung value(i)** = cost(rung-(i+1) tasks | L\_{i-1}) ÷ cost(rung-(i+1) tasks | L_i) — same tasks, libraries differing by one rung. The most decision-relevant per-rung number ("what did this rung buy"); reported as a lower bound when censored.
- **Vocabulary tax(i)** = cost inflation on _lower_-rung tasks under later libraries — read off oracle-chain columns (e.g. rung-1 tasks under L_3 vs L_1); no extra runs.
- **Budget compression** = d*raw vs max(d_i) — the reduction in *required search depth* to reach the top. The depth-flavored headline; **enablement** at a fixed budget (solve-set under L_i minus under L*{i-1}) is its binary shadow.
- **b_eff** per (library, budget) cell — fitted from per-generation composed counts. The parameter of the §2 model; watching b_eff grow with library size is the tax's mechanism made visible.
- Pool-pressure diagnostics — evicted counts, pool_size_before_truncation vs `max_pool`: required to interpret "unsolved" (censored vs evicted; E13's open eviction question).
- Cross-analysis by primitive category/provenance — free via `by_primitive` → the census rollups.

### 4.5 Named views (learn side)

- **Rung recovery table** (centerpiece): intended rung → minted at which iteration → grade: **exact** (byte-identical; E11 achieved this) / **behavioral** (study-report grading; shipped) / **specialized** (literal-bound — stalls the climb one level up, far from its cause) / **missed**.
- **False mints** — mints matching no intended rung: count, MDL gain, and whether _used_ downstream (`primitive_keys` over later solutions). A used false mint is an alternative ladder; an unused one is pure tax.
- **Climb trace** — per wake iteration: library size, newly-solved tasks by rung level, mint events, stall iteration (no new solves, no mints). The LEARN run's headline artifact.
- **Demonstration health** (E11-trap detector) — per rung: fraction of demonstrating tasks whose _retained cheapest_ solution structurally contains the rung template; early warning: the first-vs-cheapest cost gap.
- **Solution routing** — does the final Top-Rung solution route through the rungs (`primitive_keys`), and how many? A top task solved while bypassing rung 2 is a different finding than a clean climb.
- Compression accounting — MDL gain per mint, corpus description length per iteration.
- **Sleep cost** — **machinery gap**: no sleep-side analogue of `considered` exists. Decision pending (§9): proposal count + antiunify-pair count (deterministic units; pairs are O(n²) in solutions) as the unit, wall-clock as telemetry only. Must land before ladder #1's LEARN run or "worth it" silently assumes sleep is free — which stops being true under Q3's fragment options.

### 4.6 "Was it worth it" accounting

- **Laddered cost (marginal)** = Σ_i jump costs — the idealized sum (theoretical bound).
- **Laddered cost (end-to-end)** = total considered across **all** wake iterations × **all** tasks (including full-budget failures on not-yet-reachable tasks — with `reset_programs_each_wake=True` these plausibly dominate) + sleep cost. **The amortization headline is stated against end-to-end**; marginal/end-to-end ratio = loop-overhead factor.
- **Break-even horizon** = learning overhead ÷ per-new-task savings: how many future top-level tasks justify the ladder. Instrument: heldout/eval split (as in studies) — new-task cost under L_R vs Floor.
- Raw-baseline strategy (raw cost is usually **censored**, per E13): (a) **calibration ladders** — height-2, raw measurable, exact ratios anchor everything (expect high rung-to-rung variance; that is why b is fitted per cell and residuals are the signal); (b) **extrapolation** — fit per-round growth on completed rounds, extrapolate to the raw solution's known depth (fragile under pool eviction; always labeled as extrapolation); (c) **censored bounds** — "≥ N considered, unsolved" reported as-is.

### 4.7 Batch tier

Across ladders: the b^d law fit (measured c_i vs b^(d_i), residual structure), climb-scaling-with-height curves, vocabulary-tax-vs-library-size curve, recovery rate vs demonstration count/design. All derivable from tier-0 + specs.

## 5. Finding ladders (construction methodology)

### 5.1 Two methods, asymmetric roles

- **Method 2 — backward bisection** (primary, for _anchored_ ladders): fix Floor and Top Rung, recursively insert a mid-rung into the largest jump until every jump passes §5.2. Tops are meaningful by construction; learnability of each inserted rung is a claim to verify. Only this method can connect a designated Floor to a designated Top.
- **Method 1 — forward extension** (for _synthetic free-growth_ families): grow upward from what's learnable — each new rung a template over the current L_i, plus demonstrating programs/tasks. Learnable by construction; the top is wherever the walk lands (undirected). Role: calibration ladders and controlled-d_i-profile families, where the top's identity doesn't matter.

Record method-of-construction per ladder: the two produce systematically different objects (learnable-by-construction vs meaningful-by-construction; neither gives both). Even for synthetic families, prefer picking the top competence _first_ and bisecting down — forward growth's attractor is learnable-but-arbitrary telescopes (§5.5).

### 5.2 Validity invariant (the tractability sandwich)

For every rung i, with margin:

- **jump tractable with headroom**: predicted cost b_eff^(d_i) fills ≤ ~half the wake budget, where b_eff is estimated **at the library size expected when the rung comes due** (the library is fatter by iteration i — E12's tax; edge-of-tractability designs validate under oracle conditions and stall under learned conditions);
- **double-jump intractable**: the **inlined depth** of rung i+1 over L*{i-1} — rung i+1's template with every rung-i call site *expanded to rung i's template* — clearly exceeds budget reach. Never computed as d_i + d*{i+1}: depth compounds by substitution (the 4093f84a Total-vs-Jump-only distinction).

**The skip-path problem**: the sandwich checks the _intended_ decomposition; search may find shortcut programs never designed. Statically uncomputable (it is the search problem); **empirically certified by the oracle chain** (§6): the L\_{i-1} column must solve rung-i tasks and solve _zero_ rung-(i+1) tasks. Rung necessity is the same certificate.

### 5.3 Learnability per rung

Demonstration shape selects the proposer:

| Demonstration shape | Learnable by |
| --- | --- |
| solution _is_ the rung template, params varying across tasks | `AntiunifyPairs` (proven: E11, E12) |
| rung embedded in solutions, occurrences identical | `FrequentSubtree` |
| rung embedded, params varying across occurrences | Stitch (whole-program antiunify with differing context collapses to a bare variable; exact-subtree counting misses varying params) |

Default discipline: **full-solution demonstrations at each rung's own level; embedded use arrives free one level up** (rung i appears inside rung i+1's demonstrations) — keeps every mint on the proven `AntiunifyPairs` path while still exercising composition. Fragment-only demonstrations are an experimental _condition_ (paired with the proposer that can exploit it), not a default.

Per rung, additionally:

- **Parameter variation plan** — for each template parameter: fixed-within-task, varied-across-tasks (the E11 discipline; perceived quantities vary within-task). Absent this, sleep mints a **specialized** (literal-bound) rung; the mint "succeeds", the climb stalls one level up. Cheap to lint statically, miserable to debug empirically.
- **MDL break-even check** — demonstration count × per-use savings clears the definition cost (computable statically from template size + demo count; interacts with jump size: small rungs may not clear at 2 uses).

### 5.4 Task derivation (program → tasks is an inverse problem)

Consistency is mechanical (deterministic inputs — no RNG anywhere — outputs computed); **uniqueness is the work**: no shallower program may agree on all of a task's examples. Tools: multi-example tasks (kills literal shortcuts — E11), input diversity, static collision checks against the cheap end of the floor's space where feasible (E13's fix: verified against all 8 D4 members), and the empirical certificate (the L\_{i-1} run shows what the retained cheapest solution actually was).

### 5.5 Shape metadata (guard against the telescope degeneracy)

Naive forward growth produces **telescopes**: rung\_{i+1} = one application wrapped around rung_i, d_i = 2 forever, fan-in 1 — a valid but degenerate geometry; a 25-telescope batch silently overclaims. Record per-rung **fan-in** (distinct lower rungs used, with multiplicity) and ensure fan-in > 1 is represented. Fan-in > 1 is also the first foothold of the chain→DAG future axis, with no new machinery.

### 5.6 Bisection failures are findings

Method 2's step "derive a mid-level abstraction learnable from below and useful for above" presupposes a foothold exists; some jumps are plausibly **atomic** (the insight is a program _shape_, not a nameable sub-quantity — cf. the fold-accumulator trick). A failed bisection after honest effort is a finding about the geometry of abstraction space: log it (notebook + EXPERIMENTS.md), recording _which_ requirement failed — **not-learnable-from-below** vs **not-useful-for-above** (rung necessity) — those are different geometries.

### 5.7 The recipe, consolidated

Anchor Floor + Top → bisect largest jump until §5.2 passes with headroom → per rung: full-solution demos at own level, ≥2 tasks, variation plan, MDL break-even → derive tasks with collision checks → run the oracle chain as the **admission test** → admit to batch with shape metadata (height, d_i profile, fan-ins, tasks-per-rung, construction method, static-vs-certified checks). Only validated ladders count toward batch metrics; everything else is exploratory.

## 6. Run structure per ladder

A ladder with R rungs (rung R = Top), at one (params, budget) cell:

- **1 LEARN run** — the climb itself (wake-sleep; `iterations ≥ R+1` headroom; `early_stop` on).
- **R−1 oracle SEARCH runs** — libraries L*1 .. L*{R-1}, gifted, over the **full corpus**, at the **same wake budget** (or the columns aren't comparable).
- **1 off-chain SEARCH run** — Floor + Top-Rung-only (do intermediate rungs matter for the top task, or only the final abstraction?). Optional but cheap.
- **L_0 comes free**: iteration 0's wake _is_ a Floor search over the corpus; via content-hashed caching its recorded run should coincide with the L_0 column — **to confirm in `execute.py`** (whether derived wake searches record as plain SEARCH runs with the same `run_id`). Else +1 run.

Each oracle run fills a full **column** of the cost matrix: jump-i measurements on rung-i tasks, **censored raw bounds on all higher-rung tasks** (they fail at full budget — the baseline data, free), and **vocabulary-tax readings on all lower-rung tasks**. The oracle chain is simultaneously: the with-ladder-without-learner arm, the validity certificate (§5.2), and the raw-baseline instrument. The full raw deep-search run is _not_ executed (censored by construction; §4.6 strategies instead).

"1 Learn run = 1 Ladder" is shorthand: 1 LEARN run = one **(ladder × params × budget)** cell; Q2 sweeps multiply cells (cache makes repeats free).

## 7. Batch design

- **Start with one ladder**: height-3 chain, **Method 2 from a synthetic anchor** — the minimal genuinely-new datum beyond E12 (does the ~4x tax compound at rung 3? does greedy-MDL stay clean three generations deep?), while rehearsing the bisection workflow the real-ARC anchors need.
- **Then families varying one axis each** (5–25 ladders total; a heterogeneous batch averages to mush):
  - **Family A** — height {2,3,4,5}, fixed jump size: climb-scaling + tax compounding (Q1);
  - **Family B** — design jump {2,3,4}, fixed height: calibrates the b^d law;
  - **Family C** — tasks/programs per rung, demonstration design: feeds Q3.
- **Calibration ladders** — height-2 (Method 1 fine here): raw baseline actually measurable; anchors extrapolated/censored baselines for everything taller.
- **1–2 real-ARC anchor ladders** — hand-derived (the 4093f84a exercise done under this design): the external-validity bridge; expected to be expensive and to fail bisection in interesting places (§5.6).

## 8. Structural home

A ladder generalizes `StudySpec` rather than replacing it: **`LadderSpec`** = floor + corpus + _leveled_ `TargetAbstraction`s (ordered rung levels, each with its demonstrating task-ids) + per-task rung annotation as solver-invisible meta (like `Split` — observables behind the blindness seam, never a training signal). Its activities: the LEARN run + the oracle chain + the off-chain cell (§6); its report is the **climb trace** (§4.5) plus the cost-matrix views (§4.4) — the study report's multi-rung generalization. Search/learn engines need little or nothing new.

## 9. Machinery gaps (build list, rough order)

1. **Run-record exposure of cost-to-first / cost-to-cheapest** (`candidate_index` of accepted candidates) — the atom every ladder metric is built from; rides the in-flight tracking work.
2. **Ladder lint** — static validator: typed templates over L\_{i-1}, inlined-depth sandwich with headroom, MDL break-even, variation-plan presence, collision checks. Highest-value new machinery given the silent-failure surface.
3. **`LadderSpec` + climb-trace report** (§8) — the actual build for this direction.
4. **Sleep-cost instrumentation** — unit decision pending (§10); must precede ladder #1's LEARN run.
5. _(Q3, later)_ **top-K solution retention** per task — smallest AF-visibility change, de-risks corpus engineering broadly.
6. _(Q3, later)_ **partial-credit scoring** at extraction (train-output cell match) — the non-solution selector that doesn't flood with `Input()` trivia.
7. _(optional)_ `max_considered`-style budget cap — cleaner censored baselines and cost-matched controls than depth-quantized budgets (touches run identity/locks; not required for ladder #1).
8. _(rejected for measurement)_ early stop / `stop_after_solutions` — changes identity, destroys the first-vs-cheapest observable; candidate policy experiment only.

## 10. Decisions and open questions

Decided in design sessions (2026-07-16):

- Rungs v1 = mintable abstractions; substrate-laddering deferred as a named contrast (§1).
- Cost accounting: all three costs, no early stop (§4.3).
- Amortization headline: end-to-end laddered cost; marginal as bound (§4.6).
- Atoms/views split: tier-0 exhaustive at run time; all named metrics read-side (§4.1).
- Oracle chain = validity certificate = baseline instrument (one set of runs, three roles) (§6).
- First ladder: height-3 chain, Method 2, synthetic anchor (§7).
- Q3 sequencing: top-K solutions first; fragment options after (they force the usefulness-governance question) (§3).

Open:

1. **Rung necessity: strict or permissive?** Enforce double-jump-intractable for _every_ consecutive pair (clean amortization attribution, stricter design burden), or admit ladders with a skippable rung, recorded as a covariate? Leaning: strict for the batch, permissive for exploratory singles.
2. **Method 1's "programs that use the abstraction as _part_ (not all) of it"** — if the intent was "demonstrate composition", the default discipline (§5.3: full-solution at own level, embedded use one level up) satisfies it on the proven proposer path; confirm or state the other intent.
3. **Sleep-cost unit** — proposal count + antiunify-pair count (recommended) vs alternatives; decide before the first LEARN run.
4. **L_0 cache-sharing** — confirm derived wake searches record as plain SEARCH runs (§6).
5. **Aggregation convention final check** — per-rung costs as sums with per-task variance retained (§4.3); confirm.

## 11. Pointers

- Run model / activities: [EXECUTION.md](../EXECUTION.md) · engine/substrate: [ARCHITECTURE.md](../ARCHITECTURE.md)
- Prior findings: [EXPERIMENTS.md](../EXPERIMENTS.md) (E11 2026-07-12 · E12 2026-07-12 · E13 2026-07-15) · queue: [EXPERIMENT_QUEUE.md](../EXPERIMENT_QUEUE.md)
- Study machinery this generalizes: `src/arc_lab/program_search/execution/model/study_spec.py` · `execution/studies.py`
- Tracking instruments: `src/arc_lab/program_search/search/tracking.py`
- Precursor hand-worked ladder: [task_specific/4093f84a-EXPRESSIBILITY-2026-07-15.md](task_specific/4093f84a-EXPRESSIBILITY-2026-07-15.md)
