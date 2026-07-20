# Abstraction Ladder Experiments — design (2026-07-16)

The design snapshot for the **Abstraction Ladder Experiments**: a batch of LEARN experiments measuring whether — and by how much — learned abstractions convert an intractable search into a sequence of tractable ones. This document is the merged output of the 2026-07-16 design sessions; it records the concept, the quantities & metrics, the ladder-construction methodology, the run structure, and the open decisions.

## 1. Core experiment design

- Focus: "Abstraction Ladders" – a series of abstractions that build on each other, where each Rung of the Ladder is a new abstraction that can be learned from the previous Rungs.
  - We may have multiple LEARN runs per Ladder, to measure the impact of different params (eg budget, proposer — §3.2). Varying a _design choice_ (eg the Floor) makes a _different_ Ladder.
  - Each Ladder should consist of:
    - **Floor** (the starting library of primitives)
    - **Top Rung** (solving the target Task)
      - This should be the program that solves the most difficult Task in the Corpus.
      - Inherently, it should be _possible_ for a SEARCH run to get all the way to the Top Rung, without any abstraction learning, but it would be very high search cost.
    - **Bridging Rungs**
      - Each rung in between the Floor and the Top Rung represents "bridging abstractions" that can be learned from the previous Rungs and can help reduce search cost to reach the Top Rung.
      - There should be at least 1 Bridging Rung, but there could be many.
      - Important: For all Bridging Rungs in the Ladder, we must have some set of Tasks whose solution programs demonstrate the use of those abstractions. Otherwise, the Bridging Rung is not learnable.
  - A "jump" is the transition from one Rung to the next Rung in the Ladder (its static and measured sizes: §2).
  - Overall, the goal is to measure:
    - The search cost to go from the Floor to the Top Rung, _without_ any abstraction learning.
    - The search cost to go from the Floor to the Top Rung, _with_ abstraction learning (ie using the Bridging Rungs).
    - Various other metrics/comparisons.

Corpus:

- The Corpus must consist of:
  - **Top Rung Task(s)** – the Task(s) that require the Top Rung program to solve.
    - (At least 1, possibly more.)
  - **Bridging Rung Tasks** – Tasks whose solution programs demonstrate the use of the Bridging Rung abstractions.
    - (At least 2 per Bridging Rung, possibly more.)
      - [A design choice (§3.3) — swept via Ladder families, RQ2.]
  - A small **heldout split** (a few tasks per rung level, excluded from learning) — needed for transfer and the break-even horizon (§3.5).
- Overall, the Tasks should err on the side of being relatively easier, so that the search cost is not too high, and the focus is on the abstraction learning.
  - Likely many synthetic Tasks.
- Some Tasks may be able to be generated from the bridging abstractions.

Batch design:

- Likely 5 to 25 ladders total, ultimately.
  - In order to calculate batch metrics.
- We can likely start with 1 ladder, and go from there.
- Likely: Structure the batch as families that each vary ONE axis (eg height, jump depth, tasks-per-rung), plus short calibration ladders (height 2 — raw cost actually measurable), and possibly 1-2 real-ARC-anchored ladders.
  - (TBD after running the first few Ladders.)
- Each Ladder may have multiple LEARN runs, with different params, to measure the impact of those on the results.

## 2. Definitions

