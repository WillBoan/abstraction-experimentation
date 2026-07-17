# Abstraction Ladder Experiments — design (2026-07-16)

The design snapshot for the **Abstraction Ladder Experiments**: a batch of LEARN experiments measuring whether — and by how much — learned abstractions convert an intractable search into a sequence of tractable ones. This document is the merged output of the 2026-07-16 design sessions; it records the concept, the metrics, the ladder-construction methodology, the run structure, and the open decisions.

## 1. Core experiment design

- Focus: "Abstraction Ladders" – a series of abstractions that build on each other, where each Rung of the Ladder is a new abstraction that can be learned from the previous Rungs.
  - We may have multiple Learn runs per Ladder, if we want to measure the impact of different parameters/metaparameters (eg budget, floor, etc).
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
      - [This could be a metaparameter: Number of Tasks per Bridging Rung.]
  - A small **heldout split** (a few tasks per rung level, excluded from learning) — needed for transfer and the break-even horizon (§5.2).
- Overall, the Tasks should err on the side of being relatively easier, so that the search cost is not too high, and the focus is on the abstraction learning.
  - Likely many synthetic Tasks.
- Some Tasks may be able to be generated from the bridging abstractions.

Batch design:

- Likely 5 to 25 ladders total, ultimately.
  - In order to calculate batch metrics.
- We can likely start with 1 ladder, and go from there.
- Likely: Structure the batch as families that each vary ONE axis (eg height, jump depth, tasks-per-rung), plus short calibration ladders (height 2 — raw cost actually measurable), and possibly 1-2 real-ARC-anchored ladders.
  - (TBD after running the first few Ladders.)
- Each Ladder may have multiple Learn runs, with different parameters/metaparameters, to measure the impact of those on the results.

## 2. Definitions

- Core:
  - **Ladder** = A series of abstractions that build on each other, where each Rung of the Ladder is a new abstraction that can be learned from the previous Rungs.
  - **Floor (`L_0`)** = The starting `Library` of primitives, from which the Ladder begins.
  - **Top Rung (rung R)** = The final abstraction that solves the most difficult Task(s) in the Corpus, and is the "goal" of the Ladder.
  - **Bridging Rung / Bridging Abstraction (`r_i`)** = An intermediate abstraction that helps bridge the gap between the Floor and the Top Rung, reducing the search cost to reach the Top Rung.
    - A closed template over `L_{i-1}` (a `TargetAbstraction`), together with its **demonstrating tasks** (>= 2) whose cheapest solutions exercise it.
  - **Jump**
  - **Cumulative Library (`L_i`)** — `L_0 ∪ {r_1..r_i}`.
    - The Cumulative Library at Rung `i` is the set of all primitives available at that Rung, including the Floor and all Bridging Rungs up to `i`.
    - It can be either one of two flavors:
      - **oracle** — `L_i` with the _intended_ rungs gifted;
      - **learned** — whatever sleep actually minted by wake-iteration i. These diverge exactly when learning is imperfect
  - **Ladder height** = The number of Rungs in the Ladder, including the Top Rung.

- Search cost metrics (general terms):
  - **Search cost** / **Considered count** = The number of candidate programs considered by the search engine to find a solution program.
    - (_observable; depends on the specific search engine and params_)
    - (_The main currency for measuring search cost._)
    - **cost-to-first-solution** — cumulative considered count, at the end of the generation where the first solution program is found. (That program is guaranteed to be the cheapest of that generation, but not overall.)
    - **cost-to-cheapest-solution** — cumulative considered count, to find the _overall cheapest_ solution program. Can exceed cost-to-first.
    - **cost-paid-full** — total considered count at budget exhaustion. Can exceed cost-to-first / cost-to-cheapest, if _early stop_ is not enabled.
  - **Solve generation** — the 0-indexed composition round at which the first accepted program appeared.
    - (_observable; depends on the specific search engine and params_)
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
    - **Rung search cost** / **Rung considered count (`c_i`)** = The observed considered count to solve the Rung `i` Task(s), starting from Rung `i-1`'s library.
    - **Rung solve generation (`g_i`)** = The observed depth to solve the Rung `i` Task(s), starting from Rung `i-1`'s library.
    - **Rung compositional depth (`d_i`)** = The compositional depth of Rung `i` solution program(s), expressed over Rung `i-1`'s library.
  - **Laddered cost** = The search cost to go from the Floor to solving the Top Rung, with abstraction learning (ie using the Bridging Rungs).
    - **Laddered search cost** / **Laddered considered count (`c_l`)** = sum over Rung considered counts
    - **Laddered solve generation (`g_l`)** = sum over Rung solve generations
    - **Laddered compositional depth (`d_l`)** = sum over Rung compositional depths

