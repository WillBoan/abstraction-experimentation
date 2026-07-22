# Sleep-side micro-probes — the mint laws, measured (2026-07-23)

**Goal.** AL-PLAN Phase 2 item 5: single-factor attribution for the learn half, which until now
rested entirely on confounded cross-ladder readings. Same recipe as the search-side micro-probes:
synthetic solved-task sets over a tiny floor, one factor per cell, `GreedyMDLLearnEngine.run`
directly -- no search, milliseconds per cell.

Artifacts: `artifacts/sleep_probes.py` (+`.out`) -- batteries S-A..S-E;
`artifacts/w_calibration.py` (+`.out`) -- S-F on the clean set's own recorded runs.

## The laws

**S-A -- the pairing floor is exactly 2.** One demo mints nothing (al12's mechanism, isolated);
two through four demos mint identically. Demo count beyond 2 bought nothing here.

**S-B -- mint arity = the number of distinct value-patterns across demos, not the intended
parameter count.** The intended `map_color(mirror(#0), #1, #2)` (arity 3):

| demo params | mint |
| --- | --- |
| vary independently: (1,2) (3,4) | arity 3, as intended |
| frozen: (1,2) (1,2) | **arity 1, literals baked** -- al13's zero recovery, isolated |
| one frozen: (1,2) (1,4) | arity 2, the frozen one baked |
| equal-valued: (2,2) (5,5) | **arity 2 with a SHARED param** (`#1, #1`) -- antiunify fuses positions that covary |

So a rung's demonstration plan does not merely *risk* the wrong arity -- it *determines* the
arity, mechanically. The `free-param-varies` lint checks the frozen case; the equal-valued fusing
case is new and un-linted (a rung whose demos accidentally covary two params mints a fused
abstraction that cannot express the general case).

**S-C -- governance refused nothing in the probed range** (motif 2-3 ops x 2-3 uses, distinct
remainders): the break-even frontier sits below the smallest probed cell. Refusals need
single-use or near-zero-compression shapes (the lint's `mdl-break-even` proxy and al11's
greedy-trap remain the evidence there); this battery maps where the frontier is NOT.

**S-D -- the skip-solved junk mechanism is frozen-param specialization, not staleness itself.**
With `abs0 = mirror` already in the library: fresh re-expressed solutions -> nothing; plain stale
spellings of abs0's own body -> nothing (sleep does NOT re-mint a duplicate of a plain motif);
mixed -> nothing. But *repeated identical solutions with frozen params* (`recolor(3,4)` carried
twice) -> `abs1/1: map_color(mirror(#0), 3, 4)` -- byte-for-byte the junk mint witnessed under
skip-solved on al1. Mechanism: full mode re-searches and re-expresses solutions via the general
rung, erasing the frozen pattern each wake; carrying preserves it, and S-B's frozen-param law does
the rest. The junk is S-B's arity-1 row, delivered by carrying.

**S-E -- the proposers surface different KINDS of abstraction, not just different hit rates.**
On fragment-shared sets (the same motif buried in otherwise-distinct programs) `AntiunifyPairs`
mints NOTHING -- whole-program antiunification structurally cannot see it -- while
`FrequentSubtree` finds the fragment. On whole-similar sets antiunify mints the full arity-3
template where FrequentSubtree mints only the arity-1 inner motif. The register's al4/real-ARC
claim ("real solutions rarely share whole-program structure"), isolated and confirmed.

**S-F -- `w` measured: sleep cost is negligible at clean-set scale.** Wake throughput 42-46k
candidates/s (from the recorded L_0 columns); one sleep = 2 proposal/pair units at w ~= 3
considered-equivalents/unit -> a whole sleep costs ~6-8 considered-equivalents against wakes of
2k-50k considered. **The "wake-side-only denominators" caveat on the clean-set RQ1 table is
measured to be a rounding error** -- for AntiunifyPairs at this corpus size; a Stitch-scale
proposer or a real-ARC corpus re-opens the question.

## Consequences

- Two of the clean-set table's three accounting caveats are now measured no-ops (oracle-flavor
  gap = 0; sleep cost negligible). The marginal-vs-end-to-end distinction is the one that matters.
- A new lint candidate: **param-covariance** (S-B's equal-valued fusing) -- demos where two free
  params always take equal values will mint a fused, under-general abstraction.
- The demonstration plan is the mint's specification, mechanically: count >= 2, every param varied
  independently, no accidental covariance. Ladder generation (Phase 3) can enforce this by
  construction.

## Next

Phase 2 item 4 second half (grow the set -- needs interestingness steer) or Phase 3 item 7 (the
granularity family, fully measurable with raw cancelling). The param-covariance lint is a small
standalone item.
