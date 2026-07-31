# Ladder process

How to build a ladder: what to do, in what order, with which instrument — and what each instrument can and cannot prove.

**What this is not.** It is not a list of checks: [LINT-CHECKS.md](LINT-CHECKS.md) is generated from the code and is the authority on what fires and why. It is not the format spec ([LADDER-FORMAT.md](LADDER-FORMAT.md)) or the register ([LADDERS.md](LADDERS.md)). What lives here is the part machinery cannot enforce — **order, judgement, and inference** — which is why it is short: nearly everything else became a check.

Written after the first real-ARC ladder ([`dae9d2b5-halves-union`](../../src/arc_lab/program_search/ladders/registry/dae9d2b5-halves-union.ladder)) cost far more than it should have. The machinery half of that response is [2026-07-26-AL-PLAN.md](../archive/abstraction_ladders/AL-PLAN-PROCESS-2026-07-26.md); the failures are in [EXPERIMENTS.md](../../EXPERIMENTS.md) under 2026-07-25/26. Almost every rule below is a scar.

---

## 1. The one law

```
cost ~ (primitives x constants) ^ depth
```

Depth is the exponent and no pruning beats it. Breadth is the base, and it is the one that actually bit: on `dae9d2b5-halves-union` rung 1, depth was fixed at 3 while the base alone moved the cost from **4** to **21,149,854** — a 5.3-million-fold spread over the _same_ rung at the _same_ depth.

Both axes are now instrumented ([BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md)): the depth schedule per level and the round-1 breadth census, both printed by `lint-ladder` in ~1s. The instrument _ordering_ in §3 and the breadth items in §5 are corollaries of this line; the instrument _contracts_ (what each can prove) are not — they come from what each instrument observes.

## 2. Building a ladder

### Order: competences -> floor -> demos

**This order is the finding, not a preference.** Every 2026-07-25 breadth wall traces to the reverse: floors inherited from authoring convenience, rungs then bent to fit them.

1. **Anchor the term first — the hard gate.** Hand-author the solution program for the real task and verify it against _all_ train examples and the held-out tests, then pin it as a test. Nothing downstream is worth building until this holds; it was the most solid single step of the whole 2026-07-25/26 arc, and everything else derives from the term.
2. **Cut the term into competences.** Read the natural cut-sets off the verified term and name each one. If you cannot name a rung in three words, it is a fragment of a competence, not a rung.
3. **Then choose the smallest floor** that puts each cut at depth 2–3, preferring _perceived_ geometry over _computed_ (§5). The floor is chosen to serve the cuts — never inherited and then worked around.
4. **Author demonstrations last.** They are the plan's dominant cost centre, so they are the last thing to commit to a spine that might still move.
5. **Register the expected profile, then verify** — lint, probe, `diff-ladder` for any member derived from another (membership/equivalence, picking the validator the floor relationship licenses — [LADDER-RELATIONSHIPS](LADDER-RELATIONSHIPS-2026-07-23.md)), taskgen, run, analyse (§3 for the order, §4 when something fires). Write the predicted per-rung verdict profile down **before** `run-ladder`: a profile is evidence only against a stated expectation, and a prediction cannot be retro-fitted ([MVE-PLAN](../archive/abstraction_ladders/MVE-PLAN-2026-07-25.md)).

Start a ladder, or the next variant of one, with `arc-lab new-ladder <name> [--from <existing>]`. It refuses to overwrite; that is the point (§7).

### Choosing which ladder to build

Soundness is not worth much on a task that measures nothing. Two selection criteria beyond the task screen in [MVE-PLAN-2026-07-25.md](../archive/abstraction_ladders/MVE-PLAN-2026-07-25.md):

