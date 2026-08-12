# dae9d2b5: plumbing depth, and an abstraction that typed itself out of its own search

**Investigation:** can the first real-ARC ladder be made tractable by redesign rather than by budget?
**Historical abstract:** [EXPERIMENT_LOG.md](../../EXPERIMENT_LOG.md), entry `2026-07-27 — The first certified real-ARC ladder`.
**Outcome:** yes — `dae9d2b5-split-recolor` is **ADMITTED**, the program's first certified ladder on a real ARC task. Two machinery defects found on the way, one of them a silent unclimbability bug that no lint could see.

---

## The question

`dae9d2b5-halves-union` cost **21,149,854** considered per cell against **4** optimally pruned (2026-07-26). The attribution said the bill was `map_color`/`overlay`/`__const__` — none of which its rungs use. But those are needed by the **top**, and a climb has one library per level, so:

> the base `b` is pinned by the top's vocabulary and no rung redesign removes it.

Which leaves exactly one lever a spine controls: **the exponent at each level**. The question was whether that lever alone is enough.

## The answer, up front

It was, and the exponent was being spent on **plumbing**:

```
crop_rect(g, head(halves_h(g)))     d3  — two of three levels convert List[Rect] -> Rect -> Grid
nth(split_h(g), 0)                  d2  — one level, and it computes the thing
```

`split_h : (Grid) -> List[Grid]` (+ `split_v`) returns the halves in the type the consumers want. The floor drops 6 -> 4 primitives, every level runs at depth 2, and the ladder certifies.

**The general form:** a `Rect`-returning producer is right when the rect is used as an **address** (a paste target). When every consumer immediately crops it, the Grid-returning form saves a level *everywhere it is used*.

## Running log

### 1. Anchor the term first (the hard gate)

[`gt.py`](artifacts/gt.py) / [`.out`](artifacts/gt.out) — hand-authored the term over the new floor and checked it against arc1-train ground truth **before** any floor or demo work.

- `7/7` match (5 train + both held-out tests), `d_raw` 4, `west` at d2. Pinned in `test_real_arc_anchoring.py`.

### 2. Demo grids

[`seeds.py`](artifacts/seeds.py) / [`.out`](artifacts/seeds.out) — deterministic (no RNG), task-realizable `h x 2w` grids, asserted discriminating: both colours present in **both** halves, so `map_color(half, 4, 6)` is forced by the demo and the two halves are never equal.

First version was junk — a `variant % 3` bug gave several tasks identical grids, and `.replace(" ","")` ate the indentation. Rewritten with a cross-task duplicate assertion.

### 3. Lint: clean, and wrong

Both members linted **0 errors** (fine: schedule `[2,2,2,2,2]`; coarse: `[2,2,3]`). The new `primitive-necessity` check read the fine member **clean**. All of that was true and none of it was sufficient — see §5.

### 4. The probe convicted (and it was right to)

[`probe-01-prefix-censored.out`](artifacts/probe-01-prefix-censored.out) — `0/4 rungs probe clean` at the default guard. Every cell pinned at exactly 50,000, `overlay` at 99.7%.

Raised the guard **once**, explicitly to *size a budget*, not to buy an acquittal:
[`probe-02-prefix-exhausted-unsolved.out`](artifacts/probe-02-prefix-exhausted-unsolved.out) — and this is the cell that broke the case open:

```
wake  recolored_west-00   unsolved   230,497       <- EXHAUSTED, not censored
skip  dae9d2b5            no-skip    230,493
floor tax: pruned 11 vs full 230,497  [clean]
```

`unsolved` after exhausting the whole depth-2 space is not a budget fact. The target was reachable and the search never found it.

### 5. The bug hunt

Four probes, cheapest first. Two were dead ends, and both were worth running because each killed a hypothesis outright.

| probe | hypothesis | verdict |
| --- | --- | --- |
| [`why.py`](artifacts/why.py) | the target isn't really d2, or doesn't match its demos | **killed** — d2, in `L_2`, matches both train examples |
| [`pool.py`](artifacts/pool.py) | `max_pool: 150` truncates `west(input)` out of the pool | **killed** — `considered` *identical* at 150/400/1000/4000, so the cap never bound |
| [`consts.py`](artifacts/consts.py) | colour `6` isn't minted (it appears in no input grid) | **killed** — `COLOR 0..9` all minted. But it isolated the real symptom: `west(input)` **unreachable at depth 1**, while `map_color(input,4,6)` solved fine |
| [`abs.py`](artifacts/abs.py) | the abstraction itself is malformed | **confirmed** |

`abs.py` is the decisive A/B — same rung name, same ladder shape, two floors:

```
dae9d2b5-split-recolor: west   ['grid'] -> a       nth(split_h(#0), 0)          solved=False
dae9d2b5-halves-union:  west   ['grid'] -> grid    crop_rect(#0, head(...))     solved=True
```

**`nth(split_h(g), 0)` typed as `a`.** `Program.result_type` reports a primitive's *declared* return type without unification, so a template rooted at a **polymorphic** primitive derives a free type variable even when its argument pins it completely (`split_h : (Grid) -> List[Grid]`).

