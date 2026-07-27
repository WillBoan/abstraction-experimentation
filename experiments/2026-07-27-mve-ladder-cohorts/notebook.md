# Building the MVE's real-ARC ladder set (2026-07-27)

The investigation that took `dae9d2b5` from one expensive, uncertified ladder to a set of eight
across three real ARC tasks — and the two machinery defects found on the way.

Abstract entries in [EXPERIMENTS.md](../../EXPERIMENTS.md): "The first certified real-ARC ladder…",
"A ladder run is 25x cheaper…", "The MVE's ladder set…". The follow-on analysis (and the corrections
it forced) is a separate investigation: [2026-07-27-mve-batch-analysis](../2026-07-27-mve-batch-analysis/notebook.md).

## Goal

`dae9d2b5-halves-union` cost 21,149,854 considered per cell against **4** optimally pruned, and had
never been certified. The 2026-07-26 attribution blamed floor breadth. Since the base `b` is pinned
by the TOP's vocabulary — every primitive the top needs sits in the pool at every level below it —
the question was whether the ladder is redesignable at all, and on what lever.

## The lever: the exponent, not the base

The answer is that a spine controls only the **exponent at each level**. And the old ladder's
exponent was *plumbing*: `crop_rect(g, head(halves_h(g)))` is d3 and only ONE of its three levels
computes anything — the other two convert `List[Rect] -> Rect -> Grid`.

**`split_h` / `split_v : (Grid) -> List[Grid]`** return the halves in the type consumers want,
making the same competence **d2**. The floor drops 6 -> 4 primitives. The general rule (now in
LADDER-PROCESS §5): a `Rect`-returning producer is right when the rect is an *address*; when every
consumer immediately crops it, the Grid-returning form saves a level everywhere.

## Log

### Probe 1 — ground-truth anchoring of the redesigned term
`artifacts/` equivalent ran in-session; the check is pinned permanently as
`tests/program_search/ladders/test_real_arc_anchoring.py`. Term
`overlay(0, map_color(nth(split_h(g),0),4,6), map_color(nth(split_h(g),1),3,6))` — **7/7** against
arc1-train ground truth, `d_raw` 4, `west` at d2 as predicted.

### Probe 2 — the abstraction that typed itself out of its own search  (DEFECT 1)
The 4-rung ladder linted **98 checks clean** and its consumer's wake then exhausted the entire
depth-2 space (230,497 considered) **without once composing the rung it had been gifted**, reporting
`unsolved`.

Diagnosis, by isolation rather than inspection: `west(input)` was unreachable at depth 1 while
`map_color(input,4,6)` was reachable — so the engine was not composing the abstraction at all. The
abstraction's `return_type` was **`a`**, a free type variable, not `grid`.

- `Program.result_type` reports a primitive's DECLARED return type without unification, so a
  template rooted at a POLYMORPHIC primitive (`nth : (List[a], Int) -> a`) derives `a` even though
  `split_h : (Grid) -> List[Grid]` pins it completely.
- An abstraction with an unpinned result is **not rejected** — the enumerator silently SKIPS it
  (`unpinned_type_var_mode='reject'`, the default in every preset).
- `lang/load.py::_template` builds the primitive WITH the declared signature, asserts it, and then
  **discards it**; `chain.py::oracle_libraries` rebuilds without one. Every prior rung in the repo is
  rooted monomorphically (`crop_rect`, `map_color`, `rot180`), which is why this never fired.
  `learn/engines.py` mints with no signature either, so learned abstractions had the same hole.

Fixed by a unifying inference in `make_abstraction`, applied **only** when the declared reading
leaves free variables — a refinement, so every existing abstraction keeps byte-identical types,
library serialisation and run identity. Regression tests:
`tests/program_search/substrate/test_abstraction_typing.py` (5 cases, including that inference
REFINES and does not invent — an unpinnable root still reports a variable).

**Dead end worth keeping:** my first fix was silently a no-op. `unify` returns the *same dict object*
when nothing new binds, so `subst.clear()` wiped the mapping `subst.update(unified)` was about to
read back. Copy before clearing.

### Probe 3 — the granularity pair, and a prediction that held then reversed
Two members over the new floor, same task, same top, same budget — only cut density differs.

