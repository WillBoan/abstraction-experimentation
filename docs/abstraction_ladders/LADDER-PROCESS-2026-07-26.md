# Ladder process (2026-07-26)

How to build a ladder: what to do, in what order, with which instrument — and what each instrument can and cannot prove.

**What this is not.** It is not a list of checks: [LINT-CHECKS.md](LINT-CHECKS.md) is generated from the code and is the authority on what fires and why. It is not the format spec ([LADDER-FORMAT.md](LADDER-FORMAT.md)) or the register ([LADDERS.md](LADDERS.md)). What lives here is the part machinery cannot enforce — **order, judgement, and inference** — which is why it is short: nearly everything else became a check.

Written after the first real-ARC ladder ([`dae9d2b5-halves-union`](../../src/arc_lab/program_search/ladders/registry/dae9d2b5-halves-union.ladder)) cost far more than it should have. The machinery half of that response is [2026-07-26-AL-PLAN.md](2026-07-26-AL-PLAN.md); the failures are in [EXPERIMENTS.md](../../EXPERIMENTS.md) under 2026-07-25/26. Almost every rule below is a scar.

---

## 1. The one law

```
cost ~ (primitives x constants) ^ depth
```

Depth is the exponent and no pruning beats it. Breadth is the base, and it is the one that actually bit: on `dae9d2b5-halves-union` rung 1, depth was fixed at 3 while the base alone moved the cost from **4** to **21,149,854** — a 5.3-million-fold spread over the *same* rung at the *same* depth.

Both axes are now instrumented ([BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md)): the depth schedule per level and the round-1 breadth census, both printed by `lint-ladder` in ~1s. Everything in §3 and §5 is a corollary of this line.

## 2. Building a ladder

### Order: competences -> floor -> demos

**This order is the finding, not a preference.** Every 2026-07-25 breadth wall traces to the reverse: floors inherited from authoring convenience, rungs then bent to fit them.

1. **Anchor the term first — the hard gate.** Hand-author the solution program for the real task and verify it against *all* train examples and the held-out tests, then pin it as a test. Nothing downstream is worth building until this holds; it was the most solid single step of the whole 2026-07-25/26 arc, and everything else derives from the term.
2. **Cut the term into competences.** Read the natural cut-sets off the verified term and name each one. If you cannot name a rung in three words, it is a fragment of a competence, not a rung.
3. **Then choose the smallest floor** that puts each cut at depth 2–3, preferring *perceived* geometry over *computed* (§5). The floor is chosen to serve the cuts — never inherited and then worked around.
4. **Author demonstrations last.** They are the plan's dominant cost centre, so they are the last thing to commit to a spine that might still move.
5. **Verify** — lint, probe, taskgen, run (§3 for the order, §4 when something fires).

Start a ladder, or the next variant of one, with `arc-lab new-ladder <name> [--from <existing>]`. It refuses to overwrite; that is the point (§7).

### Choosing which ladder to build

Soundness is not worth much on a task that measures nothing. Two selection criteria beyond the task screen in [MVE-PLAN-2026-07-25.md](MVE-PLAN-2026-07-25.md):

