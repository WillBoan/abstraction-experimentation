# Census of the run store: what we have actually run (2026-08-03)

> **Reviewed interpretation (2026-08-12).** This is a read-side audit of the store as it existed on 2026-08-03. Its provenance defects remain historical facts, but later re-baselining and the generated [batch of record](../../docs/abstraction_ladders/BATCH-OF-RECORD.md) changed the current state. In particular, F4 must not be read as saying the current findings rest on an unreadable format. Old experiments do not acquire modern `RunSpec` identity retroactively. See the [reviewed synthesis](../../EXPERIMENTS.md).

A planning question — "what are the best next experiment runs?" — that turned into an audit when
the planning kept having to be done from prose. `LADDERS.md` said which ladders ran; `EXPERIMENT_LOG.md`
says what they showed. Neither is derived from `runs/`. This walks the store itself.

The intent was to size the next batch. What it found is that **the batch cannot currently be sized,
verified, or reproduced from the artifacts**, because no committed report records which runs produced
it — and that this, not compute and not ladder design, is what every retraction of the last week has
in common.

Read-side only. No searches were run; nothing under `runs/` was written or deleted.

## Why it needed doing

The last week produced four retractions ([mve-batch-analysis](../2026-07-27-mve-batch-analysis/notebook.md),
the loop-overhead invalidation, the granularity curves, the
[census calibration](../2026-07-27-census-calibration/notebook.md)). Each was found by a different
accident. The recurring shape, in that last notebook's words: _"the data existed, nothing compared it
to the claim."_ `runs/` is 797 MB of exactly that data, and no instrument had ever read across it.

`runs/` is a gitignored regenerable cache, so there is also no durable record of what was ever run
except the runs themselves. That makes the flat census below the only committed artifact of the
program's execution history.

## Method

Two scripts, both walking every run dir under `runs/`, parsing `runspec.json` (identity, full
`Config`, corpus, commit, timestamp) and `results.json` (completion, solved, considered, censoring,
wall clock).

- [`run_census.py`](artifacts/run_census.py) · [`.out`](artifacts/run_census.out) —
  classifies each run (kind / ladder / arm / run type / budget + engine + learn fingerprints) and
  emits a flat [`run_census.csv`](artifacts/run_census.csv) plus ten rollups.
- [`run_integrity.py`](artifacts/run_integrity.py) · [`.out`](artifacts/run_integrity.out) —
  the four integrity questions: single-generation coherence, double-paid cells, pre-`RunSpec` runs,
  artifact provenance.
- [`batch_cost_estimate.py`](artifacts/batch_cost_estimate.py) · [`.out`](artifacts/batch_cost_estimate.out) —
  what one full pass per ladder would cost, taken from each ladder's largest coherent run group.

Run classification comes from `corpus_name`, which turns out to already encode it:
`probe:<ladder>:<library>[:pruned]:<task>` for probe cells, `<ladder>:train|:heldout[:raw-arm]` for
ladder cells, bare dataset/testbed names otherwise.

## The store, in one table

| | |
| --- | --- |
| recorded runs (with `runspec.json`) | **811** |
| pre-`RunSpec` run dirs (no runspec) | 34 |
| ladder-corpus runs · probe cells · other | 549 · 219 · 43 |
| SEARCH · LEARN | 713 · 98 |
| incomplete (no `results.json`) | 11 |
| distinct commits represented | 34 |
| total candidates considered, ever | **289,304,962** |
| total wall clock, ever | **4.21 h** |

## Log

### F1 — no committed report records any provenance

All 21 `report.json` files under `docs/abstraction_ladders/ladders/` were scanned for `run_id`,
`run_ids`, `commit`, `run_dir`. **All 21 have none of them.** (A first pass looked promising —
a regex for 16-hex tokens hit 48 matches — but they are `by_primitive` share values like
`0.9998352417826839`. There is no provenance.)

Consequences, in order of severity:

1. **A committed number cannot be checked against the run that produced it.** The reports carry
   `cost_matrix`, `climb_trace`, `rung_recovery` — and no way to reach the `results.json` behind any
   of them.
2. **Staleness cannot be detected mechanically.** `run_id` is a content hash of `RunSpec`, so
   "re-derive what the current spec would produce and compare" is the natural guard — and it is
   unbuildable, because the artifact never records what it used. When the derived depth schedule
   landed (2026-07-26) and moved 8 ladders' `run_id`s, nothing could flag which artifacts had gone
   stale. `LADDERS.md` records that in prose instead.
3. **The comparability rules cannot be evaluated.** Deciding whether two cells may be compared
   requires each cell's actual config. The report holds the ladder's nominal config, not the
   per-cell resolved one.

This is a precondition failure for the whole comparability programme, and it inverts the ordering
sketched during planning: provenance is not a nice-to-have alongside the licenses, it is the thing
they are built on.

### F2 — no ladder has a complete single-generation cell set

Grouping each ladder's runs by `(commit, base budget)` — where base budget is
`depth_limit / max_pool / max_arity`, the search space, with stop-mode knobs excluded:

| ladder | runs | `(commit, budget)` groups | largest group |
| --- | --- | --- | --- |
| `al1-mirror` | 45 | **8** | 31% |
| `dae9d2b5-split-halves-lean` | 17 | **8** | 29% |
| `94f9d214-nor-recolor` | 21 | **7** | 19% |
| `dae9d2b5-split-asym-lean` | 22 | 7 | 32% |
| `94f9d214-nor-halves` | 14 | 5 | 36% |
| `fafffa47-nor-halves` | 14 | 5 | 36% |
| `fafffa47-nor-recolor` | 21 | 5 | 38% |
| … | | | |
| `94f9d214-nor-merged` | 25 | **2** | **96%** |
| `fafffa47-nor-merged` | 22 | **2** | **95%** |

**The bottom two rows are the finding.** The `nor-merged` pair are the only ladders in the store with
a coherent run set, and they are precisely the two members that came through the 2026-07-27
re-certification as **admitted, uncompromised, top-reached in chain and climb, 5/5 rungs recovered**
— the only real-task cells whose cost figures were never retracted or caveated.

Run-set coherence predicts result survival. That is a stronger argument for the comparability work
than any of the a-priori ones: this is measurable, and it was already measurable before any of the
retractions happened.

`94f9d214-nor-halves` alone spans **seven** budget fingerprints across 14 runs — `depth_limit` 2, 3
and 4; `max_pool` 30, 150 and 750 — all on one date. `al1-mirror` spans 5 budgets and 9 commits
across three dates, including 14 runs from before `considered_limit` existed at all
(`climNone:None`).

### F3 — 16% of runs are redundant, against a documented design intent

Keying completed runs on `(subject, arm, corpus_hash, library, run_type, base budget,
considered_limit, engine)` — everything except the stop mode:

| | |
| --- | --- |
| duplicate-key cell groups | 107 |
| redundant runs | **133 (16% of all runs)** |
| redundant candidates considered | **33,208,607 (11% of all compute)** |
| redundant wall clock | 30 min (12%) |

What differs inside a duplicate group is almost always the stop mode: **55 groups** are exactly
`(solution_limit=1, immediate)` against `(None, generation-end)`.

[`compromise.py`](../../src/arc_lab/program_search/ladders/compromise.py)'s own docstring:

> The default position is NO compromise: `ladder_default_config` leaves `solution_limit` unset
> precisely so one exhaustive run yields three cost quantities at once (`first_solution_index`,
> `cheapest_solution_index`, `considered`).

The design was right and was not followed. The cost was paid twice, and the mixed accounting modes
are what later forced the granularity curves to be re-bought in cost-to-first. Worth noting the
shape: this is not a case of the machinery lacking the right concept — the concept was written down,
in the right file, and the runs went the other way anyway.

