# The clean-set re-run — first trustworthy aggregates (2026-07-23)

**Goal.** Re-run the 8 admitted ladders through the current pipeline end to end — probe-gated,
staged (`run_ladder_chain` → certificate → climb), raw arms per decision 1 — and write out the
artifacts that were missing. AL-PLAN-2026-07-23 Phase 2 item 4, first half. Everything the
2026-07-20 batch reported predates the instruments and the RQ1 decision; this is the replacement
baseline.

**Method.** Gates first: all 8 lint clean and probe clean (post the `.ladder` format upgrades and
depth rework — a real regression check, not a formality). Then `arc-lab run-ladder <name>
--artifacts docs/abstraction_ladders/ladders/<name>/` per ladder at the committed reference
configs, raw arms at the default K=10. Oracle chains and climbs hit the run cache where the
2026-07-20 runs were cache-clean; every raw arm is a fresh, deliberately-purchased run.

Artifacts: `artifacts/aggregate.out` (the extraction script's table, verbatim); per-ladder
`spec.md` / `results.md` / `report.json` under [../../docs/abstraction_ladders/ladders/](../../docs/abstraction_ladders/ladders/)
(al15–al20 get their folders for the first time; al1/al2's stale artifacts — including al1's
retired 78x–530x claim — are regenerated under the new report).

## The aggregate

| ladder | RQ1 (decision 1) | kind | laddered | loop overhead | recovery | off-chain top |
| --- | --- | --- | --- | --- | --- | --- |
| al1-mirror | **3.59x** | measured | 53,711 | 3.7x | 2/2 | solvable |
| al2-rot90-calibration | **0.48x** | measured | 27 | 2.2x | 1/1 | solvable |
| al15-shift-frame | **>= 10x** | proven bound | 18,627 | 3.0x | 2/2 | needs chain |
| al16-layout-nest | **>= 10x** | proven bound | 1,817 | 3.1x | 2/2 | solvable |
| al17-shift-frame-tall | **>= 10x** | proven bound | 26,677 | 4.0x | 3/3 | solvable |
| al18-fanin-rotate | **>= 10x** | proven bound | 2,161 | 3.1x | 2/2 | needs chain |
| al19-fanin-recolor | **>= 10x** | proven bound | 47,807 | 3.0x | 2/2 | needs chain |
| al20-recolor-telescope | **>= 10x** | proven bound | 36,279 | 3.0x | 2/2 | solvable |

Bound conditions (identical across the six): raw arm at `depth_limit = min_depth_limit(unfolded
top)`, `max_pool` 200,000, guard = 10x the chain-measured laddered marginal per top task,
censored exactly at the guard (`immediate`), **no funnel saturated** — every bound is sound.

## Findings

1. **The rebuild set's amortization is now PROVEN, not estimated: >= 10x on all six.** Their raw
   arms spent 10x the laddered cost without finding a solution at a freed pool. This is the claim
   shape the program wanted all along — strengthenable by raising K, wrong in no direction.
2. **al1, the old headline ladder, is the WEAKEST admitted ladder** (3.59x measured). The ladder
   whose estimated 78x–530x anchored the program's story is outperformed by every rebuild — the
   estimate had the ranking upside down.
3. **al2 reads 0.48x** — the ladder costs ~2x what raw does. Correct behavior for the
   trivial-regime instrument, and the first time the pipeline can say it plainly.
4. **Recovery is 16/16 rungs** across the set, at loop overheads 2.2x–4.0x (tracking the
   wake-iteration count, as the batch's overhead reading predicted).
5. **Off-chain necessity separates the set as designed**: al15/al18/al19's tops need the whole
   chain (`off_chain=False`); the telescoping tops (al1/al2/al16/al17/al20) don't. al19-vs-al20
   reads exactly as the 2026-07-21 resolution said it should.

## What this replaces

Every number previously quoted for these ladders (the 2026-07-20 batch's estimated ratios, al1's
78x–530x) is superseded by this table. The register rows now carry these values; the retired
ladders have no RQ1 (a rejected ladder's RQ1 is not a question).

## Open (the second half of Phase 2 item 4)

- **Grow the set.** Eight ladders — two of them instruments — is not an aggregate to generalize
  from. New ladders must lint clean, probe clean, and produce usable cost data to count.
- Worksheets for al15–al20 folders (design narrative — generated artifacts only for now).
- `w` (wake/sleep currency) still uncalibrated: RQ1 denominators are wake-side only, stated as
  such in every report.