- Core:
  - **Ladder** = A series of abstractions that build on each other, where each Rung of the Ladder is a new abstraction that can be learned from the previous Rungs.
  - **Floor (`L_0`)** = The starting `Library` of primitives, from which the Ladder begins.
  - **Top Rung (rung R)** = The final abstraction that solves the most difficult Task(s) in the Corpus, and is the "goal" of the Ladder.
  - **Bridging Rung / Bridging Abstraction (`r_i`)** = An intermediate abstraction that helps bridge the gap between the Floor and the Top Rung, reducing the search cost to reach the Top Rung.
    - A closed template over `L_{i-1}` (a `TargetAbstraction`), together with its **demonstrating tasks** (>= 2) whose cheapest solutions exercise it.
  - **Demonstration relationships** — a Rung `i`'s Tasks' solution programs stand in two distinct relationships (both stated over `L_{i-1}`, ie pre-mint):
    1. **vs the Rung's library (`L_{i-1}`)** — always _fragment-only_: every solution is a _proper composition_ of existing primitives (a Task whose cheapest solution is a bare primitive belongs to a lower Rung; equivalent to "jump depth >= 2"). Not merely definitional — verified on _retained cheapest_ solutions by the certificate, since it can fail via skip paths.
    2. **vs the Rung's target abstraction** — per Task, either **full-solution** (solution = the template, instantiated) or **fragment** (the template is a proper subprogram of the solution). A Rung carries a _mix_; the mix is a design choice (RQ2). Does not apply to the Top Rung (no target abstraction).
    - This affects which `AbstractionProposer` is required:
      - \>= 2 full-solution tasks ⇒ `AntiunifyPairs` viable
      - fragment occurrences with _identical_ instantiations ⇒ needs at least `FrequentSubtree`
      - fragment occurrences with _varying_ parameters ⇒ needs `StitchProposer`
  - **Jump** = the transition from Rung `i-1` to Rung `i`. Static size: **jump depth** (`d_i`, compositional). Measured size: **jump cost** (`c_i`, considered count).
    - A **double jump** goes from `L_{i-1}` directly to Rung `i+1`, skipping `r_i`. Its depth is computed on the _inlined_ template (rung-`i` call sites expanded) — NOT as `d_i + d_{i+1}`. For the last bridging rung `r_k`, the "rung above" is the Top layer: its double jump is a top reference solution inlined over `L_{k-1}` (the shallowest one, if several).
  - **Fan-in** (of a rung, or of a top reference solution) = the number of calls its template makes to _any_ lower rung's abstraction — not just the rung immediately below — counted with multiplicity; floor primitives don't count. 0 = composes floor material only (typical for `r_1`); 1 throughout the ladder = a pure telescope; > 1 = recombination (the same lower rung twice, or two different ones). Distinct from the rung's **dependency edges** (_which_ lower rungs it references): fan-in is the sum of the edges' multiplicities.
  - **Cumulative Library (`L_i`)** — `L_0 ∪ {r_1..r_i}`.
    - The Cumulative Library at Rung `i` is the set of all primitives available at that Rung, including the Floor and all Bridging Rungs up to `i`.
    - It can be either one of two flavors:
      - **oracle** — `L_i` with the _intended_ rungs gifted;
      - **learned** — whatever sleep actually minted by wake-iteration i. These diverge exactly when learning is imperfect
  - **Ladder height** = The number of Rungs in the Ladder, including the Top Rung.
  - Scope (v1): Rungs are _mintable library abstractions_. Substrate-level mechanisms that yield a similar additive-depth profile without learning (eg parameter-passing higher-order primitives) are out of scope — a deferred contrast arm.

