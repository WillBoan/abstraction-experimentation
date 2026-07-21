# Abstraction Ladder batch: reading all 20 ladders, and the al14 diagnosis

**Date:** 2026-07-21 · **Commit:** `f0fe2e1` · Abstract: [EXPERIMENTS.md](../../EXPERIMENTS.md) entries of 2026-07-21 · Register: [LADDERS.md](../../docs/abstraction_ladders/LADDERS.md) · Design: [ABSTRACTION-LADDERS-2026-07-16.md](../../docs/abstraction_ladders/ABSTRACTION-LADDERS-2026-07-16.md)

## Goal

All 20 ladders had been built and run on 2026-07-20, but only **three** (al1, al2, al5) ever had a report generated — the other 17 existed as certificate booleans and nothing more. Two questions:

1. What do the batch's results actually say, read across all 20?
2. Specifically: **how tractable would al14's climb really be?** It is statically the batch's strongest ladder (`d_raw` 54, 18x depth compression, the only validity window of width > 1), and my first recommendation was to re-run it at a bigger compute guard. Was that right?

Answer to (2), up front: **no.** al14 is not expensive-but-doable; it is mis-specified, and the re-run would have produced a wrong-abstraction climb that stalls at r2. That recommendation is retracted below.

## Setup

Everything here is a **read over the existing `runs/` cache** — no ladder was re-run. Two wrinkles made that harder than expected:

- The al1–al14 runs of 2026-07-20 were made with a **`considered_limit=50000` guard that is not carried in the committed `LadderSpec`s**, so their cells sit under a `cl50k-*` budget variant and are cache-orphaned relative to `arc-lab run-ladder <name>` today. al15–al20 ran as-committed. [batch_reports.py](artifacts/batch_reports.py) probes all three variants per ladder.
- **`run_ladder` silently executes on a cache miss.** My first attempt verified only the LEARN run id, so for al14 it fell through to an uncached variant and began an *uncapped* search; it ran ~10 minutes before I killed it. The committed script verifies **every** id (LEARN, oracle chain `L_0..L_k`, off-chain, and both derived searches) and skips rather than executes. With that guard, all 20 reports generate in ~10s total — 9.3s of which is al14 alone.

## Log

### Probe 1 — generate and read all 20 reports

[batch_reports.py](artifacts/batch_reports.py) → [reports.json](artifacts/reports.json), [batch_reports.out](artifacts/batch_reports.out); tables via [cross_ladder_tables.py](artifacts/cross_ladder_tables.py) → [cross_ladder_tables.out](artifacts/cross_ladder_tables.out).

Verdicts across the batch: **9 admitted** (al1, al2, al12, al15–al20), **7 rejected on structure** (al3–al8, al13), **1 inconclusive** (al14, every cell censored), plus the controls behaving as designed (al10 correctly rejected; al12 admitted-with-failed-climb).

### Probe 2 — is al14's generation 3 reachable?

[al14_reachability.py](artifacts/al14_reachability.py) → [al14_reachability.out](artifacts/al14_reachability.out). One r1 task, `depth_limit=3`, hard cap 3M, at two pool sizes. Both consumed the full 3M without completing generation 3, at **18,847/s** (`max_pool=2000`) and **5,231/s** (`max_pool=20000`) — the throughput anchors every estimate below.

An early hand model predicted generation 3 at ~4×10⁹ compositions (i.e. ~50 h/task). That was **wrong**: it assumed the INT pool compounds through `sub`. It does not — see probe 3.

### Probe 3 — al14's actual structure

[al14_literal_collapse.py](artifacts/al14_literal_collapse.py) → [al14_literal_collapse.out](artifacts/al14_literal_collapse.out). Four cheap steps that together explain al14 completely.

## Findings

### A. Batch-level

**A1. The RQ1 raw-cost estimator degrades to noise exactly where ladders get interesting.** Bracket width against extrapolation distance:

| rounds extrapolated | 2 | 3 | 4 | 6 | 8 | 51 |
| --- | --- | --- | --- | --- | --- | --- |
| hi/lo spread | 1–10x | 20–62x | 250x | 111–1,125x | 3.6×10⁷ | 7.6×10⁷⁰ |