The single largest duplicate group is not a ladder at all: `quick-check-d511f180` at 14.3M redundant
considered, plus `arc1-train` at 5.3M and the `grain-contrast` pair at 3.8M.

### F4 — historical runs behind the then-current README finding were not readable by the modern census

34 run dirs have no `runspec.json` — the pre-`RunSpec` layout (`library.json`, `summary.json`,
`trace.jsonl`), all dated 2026-07-08, all from the `L1/L2/L3` study era:

```
9x e10-stitch-refactor   5x e8-mirror-index-sub   5x e1-rot90
5x e2-swap-cells         5x e3-swap-cols          5x e4-swap-cols-mdl
```

`e8-mirror-index-sub` and `e10-stitch-refactor` were used by the then-current report's
compression-versus-reuse presentation. The modern reader could not parse those 34 directories,
and no later documentation can give them `RunSpec` identity retroactively. They remain historically
traceable through committed notebooks, scripts, and outputs. The current generated batch of record
and modern reports are a different provenance class; this F4 finding describes the 2026-08-03 store,
not the repository's current generated state.

### F5 — compute has never been the constraint

Per-ladder, taking the largest coherent run group as the estimate of one full pass:

| set | ladders | estimated wall clock |
| --- | --- | --- |
| ladders with a committed `report.json` | 20 | **17 min** |
| rejected ladders + controls (no report) | 11 | **17 min** |
| **both** | **31** | **34 min** |

Against a program history of 4.21 hours total.

Two things follow. First, the batch of record is not a project — it is half an hour of compute, once
a driver and provenance exist. Every discussion that treated re-running the batch as expensive was
working from an intuition the store does not support. (The only genuinely slow cells are
`dae9d2b5-split-recolor` at 743s — the `max_pool` 150 parent kept deliberately as the lean arm's
calibration baseline — and `al14-cell-row-grid` at 629s.)

Second, the **rejected ladders cost the same as the admitted ones**. All 8 rejections plus 4 controls
re-run in ~17 minutes, and none of them has a committed `report.json` at all — their findings, which
`LADDERS.md` calls "the batch's most valuable output so far," exist only as prose. There is no reason
for them to be outside the batch.

### F6 — smaller things the census surfaced

- **11 incomplete runs** (`runspec.json` written, no `results.json`): 3 from the 2026-07-20 batch
  (`al3` x2, `al4`), the parked `dae9d2b5-halves-union` cell, a `dae9d2b5-split-halves-lean` raw arm,
  a `dae9d2b5-split-halves` probe, and 5 from the 2026-07-13..16 era. They are indistinguishable from
  completed runs without opening each directory.
- **22 subjects have runs but no committed report** — every rejected ladder (al3, al4, al6, al7, al8,
  al13), every control (al9-al12), al14, all four `recolor-first` probe candidates, `recolor-solo`,
  `a740d043-crop-normalize`, `dae9d2b5-split-halves`, `dae9d2b5-halves-union`, and the two 2026-07-13
  study corpora.
- **Three probe runs report subject `?`** (2026-07-20) — a `corpus_name` the classifier cannot parse.
- **LEARN-side variation is almost nil**: 87 of 98 LEARN runs are `AntiunifyPairs` +
  `CompressionMetric`; the only variation is the 2026-07-27 proposer swap (3 runs each of
  `FrequentSubtree`, `TypeScopedFrequentSubtree`, `StitchProposer`) plus `iterations`. **Not one run
  in the entire store uses `TwoPartMDL`** — the metric the
  [half-param audit](../2026-07-27-half-param-governance/notebook.md) found to be the correct one at
  the batch's actual operating point.

## Findings

1. **Zero of 21 committed ladder reports record a `run_id`, commit, or run directory.** Committed
   numbers cannot be traced, verified, or checked for staleness. This is the common cause behind the
   week's retractions, and the precondition for every comparability mechanism proposed so far.