- Ladder cost metrics:
  - **Learning cost** = Costs associated with running the learning side of the loop, to actually learn the bridging abstractions.
  - **Vocabulary tax** = The cost of having a larger library of primitives, which increases the search space and therefore the search cost. This is a cost that is paid on every Task, even if the new primitives are not used in the solution program.
    - (This should be subsumed within the Laddered search cost.)

## 3. Core research questions

### RQ1 – Quantify the amortization: Compare raw cost vs laddered cost

- To what extent does the Ladder impact the search cost to reach the Top Rung?
- Overall: Is it "worth it"?
- Amortization ratio = (raw cost) / (laddered cost + learning cost)

### RQ2 – Quantify the effects on the amortization of various params/metaparams

- Params:
  - budget.max_depth
  - budget.max_arity
  - budget.max_pool
  - beam_width (if `BeamBottomUpSearchEngine`)
  - constant_sources
  - function_hole_fill_mode
  - polymorphism_instantiation
  - unpinned_type_var_mode
  - function_sample_size
- Core metaparams:
  - What the Floor is
  - What the Top Rung is
  - number of bridging rungs
  - raw total depth
  - average jump depth
  - max jump depth
- Other metaparams:
  - corpus size/design
    - How many different programs per Bridging Rung?
    - How many Tasks per Bridging Rung?
    - How many of the Bridging Rung Tasks are full-solution vs fragment-only?
    - How many different programs at the Top Rung?
    - How many Tasks at the Top Rung?
  - Are only next-Rung Tasks included vs all Tasks?

### RQ3 – Quantify the effects on the amortization of what programs/fragments get seen by AF

- We run the LEARN runs with different metaparams for _what programs/fragments get seen by AF_, and we cross-analyze the results.
  - OPTION: 0-1 solution programs per task. (_how it works currently_)
  - OPTION: Up to K solution programs per task.
  - OPTION: Up to K non-solution, Grid→Grid programs per task.
  - OPTION: Up to K non-solution, non-Grid→Grid programs per task.
  - OPTION: Solution sub-programs (from lambda synthesis)
- (Possibly also things like distractors, shared structure, weaker per-rung task design, etc.)

## 4. Methodology

## 4.1 Ladder construction methodology

Two construction methods:

1. Adding a Rung to the top of a Ladder
   - Start with (1) a Floor and (2) an abstraction that's able to be built on/expressed with that Floor.
   - Derive:
     - (3) 1+ programs that use that abstraction as _part_ of it (though not all of it); and
     - (4) 2+ Tasks where the solution is one of those programs.
2. Adding a Rung in the middle of a Ladder
   - Start with (1) a Floor and (2) a Ladder with at least 1 Rung on top of that Floor.
   - Choose (3) a Rung in the Ladder to add a new Rung below it.
   - Derive:
     - (4) a new, "mid-level" abstraction that can be learned from the Rung/Floor immediately below, and that can be used to help reduce search cost to reach the Rung immediately above.
     - (5) 1+ programs that use that new abstraction.
       - The abstraction could be the _full_ program; or it could be a _fragment_ of the full program.
         - [And we should maybe track this, as a metaparameter: "How many of the Bridging Rung Tasks are full-solution vs fragment-only?"]
     - (6) 2+ Tasks where the solution is one of those programs.

Notes:

- If we start with a Floor and a Top Rung, and we repeatedly do either (1) or (2), we will end up with a Ladder.
- Overall, ideally, the Ladders should "make sense" (I think this will happen naturally if we do (1) and (2) above, but we should keep an eye on it).
- Ideally:
  - The search cost for each jump (from the Floor/each Rung to the Rung above) should be _tractable_.
  - The search cost for a double-jump (from the Floor/each Rung to the Rung 2 above) should be less tractable.

## 4.2 Run structure per Ladder

A ladder with R rungs (rung R = Top), at one (params, budget) cell:

