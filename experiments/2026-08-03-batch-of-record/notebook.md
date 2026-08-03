# The batch of record, and the first thing it bought (2026-08-03)

The repair for what [2026-08-03-run-store-census](../2026-08-03-run-store-census/notebook.md) diagnosed: no committed ladder report named the runs behind it, no ladder had a single-generation run set, and a full pass over everything ever built was ~34 minutes of compute nobody had spent.

Three pieces of machinery, then the ablation they existed to make possible. The ablation's result is the reason to care: **rung recovery across the batch goes 55/57 to 1/57 under a compression metric that charges definition size** — and the instrument built in step 2 is what makes that readable as "the learner declined" rather than "the learner failed."

Every number below is from a recorded run; the artifacts are re-runnable against the repo.

## What was built

Ordering was forced: provenance is the precondition for the rest.

1. **[`ladders/provenance.py`](../../src/arc_lab/program_search/ladders/provenance.py)** — per-cell `run_id` + run-dir + commit + comparability key, read off each cell's own `runspec.json`. `create_ladder_report` already received every `RunRecord` (`oracle_chain`, `learn`, `off_chain`, `raw_arm.record`) and dropped them on the floor, so this was additive, not plumbing.
2. **[`ladders/recovery.py`](../../src/arc_lab/program_search/ladders/recovery.py)** — `recovered` unchanged; new is _where the pipeline broke_ when it is false: `no-material` / `not-proposed` (proposer reach) / `proposed-not-selected` (governance preference) / `undiagnosed`. Proposals are **recomputed** read-side from the recorded wake programs and per-iteration libraries — the run logs only `proposal_count`, but proposers are pure frozen dataclasses and the trace carries both inputs. No new telemetry, no `run_id` moves.
3. **[`ladders/batch.py`](../../src/arc_lab/program_search/ladders/batch.py)** + `arc-lab run-batch` — the whole set as one pass, with a declared `EXCLUDED` membership, a per-member config-generation check, `--set` for arms, and failure isolation.

Plus one machinery fix that fell out of running it (below): raw-arm reuse.

## Log

### B1 — provenance, and what it could not be built on before

Scanned all 21 committed `report.json` for `run_id` / `run_ids` / `commit` / `run_dir`: **0 of 21** carried any. The staleness guard proposed during planning ("re-derive the hash from the current spec and compare") was therefore unbuildable — there was nothing to compare against.

Driving it on `al21-dag-siblings` showed the property that matters: every cell came back from `20260726_*` at commit `99d38b28`, not that day's HEAD. **The provenance records the run that happened, not the code that read it**, which is what makes hash comparison a real staleness test rather than a tautology.

Design note: `run_dir` stores the directory _name_, never an absolute path — a committed artifact must not carry a developer's home directory. Pinned by a test.

### B2 — the recovery diagnosis, validated against both known ground truths

Not unit-tested against fixtures; driven through the real engine against the two cases the program had already established by hand:

| case | expected mechanism | diagnosis |
| --- | --- | --- |
| `dae9d2b5-half-param` | governance (2026-07-27 audit: `nth(split_h(#0),#1)` offered, `GreedyMDL` discarded) | **`proposed-not-selected (iter 0)`** |
| `al21` + `FrequentSubtree` | proposer reach (mines `walk()[1:]`, root excluded) | **`not-proposed`** |
| `al12-unlearnable` | its own design note: "one demo, so `AntiunifyPairs` has nothing to pair" | **`not-proposed`** |

The third is the strongest of the three: the instrument independently named the mechanism a control was _designed around_, without being told.

### B3 — the batch driver, and a design error it exposed in its first run

First full pass estimated **80–110 minutes**, and it spent its first 5 minutes on `94f9d214-nor-halves:train:raw-arm` at a `considered_limit` of **20,010,480**.

That arm should not have existed. LADDERS.md: _"RQ1 is purchased once per cohort (raw arm on the 4-rung member only); the 2-rung members run `--raw-arm-k 0`."_ The raw arm searches the top task from the bare floor at `d_raw`, so **same task + same floor + same `d_raw` is the same search** — a member's budget changes only its guard. `94f9d214-nor-halves` had never had a raw arm in the entire run history; the driver invented one.

Not merely slow: per-member arms manufacture per-member RQ1 ratios that invite exactly the cross-member comparison the cohort rule forbids. A comparability instrument generating incomparable numbers. Killed and fixed: `RAW_ARM_MEMBERS`, declared with reasons like `EXCLUDED`, plus `--no-raw-arms` for iteration passes.

### B4 — the raw arm's identity is coupled to a measured quantity (machinery fix)

`guard = ceil(k * laddered_marginal / |top tasks|)` — a function of a **measured** cost, so it lands in `Budget` -> `Config` -> `run_id`. Any drift in the chain's cost re-buys the whole enumeration. Already measured, from the census CSV:

| member                 | guards recorded          | spend         |
| ---------------------- | ------------------------ | ------------- |
| `94f9d214-nor-recolor` | 1,201,460 then 5,231,740 | 63s then 291s |
| `fafffa47-nor-recolor` | 1,364,420 then 5,237,270 | 85s then 349s |

