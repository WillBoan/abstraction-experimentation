# The certificate is a per-rung verdict profile, not a sandwich gate (2026-07-24)

A reframe of what a ladder's certificate _is_, reached in the 2026-07-24 v5-design discussion. Sits under [LADDER-SET-DESIGN-2026-07-24.md](LADDER-SET-DESIGN-2026-07-24.md) (spines/granularity) and [BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md) (the joint budget); the checks it recasts are in [LADDER-CHECKS-2026-07-21.md](../archive/LADDER-CHECKS-2026-07-21.md).

## The sandwich, unbundled

The "depth sandwich" is two constraints on a single global `depth_limit` L:

1. **Jump-affordability** — `L >= max(d_i)`: every rung's own program is reachable at the budget. Near-fundamental: if a rung's program is unreachable, the climb cannot even measure it. (Even this is per-rung, not intrinsically global.)
2. **Skip-freeness** — `L < min(double_jump_i)`: no rung's target is reachable without it.

**Constraint 2 is a _simplification_, not a requirement.** It buys the "every rung is necessary" enablement claim and nothing else. The thing the program studies -- how far rung abstractions bridge floor->top, and what that costs to search and to learn -- does not need it.

## Why relaxing it is safe for cost but not free for learnability: the two climbs

- **Oracle chain** (`ladders/chain.py::oracle_libraries`): `L_0..L_k` with each intended rung **gifted**. Drives task generation and the curriculum/marginal-cost measurement. **Skip-robust**: the abstraction is in the library regardless of what search finds, so a skippable rung cannot unravel the tower here.
- **Learned climb** (`execution/run_search_learn` -> `LearnEngine.run`, "grow the library from a whole corpus's wake solutions"): the library is built from what sleep **mints** from wake's _actual_ solutions. **Search-dependent**: a skip means wake finds the skip, sleep mints from it, and the learned library **diverges** from intended -- and can **cascade** downstream. This is exactly the al14 collapse (wrong-arity mint) and the al1/al17 junk-mint mechanism.

So skip-freeness has more teeth than "just the enablement claim": it is also what keeps the _learned_ mints intended. But the divergence is **measured** (recovery %, junk-mint count -- the schedule-comparison instrumentation), not silently corrupting, and the clean batch held **100% behavioral recovery** despite junk mints. Relaxing skip-freeness therefore degrades _library quality_, and changes _what the learned climb measures_ at a skippable rung (divergence, which is itself the granularity-knee signal) -- it does not invalidate the experiment.

| Question | Climb | Skip-freeness | On relaxing |
| --- | --- | --- | --- |
| Search cost (raw vs laddered) | oracle / curriculum | not needed | genuinely free |
| Learnability (what sleep mints, recovery) | learned | load-bearing | junk / cascade -- measured, not fatal |

## The reframe

**A ladder's certificate is a per-rung verdict profile, not a global pass/fail gate.** The probe already emits one per rung -- `{clean-jump | skippable | collapsed | collision | saturated}` -- and the profile spans both climbs: the oracle probe says "is this rung reachable / necessary," the learned climb says "does sleep recover it, or diverge." The all-clean ladder is the _special case_, not the admission requirement. The sandwich becomes a **quality lens** ("is this a clean staircase, and where isn't it?"), not a **gate** ("may this ladder exist?").

## Two mechanical facts this rests on

- **The double-jump is a (rung, consumer) property, not a rung-depth property.** Inlining a rung of depth `d_r` on its consumer's critical path raises that consumer by `d_r - 1`. So a d2 rung is skippable at L iff its _shallowest_ consumer has depth `<= L - 1`. A single d2 rung does **not** force a skip; the danger is specifically **shallow-feeds-shallow chains** (and a shallow rung feeding a shallow top). An isolated d2 rung under deep consumers is clean. (Verified 2026-07-24.)
- **"Mixed d2/d3 rungs can't coexist" is a depth-only-lint statement.** Under the real gate (the probe's joint depth+considered budget), a depth-affordable-but-breadth-intractable skip is correctly NO_SKIP (BREADTH-AXIS, cell A'). So mixed depths are fine; uniform-depth spines are one granularity choice among many, not a requirement.

## Consequences (adopted for v5 and the set)

- **Do not uniformize depth.** Author ladders at their natural mixed depths; do not split a whole tower to all-d2 just to satisfy the depth-only lint. Uniform spines (all-d2 / all-d3) are deliberate granularity _members_, authored when wanted, not the default shape.
- **Gate with the probe, record the profile.** The verdict profile is a primary output, not a footnote; a skippable cheap rung is a data point about that cut placement, not a failure.
- **Run both climbs.** The learned climb is where skips bite -- run it (full + skip-solved) and watch **recovery / junk / cascade**, not just the oracle probe. Cascade -> non-recovery is the genuine failure signal (the clean synthetic batch never showed it; a real task might).
- **Per-rung budgets** (relaxing the "same budget throughout" simplification) is the principled fix that makes mixed-depth ladders _cleanly measurable_ rather than merely valid -- a Phase-2 machinery item (see the TODO), not a Phase-1 blocker.