- Fine (4 rungs), schedule `[2,2,2,2,2]`; coarse (2 rungs), schedule `[2,2,3]`.
- Registered prediction (written into the coarse member's header *before* running): folding the
  recolours into the top makes it d3, so the coarse member should be **more** expensive despite
  having half the rungs.
- At `max_pool` 150 the prediction **held**: every coarse skip search censored at 2M where the fine
  member's exhausted at ~300k.
- At `max_pool` 30 it **reversed**: coarse marginal 72,165 vs fine 100,973.

So the direction of the granularity comparison is **budget-dependent** — coarser trades rungs for
depth, and depth only bites while the base is large. (Both readings were later invalidated for a
different reason — see the analysis notebook.)

### Probe 4 — the speed calibration
Where a 45-minute run actually went: **raw arm 25,007,890 considered (76%)** vs laddered end-to-end
7,690,929 (24%).

`max_pool` was **saturated**: on `recolored_west` over `L_2`, pool 150/100/60 all cost 282,419 (the
pool never binds); 40 -> 86,289; **30 -> 12,159** (23x) still retaining the exactly-intended program;
20 -> unsolved.

`dae9d2b5-split-recolor-lean` (pool 30, one variable changed) reproduced its parent's verdict profile
**byte-identically** — 4/4 tractable, no skip paths, health 1.0 x4, all four rungs recovered by the
same mint names, same climb trace, same RQ1, same depth compression — at **25.4x** less spend and
**1m51s vs ~45min**.

**The generalisation error this later caused is recorded in the analysis notebook**: the pair shared
an all-depth-2 schedule, and I did not name that as a precondition.

### Probe 5 — the cohort template
A shape survey of all 400 arc1-train tasks: the exact two-halves geometry is **only three tasks**
(the earlier "10" counted separator variants). Testing six boolean combiners against ground truth:
`dae9d2b5` = **OR**; `94f9d214` and `fafffa47` = **NOR**, both vertical, both target colour 2,
differing only in the north palette (3 vs 9).

NOR without the mask tier: the obvious route (`mask_by_color` + `mask_complement` +
`paint_through_mask`) forces Mask-valued rungs (a wrapper per demo — the demo-affordability law) AND
puts a TERNARY writer in the floor. Instead **`swap_colors` inverts at the grid level**: recolour
each half to the target, `overlay` (grid-level OR), then swap 0 with the target. Every rung stays
Grid-valued; every demo is a full solution. Anchored **5/5** and **6/6**.

`artifacts/gen_nor_ladders.py` is the cohort template made concrete — one floor, one spine, one demo
generator, instantiated per task; the second task cost a colour constant. It mechanically asserts the
discriminating properties (both colours present in both halves, halves differing as patterns, the NOR
non-trivial), which is the deferred demo-pool selector scoped to one family.

## Artifacts

Each script is paired with its captured output by matched basename.

| script | what it showed |
| --- | --- |
| [`task_survey.py`](artifacts/task_survey.py) · [`.out`](artifacts/task_survey.out) | the exact two-halves geometry is only 3 arc1-train tasks; the screen leads' shapes |
| [`halves_rule.py`](artifacts/halves_rule.py) · [`.out`](artifacts/halves_rule.out) | six boolean combiners vs ground truth: `dae9d2b5`=OR, `94f9d214`/`fafffa47`=NOR |
| [`ground_truth_split_h.py`](artifacts/ground_truth_split_h.py) · [`.out`](artifacts/ground_truth_split_h.out) | the redesigned `split_h` term, 7/7 vs ground truth, `d_raw` 4 |
| [`anchor_nor.py`](artifacts/anchor_nor.py) · [`.out`](artifacts/anchor_nor.out) | the NOR terms anchored 5/5 and 6/6, `d_raw` 5 |
| [`abstraction_typing_diagnosis.py`](artifacts/abstraction_typing_diagnosis.py) · [`.out`](artifacts/abstraction_typing_diagnosis.out) | DEFECT 1 isolated: `west` typed `a` vs `grid`, unreachable at depth 1 |
| [`max_pool_sweep.py`](artifacts/max_pool_sweep.py) · [`.out`](artifacts/max_pool_sweep.out) | the pool saturates at ~60; 30 costs 23x less and still retains the intended program |
| [`gen_recolor_demo_grids.py`](artifacts/gen_recolor_demo_grids.py) · [`.out`](artifacts/gen_recolor_demo_grids.out) | the `dae9d2b5` recolour-rung demo grids |
| [`gen_nor_ladders.py`](artifacts/gen_nor_ladders.py) · [`.out`](artifacts/gen_nor_ladders.out) | the vertical-NOR cohort template (import-only; writes the `.ladder` files) |

**Runs.** Every cell is an ordinary content-hashed recorded run under `runs/` (gitignored). The
ladders' own committed artifacts — `spec.md`, `results.md`, `report.json` — live beside each ladder
in `docs/abstraction_ladders/ladders/<name>/` and are the durable record; `arc-lab runs --probes`
lists the probe cells.

## What shipped

- `split_h` / `split_v` in `substrate/primitives/regions.py`, registered.
- The `make_abstraction` unification fix + 5 regression tests.
- New advisory check `primitive-necessity` (and its own correction — see below).
- 8 ladders across 3 real tasks, all ground-truth anchored, all lint-clean.

**`primitive-necessity` was a false negative on the very ladder it was built for.** Gated on depth
>= 3 alone, it read `dae9d2b5-split-recolor` clean at an all-depth-2 schedule while `overlay` — needed
only by the top — took **98.8%** of a 230,497-considered cell. It now flags two independent reasons,
one per side of `b^d`: a deep carried level (the exponent) OR arity >= 3 (the base — a
ternary/variadic primitive is superlinear in the pool inside a single round, so depth never enters).

## Open questions handed to the analysis

Everything measured here was read off headline numbers in each `results.md`. Nothing cross-cutting
was computed, and no one had opened `cost_matrix`. That is what the next investigation did, and it
invalidated several claims above.
