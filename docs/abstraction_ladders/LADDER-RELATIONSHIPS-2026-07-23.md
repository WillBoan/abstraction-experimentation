# Ladder relationships & cohorts (2026-07-23)

How two ladders relate, what comparison each relationship licenses, and how to record it. A dated snapshot; the living notion of a run's cost model is [EXECUTION.md](../EXECUTION.md) and the checks are [LADDER-CHECKS-2026-07-21.md](../archive/LADDER-CHECKS-2026-07-21.md).

## Why this exists

The cfb2ce5a task now has four ladder variants (v1 basic, v2 collapsed, v3 parameterized, v4 fold). They are _comparable_ to different degrees, and the degree determines what a comparison MEANS. This file names the relationships so a comparison is never read as more (or less) controlled than it is.

## Two axes

Every comparison needs a **shared top task** — same target, or there is nothing to compare. Given that, two orthogonal axes:

**Axis 1 — the floor (what cancels).**

- **Cohort — shared floor + top.** Raw search cost is identical, so it _cancels_: costs are directly subtractable and any difference is attributable to the decomposition alone. The controlled comparison. (v1 and v3 are a true cohort; v2 and v4 changed the floor and are not.)
- **Ablation — shared top, different floor.** Raw does NOT cancel — and that is the measurement: the raw-cost **delta between the floors quantifies how much work the changed primitive was doing**. This is the "lower the floor" comparison, and it is a library ablation (what `run_study` already does over `L1/L2/L3`).

**Axis 2 — the rungs (within shared endpoints).**

- **Sub-ladder (skip)** — one ladder's rungs are a subsequence of the other's (a skip-rung version).
- **Refinement** — a rung is split into several (`B` becomes `F, G`), or the reverse (coarsening).
- **Sibling** — same endpoints, genuinely different rung sets (neither a subset nor a refinement).

## Each relationship IS an experiment

| Relationship | Licenses | Existing thread |
| --- | --- | --- |
| Cohort | direct cost subtraction (raw cancels) | the headline comparison |
| Ablation | "how much was the primitive worth?" (read the raw delta) | library ablation / `run_study`; the floor-lowering work |
| Sub-ladder (skip) | rung **necessity** — a rung is skippable iff its consumers can inline it and stay tractable | `double-jump-intractable`; the certificate's skip-paths |
| Refinement | **granularity** — more smaller rungs vs fewer bigger ones | AL-PLAN Phase 3 granularity family |

So these are not four loose groupings; they are the edges of one structure, and each edge already has an experiment attached.

## Handling: declare the top, derive the rest

- **Declare only the shared top** — a `task:` pointer in the `.ladder` (the durable intent, "targets ARC task X", which survives the floor changing).
- **Derive everything else** from content: cohort membership from the floor content-hash; the rung relationship (subset / refinement / sibling) from comparing rung sets; skippability from the double-jump already computed. A declared `group:`/`cohort:` field would drift the moment a floor is edited — same reason `is_chain` is derived, never declared.
- **A cohort is a report, not a folder.** Folders encode _handling_; a cohort is a _comparison lens_. Its natural home is a study/report over the members, not the directory tree. (Per-task subfolders earn their keep only once a task spawns many ladders — and would need the recursive-glob fix first.)

Vocabulary to lock in: **task set** (shared top) ⊇ **cohort** (shared floor too); within a cohort, **sub-ladder / refinement / sibling**; across floors, **ablation**.

## The combinatorics is an upper bound, not the object

The count of sub-ladders is calculable — skip-allowed subsequences of `N` levels of size `3..N-1` are `2^N - N(N+1)/2 - 2`; contiguous ones are `N(N-3)/2`. Two caveats keep it from being the useful object:

1. **A sub-ladder keeps the top**, so the top is not a free choice. Fix top + floor and count subsets of the `R` interior rungs (`2^R` minus the degenerate sizes and the parent) — smaller than `2^N`, because it drops the subsequences that omit the top.
2. **Most subsets are not achievable.** Rungs form a dependency DAG; dropping a rung a kept rung depends on means _inlining_ it, and whether that stays under budget is exactly `double-jump-intractable`. The reachable sub-ladders are the necessity-tractable subset, not the free `2^R`. **The count bounds; the depth-sandwich selects.**

So treat the lattice as a space you _sample_ at meaningful points (a chosen skip, a chosen refinement), not one you enumerate. The value of naming a relationship is that it tells you what a given pair's comparison supports.

## Status

**Partly wired (2026-07-23).** `arc-lab diff-ladder A B` derives the floor relationship and picks the validator this table licenses: same floor → the static layer (`analysis/equivalence.py::static_equivalent`, unfold-and-compare then equational normal forms — no bodies, no grids); different floor → an EXACT observational diff over `analysis/grids.py::exact_grids`, which needs both sides implemented. It reports the verdict **and how it was reached**, with exit codes EQUAL=0 / DIFFERENT=1 / INCONCLUSIVE=2.

The headline case works with **zero primitive implementations**: cfb2ce5a `v1` vs `v3` (a same-floor refactor) is proved EQUAL by unfold-and-compare, while `v1` vs `v4` (a floor change) honestly reports INCONCLUSIVE rather than guessing.

**Both layers have now been exercised for real (2026-07-23).** The cfb2ce5a floor was implemented (`substrate/primitives/tiles.py`), which lets the static proof be cashed out: `v1` and `v3` agree on the actual ARC grids, exactly as unfold-and-compare predicted before any body existed. The observational layer ran the _ablation_ direction — a reference primitive against a lower-floor decomposition — and settled two cases: `retain_colors` **is** the mask algebra (2,400 cases, 0 splits, so it leaves the floor), while `largest_filled_square` is not decomposable at all, because nothing in the substrate produces a list of regions to select among. See EXPERIMENTS.md 2026-07-23 and TODO items 22-23.

One caveat the work surfaced, worth keeping in view here: **"has assumed primitives" is not the same predicate as "is a draft".** Implementing a floor makes a sketch resolve like a real ladder while it still has no testbed; anything keying off `loaded.assumed` to mean "draft" is wrong (`cli/lint_ladder.py` was, and is fixed).

Still a mental model: the `task:` metadata + a derived cohort-hash (add them when the second lowered-floor ladder exists, so they are tested against real cases), the rung-relationship classification (sub-ladder / refinement / sibling), and the sub-ladder lattice itself.