The consequence is the nasty part: an abstraction with an unpinned result is **not rejected** — the enumerator *silently skips* it (`unpinned_type_var_mode='reject'`, the default in every preset). So it costs nothing, finds nothing, reports nothing. **The ladder linted 98 checks clean and could not be climbed at any budget.**

`load.py::_template` builds the primitive *with* the declared signature, asserts it, and then **discards it**; `chain.py::oracle_libraries` rebuilds without one. Every prior rung in the repo is rooted monomorphically (`crop_rect`, `map_color`, `rot180`) — which is why this had never fired. `learn/engines.py` mints with no signature either, so **learned** abstractions had the same hole.

**Fix:** unifying inference in `make_abstraction`, applied *only* when the declared reading leaves free type variables — a refinement, so every existing abstraction keeps byte-identical types, library serialisation and run identity. Regression tests: `tests/program_search/substrate/test_abstraction_typing.py` (5).

> One self-inflicted detour worth keeping: my first inference returned `t0`, unresolved. `unify` returns the **same dict object** when nothing new binds, so `subst.clear()` emptied the very mapping `subst.update(unified)` was about to read back.

### 6. After the fix

[`probe-03-postfix-clean.out`](artifacts/probe-03-postfix-clean.out) — **4/4 rungs probe clean**. Every rung wakes as-intended at 2/2, sleep recovers at intended arity, and every skip search runs to **exhaustion** (`no-skip`, not `inconclusive`). Cells 230,497 -> 311,083.

[`run-ladder-fine.out`](artifacts/run-ladder-fine.out) — **certificate: ADMITTED.**

### 7. The granularity pair

[`probe-04-coarse.out`](artifacts/probe-04-coarse.out) — the coarse member (2 rungs, **same floor, same top, same budget**; only the cut density differs, which is what licenses the comparison).

Prediction, written into its header *before* running: folding the recolours into the top makes the top d3, so it should be **more** expensive despite having half the rungs.

Confirmed in direction. Both rungs wake as-intended and sleep recovers, but its skip test must reach d4 and **every skip search censors at the shared 2M budget** — where the fine member's *exhausted* at ~300k. **Fewer rungs cost more.**

Not certified: that needs the pair's shared budget raised (~20M) and both members re-run. That is a *second* budget escalation, which is an ask-the-human trigger — left as a decision rather than taken.

## Findings

| | |
| --- | --- |
| Certificate | **ADMITTED** — 4/4 jumps tractable, no skip paths, demonstration health 1.0 x4 |
| Learned climb | converged at iteration 2, **all 4 rungs recovered**; no junk, no cascade |
| RQ1 | **>= 10x** (raw arm censored at 25,007,890) — floor-relative, see the ladder's withheld-primitives declaration |
| Loop overhead | 3.08x |
| Depth compression | `d_raw` 4 -> max jump depth 2 |
| Cost per cell | 230,497 -> 341,629 exhausted (predecessor: 21,149,854) |
| Coarse member | wake/sleep clean, skip **inconclusive** at the shared budget |

**Runs:** 63 recorded cells (probe cells, the oracle chain, the climb, the raw arm) under `runs/2026-07-27/`. The full cell -> `run_id` mapping is in [`report.json`](../../docs/abstraction_ladders/ladders/dae9d2b5-split-recolor/report.json) rather than duplicated here; the raw arm is the last, `0b4d33c33c377526`.

## Dead ends and corrections (kept deliberately)

- **`max_pool` truncation** — plausible, cheap to test, wrong. `pool.py` is 12 lines and killed it in one run.
- **The colour battery** — `6` appears in no *input* grid and constants are documented as input-derived, so this looked decisive. `_finite_enumerate` mints `COLOR 0..9` unconditionally. Wrong, but it isolated the real symptom.
- **My own check was a false negative on the ladder it was built for.** `primitive-necessity` gated on depth >= 3 alone and read the fine member clean at an all-depth-2 schedule — while `overlay` took **98.8%** of a 230,497-considered cell. Now flags two independent reasons, one per side of `b^d`: a deep carried level (the exponent) **or arity >= 3** (the base — a ternary/variadic primitive is superlinear in the pool inside a *single* round, so depth never enters). [`sweep.py`](artifacts/sweep.py) / [`.out`](artifacts/sweep.out) is the batch-wide read after the change.
- **A retired claim in the predecessor's header.** It justified withholding `split_h` on the grounds it "would make each half-crop depth 1 and the whole ladder trivial". Measured: `nth(split_h(g), 0)` is **d2**, satisfies `proper-composition`, and the ladder built on it certifies with four real rungs. Corrected in the file.

## Note on the artifacts

`*.py` outputs were regenerated **after** the typing fix, so they show the fixed behaviour; the pre-fix values are quoted inline above and preserved verbatim in `probe-01`/`probe-02`. `pool.py` and `consts.py` therefore now read `solved=True` where the investigation saw `solved=False` — that difference *is* the fix.

## Open

- The coarse member's certificate (shared budget -> ~20M, re-run both so the comparison stays licensed).
- `split_v` ships alongside `split_h` and unlocks `94f9d214` / `fafffa47` on the same skeleton — untested.
- `primitive-necessity` now fires on ~half the batch. It is a map to read against attribution, not a defect list; whether that is the right noise floor is unsettled.