Usable range is roughly `d_raw − depth_limit <= 3`. al4's bracket spans seven orders of magnitude; al14's is physically meaningless — and its *spread of 1* is false comfort, both ends being the same absurd number (the fit ran on two points, `composed = [16, 300]`). Since design doc §5.3 makes estimation **the method**, this bounds the whole RQ1 programme. Worse, **al2 — the designated validation arm — sits at the trivial end** (amortization 1x–1x; raw 31 vs laddered 27), so it cannot validate the regime every other number depends on.

**A2. A third of all measured cells are censoring artifacts.** 172 / 532 cells (32%), and censoring is all-or-nothing per ladder: al3, al4, al5, al6, al13, al14 are **100% censored**, every other ladder 0%. For those six, all cost figures are artifacts of the 50k cap — which is exactly why their vocabulary tax reads `1.00` across the board (both sides pinned to the cap). They currently have structural verdicts and **no usable cost data**.

**A3. The first rung never pays for itself.** Own-task speedup — the honest, uncensored measure (a rung's own demonstrating tasks, cost-to-first, with vs without it gifted) — is **1.0–1.7x for r1 on every uncensored ladder**, while r2+ delivers 1.8x–52x and compounds with level (al17: 1.0 → 30.4 → 52.1; al19: 1.0 → 38.1). This is structurally forced: r1's tasks must be floor-solvable to be learnable at all, so r1 has no gap to close. **The ladder pays at the bottom and earns at the top** — an argument that height is what makes ladders worth building, and the sharpest measured form of the ladder thesis so far.

**A4. The loop-overhead factor is close to a tautology.** It tracks wake-iteration count almost exactly (2 iters → 2.00; 3 → 3.00–3.11; 4 → 4.04; 5 → 5.27), because cost-paid-full is nearly task-independent. It measures how many wake passes ran, not a property of the ladder, and §2's four-way decomposition (re-search / overshoot / termination / learned-vs-oracle) is not visible in it. It needs early stop to become informative.

**A5. Vocabulary tax is an arity phenomenon, not a library-size one.** Param-free geometric rungs (al15–al20) cost 1.03–1.43x with `b_eff` essentially flat (15.3 → 16.0); colour-parameterised ladders cost 3.8–4.4x with `b_eff` doubling (al1 24.6 → 48.8, al6 20.8 → **110.5**). al1's single-ladder finding generalises: what costs you is the *parameter space* a minted abstraction opens, not the count of library entries.

**A6. Top-level recombination is what makes intermediate rungs search-path-necessary.** `off_chain_top_solved` is False only for al14, al15, al18, al19. al18/al19's recombining tops (`concat_v(pair, rot)`) need *both* rungs, so Floor + `r_k` cannot express them; al20's telescoping top (`pair(recol)`) is off-chain solvable. **This resolves the al19/al20 fan-in problem**: the pair is a genuine contrast, but the discriminating property is *shared-input recombination vs chaining* — precisely what off-chain necessity measures and what the fan-in **count** cannot distinguish (both tops score fan-in 2 under §2's definition). Recommend retiring fan-in as the axis label in favour of off-chain necessity.

**A7. Structure fails; learning works.** Full rung recovery in 11/20, partial in 2, zero in 4 — and al7/al9/al11 recovered **5/5** rungs while still being rejected. Learning has not been this batch's bottleneck; ladder design has.

**A8. Overshoot is large and now removable.** Paid-full ÷ cost-to-first runs 1.2x–15.5x (al3 15.5, al5 11.3, al13 8.9, al1 6.4). `solution_limit` shipped 2026-07-20 and would recover most of it.

### B. al14 — the tractability question

**B1. Compute is not the obstacle.** The pool after generation 2 holds **10,615 grids but only 17 ints and 14 colours** — `sub` does *not* compound the INT pool, because signature dedup collapses it to 17 distinct values. Since `set_cell` composes as `|GRID| × |INT|² × |COLOR|`, generation 3 costs ~**8.0M** compositions at `max_pool=2000`: about **7 minutes per task**, ~1 hour for the 7-task corpus. The 50k guard was simply three orders of magnitude too small — al14's search died partway through generation *1*.

**B2. r1 solves at depth 2, not 3.** In 2.0 seconds:

```
intended:  set_cell(set_cell(#0, sub(#1,1), #2, read(#0,#1,#2)), #1, #2, 0)     d=3
found:     set_cell(set_cell(input, 1, 0, 0), 0, 0, read(input, 1, 0))          d=2
```

`sub(ROW,1)` is dead weight. The batch convention is "free params **fixed within-task**", so within a task the row index *is* a literal — and the floor enumerates INT constants. The depth `sub` was meant to contribute does not exist for the search. So `d_1 = 2`, and al14's advertised sandwich (jumps [3,3,3], window [3,5], 18x compression) is computed on a template the search bypasses.

**B3. The retained solutions are overfits.** Task `-01`'s solution reads (0,2) to write (1,1) — sound only because those cells share a colour in both train examples. That is exactly the **task-collision check** design doc §6 lists ("no shallower program coincides with the intended solution on all train examples") and which is evidently not implemented or not firing.

**B4. So sleep mints the wrong abstraction — and it is the expensive kind.** Running the reference proposer on the two retained solutions:

```
proposed: set_cell(set_cell(#0, #1, #2, 0), #2, #2, read(#0, #3, #4))     5 params
```

Four free INT params instead of the intended two, and semantically wrong: it **fused row and col into `#2`** because both tasks happened to have row == col at that position. Cost of using it at generation 1 ≈ `2000 × 17⁴ = 167M` per round, against `2000 × 17² = 578k` for the intended form — **289x worse** — and r2 needs three nested calls of it.

**Profile: iteration 0 cheap (~1 h) → wrong 5-param mint → iteration 1 ~289x worse → r2 unreachable.** al14 fails in the way it was least expected to.

### C. Three collapse families (the batch's real output)

The 2026-07-20 screen plus this analysis identify three *general* failure modes, none a one-off design slip:

1. **Self-similar doubling telescopes** (al3, al7, al9, al11). Any self-contained doubler satisfies `r_2k == r2^k`, so every even rung is a depth-2 composition of the rung two below. Verified **transform-independent** — a plain-`concat` tower collapses identically — so no seeding or reordering fixes it; a non-collapsing tall tower needs distinct, non-composing rung operations, i.e. a richer floor.
2. **Family-B perceiver collapse** (al5, al6, al8). Cheap perception erases the very search-cost gap the ladder exists to bridge: al8's L_0 solves the top directly via `map_color(flip_v(input), least_common_color(input), most_common_color(input))`.
3. **Literal collapse of free INT params** (al14 — new here). A rung whose free parameters are indices into an *enumerated constant domain* loses precisely the depth that computing those indices was meant to contribute, because within a task the parameter is a literal. This is the E11 literal trap relocated to the index domain, and it follows directly from the batch's own "free params fixed within-task" convention.

Family 3 has an uncomfortable corollary. To make the *relation* load-bearing, the destination index must vary within-task — which means deriving it from the grid, i.e. **perception**. Removing INT constants instead makes r1 unsolvable outright. So: **on a cell-level floor, "move up" is not learnable as a relation without perception.** That is arguably a more valuable result than the ladder would have been.

## Decisions

- **Do not re-run al14 as specified.** Retract the 2026-07-21 "highest-value re-run" recommendation. Either retire it with family 3 recorded, or rebuild with a derived (perceived) index and accept a floor that gains a perceiver.
- **al14's register row is corrected** to state that its static strength is computed on templates the search bypasses at depth 2.
- **al2's validation role becomes more urgent, not less.** Three of the four ladders otherwise trusted for cost data have depth claims the search does not honour, so validating depth-to-cost on the one measurable ladder matters more.

## Open questions

- Is the §6 **task-collision check** implemented at all? B3 is precisely what it exists to catch, and al14 shipped with two colliding tasks.
- Does the literal collapse (family 3) affect other ladders with free params — al5/al6 have 1–3 free params each, and both are 100% censored, so it has never been checked there.
- Should the reference config carry a `considered_limit`? It enters `run_id` *and* becomes part of what the certificate is anchored against, so the depth-only validity window would gain a second dimension. Currently unresolved, and the cause of the al1–al14 cache orphaning.
- Can a calibration ladder be built deep enough to test the estimator in its failing regime (`d_raw − depth_limit >= 4`) while staying measurable?

## Runs

No new recorded runs — this investigation is a read over the 2026-07-20 batch (`runs/2026-07-20/`, 245 run dirs). Per-ladder mapping is in [reports.json](artifacts/reports.json) (`ladder.train_corpus` / `_variant` per entry). The probes in `artifacts/` call the search engine directly and record nothing.