2,565,880 candidates of redundant compute, the smaller run wholly contained in the larger.

`dominating_raw_arm()` is a **semantic** cache hit where the content hash cannot see one: a recorded run over the same corpus and same config-minus-guard, stopped no earlier than needed, dominates — and both RQ1 outcomes survive it (censored -> raw exceeds the _larger_ spend, so `>= k` holds a fortiori; solved -> `first_solution_index` is stop-independent).

Verified: one recorded 5.2M run now serves k=2, 5 and 10 instead of three enumerations, and at k=2 it proves `>= 10`, not `>= 2`. It also broke `test_a_censoring_raw_arm_is_a_lower_bound`, correctly — that test fabricates a guard of 1 to force the censor branch, and reuse now serves it the stronger recorded result. `reuse=False` is the affordance for constructing such a scenario.

**Effect: the pass went from a projected 80–110 min to 5.8 min**, with `dae9d2b5-split-recolor`'s 25M-candidate arm — the most expensive cell in the repo — served in **0s**.

### B5 — my generation check was wrong, and the test caught it twice

**First**, an arm test asserted baseline and arm would differ in generation, and failed: a learn-side change moves every `run_id` while touching neither commit nor budget. The learn key was in the per-cell comparability key but not the generation label. Fixed by folding it in _uniformly_ — it is a property of the report, since only `climb/learn` carries one, and comparing per cell would split every report into "the SEARCH cells" and "the LEARN cell" and signal nothing.

**Second**, the first coherent pass flagged **4 of 32** members as multi-generation whose configs were _identical_ and differed only in commit. Commit is now excluded from the key:

> `run_id` is `content_id(config x corpus)` and this codebase is deterministic by invariant (no RNG; frozen specs), so two cells with the same `run_id` are the same computation whichever commit executed them — if that failed, the cache would be unsound and a batch would mean nothing anyway. Keying on commit would flag every report assembled from cache hits across any commit, docs-only included, and a warning that always fires is not a warning.

The same reasoning already applied to the raw-arm exemption. Commits are still recorded per cell (`recorded_commits`) as provenance — how much of a report is cache — never as a verdict. What this consequently does **not** detect is artifact staleness; that is a `run_id` comparison _across_ artifacts, and is now possible for the first time but not yet built.

Also fixed, a rendering conflation: a rejected ladder never climbs, so its climb reading is `n/a`, not `censored` — "never tried, by design" versus "tried and could not tell".

### B6 — the batch of record ([BATCH-OF-RECORD.md](../../docs/abstraction_ladders/BATCH-OF-RECORD.md))

**32 members, one pass, 0 errors, 0 multi-generation, 0.6 min.**

|                               | census, this morning | after  |
| ----------------------------- | -------------------- | ------ |
| Committed reports             | 21                   | **32** |
| With no provenance            | 21 of 21             | **0**  |
| Missing `top_reachable`       | 18 of 21             | **0**  |
| Spanning >1 config generation | every ladder         | **0**  |

The 11 rejections and controls have a `report.json` for the first time. Both known learner failures now appear in committed artifacts automatically (`half-param` -> `proposed-not-selected`; `al12` -> `not-proposed`).

### B7 — the governance arm: 55/57 -> 1/57 ([`arm_vs_record.py`](artifacts/arm_vs_record.py) · [`.out`](artifacts/arm_vs_record.out))

`arc-lab run-batch --set learn.learn_engine.metric=TwoPartMDL` — one command, 32.5 min (every climb re-runs; only chains cache). Manifest: [`arm-twopart-manifest.md`](artifacts/arm-twopart-manifest.md).

- **The wiring assertion holds: 0 members moved certificate or chain-top.** A learn-side change must touch no chain cell; if it had, everything below would be void. This is S15's method, now checked automatically over the whole batch rather than by hand on three ladders.
- **Recovery: 55/57 -> 1/57.** 20 of 21 climbing members lost all recovery; 0 held.
- **There is only ONE failure, and it is at the bottom rung.** Every affected member reads `proposed-not-selected` at its lowest rung. Everything above is cascade — verified directly:

  ```
  al17-shift-frame-tall   mints per iteration: [[]]
    level 1  shift1   proposed-not-selected     <- the only real event
    level 2  frame1   no-material               <- cascade
    level 3  shift2   no-material               <- cascade
    tasks solved per wake: [2]      (one wake, then early stop)
  ```

  Nothing minted -> the library never grows -> `early_stop` after one wake -> higher demos are unreachable from the bare floor. **Reporting "12 members had no material" would have been wrong**: it is 12 cascades from one decline.

- **The single survivor locates the boundary.** `dae9d2b5-split-asym-lean` kept `west`, and all three of its rungs have **identical demo counts (2 each)** — so demo count is not what decided it. `west` = `nth(split_h(g), 0)` recurs as a subterm across more of the retained corpus than `east` does. Under a code charging definition size, that is what pays.

## Findings

