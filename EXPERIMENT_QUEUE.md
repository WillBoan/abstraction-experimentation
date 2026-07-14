# Experiment queue

Planned experiments for arc-lab — a **drain-only queue**, rough priority order, top = next. This is _state, not events_ (the counterpart to `EXPERIMENTS.md`): it holds what we currently intend to run, and it only shrinks or gets deliberately re-fed.

**Priority spine (per [RESEARCH-2026-07-08.md](docs/RESEARCH-2026-07-08.md)):** real-ARC capability **bearings** (SEARCH census + a first real LEARN) → **axis-2 search-cost-graph mapping** (B1 partition decomposition / B2 floor-grain sweeps) → gap-climbing (intermediate type) → selection-correct governance _(deferred)_ → basis/ablation science. Two sections below: **Active** (next runs) then **Backlog** (deferred / downstream).

Floors are named per [substrate/primitives/_PRIMITIVE_BUNDLES.md](src/arc_lab/program_search/substrate/primitives/_PRIMITIVE_BUNDLES.md) (coherence-checked in `execution/bundle_sheet.py`).

**Discipline** (or this rots like its predecessor):

- **Drain on run.** When an experiment runs, its `EXPERIMENTS.md` entry is the record — delete the Active row in the same session. Rejected without running → delete too (log a dead-end entry first if the reason is itself a finding).
- **Active vs Backlog.** Active = intend to run next, specced enough to start. Backlog = real but deferred or gated; promote a row to Active when it's next and fully sized. Backlog only shrinks (run/reject) or gets promoted.
- **No IDs.** E-numbers are minted at run time, in the log — never here. Rows get names, not numbers.
- **Experiments only.** Machinery-level work is never queued here — `MACHINERY.md` tracks it (Status / Gates). The **Unmet machinery** column links each experiment to the not-yet-built mechanisms that gate it.
- **One row's worth of sizing.** The columns _are_ the sizing frame; full design is still design-time work for the experiment about to run.

---

## Active — next runs

| Experiment | Type | Starting primitives (floor) | Target / abstractor demands | Corpus | Params | Metrics / what to look for | Unmet machinery | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **arc1 preset partition census — `sym` only** | search | `SYMMETRY`=`sym` (1 run; `d4`/`synth` done, EXPERIMENTS.md 2026-07-14) | — (SEARCH: read the partition) | `arc1-train` (400) | preset as-shipped (sym depth3/arity4/harvest) | solve count (sanity vs 10) + `by_category`/`by_provenance` + outcome mix (`DEDUPED`/`PRUNED`/`EVICTED`); expect combinator (`overlay`/`tile`) arity blowup, not constant-leaf multiplicity, per the 2026-07-13 TILE-task finding | none — runs today (`analyze-run` surfaces the partition) | Deferred for cost (~32 CPU-min full-corpus, EXPERIMENTS.md 2026-07-13). Notebook: `experiments/2026-07-14-capability-census/` |
| **arc1 region-logic census** | search | `MASK_BASIC` (10 mask prims) | — (SEARCH) | `arc1-train` | `harvest`, depth 3, arity 2, pool 500, fill=none, monomorphize | **first** region-logic solve count on the full corpus (crop/mask tasks); which mask ops fire vs sit dead; `mask_difference` redundancy visible in the partition | `search --bundle <NAME>` path _or_ register a `Config` | Never run on the full corpus — real bearings on a new capability family |
| **arc1 perceiver-recolor census** | search | `PERCEIVE_TRANSFORM` (map/swap/filter_color + most/least_common_color) | — (SEARCH) | `arc1-train` | `harvest`, depth 3, arity 2, pool 500, fill=none | solve count + do the perceivers get used or sit as dead weight; `swap_colors` vs `map_color` usage | `search --bundle` _or_ register a `Config` | `harvest` misses recolor-to-a-_new_-color (accepted for the census; a `finite-enumerate` variant is the follow-up) |
| **point the loop at real ARC** | learn | `SYMMETRY` (alt: `ATOMIC`) | observed — no known target; demands a **cross-task recurring subtree** | `arc1-train` (train) + `arc1-eval` (transfer) | `harvest`, depth 3, arity 4, pool 500; `GreedyMDLLearnEngine(FrequentSubtree(min_frequency=2))`, `TwoPartMDL`, `iterations=3` | does anything mint at all? train↔eval transfer; partition/speedup before→after. **A null result answers the open "does the bootstrap climb on real ARC"** | `learn --bundle` _or_ a `Config` carrying a `FrequentSubtree` LearnSpec | The long-deferred standing move. `FrequentSubtree` not the default `AntiunifyPairs` — real solutions rarely share _whole-program_ structure |
| **learned intermediate type** | study | `MASK_MIN` (`nonbg_mask`, `crop_to_mask`) | `crop_to_content(g)=crop_to_mask(g,nonbg_mask(g))`; demands var-sharing (grid ×2) + abstraction over the **Mask** type | new synthetic (varied bg + content crop pairs) + heldout | `constant_sources=()`, deep depth3 / shallow depth2, arity 2, `AntiunifyPairs`, `iterations=5` | shallow `L1` 0 → `L2` all (enablement) + held-out transfer; the construct-**and**-consume-a-learned-type phenomenon | none (Mask + both prims shipped; the generic engine pools any hashable typed value) | Deepest gap-climbing, runnable today — the synthetic companion to the real-ARC batch |

