# The TwoPartMDL collapse is structural on real ARC, not miscalibration (2026-08-04)

[2026-08-03's governance arm](../2026-08-03-batch-of-record/notebook.md) took rung recovery
**55/57 -> 1/57** under `TwoPartMDL`, from one decline per ladder at its lowest rung. Its stated
limitation, registered before the run rather than after:

> A total collapse is equally consistent with `bits_per_primitive = 1.0` being miscalibrated —
> never swept, and the audit flagged the V=2 corner as sensitive to a 1.0-bit gap. One survivor at
> the boundary is a lever, not a resolution.

This closes that. **It is not miscalibration on the real tasks.** Of the 11 real-ARC members,
**8 decline at every possible setting of the parameter** and 0 are calibration-sensitive; all 6
calibration-sensitive members are synthetic.

Read-side only, ~15s. No searches were run.

## The parameter is decidable without sweeping it

`bits_per_primitive` enters `TwoPartMDL` **linearly, and only through the flat term**
(`analysis/compression.py`): `library_bits = b * |primitives| + Σ (learned) template.size()`.
So for one candidate abstraction over a library `L` and the wake corpus `C`:

```
DL(mint) − DL(none) = b * 1                 # one more primitive at the flat rate
                    + template.size()       # TwoPartMDL's definition term — b-INDEPENDENT
                    − saving                # program bits the corpus rewrite removes
```

Minting wins iff `b < saving − template.size()`. Call that the **break-even `b*`**. Because
`b >= 0`, a candidate with `b* <= 0` is declined at **every** admissible setting: the definition
term alone already outweighs what the abstraction saves. No sweep is needed — one closed-form
quantity per candidate answers the whole question.

**Iteration 0 only.** Iterations `>= 1` are unreachable in the counterfactual: if nothing mints at
iteration 0, the library never grows and `early_stop` ends the loop, so those iterations' libraries
are ones `TwoPartMDL` would never have seen. A first pass pooled all iterations and reported three
extra members as rescuable — wrong for exactly this reason, and corrected before any conclusion.

Proposals are **recomputed** from each iteration's recorded wake programs + library, exactly as
[`ladders/recovery.py`](../../src/arc_lab/program_search/ladders/recovery.py) does — proposers are
pure frozen dataclasses, so no new telemetry and no `run_id` moves.

## Result ([`bits_sweep.py`](artifacts/bits_sweep.py) · [`.out`](artifacts/bits_sweep.out))

| class | members | meaning |
| --- | --- | --- |
| **STRUCTURAL** (`b* <= 0`) | **11** | declined at every `b >= 0` |
| **CALIBRATION** (`0 < b* <= 1`) | 6 | some `b` below the current 1.0 would mint |
| already-mints (`b* > 1`) | 3 | minting wins at `b = 1.0` |
| no proposals | 1 | `al12-unlearnable`, by design (one demo, nothing to pair) |

**The split falls exactly on synthetic vs real ARC.** All six calibration-sensitive members are
`al15`-`al20` — the synthetic rebuild set, one recipe, all at `b*` = exactly 1.0. Of the eleven
real-ARC members: **8 structural, 3 already-minting, 0 calibration-sensitive.**

| member | `b*` | defn | saving | class |
| --- | --- | --- | --- | --- |
| `94f9d214-nor-recolor` · `fafffa47-nor-recolor` | 5.0 | 7 | 12 | already-mints |
| `dae9d2b5-split-asym-lean` | 4.0 | 4 | 8 | already-mints |
| `al15`-`al20` (six) | 1.0 | 5 | 6 | CALIBRATION |
| both `nor-halves` · both `nor-merged` · `al21` · `half-param` · `split-halves-lean` · `split-recolor` · `split-recolor-lean` | 0.0 | 4 | 4 | STRUCTURAL |
| `al1-mirror` · `al2-rot90-calibration` | -1.0 | 3 | 2 | STRUCTURAL |

### Three independent checks that the model is right

1. **It predicts the arm's actual survivor.** `dae9d2b5-split-asym-lean`'s best iteration-0
   candidate is `nth(split_h(#0), 0)` — `west`, its **authored rung** — at `b* = 4.0`. That is
   precisely the one member that held recovery under `TwoPartMDL`, derived here without being told.
2. **It explains the two apparent misses, and the explanation is already on record.** Both
   `nor-recolor` members mint at `b* = 5.0` yet scored **0** recovery. What they mint is
   `nth(split_v(map_color(#0, #1, 2)), #2)` — a 3-parameter template that is **not** the authored
   rung. Their rung-shaped candidates (`nth(split_v(#0), 0)` / `(…, 1)`, `b* = 4.0`) are on offer at
   round 0 and destroyed by the winner's corpus rewrite. That is the greedy myopia the
   [2026-07-27 audit](../2026-07-27-half-param-governance/notebook.md) located, reproduced from a
   different direction. **Minting is not recovering** — the instrument measures the latter.
3. **The six ties are exact, not approximate.** `al15`-`al20` land at `b* = 1.0`, i.e. `ΔDL = 0` at
   the current setting. `GreedyMDL` accepts on **strict** improvement (`dl < best_dl`,
   `learn/engines.py:203`), so they decline by a hair — and any `b < 1.0` flips all six at once.

## Findings

1. **`bits_per_primitive` is not the explanation on real ARC.** 8 of 11 real-ARC members have
   `b* <= 0`: a 4-node definition saving 4 program-bits breaks even at zero, so the abstraction pays
   for its uses but never for its own definition, at any flat rate. 0 of 11 are rescuable by tuning.
2. **The 6 rescuable members are all synthetic, all one recipe, all at `b*` exactly 1.0** — sitting
   on the tie that strict-improvement greedy declines. The "1.0-bit gap" the audit flagged is real,
   and it is confined to `al15`-`al20`.
3. **Three members mint under `TwoPartMDL` and two of them still recover nothing**, because greedy
   takes a wider non-rung template first and the rewrite destroys the rung-shaped candidates.
4. **The parameter never needed sweeping.** It enters linearly through a term that is one primitive
   wide, so the break-even is closed-form; the definition term it competes against is
   parameter-independent by construction.

## Interpretation

The 2026-08-03 caveat is closed, and the uncomfortable reading it hedged now stands with support
rather than mere consistency: **the register's rung-recovery column is a fact about the ladders'
demonstration corpora, not about the learner.** At 2-4 demonstrating programs per rung, no
abstraction on a real task pays for its own definition, and no setting of the flat rate changes
that — the competing term does not depend on it.

Two consequences follow directly. First, **adopting `TwoPartMDL` as `ladder_default_config`'s metric
would zero the recovery column on real ARC and could not be tuned back** — the decision deliberately
left open on 2026-08-03 now has an answer on the calibration side, though whether the *right* move is
to change the metric or to build corpora where abstractions recur enough to pay is a design question
this does not settle. Second, the finding relocates where the leverage is: not in the selector's
parameters but in **how many times a rung's abstraction recurs across the retained corpus** — which
is exactly what 2026-08-03's single-survivor observation suggested (`west` recurs as a subterm across
more of the corpus than `east`, at identical demo counts) and what this prices directly.

