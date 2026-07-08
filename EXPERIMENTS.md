# Experiments

A shared human+AI **event log** of experiments and findings for arc-lab. Append-only, newest last. This records _what happened at a point in time_ — it does not mirror current state (that lives in the code, the regression locks, and `CLAUDE.md`).

**Discipline** (or this rots into noise):

- **Terse.** Hypothesis / what ran / result / interpretation / next. Not essays.
- **Record dead ends.** Negative results are as valuable as wins — often more.
- **Anchor to a commit** so the numbers stay reproducible.
- **Events, not state.** "On date X, measured Y" never goes stale; "current best is Y" does.
- **Planned work lives in `EXPERIMENT_QUEUE.md`.** When you log a run here, drain its queue entry there. `Next:` lines are events (what seemed next at the time); the queue is the canonical current list.

Entry template (tier the bullets; put the numbers in an explicit **Metrics** block so they're scannable):

```
## YYYY-MM-DD — <short title>
- **Commit:** <hash>
- **Question:** ...
- **Ran:** ...
- **Result:**
  - <one-line what-happened>
  - **Metrics:**
    - <metric>: <value> (<from → to>)
    - ...
- **Interpretation:** ...
- **Next:** ...
```

> Seed entries below reconstruct the findings made while building the first solvers (this is a back-fill; later entries are written as the work happens).

---

## 2026-07-03 — D4 geometric baseline (`dsl`)

- **Commit:** 498cdbb (measured on current code at a220dd5)
- **Question:** How far does "the output is one rigid whole-grid transform" get on ARC-1?
- **Ran:** `arc-lab eval dsl` on arc1-train and arc1-eval. Library = D4 (8 square symmetries), search = single application.
- **Result:** 7/400 train (2× rot180, one each flip_h / flip_v / rot90, 2× transpose); 0/400 eval.
- **Interpretation:** single rigid transforms are a real but tiny slice of ARC-1, and near-absent in the harder eval split.
- **Next:** expand expressiveness — but the obvious lever (composition) needs checking first.

## 2026-07-05 — D4 is closed under composition (dead end)

- **Commit:** a220dd5
- **Question:** Can we get more from D4 by searching _compositions_ of the 8 transforms?
- **Ran:** composed all 64 ordered pairs of the 8 primitives on a labelled 3×3 grid; counted how many produced a function outside the base 8.
- **Result:** 0/64 escaped — still exactly 8 distinct functions. (The 8 are the dihedral group D₄, closed under composition.)
- **Interpretation:** composition over D4 gains **nothing**. Expressiveness has to come from a different _combinator_ over the transforms' outputs, not from composition depth.
- **Next:** combinators that combine transformed _copies_ (overlay, tile).

## 2026-07-05 — Combinators lift, and generalise (`dsl-sym`)

- **Commit:** a220dd5
- **Question:** Can overlay (symmetry-repair) + tile (mosaic) — combining D4 _outputs_, no new transforms — lift the score, and does it generalise?
- **Ran:** prototyped the exact solver logic to _size_ each combinator on arc1-train first; then built `dsl-sym` and evaluated.
- **Result:** sizing predicted overlay = 3, tile = 9; the built solver got **19/400 train** (7 D4 + 3 overlay + 9 tile, exactly as predicted, 0 errors) and **7/400 eval**.
- **Interpretation:** the biggest single jump (7→19) used _zero_ new transforms — expressiveness came from _how outputs are combined_. It generalises (0→7 on unseen eval), so it's real abstraction, not train overfit. "Size the idea empirically before building" paid off; repeat it.
- **Next:** a _general_ composition engine over more atomic primitives.

## 2026-07-05 — Typed enumeration engine + atomic primitives (`dsl-synth`)

- **Commit:** a220dd5
- **Question:** Does a general bottom-up typed enumeration engine over atomic primitives (map_color, scale) find more?
- **Ran:** `dsl-synth` = ATOMIC_LIBRARY (D4 + map_color + scale) + `Enumerate` (typed, bottom-up, observational-equivalence dedup).
- **Result:** 11/400 train (7 D4 + 1 scale + 3 map_color); 1/400 eval.
- **Interpretation:** the engine works and the atoms add 4 over D4 — but modest.
- **Next:** does composition _depth_ help this time?

## 2026-07-05 — Depth-2 composition adds nothing here (key negative result)

- **Commit:** a220dd5
- **Question:** Does allowing depth-2 program composition (vs depth-1) solve more?
- **Ran:** `dsl-synth` at `max_depth=1` vs `max_depth=2` on arc1-train; plus a synthetic `map_color(rot180(x))` task solvable _only_ at depth 2.
- **Result:** depth-1 = 11/400, depth-2 = **11/400 (identical set)**, at ~30× the runtime. Synthetic task: depth-1 fails, depth-2 solves → the engine composes correctly; the vocabulary just doesn't benefit.
- **Interpretation:** depth is not the lever on this vocabulary. Sequential `map_color` can't express a color _swap_ (1→2 then 2→1 collapses), D4 is closed, and scale rarely composes. **Richer atoms are the lever** — a color _permutation_, crop-to-content, object extraction.
- **Next:** add composition-friendly atomic primitives (color permutation, crop, objects) and re-test whether depth-2 then pays. **[primary open direction]**

> Note: these numbers are pinned by `tests/test_integration.py` and were preserved unchanged across the subsequent behaviour-preserving refactors (Program-as-class, logging, Constraint/Cost — commits 7ed27de … ca9a52c).

---

## 2026-07-06 — Metrics instrument: run artifact + compression (build + validate)

- **Commit:** 00ed308
- **Question:** Can we measure abstraction formation directly — compression, search effort — rather than only solve-count? And does the instrument agree with a known object before we trust it?
- **Ran:** Built `SearchResult`/`SearchStats` (structured, standardised search-effort counters), a two-part-MDL `CompressionMetric` over the `Cost` family (`DL = library_bits + Σ program_bits`), and a content-hashed, cached, resumable `run` artifact (`arc-lab analyze`, gitignored trace + committed summary/library). Validated on `analyze dsl-synth --dataset arc1-train`.
- **Result:** 11/400 — _exactly_ the locked ids (7 D4 + 4 atomic). `program_bits=28` (verified = summed node counts), `library_bits=10`, `considered=283184`. All locks (7/19/11) preserved; `make check` green.
- **Interpretation:** the instrument reproduces the known object, so the metrics are trustworthy. Measuring the ruler first immediately paid off — it corrects the entry above: the 4 atomic solves are **2 scale + 2 map_color**, not "1 scale + 3 map_color".
- **Next:** transfer metric + the library-learning loop, then the low-primitive-floor experiment — does a minimal basis + learned abstractions re-derive D4? **[primary open direction]**

---

## 2026-07-06 — E1: the abstraction loop re-derives rot90 from the D4 generators

- **Commit:** 3538005
- **Question:** Does the library-learning loop actually _form abstractions_ — discover a useful factoring from solved programs, compress, and speed up search — on a controlled testbed with a known-reachable target?
- **Ran:** Built the mechanism (a `Param` hole node + closed-template learned primitives, `make_abstraction`), the wake-sleep loop (antiunify → greedy-MDL governance over the existing `CompressionMetric` → `Library.extended`), a three-library harness + a _behavioral_ (observational-equivalence) checker, and a deterministic testbed generator. **E1:** starting primitives `{flip_h, transpose}`, target `rot90` **withheld**; `arc-lab learn e1-rot90`.
- **Result:**
  - Learned `abs0 = transpose(flip_h($0))`, behaviorally **== target rot90** (matched; 0 missed, 0 novel).
  - **Metrics:**
    - compression: **×1.30** (DL 35→27)
    - speedup: **×1.42** (considered 143→101)
    - enablement: **9 tasks** solved only by the learned library (depth-1 budget)
    - locks 7/19/11 unchanged; `make check` green
- **Interpretation:** the loop forms a real, transferable abstraction on a known-answer microworld — the depth-2 word `transpose(flip_h)` collapses to a depth-1 primitive, and the collapse shows up in _both_ compression and speedup. Targets stayed pure observables (never guided learning), so the anti-teleological design holds. Caveats: the abstractor is v1 (recurring-identical programs, no variable-sharing), and the MDL library term is still flat (undercharges an abstraction's definition size).
- **Next:** E2 (cell-level `{read, set_cell}` → fixed-cell `swap_cells`), then E3 (varied-cell → earns LGG variable-sharing). Then richer testbeds and the low-primitive-floor.

---

## 2026-07-06 — E2: re-derive fixed-cell swap_cells from {read, set_cell}

- **Commit:** 0946c25
- **Question:** Does the loop form a genuinely _cell-level_ abstraction — a multi-step composition of `read`/`set_cell` — and how large is the search-collapse payoff at a lower floor?
- **Ran:** New primitives `read (Grid,Int,Int)→Color`, `set_cell (Grid,Int,Int,Color)→Grid`; `Enumerate(coord_ints=True)` mines coordinate `Int` leaves. Testbed: 8 tasks each swapping cells (0,0)↔(1,1) on 2×2 grids, **3 train demos each** (so a literal-colour program can't fit — the solution must `read`). `arc-lab learn e2-swap-cells`.
- **Result:**
  - Learned `abs0 = set_cell(set_cell($0,0,0,read($0,1,1)),1,1,read($0,0,0))`, behaviorally **== target swap_cells**.
  - **Metrics:**
    - compression: **×6.42** (DL 122→19)
    - speedup: **×104** (considered 31624→304) — the depth-4 solution collapses to depth-1
    - enablement: **8 tasks** (all, depth-1 budget)
- **Interpretation:** the mechanism works unchanged at the cell floor — no AST lambda needed, `read`/`set_cell` compose as ordinary typed transforms. The payoff is far larger than E1 because the raw solution is a depth-4 composition (11 nodes) collapsed to a single call: the deeper the gap the abstraction bridges, the bigger the compression/speedup. Fixed cells → identical solved programs → the simplest abstractor (no variable-sharing) suffices.
- **Next:** E3 — vary the cells so coordinates must generalise (variable-sharing).

## 2026-07-06 — E3 / E4: variable-sharing works; flat MDL bloats, two-part MDL fixes it

- **Commit:** 0946c25
- **Question:** With coordinates that recur across positions (a coord feeds both a `read` and a `set_cell`), does antiunification produce the _correct shared-variable_ abstraction — and does the governance keep the library clean?
- **Ran:** E3 testbed: 8 tasks swapping `(0,X)↔(1,Y)` for varied `(X,Y)` on 2×2 grids. Added variable-sharing to `AntiunifyPairs` (a memo mapping a differing subterm pair to one shared `Param`). **E3** under the flat `CompressionMetric`; **E4** the _same_ environment under `TwoPartMDL` (charges each abstraction its definition size).
- **Result:**
  - Both learned the correct general `abs0 = set_cell(set_cell($0,0,$1,read($0,1,$2)),1,$2,read($0,0,$1))` — `$1`,`$2` each shared across two positions, behaviorally **== target swap_cols**.
  - **Metrics:**
    - E3 (flat MDL): **16 abstractions** — abs0 + 15 marginal specialisations (`abs0($0,0,0)`, …): _library bloat_
    - E4 (two-part MDL): **1 abstraction**, no bloat
- **Interpretation:** two findings. (1) **Variable-sharing is correct** — the memo gives the least-general-generalization that keeps a swap sound. (2) **The flat library cost is a broken governance objective**: a specialisation that saves 2 nodes still nets negative, so the loop hoards them. Charging the _definition size_ (two-part MDL) makes a marginal specialisation cost more than it saves → it is rejected. This is the "abstraction governance" problem made concrete, and the cheapest principled fix. Kept both metrics (flat baseline + `TwoPartMDL`) so the regimes stay comparable.
- **Next:** richer testbeds (perceive→transform, masks), and the low-primitive-floor — where governance pressure will matter far more.

---

## 2026-07-06 — E3 analysis → loop hardening (dedup + DL-stop)

- **Commit:** 3ccc2b1
- **Question:** _Why_ did E3's flat-MDL run bloat to 16 abstractions — and is two-part MDL the only thing keeping the loop honest?
- **Ran:** Inspected E3's learned library + per-generation history, then added two loop safeguards — library-dedup (never re-mint a template already a primitive) and a DL-monotonicity stop (discard a generation that doesn't lower total DL) — and re-ran E3.
- **Result:**
  - The 16 were only **4 distinct** abstractions (abs0 + 3 specialisations); the 3 were **re-minted every generation** under new names, and total DL _climbed_ 20→23→26→29→32.
  - **Metrics (E3, before → after hardening):**
    - abstractions: 16 → **4**
    - generations run: 5 → **1**
    - E1 / E2 / E4: unchanged
- **Interpretation:** the bloat had **three** causes, not one. (1) greedy over-abstraction _within_ a generation [flat MDL — the one two-part MDL/E4 fixes]; (2) no dedup against the library, so duplicates get re-minted; (3) no convergence guard, so DL climbs to the generation cap. Two-part MDL _masked_ (2) and (3) by removing the incentive, but they were latent — the hardening addresses them directly, independent of the metric. A deeper root cause remains noted: `Enumerate` keeps the _first-considered_ program per behaviour (library order), not the smallest, so the wake can return a longer program the next sleep then "compresses" — a keep-smallest fix is worth doing later.
- **Next:** richer testbeds and the low-primitive-floor.

---

## 2026-07-07 — Machinery bundle: governance ABC · subtree-match · keep-smallest · cost-guided beam

- **Commit:** aa8e5df (search: keep-smallest + beam; learn plug points in 4461a9f)
- **Question:** Ship the four tractable `🔜` MACHINERY mechanisms — F1 cost-guided beam, F3 subtree-match rewrite, F4 governance-as-a-plug-point + keep-smallest wake — without disturbing the E1–E4 objects or the 7/19/11 locks. Does anything move?
- **Ran:** Implemented all four (MACHINERY.md rows flipped ✅; lambda-index F0 deferred). Re-ran E1–E4 (`arc-lab learn`, incl. a fresh-cache E1) and `arc-lab eval dsl-beam / dsl-synth --dataset arc1-train`.
- **Result:**
  - `make check` green (114 tests, +8 new); locks 7/19/11 unchanged.
  - **Metrics:**
    - E1–E4 identical to baseline: E1 ×1.30 / ×1.42, E2 ×6.42 / ×104, E3 4 abstractions / novel=[abs1,abs2,abs3], E4 1 abstraction / no bloat.
    - `dsl-beam` (beam_width=16): **11/400 == `dsl-synth` 11/400** (same task ids).
- **Interpretation:** All four are behaviour-preserving everywhere we can measure today — as predicted, a **null result with a reason**. Subtree-match and keep-smallest are no-ops on E1–E4 (templates match at the whole-program root; the cell-swap solutions are already unique-shaped minimal programs), and the beam is near-lossless on the atomic floor (its grid pool never exceeds the width, so the cost-ranked frontier keeps everything the blind cut kept). The value is **latent**: subtree-match bites on heterogeneous corpora, keep-smallest on libraries with size-varying equivalents, the beam once a vocabulary's grid pool actually explodes (objects / cell-floor) — none of which exist yet. What _did_ change structurally: governance is now a swappable `AbstractionSelector` (`GreedyMDL` default), and `Cost` is finally consumed by a search (`BeamSearch`). Net: the critical path collapses to a single remaining keystone, **lambda-index binding (F0)**.
- **Next:** the runnable-today queue (perceive→transform, layered abstraction) exercises the loop on real abstractions with zero new machinery; the low-primitive-floor keystone now waits only on lambda-index.

---

## 2026-07-07 — Landscape & build-strategy review (Ferré/MADIL · Stitch · CompressARC · the field)

- **Commit:** 091d717 (docs only — no code touched)
- **Question:** Where does this project sit vs. prior art, and how should we balance building machinery ourselves vs. adopting third-party tools (YAGNI-vs-rework, in service of the research not the score)?
- **Reviewed:** Ferré's ARC-MDL / MADIL (object-centric _descriptive_ MDL, `L(M)+L(E|M)`, MDL-guided refinement, OCaml/GPLv3, single-CPU, **2%→7% ARC-1**, _no cross-task library learning_); Stitch (top-down library-learning compression, 3–4 orders faster than DreamCoder) + babble/egg + LILO + AbstractBeam; CompressARC (pure-MDL neural, no pretraining, **~20% eval / ~4% ARC-2**); the LLM-TTT / evolutionary frontier (ARChitects 53.5%, SOAR; "fast search still beats smart search"; ARC-2 collapse).
- **Findings:**
  - Pure symbolic/MDL ARC solving lands single-digit→~20% _as a score_ — not our deliverable; understanding is. We sit **deliberately off the LLM-TTT frontier** (it trades away the determinism/inspectability that make findings mean anything).
  - The **descriptive (perceive/render) half** is the identified highest-leverage empty region — Ferré is a worked existence proof. The **unoccupied position:** descriptive representation × cross-task library learning.
  - **Adopt don't rebuild:** Stitch for F4 invention-at-scale, egg/babble for equivalence-at-scale, Hodel's `arc-dsl` as vocabulary reference; own the substrate + instrumentation. Build the lambda-index keystone as a **Stitch-compatible De Bruijn index** (serves the low-floor thesis _and_ cheap future adoption).
- **Interpretation / strategy:** captured in [MACHINERY-STRATEGY-2026-07-07.md](MACHINERY-STRATEGY-2026-07-07.md) (the build methodology); frame updated in [RESEARCH-2026-07-07.md](RESEARCH-2026-07-07.md) (supersedes 07-06); [MACHINERY.md](MACHINERY.md) / [ONTOLOGY.md](ONTOLOGY.md) annotated surgically.
- **Next:** the F0 substrate keystone (De Bruijn λ-index); then shift the workload from synthetic microworlds toward real ARC tasks so reality writes the build queue.

---

## 2026-07-07 — F0 keystone: the Stitch-compatible De Bruijn lambda substrate (`build_grid`)

- **Commit:** a490432
- **Question:** Build the lambda-index binding — the one `unbuilt` F0 row under the low-floor thesis — as a general, Stitch-compatible substrate, and verify a single size-general `build_grid` program can express D4 geometry. (Substrate only; the search + pixels→D4 experiment are the deferred follow-on, per the barbell + Principle 5.)
- **Ran:** Added two AST nodes — `Var` (De Bruijn `$i`, distinct from `Param` = Stitch's `#j`) and `Lam` (unary `(lam …)`) — plus a `scope` channel on `evaluate` (env-based/closure interp → no index-shifting), a runtime `Closure` value, an opaque `FN` type, and the `build_grid`/`width`/`height`/`sub` clique (`BUILD_LIBRARY`, wired into no locked solver). Hand-verified by construction (no search).
- **Result:**
  - A single program `build_grid(width(input), height(input), lam(lam(read(input, $0, sub(sub(width(input),1), $1)))))` re-derives `rot90` on grids of **any shape** (drove 2×3→3×2, 4×2→2×4, all == `np.rot90`); likewise `flip_h`, `transpose`.
  - **Metrics:**
    - `make check` green (121 tests, +7 new); locks 7/19/11 unchanged; mypy `--strict` clean.
    - De Bruijn correctness, `to_dict` round-trip, and `make_abstraction` over a `build_grid` template (arity 1 — loop vars stay internal) all pass.
- **Interpretation:** The keystone lands as a *representation*, not yet a capability — the substrate is proven by hand, but nothing *searches* for `build_grid` programs yet. Two-channel binding (`env`=`#j` abstraction args vs. `scope`=`$i` bound vars) is what lets a size-general geometry program mint cleanly as an abstraction, and env/closure evaluation sidestepped De Bruijn's index-shifting entirely. Cost was modest and contained (one `FN` tag, a runtime `Closure`, ~physics-only churn in `program.py`), and it's Stitch-shaped so future invention-engine adoption is near-drop-in. Also renamed `Param`'s display `$0`→`#0` to match Stitch's `#j` and free `$i` for `Var`.
- **Next:** the bespoke `build_grid` search (open-term body enumeration — "where does search break?"), then pixels→D4 through the loop (does a learned `mirror_index` bootstrap the deep D4 members?). Or, per the strategy, point the loop at a real ARC slice instead of another microworld.

---

## 2026-07-07 — BuildGridSearch: open-term body enumeration + the "where does search break?" sweep

- **Commit:** 8b0819b
- **Question:** Can a bespoke search find size-general `build_grid` programs (whose bodies are *open terms* — free `$i` — that `Enumerate` can't pool), and *where does it break*?
- **Ran:** Built `BuildGridSearch` (`search/build_grid_search.py`): enumerate INT coordinate-expressions over `{$0, $1, width, height, 0, 1}` composed with `sub`, deduped by a *per-cell* battery signature (obs-equivalence lifted to cells), cost-beam bounded; assemble `build_grid(dh, dw, lam(lam(read(input, row, col))))` over dims that match the output shape, cost-ordered early-exit on the first (min-cost) consistent program. Swept depth × beam over the seven D4 members.
- **Result:**
  - Finds `rot90`/`flip_h`/`transpose` as single size-general programs that generalise to unseen shapes; the whole ladder is reachable at `max_coord_depth=2, beam=128`.
  - **Metrics (the ladder):**
    - depth: `transpose` solvable at depth 0 (bare `$0`/`$1`); every reflection/rotation needs depth **2** (a reflection `n-k-1` is inherently two `sub`s — nothing new at depth 1). Program size ladder 11 (transpose) → 16 (single reflection) → 21 (rot180 / anti_transpose).
    - **beam cliff:** at depth 2, all reflection members are found *only* at beam **128**, and fail sharply at beam ≤ 64 — the reflection expression sits at rank 64-128 in the cost-ranked pool, so a tighter beam *silently* drops it.
    - effort (beam 128, early-exit): `rot90` ~700 candidate-checks / ~130ms; `rot180` ~15k / ~270ms.
- **Interpretation:** open-term enumeration works, generate-and-test over *behaviours* (out-of-bounds `read` + cell-battery dedup prune the space). But it does **not** degrade gracefully — there is a hard beam cliff, because the correct coordinate formula is buried deep in the cost ranking. This is the concrete "where search breaks", and it predicts the bootstrap: a learned `mirror_index` would collapse the reflection to a depth-1 call, moving it to the *top* of the ranking → findable at tiny beam.
- **Next:** run it through the loop (pixels→D4).

## 2026-07-07 — pixels→D4: the loop re-derives D4 (E5/E6/E7), and a bound-var scope bug

- **Commit:** 73af6e5
- **Question:** Starting from the cell-render floor (`{read, set_cell, width, height, sub, build_grid}`, **no D4 primitive**), does the wake-sleep loop re-derive geometry as size-general `build_grid` abstractions — and does a shared `mirror_index` bootstrap the ladder?
- **Ran:** `E5` (rot90 alone), `E6` (full D4 ladder, naive proposer), `E7` (same ladder, a **bound-var-safe** proposer). Tasks are multi-shape demo sets (three varied shapes) so the solved program must be size-general. Taught antiunify to descend `Lam`/`Var`; `search = BuildGridSearch`, `enablement = Enumerate(depth 1)` (which now skips `FN`-typed prims instead of `KeyError`-ing).
- **Result:**
  - **E5:** learned exactly `abs0 = build_grid(width(#0), height(#0), lam(lam(read(#0, $0, sub(sub(width(#0), $1), 1)))))`, behaviorally **== rot90**. matched=[rot90], 0 novel, enablement=6. Clean re-derivation.
  - **E6 (naive):** matched=**['flip_v']**, missed 5, **6 novel** broken abstractions. Whole-program pairwise antiunification generalises *across* members by holing bound-var-containing coordinate subterms into abstraction params (`read(#0, #1, #2)`) — a **scope violation** (`$i` is per-cell; `#j` is per-call). Worse, two-part MDL *prefers* the broken abstraction (it "compresses" by covering several members) — compression and correctness diverge.
  - **E7 (bound-var-safe proposer):** matched=**all 6** D4 members, 0 missed, 0 novel, enablement=24. The fix: refuse to hole a differing subterm that contains a bound `$i`; only the sound per-member recurrences mint.
  - **Metrics:** `make check` green (130 tests, +9); locks 7/19/11 + E1-E4 unchanged. E7 DL L1→L2 = 390→492 (compression **×0.79**, i.e. *worse*).
- **Interpretation:** the low-floor thesis holds — the machinery re-derives the entire dihedral group from pixels, size-generally, blind. Two findings fall out: (1) a real **antiunification soundness bug** — it must respect the `$i`/`#j` boundary (now a swappable `bound_var_safe` flag; E6/E7 are the flat-vs-fixed contrast, à la E3/E4); (2) **`mirror_index` does not bootstrap** — E7's DL *rises* because the six members are six separate large abstractions with no shared reflection idiom. Whole-program antiunification can't mine a recurring *subterm*; that needs a **frequent-subtree proposer** (MACHINERY F4, unbuilt) — the concrete next machinery the compression signal is pointing at.
- **Next:** a frequent-subtree / e-graph proposer (to invent `mirror_index` and actually compress the ladder); or, per the strategy, point the loop at a real ARC slice.

## 2026-07-07 — pixels→D4 compresses: a frequent-subtree proposer + primitive-driven search (E8/E9)

- **Commit:** 8051ad4
- **Question:** Does a **frequent-subtree proposer** invent `mirror_index` and finally *compress* the D4 ladder (inverting E7's ×0.79) *and* speed the search past its beam cliff? Run as a **grammar × learning matrix**: `{sub}` (E8) vs the honest affine `{sub,add,mul}` (E9).
- **Ran:** Added `add`/`mul` (the affine family); made `BuildGridSearch` **primitive-driven** (composes every library `INT^n→INT` op, so it can *reuse* a learned coordinate); a `FrequentSubtree` proposer (mine Lam-free proper subtrees; sound Var-holing — the mirror image of `bound_var_safe`). E8 = sub-only (beam 128); E9 = affine (beam **224**, the threshold to solve a reflection at all — ≤192 fails). `enablement = BuildGridSearch` at a *tight* beam (the cliff).
- **Result:**
  - **A rewrite bug, first:** `rewrite_with` didn't descend into `Lam` bodies, so `mirror_index` — which lives *inside* the coordinate lambda — never folded and nothing minted. Fixed (descend `Lam.body`; E1–E7 unaffected).
  - **The divergence (the load-bearing finding):** the *naive* proposer + greedy MDL mints two **unreusable `COLOR` read-body idioms** (`read(#0,#1,sub(sub(width(#0),#2),1))` and its height twin — the two "axis half-reflections"), **not** `mirror_index`. They compress the *train corpus* more, but `BuildGridSearch` can't compose a `COLOR` read-body → re-solve DL *worsens* (×0.95), zero speedup. And iteration can't recover `mirror_index`: once the read-bodies absorb it into their *definitions*, the corpus-only proposer can't see it (no library refactoring). **Train-DL ≠ reusability** — and a compression-optimal inventor (Stitch) would hit this too.
  - **The fix (a labelled stopgap):** scope invention to the signature the search composes (`INT^n→INT`), **derived from the search itself** (`SearchScopedFrequentSubtree(composes=search.composes_signature)`, not a declared type). Then `mirror_index` mints and the search reuses it.
  - **E8 (sub):** `abs0 = sub(sub(#0,#1),1)`, behaviorally **== mirror_index**. matched, 0 missed/novel.
  - **E9 (affine):** `abs0 = sub(#0, add(#1, 1))` — *same behavior* via `add` (the checker matches by signature). Same idiom, different structural form → invention is robust to the grammar.
  - **Metrics:** `make check` green (139 tests, +9); locks 7/19/11 + E1–E7 unchanged.
    - compression (L1→L2 DL): E8 390→348 **×1.12**, E9 392→350 **×1.12** (inverts E7's ×0.79)
    - speedup (considered): E8 **×3.47**, E9 **×5.00** (bigger against the wider grammar)
    - enablement (tight-beam solves, L2 not L1): **20 tasks** (all 5 reflection members) in both — the beam cliff dissolved
    - base blowup (L1 considered): sub 77.1k → affine 234.8k (**~3×**) — the measured cost of `add`/`mul`
- **Interpretation:** the `mirror_index` bootstrap works — a shared coordinate factor is invented, *reused* by the primitive-driven search, so the ladder compresses (×1.12) and the cliff dissolves (×3.5–5); the affine matrix shows the same idiom emerges under a wider grammar and matters *more* there. But the headline is the **compression/reusability divergence**: greedy MDL over train-DL prefers the largest compressor, which is not the reusable one. The type-scoping that recovers `mirror_index` is *anti-open-ended* (can only invent what the search already composes, foreclosing new-type / layered vocabulary) — hence a **stopgap**. The general fixes are **search-aware / transfer-aware governance** (score by usefulness, not node-count) or **library refactoring** (compress the *library*, not just the corpus — the missing half of iteration; ≈ Stitch's core). Full approach catalog in `MACHINERY.md` F4.
- **Next:** the general fix — search-aware governance, or library refactoring **via Stitch** (deferred to real-ARC scale per MACHINERY-STRATEGY's "not yet"); and the standing move — point the loop at a real ARC slice.