- Search cost metrics (general terms):
  - **Search cost** / **Considered count** = The number of candidate programs considered by the search engine to find a solution program.
    - (_observable; depends on the specific search engine and params_)
    - (_The main currency for measuring search cost._)
    - **cost-to-first-solution** — the considered count paid up to the first solution. Two recorded variants (both derivable from the atoms; headline chosen post-data — §7):
      - **(exact)** — the `candidate_index` at which the first accepted program was absorbed.
      - **(generation-end)** — cumulative considered count at the end of the solve generation. (That generation's best solution is the cheapest of that generation, but not necessarily overall.)
      - (They differ by at most one generation's composed count — but the last generation dominates in the steep-growth regime, so they can diverge substantially.)
    - **cost-to-cheapest-solution** — cumulative considered count, to find the _overall cheapest_ solution program. Can exceed cost-to-first.
    - **cost-paid-full** — total considered count at budget exhaustion. Can exceed cost-to-first / cost-to-cheapest, if _early stop_ is not enabled.
  - **Solve generation** — the 0-indexed composition round at which the first accepted program appeared.
    - (_observable; depends on the specific search engine and params_)
  - **Depth limit (`Budget.depth_limit`)** = the budget's inclusive cap on compositional depth (leaf = 0): a program of depth `d` is reachable iff `d <= depth_limit` — equivalently, the engine runs generations `0..depth_limit` (generation 0 = the round-0 leaves). ONE unit everywhere: program depth, solve generation, and the budget cap all speak it; the engine's internal round count (`depth_limit + 1`) is the only place a `+1` exists.
    - The reference config's value is the **pinned `depth_limit`** — the anchor every sandwich claim (lint + certificate) is stated against.
    - (_a param — `solve generation <= depth_limit` always_)
  - **Compositional depth** = The depth of a program's template expressed over a particular library of primitives.
    - (_static_)

- Search cost metrics (specific to this context):
  - **Raw cost** = The search cost to go from the Floor to solving the Top Rung, without any abstraction learning.
    - **Raw search cost** / **Raw considered count (`c_raw`)** = The observed considered count to solve the Top Rung Task(s), without any abstraction learning.
      - (_usually intractable to measure_)
    - **Raw solve generation (`g_raw`)** = The observed depth to solve the Top Rung Task(s), without any abstraction learning.
      - (_usually intractable to measure_)
    - **Raw compositional depth (`d_raw`)** = The compositional depth of the Top Rung solution program(s), expressed over the Floor's primitives.
  - **Rung cost** = The search cost to go from one Rung `i-1` to Rung `i`.
    - **Rung search cost** / **Rung considered count (`c_i`)** = The observed considered count to solve the Rung `i` Task(s), starting from the cumulative library `L_{i-1}`.
    - **Rung solve generation (`g_i`)** = The observed depth to solve the Rung `i` Task(s), starting from the cumulative library `L_{i-1}`.
    - **Rung compositional depth (`d_i`)** = The compositional depth of Rung `i` solution program(s), expressed over the cumulative library `L_{i-1}`.
  - **Laddered cost** = The search cost to go from the Floor to solving the Top Rung, with abstraction learning (ie using the Bridging Rungs).
    - **Laddered search cost** / **Laddered considered count (`c_l`)** = sum over Rung considered counts
    - **Laddered solve generation (`g_l`)** = sum over Rung solve generations
    - **Laddered compositional depth (`d_l`)** = sum over Rung compositional depths
    - The sums above are the **marginal** accounting. The **end-to-end** laddered cost = total considered count across _all_ wake iterations x _all_ tasks — including full-budget failures on not-yet-reachable tasks and re-searches of already-solved tasks. Both are reported in RQ1 — end-to-end as the achieved value, marginal as the ceiling; their quotient is the **loop-overhead factor**.

- Laddered cost breakdown (everything paid to get from Floor to solved Top Rung, with learning):
  - **Search cost (wake side)** — currency: considered count.
    - **Jump costs proper** — `sum_i cost(rung-i tasks | L_{i-1})`: the irreducible core.
      - **Vocabulary tax** = the increase in a _single task's_ search cost from extra library entries, paid even when the solution doesn't use them (wider round-0 leaf set, more compositions per round). Inherently _inside_ each jump — an attribution view (read off the oracle-chain columns), never an additive term.
      - **Learned-vs-oracle flavor gap** — jumps are actually paid under `L^learned`; specialized/junk mints inflate every later jump relative to the oracle-flavor marginal.
    - **Re-search overhead** = the cost of each wake re-searching every task: full-budget _failures_ on not-yet-reachable tasks (likely the dominant single component) + re-solving already-solved tasks.
    - **Overshoot** — no early stop: every task pays cost-paid-full, not cost-to-solution.
    - **Termination overhead** — _conditional_: one quiet wake pass under `early_stop` (the sleep after the top-solving wake usually still mints something, forcing one more wake before convergence is declared); zero under fixed `iterations = R` (exactly one wake per rung — but that uses mild oracle scheduling knowledge and is brittle to imperfect climbs, so `early_stop` stays the default mode).
  - **Learning cost (sleep side)** — currency: proposal count + antiunify-pair count (wall-clock as telemetry only): proposer work per cycle + governance (MDL evaluation of proposals).
    - Currency conversion: wake and sleep are different units (considered count vs proposal/pair count). For the amortization denominators, sleep cost is converted into considered-count-equivalents via a calibration weight `w`, estimated from wall-clock comparisons and stated per batch. `w` is an explicit assumption — but a defensible one: hardware that speeds up search speeds up learning in roughly the same ratio.
  - Rollups:
    - **Marginal** = jump costs proper only — the idealized bound; achieved only under perfect curriculum + early stop + perfect mints.
    - **End-to-end** = all of the above — the achieved cost.
  - Explicitly excluded (keeps the ratio honest): measurement apparatus (oracle-chain / off-chain / calibration runs); one-time design costs (ladder construction, taskgen, lint); _ongoing_ vocabulary tax on future tasks after the climb (belongs to the break-even horizon, not laddered cost).

- Derived-view terms:
  - **Effective branching factor (`b_eff`)** = the fitted per-generation growth of composed candidates over a run's pre-saturation rounds. A summary statistic per (task, library, budget) cell — not a constant of nature.
  - **Enablement** = tasks solvable under `L_i` but not `L_{i-1}`, at a fixed budget.
  - **Budget compression** = `d_raw` vs `max(d_i)` — the reduction in _required search depth_ to reach the Top Rung.
  - **Validity window** = the inclusive range of `depth_limit` over which the Ladder property holds — lower edge: every jump affordable; upper edge: no (inlined) double jump reachable. Depth-only, hence necessary but not sufficient (the certificate completes it at the reference config). Its _width_ is a per-Ladder robustness property.

### 2.1 Cost model (candidate — to be measured, not assumed)

Let `cost_L(d)` = cumulative considered count to reach composition round `d` under library `L` (measured, per task). The Ladder's central bet, stated without assuming a functional form:

- Raw pays ONE deep term: `cost_{L_0}(inlined Top-Rung depth)`.
- Laddered pays R shallow terms: `sum_i cost_{L_{i-1}}(d_i)` — plus learning cost.

If cost-to-depth grows steeply, the sum of shallow terms is far smaller than the one deep term. A geometric summary (`cost ≈ b_eff^d`) is useful for design-time headroom estimates, but is itself an object of measurement (via the calibration ladders), not an assumption. Two regimes to watch for:

- **Pre-saturation** (pool still growing): steep growth; the ladder buys _cost collapse_.
- **Pool-saturated** (`max_pool` binding): growth flattens; the ladder instead buys _reachability_ — a rung is a round-0 leaf that cannot be evicted.

## 3. Quantities

The experiment is a function: **(design choices x params) → observables**. Shape properties are the statically-known structure of the domain; analysis conventions and arms govern how outputs may be compared.

### 3.1 Ontology: categories of quantities

Every quantity in these experiments belongs to one category. The test: _what do you have to do to learn its value?_

| # | Category | What it is | Lives in | Known via | Used as |
| --- | --- | --- | --- | --- | --- |
| 1 | **Params** (§3.2) | Machinery knobs | `Config` | chosen | sweep axes (direct, per cell) |
| 2 | **Design choices** (§3.3) | The Ladder's identity | `LadderSpec` | chosen | sweep axes (via Ladder families) |
| 3 | **Shape properties** (§3.4) | Static deriveds of (design, reference config) | `LadderSpec` (computed fields) | lint | stratification axes |
| 4 | **Observables** (§3.5) | Runtime quantities: atoms → views | run records | execution | outcomes |
| 5 | **Analysis conventions** (§3.6) | Read-side choices | reports | declared | interpretation rules |
| 6 | **Arms** (§3.7) | A run-cell's epistemic role | derived from the cell, recorded first-class | derivation | comparison legality |

Notes:

- A Ladder run-cell = `LadderSpec` x `Config` — mirroring `RunSpec = Config x Corpus`: category 1 is the `Config` factor, category 2 the `LadderSpec` factor.
- The categories recur at three **scopes**: cell (one run), Ladder, batch (family structure/membership = design choices at batch scope; batch metrics = observables at batch scope).
- **Budget's dual role.** Budget is a param (category 1) — but the Ladder's validity claims are claims _about_ budgets. The Ladder doesn't own a budget; it owns two claims recorded in its spec: the pinned **reference config** (the anchor at which lint + certificate assert the tractability sandwich) and the **validity window** (a shape property in `depth_limit` units). Sweeping budget never changes the Ladder — it changes which claim-region the cell sits in, and thus its arm: inside the window ⇒ honest cell; below ⇒ stall regime; above ⇒ rung-necessity probe.
  - Budget's components play different roles: `depth_limit` = the horizon (the window's axis); `max_pool` = the regime selector (§2.1); `max_arity` = a branching modifier. The static window is depth-only — necessary, not sufficient; the empirical certificate at the reference config covers the rest.
- Deliberate absences: **replicates/seeds** (no RNG anywhere — every cell is one exact point; no statistics machinery needed beyond aggregation) and **invariants** (the fixed background: determinism, the goal test, the blindness seams — rung annotations recorded but solver-invisible — which must never migrate into category 1).
- Terminology: "metaparameter" is retired — it blurred categories 2 and 3.

### 3.2 Params

Used by: one **reference config** chosen per Ladder (pinned in the `LadderSpec` — §3.1); swept directly, per cell; recorded per cell.

- budget.depth_limit
- budget.max_arity
- budget.max_pool
- beam_width (if `BeamBottomUpSearchEngine`)
- constant_sources
- function_hole_fill_mode
- polymorphism_instantiation
- unpinned_type_var_mode
- function_sample_size
- proposer (`AntiunifyPairs` / `FrequentSubtree` / `StitchProposer`)
- governance (`GreedyMDL` threshold)
- `LearnSpec.iterations`
- (RQ3, once built: what-AF-sees options — top-K retention, fragment selectors / partial-credit scoring)

Sweep policy: budget sweeps get arm labels from validity-window position (§3.1): inside = honest cells; below = stall regime; above = rung-necessity probes.

### 3.3 Design choices

Used by: constructed via the methods (§5.1); fixed per Ladder — they _are_ the Ladder's identity, so varying one makes a _different_ Ladder; swept across Ladders via families.

- What the Floor is
- What the Top Rung is
- The Rungs: how many, which templates
- Corpus design:
  - How many different programs per Bridging Rung?
  - How many Tasks per Bridging Rung?
  - Per-rung relationship-(2) mix: how many demonstrating Tasks are full-solution vs fragment (§2)? Plus fragment-parameter variability — coupled to the `AbstractionProposer` choice via §2's mapping.
  - How many different programs at the Top Rung?
  - How many Tasks at the Top Rung?
  - The heldout split (which tasks, how many per rung level)
- Are only next-Rung Tasks included vs all Tasks?
  - (Boundary case: as different corpora this is a design choice; as a per-iteration scheduler it is machinery — an oracle-schedule arm, §3.7.)

### 3.4 Shape properties

Used by: computed + recorded by the lint; verified empirically by the certificate; the batch's **stratification** axes — not settable, achieved via design.

- height
- raw total depth (`d_raw`)
- `d_i` profile (average / max jump depth)
- inlined double-jump depths
- per-rung fan-in
- validity window (and its width)
- MDL break-even margins

### 3.5 Observables (atoms → views)

Discipline: **record atoms exhaustively at run time; every named metric is a read-side view** computed afterward (`analyze-run` / report style). The primary derived object is the **cost matrix** — cost(task, library, budget) over the oracle-chain columns plus the learned trajectory's iterations. A new view never requires a re-run.

Atoms (recorded per run x task):

- solved?, solve generation
- per-generation funnel (composed / errored / pruned / deduped / entered_pool / displaced / evicted; pool sizes)
- outcome partition, total + per-primitive
- cost-to-first / cost-to-cheapest / cost-paid-full
- accepted program + its primitive keys
- sampled/captured programs (the reservoirs — these observe later-evicted candidates too)
- per-iteration LEARN trace: library before/after, mints (template, size, MDL gain), solved-task set
- the cell's **arm** (§3.7) — derived from the cell's contents, recorded first-class
- sleep-cost counters: proposal count; antiunify-pair count

Views (read-side, per Ladder):

- **Jump cost / double-jump cost** per rung — each in both **oracle** and **learned** flavors; their divergence isolates learner imperfection.
- **Marginal rung value** = cost(rung-`i+1` tasks | `L_{i-1}`) / cost(rung-`i+1` tasks | `L_i`) — what rung `i` bought. Usually a lower bound (censored numerator).
- **Vocabulary tax** — same tasks, bigger vs smaller oracle libraries (matrix column deltas).
- **Enablement**; **budget compression** (§2).
- **`b_eff` per (library, budget) cell** — watch it grow with library size.
- **Climb trace** — per iteration: library size, newly-solved tasks by rung level, mints, stall iteration.
- **Rung recovery table** — intended rung → minted at which iteration → grade: exact / behavioral / specialized / missed.
- **False mints** — mints matching no intended rung; count, plus whether they get _used_ downstream.
- **Demonstration health** — per rung: fraction of demonstrating tasks whose retained cheapest solution structurally contains the rung template. (Early warning: the cost-to-first vs cost-to-cheapest gap.)
- **Solution routing** — does the Top-Rung solution actually route through the rungs?
- **"Was it worth it?"** — within-corpus: the amortization ratio (RQ1); across-corpus: **break-even horizon** = learning overhead / per-task savings on _heldout_ top-level tasks (how many future tasks at that level justify the ladder).
- Maybe: cross-analysis by primitive types/bundles (free from the per-primitive partition).
- EVENTUALLY (RQ3): views conditioned on what programs/fragments get seen by abstraction formation.
  - (Resolved Q: a top-K non-solution Grid→Grid selector ranked by cheapness WOULD flood with trivia like `Input()` — a fragment arm needs a _selection policy_ (size floor + signature dedup + type filter, or partial-credit scoring). No `max_pool` change needed: the sampling reservoirs already observe candidates at absorption, including later-evicted ones.)

### 3.6 Analysis conventions

Used by: declared once (per batch), applied at read time; never swept, never measured.

- The calibration weight `w` (sleep → wake currency conversion — §2).
- The headline cost-to-first variant (exact vs generation-end — §2, §7).
- Aggregation rules (per rung: sum for cost accounting; per-task values retained for variance).

### 3.7 Arms

Used by: derived from a cell's contents; recorded first-class (§3.5); gate which cells may legitimately enter which comparisons.

- **honest climb** — the LEARN run: learned libraries, full corpus, no scheduling knowledge.
- **oracle-library** — gifted `L_i` SEARCH runs (the oracle chain).
- **oracle-schedule** — curriculum / fixed `iterations = R` variants (scheduling knowledge injected).
- **raw-censored baseline** — Floor searches on higher-rung tasks (unsolved at budget ⇒ lower bounds).
- **calibration** — short Ladders where raw cost is actually measurable.

Comparison legality (examples): the end-to-end amortization ratio takes its numerator from raw-censored / calibration arms and its denominator from the honest arm; marginal rung value compares adjacent oracle-library columns; the learned-vs-oracle gap compares honest vs oracle-library at the same cell. An oracle-arm number must never be quoted as an achieved result.

## 4. Core research questions

### RQ1 – Quantify the amortization: Compare raw cost vs laddered cost

- To what extent does the Ladder impact the search cost to reach the Top Rung?
- Overall: Is it "worth it"?
- Amortization ratio, computed in BOTH accountings:
  - **Marginal ratio** = (raw cost) / (marginal laddered cost + learning cost) — the _ceiling_: what the ladder concept could deliver with perfect scheduling, stopping, and mints.
  - **End-to-end ratio** = (raw cost) / (end-to-end laddered cost + learning cost) — the _achieved_ value with today's loop mechanics.
  - Their quotient = the **loop-overhead factor**, decomposable along the laddered-cost breakdown (§2): re-search + overshoot + termination + learned-vs-oracle gap. (Raw cost cancels, so the quotient is exact even when both ratios are censored lower bounds.)
  - (Vocabulary tax and re-search overhead live _inside_ the denominators — no separate terms. Learning cost enters in considered-count-equivalents via the calibration weight `w` — §2, §3.6.)
- Secondary: characterize `cost_L(d)` itself (shape; where it saturates), via the calibration ladders.

### RQ2 – Quantify the effects on the amortization of params and design choices

- How do the RQ1 metrics (both ratios, the loop-overhead factor, `b_eff`) respond along each axis?
  - Axes: params (§3.2, swept directly per cell) and design choices (§3.3, swept via Ladder families); results stratified by shape properties (§3.4).
- Sweep rationale (approximate; itself checkable from the sweep data): params mostly move the _cost-per-depth_; design mostly moves the _depth profile_. Known exceptions move both (the Floor; `constant_sources`).

### RQ3 – Quantify the effects on the amortization of what programs/fragments get seen by abstraction formation

- We run the LEARN runs with different machinery params (§3.2, once built) for _what programs/fragments get seen by abstraction formation_, and we cross-analyze the results.
  - OPTION: 0-1 solution programs per task. (_how it works currently_)
  - OPTION: Up to K solution programs per task.
  - OPTION: Up to K non-solution, Grid→Grid programs per task.
  - OPTION: Up to K non-solution, non-Grid→Grid programs per task.
  - OPTION: Solution sub-programs (from lambda synthesis)
- (Possibly also things like distractors, shared structure, weaker per-rung task design, etc.)

## 5. Methodology

### 5.1 Ladder construction methodology

Two construction methods:

1. **Anchored bisection**: Adding a Rung in the _middle_ of a Ladder
   - Start with (1) a Floor and (2) a Ladder with at least 1 Rung on top of that Floor.
   - Choose (3) a Rung in the Ladder to add a new Rung below it.
   - Derive:
     - (4) a new, "mid-level" abstraction that can be learned from the Rung/Floor immediately below, and that can be used to help reduce search cost to reach the Rung immediately above.
     - (5) the new Rung's demonstrating programs — each relating to the abstraction as full-solution or fragment (relationship (2), §2); the mix is a design choice.
     - (6) 2+ Tasks where the solution is one of those programs.
2. **Forward extension**: Adding a Rung to the _top_ of a Ladder
   - Start with (1) a Floor and (2) an abstraction that's able to be built on/expressed with that Floor.
   - Derive:
     - (3) the abstraction's demonstrating programs — full-solution and/or fragment (relationship (2), §2); the mix is a design choice; and
     - (4) 2+ Tasks where the solution is one of those programs.
       - (Tasks later added _above_ this Rung will use it as a fragment automatically — relationship (1).)

Notes:

- Only method (1) connects a _designated_ Floor to a _designated_ Top Rung; method (2) grows upward to wherever it lands.
- Overall, ideally, the Ladders should "make sense" (I think this will happen naturally if we do (1) and (2) above, but we should keep an eye on it).
- Ideally:
  - The search cost for each jump (from the Floor/each Rung to the Rung above) should be _tractable_ at the **reference config** (§3.1) — with headroom, since the same jump depth costs more at later iterations as the library grows.
  - The search cost for a double-jump (from the Floor/each Rung to the Rung 2 above) should be less tractable.
    - Checked statically on the _inlined_ double-jump depth (§2), and confirmed empirically by the oracle chain: `L_{i-1}` should solve zero rung-`i+1` tasks. (The empirical check also catches _skip paths_ — unintended shortcut solutions the static check can't see.)
    - Both claims are anchored at the reference config; outside the **validity window** they deliberately lapse (§3.1).
- Log failed bisections (no viable mid-rung found for a jump) as findings, noting whether candidates failed as _not learnable from below_ or _not useful for above_.

### 5.2 Run structure per Ladder

A ladder with R rungs (rung R = Top), at one `Config` cell (§3.1):

- **1 LEARN run** — the climb itself (wake-sleep; `iterations ≥ R+1` headroom; `early_stop` on).
- **R−1 oracle SEARCH runs** — Libraries `L_1` .. `L_{R-1}`, gifted, over the **full corpus**, at the **same wake budget** (or the columns aren't comparable).
  - (`L_0` comes free — but **not** as a separately-cached run. `execute.py`'s LEARN branch records iteration 0's wake _inline_ in the LEARN run's trace (keyed `iter-0/<task_id>`), never as a standalone `run_id`, so no Floor SEARCH run cache-collides with it. Instead the **`L_0` column is read from the LEARN run's iteration-0 wake row**, which carries per-task `search_stats` in the identical shape a SEARCH run records (considered / outcomes / by_primitive / solved_at_generation / — once added — the per-generation funnel and solution sink), plus the solved set, accepted programs, and iter-0 samples/capture. Iteration 0 always searches every task under the Floor (`solutions` starts empty regardless of `reset_programs_each_wake`). Verified against `execute.py::_wake`; the climb-trace report extracts it, no extra run.)
  - (The `L_0` column doubles as the censored raw baseline on every higher-rung task — free.)
- **1 off-chain SEARCH run** — Floor + Top-Rung-only
  - To answer: Do intermediate rungs matter for the top task, or only the final abstraction?
  - (Optional, but cheap.)

### 5.3 Approaches for measuring / estimating the raw cost

Actually measuring the total raw search cost will be often very intractable.

However, we may be able to estimate it.

- **Based on compositional depth**: The compositional depth of the Top Rung solution program(s), expressed in terms of the Floor's primitives, gives an _upper bound_ on the _solve generation_.
  - (Caveats: assumes reachability — pool eviction can push a program to unsolved even within `depth_limit`; and the generation-to-depth correspondence breaks on floors with lambda synthesis, whose bodies are built in descended sub-searches.)
  - However, to estimate the _search cost_ (ie the considered count), we would need to estimate the average _branching factor_ across the generations, which we may be able to estimate via:
    - **Calibration ladders**: include short ladders where the raw cost is measurable, giving exact ratios that anchor everything else.
    - **Extrapolated baselines**: fit per-round growth from the rounds the raw run does complete, extrapolate to the known total depth of the raw solution.
- **Censored bounds**: if we do any actual raw (non-laddered) search attempts, we can report "≥ N considered, unsolved" (as a lower bound).

## 6. Machinery implementation checklist

Machinery that needs to be implemented in order to run the experiments:

1. Serialize the per-generation funnel into the run record (currently logging-only).
2. Expose accepted candidates' `candidate_index` per task (cost-to-first / cost-to-cheapest).
3. `LadderSpec` — generalizes `StudySpec`: leveled `TargetAbstraction`s, per-task rung annotation as solver-invisible meta, the oracle-chain grid; pins the **reference config** (§3.1); recorded shape metadata (§3.4: height, `d_i` profile, per-rung fan-in, per-rung relationship-(2) mix, validity window, construction method).
4. Ladder Linter (a static check that a Ladder/`LadderSpec` is well-formed).
   - Checks:
     - Overall `LadderSpec` is well-formed.
     - All templates are well-typed over `L_{i-1}`.
     - Each Rung's compositional depth <= the pinned `depth_limit` (§2).
     - Raw compositional depth > the pinned `depth_limit`.
     - Double-jump (_inlined_) depth > the pinned `depth_limit`, per consecutive pair.
     - Each Rung has >= 2 demonstrating tasks.
     - Each Task has >= 2 train examples.
     - Background-within/target-across: for each argument position of each rung template, classify it as derived or free, and apply the corresponding rule — derived ⇒ varies within-task; free ⇒ fixed within-task, varied across demonstrating tasks.
     - Each Task's train examples have within-task variation (killing literal shortcuts).
     - MDL break-even check.
     - Task collision check: no shallower program coincides with the intended solution on all train examples (checkable against the cheap end of the program space).
     - Compute + record the validity window (§3.1).
5. Ladder certificate (read-side, over the oracle-chain runs): each jump tractable in fact; zero skip paths (`L_{i-1}` solves no rung-`i+1` task); demonstration health. Gates a ladder's admission to the batch.
6. Climb-trace report (read-side, over the LEARN trace + oracle-chain records).
7. Sleep-cost counters
8. `taskgen` generators for ladder #1.

**Deferred (later phases):**

- Needed for RQ3:
  - top-K solution retention
  - fragment selectors and/or partial-credit scoring
- `max_considered` budget cap (would make censored baselines and cost-matched controls much cleaner)
- early-stop (`stop_after_solutions`)

## 7. Open decisions

- **Ladder #1.** Proposal: height 3, synthetic anchor, built by method (1).

Resolved:

- **Rung necessity — RESOLVED (2026-07-17).** Necessity is budget-relative, so both: enforce the full sandwich strictly at the **reference config** (lint + certificate), and treat necessity as an _observable_ everywhere else — budget sweeps outside the **validity window** are legitimate cells whose arm is relabeled (stall regime below; rung-necessity probe above), never Ladder defects. (§3.1)
- **cost-to-first granularity — RESOLVED (2026-07-17).** Record both variants (§2): **exact** (candidate-index) and **generation-end** (funnel-only) — both derive from already-planned atoms. Choose the headline after seeing how far they diverge (the last generation dominates in the steep-growth regime, so divergence is expected and informative).
- **Demonstration-shape default — RESOLVED (2026-07-17).** Framed via the two demonstration relationships (§2): relationship (1) is always fragment-only by definition; relationship (2) is the free choice. Early experiments: full-solution only for relationship (2). Later: fragment mixes as an explicit dimension/family, tracking the per-rung mix, with the proposer mapping (§2) as a coupled param.

---