1. **0 of 21 committed reports recorded a single `run_id`.** Fixed; 32 of 32 now do, and each report states how many config generations its cells span.
2. **The raw arm's guard is a function of a measured quantity**, so cost drift re-buys the enumeration — measured at 2.57M redundant candidates across two members. A dominating recorded arm is a sound substitute for both RQ1 outcomes; the batch fell from ~80–110 min to 5.8 min.
3. **A batch of record exists**: 32 members, 223 cells, one generation each, zero unexplained gaps.
4. **Under `TwoPartMDL`, rung recovery collapses 55/57 -> 1/57**, from a _single_ mechanism — governance declining the lowest rung — with everything above it cascade.
5. **An abstraction pays for itself on corpus-wide recurrence, not on its own demonstration count** (the one survivor, against siblings with identical demo counts). That sharpens the 2026-07-27 audit's V x M framing into a statement about how the demo corpora are built.

## Interpretation

The arm does **not** show `TwoPartMDL` is wrong or the learner broken. The 2026-07-27 audit already priced the real case and found that at two distinct parameter values with two occurrences each, minting _nothing_ is the DL-optimum. What the arm adds is scale and mechanism: the same verdict, on 20 of 21 climbing members, from one decline per ladder.

The uncomfortable reading, stated plainly: **the batch's headline learnability numbers — 43/43 on the clean set, complete rung recovery at every cut density across three real tasks — hold under a compression metric whose own docstring predicts the hoarding behaviour it exhibits, and do not survive a metric that charges definition size.** That is a finding about the ladders' demonstration corpora, not about the learner: at 2–4 demonstrating programs per rung, no abstraction pays for its own definition.

**But this arm cannot yet establish that**, and the limitation was registered before the run rather than after. A total collapse is equally consistent with `bits_per_primitive = 1.0` being miscalibrated — never swept, and the audit flagged the V=2 corner as sensitive to a 1.0-bit gap. One survivor at the boundary is a lever, not a resolution.

Methodologically, the day repeated the census's own lesson one level down. Three times, a test or a first run caught a defect in reasoning that had already been written down confidently: the raw arm's per-member purchase (contradicting a protocol stated in LADDERS.md), the learn key missing from the generation label, and commit-as-drift. Each was found by _running the thing_, not by review — and the second and third were errors in the very instrument built to catch this class of error.

## The cell matrix ([`ladder_matrix.py`](artifacts/ladder_matrix.py) · [`.out`](artifacts/ladder_matrix.out))

**39 ladders authored · 32 run · 6 probed-only · 0 untouched · 223 cells in the register.**

Cell kinds: `chain/L0..Lk`, `climb/learn`, `climb/train-usefulness`, `climb/transfer`, `off-chain`, `raw-arm`. Two shapes, exactly on the admitted/rejected line — 21 admitted ladders carry 7–10 cells (full chain + all three climb runs + off-chain, with `raw-arm` on 13); 11 rejected carry 2–6 (chain only, since a rejected ladder never pays for learning).

**Gaps, all of them deliberate:**

| gap | count | why |
| --- | --- | --- |
| No climb | 11 | certificate rejected -> learning never paid for, by design |
| No raw arm | 8 | RQ1 purchased once per cohort, by protocol |
| Top unreachable (chain) | 3 | `nor-halves` x2, `al14` — censored, priced at **>30M** |

**The real gaps are one axis up, in arm coverage:**

| axis | sampled |
| --- | --- |
| Metric | `CompressionMetric` 32; `TwoPartMDL` **21** (the climbers; inert elsewhere) |
| Proposer | `AntiunifyPairs` 36; `FrequentSubtree` **4**; `TypeScoped` **3**; `Stitch` **3** |
| `bits_per_primitive` | **0** — never swept |
| Distractors | **0** on every non-control ladder |
| Wake schedule | `full` on all 32 in the register |

So **S15's headline (0/4, 0/5, 0/2) rests on 3 ladders out of 21 climbers** — ~15% coverage on the proposer axis, against 100% on the metric axis as of today.

By role, the 936 runs divide:

```
  454  48.5%  ladder runs NOT cited by the register (arms + superseded history)
  220  23.5%  cited by the register (the batch of record)
  216  23.1%  probe cells
   46   4.9%  non-ladder corpora (datasets, testbeds, studies)
```

Under a quarter of the store is what the register cites. Not waste — arms, probes and pre-batch generations — but the store is ~4x the evidence base, and that is now mechanically attributable because every cited cell names its `run_id`.

## Next

1. **The calibration question, cheaply.** Do not brute-force `bits_per_primitive` as full arms (32.5 min each). Use the audit's own method — price the end states directly under varying `bits_per_primitive` on the real retained programs, pure selector arithmetic in milliseconds — then confirm at one value with a full arm. If the boundary moves smoothly with the parameter it is calibration; if `west` survives across settings while its siblings never do, it is structural.
2. **The proposer axis is the thin one.** 3 of 21 climbers, and it now costs one `--set`.
3. **Artifact staleness detection** is now possible and not built: compare a committed report's recorded `run_id`s against freshly derived ones.
4. Deliberately not taken: whether `ladder_default_config` should adopt `TwoPartMDL`. On this evidence it would zero the register's recovery column, and the honest reading of that is not settled until (1) resolves.