A caution on scope: `b*` prices *minting*, and the register measures *recovering*. Finding 3 shows
those come apart — so a future arm that raised minting rates would not automatically raise recovery,
and reporting it as if it would is the error this instrument now makes visible.

Methodologically, the day's own lesson repeated once more and was caught in time. The first run of
this script spent **10 minutes** where I had predicted milliseconds — because it called
`run_ladder(spec)` at the default `raw_arm_k=10`, i.e. it started buying a raw arm for a member the
once-per-cohort protocol says must not have one. That is the same defect the batch driver was fixed
for on 2026-08-03 (`RAW_ARM_MEMBERS`), re-introduced from the other side, by a read-side script. It
wrote nothing before being caught. The lesson generalises past this script: **`run_ladder`'s
`raw_arm_k` defaults to 10, so any caller that is not `run-batch` buys arms unless it says
otherwise** — worth a look, since the protocol lives in the batch driver rather than in the function
the protocol constrains.

## Next

1. **The metric decision is now informed but not made.** `TwoPartMDL` is the better selector by the
   audit's evidence and would zero the real-ARC recovery column by this one. Both are true; choosing
   between them is a decision about what the ladders are for.
2. **Corpus recurrence is the measurable lever** — `b* = saving − size`, and `saving` is driven by
   how often the template recurs across the retained corpus. A demo corpus built so a rung recurs
   ~2x more would move real-ARC members off `b* = 0` without touching the selector.
3. **Guard `raw_arm_k`'s default**, or move the once-per-cohort rule from `batch.py` into
   `run_ladder` itself, so a read-side caller cannot silently buy an enumeration.