- **Demo-pool cheapness.** Rungs demonstrable with task-realizable, full-solution *Grid* demos are the cheap case. Fragment-demoed rungs (any non-Grid rung must be wrapped, and the wrapper's depth is what the wake pays) are a deliberate sample, never an accident.
- **Floor leverage.** Prefer families where one perceived-geometry producer unlocks several tasks — one `panels`-style producer serving the whole separator/two-halves family beats a bespoke floor per task.

### Declare withheld primitives

A floor designed around a known solution **manufactures** raw-intractability. That is the method, not a flaw — but say so in the `.ladder` header: which primitives were deliberately withheld, and why. Undeclared, every RQ1 amortization bound reads as an absolute claim about search when it is a claim *relative to a floor you chose*.

### Done looks like

Certificate admitted (or deliberately not, with the reason) · artifacts written (`arc-lab run-ladder <name> --artifacts …`) · a [LADDERS.md](LADDERS.md) row · an [EXPERIMENTS.md](../../EXPERIMENTS.md) entry, including if it failed.

## 3. Which instrument, in which order

Every question has a cheapest instrument that can settle it. **Exhaust the cheaper ones before escalating.**

| # | Instrument | Cost | Proves | Cannot prove |
| --- | --- | --- | --- | --- |
| 1 | **hand algebra** | free | a rung is skippable; a term collapses | anything about search cost |
| 2 | `lint-ladder` | ~1s, static | the ladder is unsound on paper | that it is sound |
| 3 | pruned probe cell | seconds | the rung's own search is too costly | that the floor is affordable |
| 4 | full probe cell | tracks the enumeration | a rung is broken in fact | that a rung is fine |
| 5 | `run-ladder` | the whole chain | the certificate — the admission verdict | — |

The session's own contrast: `dae9d2b5-3-recolor-rungs` was killed by **one lint, no probe**; the `map_color`/`overlay` skip path cost a **25-minute probe** that hand algebra would have found in minutes.

**The probe convicts; only the certificate acquits.** A skip path, collapse, collision or wrong mint the probe finds is real. A clean probe is not a pass — the climb pays each jump under a library inflated by earlier mints, and cross-rung interactions are invisible to a per-rung cell.

**INCONCLUSIVE is a non-result by design, not a defect to tune away.** A censored cell means the search was cut short, so "unsolved" is a budget fact, not a verdict. Raising `--guard` buys a longer search, never a stronger verdict; if the answer matters, run `run-ladder`. (2026-07-25: six escalating guard runs, >1h. The CLI's own help was recommending it — that text is fixed; this is the reason.)

**Pruning is a bound, never a measurement.** Anything built on `prune_library` chose its library by reading the answer. It prices a floor and sizes a guard; it is never a run whose cost may be quoted (§6, `pruned-library`).

**The breadth census is an indicator, never a prediction.** Exact for round 1 and it understates badly at depth: `dae9d2b5-halves-union` r_1 reads 1,211x statically against ~5.3e6 measured at depth 3. Use it to rank floors and to compare a ladder against itself.

## 4. When something fires

[LINT-CHECKS.md](LINT-CHECKS.md) says what each check tests. Listed here only where the **response** is a judgement call:

| Fires | The judgement |
| --- | --- |
| `double-jump-intractable` (warn) | a data point about where the cut was placed, **not** a reason the ladder may not exist ([CERTIFICATE-PROFILE](CERTIFICATE-PROFILE-2026-07-24.md)). Do not redesign to silence it |
| `raw-intractable` | the top is reachable from the bare floor — the ladder measures nothing. Redesign the top; do not just lower the budget |
| `rewrite-shallow` | real, and the witness is printed. The rung buys less depth than it claims |
| `constant-subterm` | a composite subterm is train-constant and beaten by a literal. Vary the grids so the value cannot be baked in (al14) |
| probe: COLLAPSED | search retains something cheaper than intended — the rung is not the competence you think it is |
| probe: COLLISION | the demonstrations under-determine the rung. Add or vary tasks; do not relax the check |
| probe: CENSORED (wake) | read the **floor tax** before touching the rung: is it the rung, or the floor? |
| floor tax `rung-too-expensive` | the pruned cell censored. A leaner floor will not save it — redesign the rung |
| floor tax `floor-too-broad` | the rung is fine; the dropped primitives are the bill |

### Tractability triage

1. **Read what you already have.** `by_primitive` (shares overlap — not a partition), `first_solution_index` vs `considered`, `generations`, the retained programs. On 2026-07-25 all of it was available from the first run, unread for hours, while mechanisms were asserted instead.
2. **Read the breadth census.** A large `b1 (full)` / `b1 (min)` ratio, or a `10 minted / 0 used` battery row, explains most fat cells outright and names the primitive responsible.
3. **Ablate to the minimum.** The probe's floor-tax cell does this automatically; do it by hand for a different cut.
4. **Ask the human** — any one of these is a trigger:
   - a second escalation of any budget or guard;
   - an expected duration over ~10 minutes (estimate *before* launching, §7);
   - a measurement that contradicts a written claim in a doc or docstring;
   - two consecutive redesigns of the same rung;
   - **a gate and a natural design disagreeing** (§5).

## 5. Design taste

Heuristics, explicitly not rules. Each is a scar.

- **Run the algebraic skip-audit as a design step, before any probe.** Actively try to prove each rung skippable by hand: is there a law letting a consumer reroute around it (`map_color` distributing over `overlay`)? Is there a sibling reachable at the same depth from the floor (`4347f46a-1`'s four shift rungs, skippable by construction)? **Both 2026-07-25 skip findings were hand-derivable** — and both were found by an expensive probe instead.
- **When a gate and a natural design disagree, the prior is that the gate measures the wrong thing.** The folded `recolored_west`/`recolored_east` rungs are the type case: they were collapsed into the top purely to pass skip-freeness — a gate [CERTIFICATE-PROFILE](CERTIFICATE-PROFILE-2026-07-24.md) already said should be a verdict profile — and per-rung budgets later made the 4-rung form both valid *and cheaper*. The machinery was wrong; deforming the design to satisfy it destroyed the better ladder. This is an ask-the-human trigger, not a licence to ignore gates.
- **Never collapse a natural rung to satisfy a gate.** The corollary of the above.
- **Anticipate the constant battery when choosing floor primitives.** Minting is gated on whether *any* floor primitive mentions a type, so one colour-taking primitive buys *every* rung the full ten-colour battery. Prefer **perceived** geometry (`halves_h`, region producers) over **computed** (`floordiv(width(g), 2)`): the arithmetic then never enters the search space at all. `lint-ladder` prices this before you commit.
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
- **Never pipe long-running output through a buffering filter.** `tail`/`head`/`sort` swallow everything until exit, so a live job looks dead (hit three times in one session, twice *after* diagnosing it). Write to a file and read that. Background long runs; do not chain sleeps to poll.
- **Probe cells are cached**, so a re-probe of an unchanged rung is free — but the *first* probe of a fat floor costs what the enumeration costs. Lint before probing.

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

**Structure:** `skippable` (a rung whose consumer is reachable without it — a verdict-profile data point, not an admission failure) · `chain` vs `DAG` · `telescope` vs `recombination` (fan-in > 1).

**Certificate:** `tractable_jumps` · `no_skip_paths` — **tri-state**: `True` none found, `False` found, `None` inconclusive because a search censored; `None` fails admission exactly as `False` does · `demonstration_health` (fraction solved *and* routed through the rung's own dependencies).

**Learning:** `recovered` (a mint behaviourally matches the intended rung) · `junk` (mints nothing intended) · `cascade` (a wrong mint that later mints build on).

**Cost:** `considered` · `first_solution_index` / `cheapest_solution_index` (exact) · `b1` (round-1 width) · `floor tax` (full/pruned, measured) · `b_eff` (fitted per-round growth).

## 10. Pointers

- Format: [LADDER-FORMAT.md](LADDER-FORMAT.md) · Register: [LADDERS.md](LADDERS.md) · Checks: [LINT-CHECKS.md](LINT-CHECKS.md)
- Verdict profile, not a sandwich gate: [CERTIFICATE-PROFILE-2026-07-24.md](CERTIFICATE-PROFILE-2026-07-24.md) · The two cost axes: [BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md)
- Set structure: [LADDER-SET-DESIGN-2026-07-24.md](LADDER-SET-DESIGN-2026-07-24.md) · Comparison licenses: [LADDER-RELATIONSHIPS-2026-07-23.md](LADDER-RELATIONSHIPS-2026-07-23.md)
- Active plans: [MVE-PLAN-2026-07-25.md](MVE-PLAN-2026-07-25.md) · [AL-PLAN-2026-07-23.md](AL-PLAN-2026-07-23.md) · [2026-07-26-AL-PLAN.md](2026-07-26-AL-PLAN.md)
- Run model: [EXECUTION.md](../../EXECUTION.md) · Engine: [ARCHITECTURE.md](../../ARCHITECTURE.md) · Notebooks: [experiments/README.md](../../experiments/README.md)
