# The wake-schedule comparison, completed — curriculum IS the marginal accounting (2026-07-23)

**Goal.** Complete the schedule table the loop-overhead experiment started: `full` / `skip-solved`
/ `curriculum` across the admitted set, not just al1 + al17. TODO item 4 (corrected to
multi-ladder). The point of the third column is to bound the loop-overhead factor from below — how
much would *perfect* scheduling save?

**Method.** All 7 clean ladders (al2 excluded — its 2-task corpus has no schedule to vary), each
under all three schedules. `curriculum` is built from each spec's own rungs: one group per level
(rung i's demos), the top last — the intended climb order, which is exactly the ladder knowledge
the arm label flags. Per cell: end-to-end considered, rungs recovered, and mints (a cheaper
schedule that dirties the library is not a free lunch).

Artifacts: `artifacts/schedule_comparison.py` (+`.out`).

## The table

| ladder | full | skip-solved | curriculum | curriculum = marginal? |
| --- | --- | --- | --- | --- |
| al1-mirror | 200,280 | 80,852 (2.48x) | 53,711 (3.73x) | ✓ |
| al15-shift-frame | 56,405 | 33,147 (1.70x) | 18,627 (3.03x) | ✓ |
| al16-layout-nest | 5,655 | 3,125 (1.81x) | 1,817 (3.11x) | ✓ |
| al17-shift-frame-tall | 107,772 | 59,824 (1.80x) | 26,677 (4.04x) | ✓ |
| al18-fanin-rotate | 6,705 | 3,731 (1.80x) | 2,161 (3.10x) | ✓ |
| al19-fanin-recolor | 144,465 | 85,291 (1.69x) | 47,807 (3.02x) | ✓ |
| al20-recolor-telescope | 109,595 | 64,749 (1.69x) | 36,279 (3.02x) | ✓ |

Recovery is 3/3 or 2/2 in **every cell** — no schedule loses a rung.

## Finding 1 — the oracle-curriculum schedule reaches the marginal accounting EXACTLY

Curriculum's end-to-end considered equals the ladder's *marginal* laddered cost to the candidate,
on all 7 ladders (verified against the clean-set-rerun `report.json` marginals). This is not a
coincidence — it is definitional, now demonstrated: the marginal accounting is "jump costs
proper" = each rung's demos searched once under `L_{i-1}`, and searching each rung's group once in
climb order under the grown library is precisely what the curriculum schedule does. So:

> **The loop-overhead factor is exactly `full / curriculum`** — the price of re-searching every
> task every wake instead of scheduling perfectly. Measured: **3.0x–4.0x**, and it grows with
> height (al17, the 4-level ladder, is the highest at 4.04x).

This gives the marginal-vs-end-to-end gap — the one accounting distinction that survived the
sleep-probes' cleanup — a concrete, achievable interpretation: marginal is not a hypothetical
ceiling, it is what an oracle scheduler delivers, and `curriculum` delivers it.

## Finding 2 — the realistic cheap mode recovers ~40-60% of that gap

`skip-solved` (the honest cheap mode — no injected ladder knowledge) sits between full and
curriculum: **1.69x–2.48x** vs curriculum's 3.0x–4.0x. It captures roughly half the schedulable
overhead by the one move available without oracle knowledge (don't re-search solved tasks). The
remaining gap to curriculum is the part that needs knowing *which rung a task belongs to* — which
an honest loop does not have.

## Finding 3 — carrying dirties the library, identically under both carrying schedules

The junk mints are **schedule-invariant among carrying schedules and ladder-dependent**:

- al1 (+1 junk) and al17 (+2 junk) mint extras under BOTH skip-solved AND curriculum — the *same*
  extras, byte-for-byte (al1's frozen `map_color(#0,3,4)`, al17's frame1 duplicate).
- al15/16/18/19/20 mint NO junk under either carrying schedule.

This confirms sleep-probes S-D mechanically at batch scale: the junk is frozen-param
specialization surfacing from carried solutions, so it appears exactly on the ladders whose demos
contain repeated frozen-param solutions (al1, al17) and not otherwise — and it does not depend on
*which* carrying schedule, only on *that* solutions are carried. `full` mints clean everywhere
because it re-expresses every solution through the general rung each wake.

## Consequences

- **The loop-overhead factor is now a measured, decomposed quantity**: `full/curriculum` total
  (3-4x), of which `skip-solved` recovers ~half honestly and the rest needs oracle scheduling.
- Curriculum is the right cell for a *marginal* RQ1 number when one is wanted — it achieves the
  marginal denominator by construction, arm-labeled as oracle-assisted.
- For 5 of 7 ladders, `skip-solved` is a strictly-better screening mode than `full`: cheaper,
  full recovery, clean library. For the 2 with frozen-param demos it is cheaper and recovers but
  dirties — the arm label's exact use case.

## Next

The junk-under-carrying result sharpens TODO item 9 (refold-carried-solutions): re-expressing
carried solutions through the current library before sleep would let the carrying schedules keep
their 1.7-4x saving without the library pollution — testable as a `LearnSpec` option against these
same al1/al17 cells.