**Next to spec (synthetic axis-2 sweeps — promote once sized):** `grain-spine` (`FLOOR→FLOOR_AFFINE→FLOOR_DIV→UNIVERSAL_FLOOR`, fixed geometric target — the cost-vs-grain curve) · `completeness-at-two-grains` (`MINIMAL_COMPLETE_FLOOR` vs `UNIVERSAL_FLOOR` — grain isolated from expressiveness) · `gifting-collapse` (gen→full pairs) · `payoff-mirror_index` (`FLOOR_AFFINE`, invent `mirror_index`; payoff = search-savings − invention-cost). These are the concrete rows of the Backlog "basis/ablation science" cluster.

---

## Backlog — deferred / downstream

| Experiment | Type | Starting primitives (floor) | Target / abstractor demands | Corpus | Params | Metrics / what to look for | Unmet machinery | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **reusable-idiom governance** | learn | `FLOOR_AFFINE` + `build_grid` (the E8/E9 environment) | `mirror_index(n,k)=sub(sub(n,k),1)`, minted for _reusability_ (not by type-fiat); demands **usefulness-scored selection** (train-side search-effort reduction per candidate) | E8/E9 reflection family (synthetic) | naive `FrequentSubtree` proposer + a usefulness-scoring `AbstractionSelector` vs `GreedyMDL` | does train-side usefulness mint the reusable idiom over the larger `COLOR` read-bodies, no type gag; selection _correctness_ (fix the `mirror_index` **false negative**) | search-aware / selection-correct governance (F4, 🔜); port the F5 usefulness score to the execution layer | **Deferred** (your call — needs a build, low value right now). The general open-ended fix to the E8 compression/reusability divergence; sibling of library-refactoring (shipped, E10) |
| **basis/ablation science** (cluster) | search / study | a _complete_ low floor (`UNIVERSAL_FLOOR` / `MINIMAL_COMPLETE_FLOOR`) | — (maps axis 2, not a single target) | synthetic grain ladders (per the sweeps above) | varies by probe | which abstractions invent + how fast (invention vs search) · which are hardest · do gifted mid-level primitives speed invention (which, how much) · primitive/machinery **ablations** — reshaping the search-cost graph | measurement layer (largely landed) + global completeness (L0 control block) | The **axis-2 payoff program** (RESEARCH-08). Its near-term concrete rows are the real-ARC bearings (Active) + the synthetic axis-2 sweeps queued under Active's "Next to spec" |