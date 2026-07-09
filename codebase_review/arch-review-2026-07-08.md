---
name: arch-review-2026-07-08
description: "Architecture review findings (2026-07-08) — prioritized structural debt in arc-lab; verify before acting, may be fixed later"
metadata:
  node_type: memory
  type: project
  originSessionId: 52448f9b-5f5f-462c-b1be-01fcf5019e5c
---

Architecture review pass on 2026-07-08 (at commit 6f38706, "Phase H of Stitch integration"). Overall verdict: architecture is sound — narrow `Solver` interface genuinely holds, layering is a clean acyclic DAG (`core` leaf < `eval`/`viz` < `solvers`; within dsl: `substrate` < `search` < `solver` < `analysis` < `learn`), optional deps leak-proof. Debt is concentrated, not pervasive.

**Top-3 systemic findings (causes, not symptoms) — verify each still applies before acting:**

1. **`Solver.predict` is too narrow for the DSL family → solve re-implemented 3×.** `predict` (solver.py), `analysis.runner._run_task`/`_score`, and `loop._solve_corpus` each re-derive search→rank-by-cost→evaluate→score; `_FALLBACK=Input()` defined twice. Fix: one `ProgramSearchSolver.solve()->RankedSolve` (programs+stats+fallback) that all three call; `predict` becomes a thin grid projection. Highest leverage; behavior-preserving.

2. **Constraint & cost "pluggability" is advertised but wired shut.** No call site passes `constraints=`; `Enumerate`/`BeamSearch` never call `self.accepts` (dead filter). Solver unconditionally re-sorts every search's output by `self.cost`, overriding "best first"; `OverlaySearch` ranks by bespoke subset-size ignoring `Cost`; only 2/7 strategies accept a `Cost`. Either make seams real or delete the unused injection surface.

3. **Substrate has `walk`/`children` (read) but no `map_children` (rebuild) → 4 hand-rolled walkers that drifted.** `Program.from_dict` (central if-ladder, not enforced by abstract methods), `rewrite_with` (**omits `AppFn` → silently fails to fold idioms in higher-order nodes — latent bug**), `_close_template`, `stitch_shim._resolve_types`. Fix: add `map_children`/visitor + `__subclasses__` round-trip test.

**Tier-2 cohesion:** `experiments.py` (698-line god-file: framework + diagnostic + ~480 lines E1–E10 fixtures); `stitch_shim.py` mis-named (only `_compress` is the stitch boundary; ~200 lines are a general s-expr codec + HM re-inference; imports antiunify privates); `harness.py` grab-bag (`train_usefulness` fragile 4-positional-RunSummary sig); `Enumerate` is two engines in one file.

**Tier-3 hygiene:** strategy stats-tail boilerplate ×6 / missing-output guard ×4 (no shared base helper); `OverlaySearch.max_symmetries`/`TileSearch.max_factor` un-configurable class attrs; `Library.get()` O(n) in hot path; `Primitive.is_unary` dead code; CLI `analyze` help lists llm/identity but rejects them, no `--metric`/`--model` flags; `anthropic>=0.40` floor predates the `thinking:adaptive` shape it sends; viz docstring claims Agg backend never set.

User chose to leave as report (not act) on 2026-07-08. Relates to [[arc-lab-project]], [[arc-lab-high-standards]].
