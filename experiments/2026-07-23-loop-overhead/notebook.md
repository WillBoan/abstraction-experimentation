# Loop overhead, decomposed — the flavor gap is zero; scheduling buys 1.8-2.5x and dirties the library (2026-07-23)

**Goal.** Two questions left open by the clean-set re-run, both about the gap between the marginal
accounting (al1 3.59x) and the achieved one (al1 0.96x):

1. **AL-PLAN Phase 2 item 6** — the learned-vs-oracle flavor gap: climbs pay under `L^learned`,
   all probing prices under oracle libraries. How big is the difference?
2. How much of the re-search overhead does the new `wake_schedule="skip-solved"` actually recover
   — and at what cost to what sleep sees? (Arm-labeled cells by construction.)

Artifacts: `artifacts/flavor_gap.out` · `artifacts/skip_solved.out` · `artifacts/extra_mints.out`.

## Result 1 — the flavor gap on the clean set is exactly zero

Wake iteration `i` (searching under `L^learned_i`) against oracle column `L_i` — same corpus, same
budget, only the library flavor differs. Across **all 24 wake iterations of all 8 admitted
ladders: ratio 1.00x, byte-identical considered counts** (wake 0 = Floor is the built-in sanity
check, and it holds).

Reading: on the clean set, sleep's mints are *cost-equivalent to the oracle rungs* — behavioral
recovery at matching arity, no junk mints, so the searches are literally the same computation.
The learned-vs-oracle gap is a property of **imperfect climbs**, and the admitted set contains
none (the ladders that had them — al13's zero recovery, al14's 5-param mint — are retired). The
gap is real machinery risk but currently unexercised; it will need a deliberately-imperfect cell
(Phase 2 item 5 territory) to be measured at all.

Consequence for the re-run's qualifiers: the "oracle-flavor denominators" caveat on the clean-set
table is now measured to be a no-op *for these 8 ladders*. The marginal-vs-end-to-end and
wake-side-only caveats stand.

## Result 2 — `skip-solved` recovers 1.8-2.5x of the loop overhead...

al1 and al17 climbs re-run under `wake_schedule="skip-solved"` (fresh run_ids — the schedule is
run identity):

| ladder | e2e full | e2e skip-solved | saving | achieved RQ1 (arm-labeled) |
| --- | --- | --- | --- | --- |
| al1-mirror | 200,280 | 80,852 | **2.5x** | 192,865 / 80,852 = **2.39x** (vs 0.96x full) |
| al17-shift-frame-tall | 107,772 | 59,824 | **1.8x** | bound >= 266,770 / 59,824 = **4.46x** |

The wake sets shrink exactly as designed (al1: 5 -> 3 -> 1 -> 0 tasks; al17: 7 -> 5 -> 3 -> 1 -> 0),
and the remaining overhead is now full-budget failures on not-yet-reachable tasks plus vocabulary
tax — re-search of solved tasks is gone. **Under skip-solved, al1 breaks even again** (2.39x
achieved), which quantifies what the loop-overhead work is worth: the difference between al1
paying and not paying is entirely re-search.

## ...but it pollutes the library — the arm label earns its keep immediately

Both climbs still converge and still recover every intended rung — **and mint extras**:

- al1 minted 3 (full: 2). The extra: `abs2 = map_color(#0, 3, 4)` — a **specialization** with the
  colour pair frozen, compressed out of a *stale carried solution* (found under the old library,
  never re-expressed in the grown one).
- al17 minted 5 (full: 3). The extras: `abs3 = pad(#0, 1, #1)` and `abs4 = abs3(abs0(#0), 5)` — a
  **reparameterized duplicate of frame1** through a different factoring.

This is the mechanism the arm label warned about, now with witnesses: skip-solved changes what
sleep sees (stale solutions), and sleep duly compresses the staleness. The measured wake costs
above already *include* the junk's vocabulary tax (the saving survives it), but the library handed
downstream is dirtier — which is a transfer/break-even liability the e2e number does not price.
The flavor gap that was 0.00 under `full` is nonzero under `skip-solved` by construction.

## Decisions

- Item 6 is answered for the clean set (gap = 0) and re-scoped: measuring a *nonzero* gap needs a
  deliberately imperfect climb — fold into the sleep-side attribution work (item 5), where
  specialization-from-stale-input is now a concrete, witnessed mechanism to probe.
- `skip-solved` is fit for **screening** (1.8-2.5x cheaper, converges, recovers rungs) and unfit
  for library-quality claims without a `full` companion cell. Exactly the split the arm label
  enforces.

## Next

Sleep-side micro-probes (item 5): single-factor batteries for the learn half — demonstration-mix
vs mint arity, proposer choice, governance refusals, and now the stale-input specialization
mechanism. The `w` calibration rides along.