- **1 LEARN run** — the climb itself (wake-sleep; `iterations ≥ R+1` headroom; `early_stop` on).
- **R−1 oracle SEARCH runs** — Libraries `L_1` .. `L_{R-1}`, gifted, over the **full corpus**, at the **same wake budget** (or the columns aren't comparable).
  - (`L_0` comes free: iteration 0's wake _is_ a Floor search over the corpus; via content-hashed caching its recorded run should coincide with the L_0 column.)
- **1 off-chain SEARCH run** — Floor + Top-Rung-only
  - To answer: Do intermediate rungs matter for the top task, or only the final abstraction?
  - (Optional, but cheap.)

## 5. Metrics

- For each floor/rung:
  - Library size
  - Metrics with learning:
    - Jump depth to the next rung (minimum/actual)
    - Double jump depth (with learning)
    - Candidate count
    - Candidate count per generation
    - Program outcomes
    - Learning metrics
  - Metrics without learning:
    - Double jump depth (without learning)
    - Candidate count
    - Composed count per generation
    - Program outcomes
  - Double jump with/without learning ratios:
    - Double jump depth ratio
    - (Ratios for other search thoughts)
- For the overall ladder:
  - Total search metrics:
    - Total depth (without learning)
      - (Note: This may be difficult to measure due to intractability; but we can maybe estimate it, eg based on the compositional depth of the Top-Rung solution program when expressed in terms of the Floor's primitives. Or we could do some (small) Ladders where we actually measure it.)
    - Total depth (with learning)
    - Total depth ratio (with learning / without learning)
    - Enablement (assuming a particular budget)
  - Total learn metrics:
  - Metrics for “learn cost increase” / “search cost decrease” (determining “Was it worth it?”)
    - Likely depends on the task counts
- Maybe: Cross-analysis by primitive types/bundles
- EVENTUALLY: Cross-analysis with settings for what programs/fragments get seen by AF
  - OPTION: 0-1 solution programs per task.
  - OPTION: Up to K solution programs per task.
  - OPTION: Up to K non-solution, Grid→Grid programs per task.
    - Q: Would this capture trivial programs, like “Input()”?
    - We might have to adjust the max_pool functionality for this.
  - OPTION: Up to K non-solution, non-Grid→Grid programs per task.
  - OPTION: Solution sub-programs (from lambda synthesis)

### 5.1 Sleep-cost metrics

- proposal count
- antiunify-pair count

### 5.2 Approaches for measuring / estimating the raw cost

Actually measuring the total raw search cost will be often very intractable.

However, we may be able to estimate it.

- **Based on compositional depth**: The compositional depth of the Top Rung solution program(s), expressed in terms of the Floor's primitives, gives an _upper bound_ on the _solve generation_.
  - However, to estimate the _search cost_ (ie the considered count), we would need to estimate the average _branching factor_ across the generations, which we may be able to estimate via:
    - **Calibration ladders**: include short ladders where the raw cost is measurable, giving exact ratios that anchor everything else.
    - **Extrapolated baselines**: fit per-round growth from the rounds the raw run does complete, extrapolate to the known total depth of the raw solution.
- **Censored bounds**: if we do any actual raw (non-laddered) search attempts, we can report "≥ N considered, unsolved" (as a lower bound).

## 6. Machinery implementation checklist

Machinery that needs to be implemented in order to run the experiments:

1. Serialize the per-generation funnel into the run record (currently logging-only).
2. Expose accepted candidates' `candidate_index` per task (cost-to-first / cost-to-cheapest).
3. `LadderSpec` — generalizes `StudySpec`: leveled `TargetAbstraction`s, per-task rung annotation as solver-invisible meta, the oracle-chain grid.
4. Ladder Linter (a static check that a Ladder/`LadderSpec` is well-formed).
   - Checks:
     - Overall `LadderSpec` is well-formed.
     - All templates are well-typed over `L_{i-1}`.
     - Each Rung's compositional depth ≤ wake budget.
     - Raw compositional depth > wake budget.
     - Each Rung has >= 2 demonstrating tasks.
     - Each Task has >= 2 train examples.
     - Background-within/target-across: for each argument position of each rung template, classify it as derived or free, and apply the corresponding rule — derived ⇒ varies within-task; free ⇒ fixed within-task, varied across demonstrating tasks.
     - Each Task's train examples have within-task variation (killing literal shortcuts).
     - MDL break-even check.
5. Climb-trace report (read-side, over the LEARN trace + oracle-chain records).
6. Sleep-cost counters
7. `taskgen` generators for ladder #1.

**Deferred (later phases):**

- Needed for RQ3:
  - top-K solution retention
  - fragment selectors and/or partial-credit scoring
- `max_considered` budget cap (would make censored baselines and cost-matched controls much cleaner)
- early-stop (`stop_after_solutions`)

---