2. **No ladder has a complete single-generation cell set** (worst: 45 runs across 8 groups), and the
   two ladders that nearly do — `94f9d214-nor-merged` at 96%, `fafffa47-nor-merged` at 95% — are
   exactly the two whose results survived re-certification uncompromised. Coherence predicts survival.
3. **16% of runs (11% of compute, 33.2M considered) re-search an identical space under a different
   stop mode**, against an explicit docstring saying one exhaustive run yields all three cost
   quantities.
4. **The runs behind README finding #2 (compression vs. future usefulness) predate `RunSpec`** and
   cannot be read by the current tooling.
5. **A full batch of record — all 20 reported ladders plus all 11 unreported rejections and controls —
   is ~34 minutes of compute.** The entire history of the program is 4.21 hours. Nothing here was ever
   gated on compute.

## Interpretation

The program's validity discipline is asymmetric, and the census makes the asymmetry precise. A
*ladder* cannot enter the batch without passing a lint, a probe and a certificate; there are 22
executable checks and a generated register for it. A *run* enters the record with no discipline at
all — no provenance, no config-coherence requirement, no staleness detection, no duplicate check.
Every retraction of the last week landed on the run side, which is the side with no gate.

The instrument for that gate mostly exists and is pointed one level too low. `compromises_in(config)`
already reads cost/data trades off the `Config` and banners them, on the principle that "a label you
have to remember to set is exactly the thing that gets forgotten" — but it operates per run.
`CompromiseOption.forfeits` already names which quantities a compromise destroys, in prose. The
`diff-ladder` command already derives the floor relationship between two ladders and picks the
validator [LADDER-RELATIONSHIPS](../../docs/abstraction_ladders/LADDER-RELATIONSHIPS-2026-07-23.md)
licenses. What is missing is the join: per-cell provenance, so those existing pieces can be evaluated
across runs rather than within one.

The methodological lesson repeats the one from the census calibration five days earlier, one level
up. There, a static instrument had been read and built on for two days without once being placed
beside the engine's own funnel. Here, an 800-run store had been generated, cited and retracted from
for a month without once being read across. **In both cases the datum was cheap, adjacent, and
nobody had looked.** The difference is that the second one is now mechanised: `run_census.csv` is
committed, so the next audit is a diff rather than a discovery.

One correction to something asserted during the planning discussion that preceded this: the
re-run cost was estimated at "1-2 hours" and is 34 minutes, and the proposed hash-comparison
staleness guard is not buildable at all until F1 is fixed. Both errors ran in the same direction —
assuming the artifacts recorded more about their own execution than they do.

## Decisions and next

Ordering falls out of F1 being a precondition:

1. **Per-cell provenance in the ladder report.** `run-ladder` holds every `RunRecord` when it builds
   the report; record `run_id`, commit and the resolved config fingerprint per cell. Small, and
   unblocks staleness detection, number-to-run verification, dedup, and the comparability licenses.
2. **A batch of record** — one config generation, one accounting mode, artifacts regenerated,
   including the 11 rejections and controls that have never had a `report.json`. ~34 min (F5). The
   two depth-4-top NOR members are recorded as designed-censored (priced at >30M considered) rather
   than left looking runnable.
3. **Comparability licenses**, evaluated against the per-cell configs from step 1 rather than each
   ladder's nominal one — the only version that would have caught `nor-halves`' seven budgets.

Two decisions must land before step 2, since it is the artifact-generating pass: the `rung_recovery`
missed-vs-correctly-declined distinction, and whether `ladder_default_config` adopts `TwoPartMDL`
(F6: nothing in the store has ever run it).

Open, and deliberately not addressed here:

- Whether the 34 pre-`RunSpec` runs (F4) should be re-run under the current model, migrated, or
  explicitly marked as historical. Re-running is cheap; whether the old floors still exist is not
  checked.
- The 11 incomplete runs — reap, re-run, or mark.
- The three unclassifiable `?` probe runs.