- **Demo-pool cheapness.** Rungs demonstrable with task-realizable, full-solution _Grid_ demos are the cheap case. Fragment-demoed rungs (any non-Grid rung must be wrapped, and the wrapper's depth is what the wake pays) are a deliberate sample, never an accident.
- **Floor leverage.** Prefer families where one perceived-geometry producer unlocks several tasks — one `panels`-style producer serving the whole separator/two-halves family beats a bespoke floor per task.

### Declare withheld primitives

A floor designed around a known solution **manufactures** raw-intractability. That is the method, not a flaw — but say so in the `.ladder` header: which primitives were deliberately withheld, and why. Undeclared, every RQ1 amortization bound reads as an absolute claim about search when it is a claim _relative to a floor you chose_.

### Done looks like

Certificate admitted (or deliberately not, with the reason) · artifacts written (`arc-lab run-ladder <name> --artifacts …`) · a [LADDERS.md](LADDERS.md) row · an [EXPERIMENTS.md](../../EXPERIMENTS.md) entry, including if it failed.

## 3. Which instrument, in which order

Every question has a cheapest instrument that can settle it. **Exhaust the cheaper ones before escalating.**

| # | Instrument | Cost | Proves | Cannot prove |
| --- | --- | --- | --- | --- |
| 1 | **hand algebra** | ~minutes | a rung is skippable; a term collapses | anything about search cost |
| 2 | `lint-ladder` | ~1s, static (one exception, below) | the ladder is unsound on paper | that it is sound |
| 2b | `lint-ladder --full` | ~1s | — | (the `spec.md` artifact form: all six depth quantities, four breadth corners, resolved config) |
| 3 | `diff-ladder` (derived members) | ~1s same-floor; a grid battery across floors | a member is / is not behaviour-preserving | anything across floors whose primitives are still assumed — INCONCLUSIVE |
| 4 | pruned probe cell | seconds | the rung's own search is too costly | that the floor is affordable |
| 5 | full probe cell | what the enumeration costs, capped by the ladder's own guard | a rung is broken in fact | that a rung is fine |
| 6 | `run-ladder` | the whole chain | the certificate — the admission verdict | — |

The session's own contrast: `dae9d2b5-3-recolor-rungs` was killed by **one lint, no probe**; the `map_color`/`overlay` skip path cost a **25-minute probe** that hand algebra would have found in minutes.

**The probe convicts; only the certificate acquits.** A skip path, collapse, collision or wrong mint the probe finds is real. A clean probe is not a pass — the climb pays each jump under a library inflated by earlier mints, and cross-rung interactions are invisible to a per-rung cell.

**Admission is exactly two verdict families** (`certificate.py::admitted`): every jump tractable, and every `no_skip_paths` verdict `is True` — `None` (censored) fails exactly as `False` does. Everything else the certificate carries — `demonstration_health`, static skippability — is verdict-profile data, not a gate ([CERTIFICATE-PROFILE](CERTIFICATE-PROFILE-2026-07-24.md)). When this doc says "admitted", it means that predicate and nothing more.

**Read the compact table first.** `lint-ladder <name>` prints one line per rung — the level's budget, `d_i`/`needs`, the double-jump, the round-1 breadth `b1` and its `tax` ratio, and a `measured` column read back from any recorded probe cells for that level. Blank there means nobody has probed it, which is an honest gap rather than a zero. `--full` prints the artifact form; `arc-lab runs --probes` lists the cells themselves.

**Lint's ~1s has one known exception.** Unfolding a heavily-shared tall DAG can blow up — `cfb2ce5a-5-lowered-full` does not terminate (>8 min, >2.6 GB RSS). A lint that is minutes-silent on a big DAG is hitting that, not working; the fix is recorded out-of-scope in [2026-07-26-AL-PLAN](../archive/abstraction_ladders/AL-PLAN-PROCESS-2026-07-26.md) — park the ladder rather than waiting it out.

**INCONCLUSIVE is a non-result by design, not a defect to tune away.** A censored cell means the search was cut short, so "unsolved" is a budget fact, not a verdict. Raising `--guard` buys a longer search, never a stronger verdict; if the answer matters, run `run-ladder`. (2026-07-25: six escalating guard runs, >1h. The CLI's own help was recommending it — that text is fixed; this is the reason.)

**Pruning is a bound, never a measurement.** A pruned cell chose its library AND its constant values by reading the answer. It prices a floor and sizes a guard; it is never a run whose cost may be quoted (§6, `pruned-library`).

**Pruning has two halves and neither subsumes the other.** Dropping a primitive drops its types' whole constant battery for free — which is the entire story on `dae9d2b5-halves-union`'s `west` (round-1 width 131 -> 1; **corrected 2026-07-27** from 1,211 -> 1, see below). It is _no_ story on al14's `move_cell_up`, where every primitive the program uses survives and the width does not move at all (300 -> 300) until the constant VALUES are restricted (-> 12). A cell offering only library pruning reports "this rung is expensive" where the truth is "its constant battery is"; the probe does both.

**The breadth census is an indicator, never a prediction.** Exact for round 1 and it understates badly at depth: `dae9d2b5-halves-union` r_1 reads **131x** statically against ~5.3e6 measured at depth 3. Use it to rank floors and to compare a ladder against itself.

> **CORRECTION (2026-07-27), and the lesson in it.** That figure read **1,211x** until the census was first calibrated against measured cost. `forecast_cost._slot_types` — shared by the census and the forecaster — replicated a variadic primitive's *last declared parameter* instead of its `variadic_param`, so `overlay : (Color, Grid...) -> Grid` was modelled as composing colour tuples (1,110) rather than grids (30). Round 1 was over-counted **9.24x** on every floor carrying such a primitive, in the one quantity the instrument documents as EXACT. Now verified against the engine on every uncompromised rung cell: 21/42 exact before, **42/42** after.
>
> Two things this changes, and one it does not. **The ranking claim is now measured and it holds** — median `b1` per ladder ranks measured per-cell cost at Spearman **+0.97** (n=14 ladders); within a ladder, +1.00 median. **The blindness is `max_pool`**, and it is first-order: the same ladder at pool 150 vs pool 30 has a byte-identical census and costs **19-26x** more, so `b1` can never be converted to an absolute cost. What does NOT change is every diagnosis the census drove — the responsible primitives, the wasted batteries, and the fat-floor/lean-floor separation are all unmoved; only the magnitudes were wrong. Full account: [experiments/2026-07-27-census-calibration/](../../experiments/2026-07-27-census-calibration/notebook.md).
>
> **Do not reach for `forecast_cost` as the fix.** Backtested on the same cells it is *worse* at ranking (+0.46 vs the census's +0.80) and a systematic under-reader (median **0.20x** of measured), because `_capped` freezes the modelled census at `max_pool` and the new-layer restriction then makes deeper rounds structurally zero — its own docstring's saturation caveat, confirmed. Neither instrument forecasts absolute cost today.

## 4. When something fires

[LINT-CHECKS.md](LINT-CHECKS.md) says what each check tests. Listed here only where the **response** is a judgement call:

| Fires | The judgement |
| --- | --- |
| `double-jump-intractable` (warn) | a data point about where the cut was placed, **not** a reason the ladder may not exist ([CERTIFICATE-PROFILE](CERTIFICATE-PROFILE-2026-07-24.md)). Do not redesign to silence it |
| `raw-intractable` | the top is reachable from the bare floor — the ladder measures nothing. **Withhold the primitive(s) that make it shallow** (and declare them, §2), or drop the task; redesigning the top is the last resort, because it changes which competence you are measuring |
| `free-param-varies` | the demo plan feeds a rung parameter one value everywhere, so sleep will bake the literal in instead of minting at intended arity — the S-B law: **the demo value-patterns ARE the mint's spec**. Choose grids that vary the value; this is the manual demo-selection judgement the deferred selector would mechanize, and repeated pain here is that selector's build trigger ([MVE-PLAN](../archive/abstraction_ladders/MVE-PLAN-2026-07-25.md)) |
| `free-params-covary` | two parameters move in lockstep at every call site, so no mint can separate them. Vary them independently across demos — same S-B judgement as above |
| `rewrite-shallow` | real, and the witness is printed. The rung buys less depth than it claims |
| `constant-subterm` | a composite subterm is train-constant and beaten by a literal. Vary the grids so the value cannot be baked in (al14) |
| probe: COLLAPSED | search retains something cheaper than intended — the rung is not the competence you think it is |
| probe: COLLISION | the demonstrations under-determine the rung. Add or vary tasks; do not relax the check |
| probe: CENSORED (wake) | read the **floor tax** before touching the rung: is it the rung, or the floor? |
| floor tax `rung-too-expensive` | the pruned cell censored. A leaner floor will not save it — redesign the rung |
| floor tax `floor-too-broad` | the rung is fine; the dropped primitives are the bill |

### Tractability triage

**The question is not simply "is this rung expensive". It is "which primitive is expensive, what makes it necessary, and can that thing search shallower".** Cost attributes to _primitives_; primitives are necessitated by _pieces of the ladder_; and it is the piece, not the primitive, that you can move. Run it in that order:

1. **Attribute the cost to primitives.** `by_primitive` (shares overlap — not a partition), `first_solution_index` vs `considered`, `generations`, the retained programs. On 2026-07-25 all of it was available from the first run, unread for hours, while mechanisms were asserted instead. Statically, `lint-ladder`'s breadth census says the same thing without a search: a large `b1 (full)` / `b1 (min)` ratio, or a `10 minted / 0 used` battery row, names the responsible primitive outright.
2. **Map each expensive primitive to the piece of the ladder that necessitates it** — `primitive-necessity` prints this: which level's search first has to compose it, and which levels carry it below that, at what budget. The floor is one library for the whole climb, so a primitive only the _top_ needs is still in the pool (and still minting its types' constant battery) at every level beneath it.
3. **Restructure the piece, or drop the primitive.** In order of preference: make the piece that needs it search at depth 2 (§5); express the competence without it; or accept the tax and record it. Note what this rules out — _the rung that is expensive is usually not the rung to redesign_: on `dae9d2b5-halves-union` the fat cells were `west`/`east`, and the fix was neither of them (it was the plumbing that made them d3, and the top's vocabulary).
4. **Ablate to the minimum.** The probe's floor-tax cell does this automatically; do it by hand for a different cut.
5. **Ask the human** — any one of these is a trigger:
   - a second escalation of any budget or guard;
   - an expected duration over ~10 minutes (estimate _before_ launching, §7);
   - a measurement that contradicts a written claim in a doc or docstring;
   - two consecutive redesigns of the same rung;
   - **a gate and a natural design disagreeing** (§5).

## 5. Design taste

Heuristics, explicitly not rules. Each is a scar.

- **Run the algebraic skip-audit as a design step, before any probe.** Actively try to prove each rung skippable by hand: is there a law letting a consumer reroute around it (`map_color` distributing over `overlay`)? Is there a sibling reachable at the same depth from the floor (`4347f46a-1`'s four shift rungs, skippable by construction)? **Both 2026-07-25 skip findings were hand-derivable** — and both were found by an expensive probe instead.
- **When a gate and a natural design disagree, the prior is that the gate measures the wrong thing.** The folded `recolored_west`/`recolored_east` rungs are the type case: they were collapsed into the top purely to pass skip-freeness — a gate [CERTIFICATE-PROFILE](CERTIFICATE-PROFILE-2026-07-24.md) already said should be a verdict profile — and per-rung budgets later made the 4-rung form both valid _and cheaper_. The machinery was wrong; deforming the design to satisfy it destroyed the better ladder. This is an ask-the-human trigger, not a licence to ignore gates.
- **Never collapse a natural rung to satisfy a gate.** The corollary of the above.
- **Anticipate the constant battery when choosing floor primitives.** Minting is gated on whether _any_ floor primitive mentions a type, so one colour-taking primitive buys _every_ rung the full ten-colour battery. Prefer **perceived** geometry (`halves_h`, region producers) over **computed** (`floordiv(width(g), 2)`): the arithmetic then never enters the search space at all. `lint-ladder` prices this before you commit.
- **An expensive primitive may sit in the floor — but it should only ever meet the search at depth 2.** The base `b` is pinned by the TOP (every primitive the top needs is in the pool at every level, and no rung redesign removes it), so what rung design actually controls is the _exponent at each level_. That is the whole lever: at a fixed fat `b`, depth 2 vs depth 3 was the difference between ~10⁴ and ~2x10⁷ considered on `dae9d2b5`. Read `primitive-necessity` against the depth schedule and, where they collide, restructure — the usual culprit is **plumbing**, a level spent converting between types rather than computing anything (`crop_rect(g, head(halves_h(g)))` spends two of its three levels turning `List[Rect]` into a `Grid`; a `split_h: (Grid) -> List[Grid]` producer makes the same competence d2).
- **Prefer a producer that returns what the consumer wants.** A `Rect`-returning producer is right when the rect is used as an _address_ (a paste target). When every consumer immediately crops it, the Grid-returning form is the perceived-geometry version and saves a level everywhere it is used.
- **Depth-1 is not a rung** — a bare primitive already in the layer below buys no depth.
- **A non-Grid rung must be demonstrated through a wrapper**, and the wrapper's depth is what the wake pays. A real cost, not an accounting artefact.

## 6. Compromise Options

Named cost/data trades, as data in [`ladders/compromise.py`](../../src/arc_lab/program_search/ladders/compromise.py), **detected from the config rather than declared** — a label you must remember to set is the one that gets forgotten.

| Option | Saves | Forfeits |
| --- | --- | --- |
| `pruned-library` | makes an unrunnable ladder runnable (~5.3e6x measured) | **all cost interpretation (RQ1 void)**; learnability survives |
| `wake-schedule` | climb wall-clock | end-to-end cost, loop overhead, what sleep saw |
| `solution-limit` | large, when solutions are found below `depth_limit` | `cheapest_solution_index`, cost-to-exhaust, full attribution. RQ1 survives — `first_solution_index` is exact either way |

**The labelling rule: a result produced under any option carries the label at every level it appears.** The report banners them ahead of the numbers; any figure quoted elsewhere must carry it too.

**Default to no compromise.** `ladder_default_config` leaves `solution_limit` unset so one exhaustive run yields three cost quantities at once — the RQ1 cost-to-first vs cost-to-exhaust asymmetry needs no machinery, only the right column.

## 7. Operational discipline

General habits, listed because these are the ones that cost real time here.

- **Estimate a run's duration BEFORE launching, from the cost you already know.** The estimate is a decision input, not a postscript; a run whose cost you would not have approved is one you should not have started. (2026-07-26: launched a chain and only then read the log to find it was a 6–10 hour job — with the per-cell cost in the plan's own Context section.)
- **When a verification is expensive, ask whether a cheap permanent instrument buys the same evidence.** [`al21-dag-siblings`](../../src/arc_lab/program_search/ladders/registry/al21-dag-siblings.ladder) certifies the DAG reading end to end in 0.26s inside `make check`, forever; the multi-hour real-task chain would have added "and it also holds here", once.
- **Never pipe long-running output through a buffering filter.** `tail`/`head`/`sort` swallow everything until exit, so a live job looks dead (hit three times in one session, twice _after_ diagnosing it). Write to a file and read that. Background long runs; do not chain sleeps to poll.
- **Probe cells are cached**, so a re-probe of an unchanged rung is free — but the _first_ probe of a fat floor costs what the enumeration costs. Lint before probing.

## 8. Artifacts & provenance

- **One file per variant, at creation.** `arc-lab new-ladder <name> --from <existing>` copies and renames, and refuses to overwrite. Five variants died through one filename on 2026-07-25, two unrecoverably; a git-tracked-only guard would not have helped, since none had been committed.
- **A rejected ladder's file persists as the finding** ([LADDERS.md](LADDERS.md)). Retired ladders are never fixed under their own ID — rebuilds get new IDs, and the old file stays as a lint-lock fixture.
- **The `.ladder` file is the source of truth**; generated artifacts are derived and never hand-edited. Do **not** write measured costs into a `.ladder`: [LADDER-FORMAT](LADDER-FORMAT.md) keeps chosen and derived separate, and a stale cost comment is worse than none. The exception is a retired draft, whose header carries the verdict that is the reason the file exists.
- **Committed generators** live under `experiments/<date>-<topic>/artifacts/`; the `.ladder` is authoritative and regeneration is explicitly not the workflow.
- **Create an `experiments/` folder for any non-trivial investigation** — read [experiments/README.md](../../experiments/README.md) first. EXPERIMENTS.md is the terse abstract; the notebook is the appendix.

## 9. Glossary

**Probe — wake:** `as-intended` · `alternative` (different program, same behaviour and depth) · `collapsed` (solves shallower than intended) · `collision` (differs off the train support) · `unsolved` · `censored` (cut short by the guard).

**Probe — skip:** `no-skip` (searched to completion, found nothing) · `skip-path` (a real defect) · `inconclusive` (censored — proves nothing).

**Probe — floor tax:** `clean` · `rung-too-expensive` · `floor-too-broad`.

**Structure:** `skippable` (static, from lint: the consumer's double-jump fits the budget, so a skip _could_ exist — a verdict-profile data point, not a gate; distinct from the certificate's `no_skip_paths = False`, where a skip path was empirically _found_, which fails admission) · `chain` vs `DAG` · `telescope` vs `recombination` (fan-in > 1).

**Certificate:** `tractable_jumps` · `no_skip_paths` — **tri-state**: `True` none found, `False` found, `None` inconclusive because a search censored; `None` fails admission exactly as `False` does · `demonstration_health` (fraction solved _and_ routed through the rung's own dependencies).

**Learning:** `recovered` (a mint behaviourally matches the intended rung) · `junk` (mints nothing intended) · `cascade` (a wrong mint that later mints build on).

**Cost:** `considered` · `first_solution_index` / `cheapest_solution_index` (exact) · `b1` (round-1 width) · `floor tax` (full/pruned, measured) · `b_eff` (fitted per-round growth).

## 10. Pointers

- Format: [LADDER-FORMAT.md](LADDER-FORMAT.md) · Register: [LADDERS.md](LADDERS.md) · Checks: [LINT-CHECKS.md](LINT-CHECKS.md)
- Verdict profile, not a sandwich gate: [CERTIFICATE-PROFILE-2026-07-24.md](CERTIFICATE-PROFILE-2026-07-24.md) · The two cost axes: [BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md)
- Set structure: [LADDER-SET-DESIGN-2026-07-24.md](LADDER-SET-DESIGN-2026-07-24.md) · Full-set plan (Phase 2+ entry gates): [LADDER-SET-PLAN-2026-07-24.md](../archive/abstraction_ladders/LADDER-SET-PLAN-2026-07-24.md) · Comparison licenses: [LADDER-RELATIONSHIPS-2026-07-23.md](LADDER-RELATIONSHIPS-2026-07-23.md)
- Active plans: [MVE-PLAN-2026-07-25.md](../archive/abstraction_ladders/MVE-PLAN-2026-07-25.md) · [AL-PLAN-2026-07-23.md](../archive/abstraction_ladders/AL-PLAN-2026-07-23.md) · [2026-07-26-AL-PLAN.md](../archive/abstraction_ladders/AL-PLAN-PROCESS-2026-07-26.md)
- Run model: [EXECUTION.md](../EXECUTION.md) · Engine: [ARCHITECTURE.md](../ARCHITECTURE.md) · Notebooks: [experiments/README.md](../../experiments/README.md)
