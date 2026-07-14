# Experiments

A shared human+AI **event log** of experiments and findings for arc-lab. Append-only, newest last. This records _what happened at a point in time_ — it does not mirror current state (that lives in the code, the regression locks, and `CLAUDE.md`).

**Discipline** (or this rots into noise):

- **Terse.** Hypothesis / what ran / result / interpretation / next. Not essays.
- **Record dead ends.** Negative results are as valuable as wins — often more.
- **Anchor to a commit** so the numbers stay reproducible.
- **Events, not state.** "On date X, measured Y" never goes stale; "current best is Y" does.
- **Planned work lives in `EXPERIMENT_QUEUE.md`.** When you log a run here, drain its queue entry there. `Next:` lines are events (what seemed next at the time); the queue is the canonical current list.
- **This is the abstract; the appendix is `experiments/`.** For a non-trivial investigation, the full write-up + the probe scripts and their outputs live in a [experiments/](experiments/) lab notebook (see [experiments/README.md](experiments/README.md)); link it from the entry. Keep the entry here terse.

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
- **Interpretation / strategy:** captured in [MACHINERY-STRATEGY-2026-07-07.md](docs/MACHINERY-STRATEGY-2026-07-07.md) (the build methodology); frame updated in [RESEARCH-2026-07-07.md](docs/archive/RESEARCH-2026-07-07.md) (supersedes 07-06); [MACHINERY.md](MACHINERY.md) / [ONTOLOGY.md](ONTOLOGY.md) annotated surgically.
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
- **Interpretation:** The keystone lands as a _representation_, not yet a capability — the substrate is proven by hand, but nothing _searches_ for `build_grid` programs yet. Two-channel binding (`env`=`#j` abstraction args vs. `scope`=`$i` bound vars) is what lets a size-general geometry program mint cleanly as an abstraction, and env/closure evaluation sidestepped De Bruijn's index-shifting entirely. Cost was modest and contained (one `FN` tag, a runtime `Closure`, ~physics-only churn in `program.py`), and it's Stitch-shaped so future invention-engine adoption is near-drop-in. Also renamed `Param`'s display `$0`→`#0` to match Stitch's `#j` and free `$i` for `Var`.
- **Next:** the bespoke `build_grid` search (open-term body enumeration — "where does search break?"), then pixels→D4 through the loop (does a learned `mirror_index` bootstrap the deep D4 members?). Or, per the strategy, point the loop at a real ARC slice instead of another microworld.

---

## 2026-07-07 — BuildGridSearch: open-term body enumeration + the "where does search break?" sweep

- **Commit:** 8b0819b
- **Question:** Can a bespoke search find size-general `build_grid` programs (whose bodies are _open terms_ — free `$i` — that `Enumerate` can't pool), and _where does it break_?
- **Ran:** Built `BuildGridSearch` (`search/build_grid_search.py`): enumerate INT coordinate-expressions over `{$0, $1, width, height, 0, 1}` composed with `sub`, deduped by a _per-cell_ battery signature (obs-equivalence lifted to cells), cost-beam bounded; assemble `build_grid(dh, dw, lam(lam(read(input, row, col))))` over dims that match the output shape, cost-ordered early-exit on the first (min-cost) consistent program. Swept depth × beam over the seven D4 members.
- **Result:**
  - Finds `rot90`/`flip_h`/`transpose` as single size-general programs that generalise to unseen shapes; the whole ladder is reachable at `max_coord_depth=2, beam=128`.
  - **Metrics (the ladder):**
    - depth: `transpose` solvable at depth 0 (bare `$0`/`$1`); every reflection/rotation needs depth **2** (a reflection `n-k-1` is inherently two `sub`s — nothing new at depth 1). Program size ladder 11 (transpose) → 16 (single reflection) → 21 (rot180 / anti_transpose).
    - **beam cliff:** at depth 2, all reflection members are found _only_ at beam **128**, and fail sharply at beam ≤ 64 — the reflection expression sits at rank 64-128 in the cost-ranked pool, so a tighter beam _silently_ drops it.
    - effort (beam 128, early-exit): `rot90` ~700 candidate-checks / ~130ms; `rot180` ~15k / ~270ms.
- **Interpretation:** open-term enumeration works, generate-and-test over _behaviours_ (out-of-bounds `read` + cell-battery dedup prune the space). But it does **not** degrade gracefully — there is a hard beam cliff, because the correct coordinate formula is buried deep in the cost ranking. This is the concrete "where search breaks", and it predicts the bootstrap: a learned `mirror_index` would collapse the reflection to a depth-1 call, moving it to the _top_ of the ranking → findable at tiny beam.
- **Next:** run it through the loop (pixels→D4).

## 2026-07-07 — pixels→D4: the loop re-derives D4 (E5/E6/E7), and a bound-var scope bug

- **Commit:** 73af6e5
- **Question:** Starting from the cell-render floor (`{read, set_cell, width, height, sub, build_grid}`, **no D4 primitive**), does the wake-sleep loop re-derive geometry as size-general `build_grid` abstractions — and does a shared `mirror_index` bootstrap the ladder?
- **Ran:** `E5` (rot90 alone), `E6` (full D4 ladder, naive proposer), `E7` (same ladder, a **bound-var-safe** proposer). Tasks are multi-shape demo sets (three varied shapes) so the solved program must be size-general. Taught antiunify to descend `Lam`/`Var`; `search = BuildGridSearch`, `enablement = Enumerate(depth 1)` (which now skips `FN`-typed prims instead of `KeyError`-ing).
- **Result:**
  - **E5:** learned exactly `abs0 = build_grid(width(#0), height(#0), lam(lam(read(#0, $0, sub(sub(width(#0), $1), 1)))))`, behaviorally **== rot90**. matched=[rot90], 0 novel, enablement=6. Clean re-derivation.
  - **E6 (naive):** matched=**['flip_v']**, missed 5, **6 novel** broken abstractions. Whole-program pairwise antiunification generalises _across_ members by holing bound-var-containing coordinate subterms into abstraction params (`read(#0, #1, #2)`) — a **scope violation** (`$i` is per-cell; `#j` is per-call). Worse, two-part MDL _prefers_ the broken abstraction (it "compresses" by covering several members) — compression and correctness diverge.
  - **E7 (bound-var-safe proposer):** matched=**all 6** D4 members, 0 missed, 0 novel, enablement=24. The fix: refuse to hole a differing subterm that contains a bound `$i`; only the sound per-member recurrences mint.
  - **Metrics:** `make check` green (130 tests, +9); locks 7/19/11 + E1-E4 unchanged. E7 DL L1→L2 = 390→492 (compression **×0.79**, i.e. _worse_).
- **Interpretation:** the low-floor thesis holds — the machinery re-derives the entire dihedral group from pixels, size-generally, blind. Two findings fall out: (1) a real **antiunification soundness bug** — it must respect the `$i`/`#j` boundary (now a swappable `bound_var_safe` flag; E6/E7 are the flat-vs-fixed contrast, à la E3/E4); (2) **`mirror_index` does not bootstrap** — E7's DL _rises_ because the six members are six separate large abstractions with no shared reflection idiom. Whole-program antiunification can't mine a recurring _subterm_; that needs a **frequent-subtree proposer** (MACHINERY F4, unbuilt) — the concrete next machinery the compression signal is pointing at.
- **Next:** a frequent-subtree / e-graph proposer (to invent `mirror_index` and actually compress the ladder); or, per the strategy, point the loop at a real ARC slice.

## 2026-07-07 — pixels→D4 compresses: a frequent-subtree proposer + primitive-driven search (E8/E9)

- **Commit:** 8051ad4
- **Notebook:** [experiments/2026-07-07-e8-e9-mirror-index-bootstrap/](experiments/2026-07-07-e8-e9-mirror-index-bootstrap/) — full write-up + probe artifacts
- **Question:** Does a **frequent-subtree proposer** invent `mirror_index` and finally _compress_ the D4 ladder (inverting E7's ×0.79) _and_ speed the search past its beam cliff? Run as a **grammar × learning matrix**: `{sub}` (E8) vs the honest affine `{sub,add,mul}` (E9).
- **Ran:** Added `add`/`mul` (the affine family); made `BuildGridSearch` **primitive-driven** (composes every library `INT^n→INT` op, so it can _reuse_ a learned coordinate); a `FrequentSubtree` proposer (mine Lam-free proper subtrees; sound Var-holing — the mirror image of `bound_var_safe`). E8 = sub-only (beam 128); E9 = affine (beam **224**, the threshold to solve a reflection at all — ≤192 fails). `enablement = BuildGridSearch` at a _tight_ beam (the cliff).
- **Result:**
  - **A rewrite bug, first:** `rewrite_with` didn't descend into `Lam` bodies, so `mirror_index` — which lives _inside_ the coordinate lambda — never folded and nothing minted. Fixed (descend `Lam.body`; E1–E7 unaffected).
  - **The divergence (the load-bearing finding):** the _naive_ proposer + greedy MDL mints two **unreusable `COLOR` read-body idioms** (`read(#0,#1,sub(sub(width(#0),#2),1))` and its height twin — the two "axis half-reflections"), **not** `mirror_index`. They compress the _train corpus_ more, but `BuildGridSearch` can't compose a `COLOR` read-body → re-solve DL _worsens_ (×0.95), zero speedup. And iteration can't recover `mirror_index`: once the read-bodies absorb it into their _definitions_, the corpus-only proposer can't see it (no library refactoring). **Train-DL ≠ reusability** — and a compression-optimal inventor (Stitch) would hit this too.
  - **The fix (a labelled stopgap):** scope invention to the signature the search composes (`INT^n→INT`), **derived from the search itself** (`SearchScopedFrequentSubtree(composes=search.composes_signature)`, not a declared type). Then `mirror_index` mints and the search reuses it.
  - **E8 (sub):** `abs0 = sub(sub(#0,#1),1)`, behaviorally **== mirror_index**. matched, 0 missed/novel.
  - **E9 (affine):** `abs0 = sub(#0, add(#1, 1))` — _same behavior_ via `add` (the checker matches by signature). Same idiom, different structural form → invention is robust to the grammar.
  - **Metrics:** `make check` green (139 tests, +9); locks 7/19/11 + E1–E7 unchanged.
    - compression (L1→L2 DL): E8 390→348 **×1.12**, E9 392→350 **×1.12** (inverts E7's ×0.79)
    - speedup (considered): E8 **×3.47**, E9 **×5.00** (bigger against the wider grammar)
    - enablement (tight-beam solves, L2 not L1): **20 tasks** (all 5 reflection members) in both — the beam cliff dissolved
    - base blowup (L1 considered): sub 77.1k → affine 234.8k (**~3×**) — the measured cost of `add`/`mul`
- **Interpretation:** the `mirror_index` bootstrap works — a shared coordinate factor is invented, _reused_ by the primitive-driven search, so the ladder compresses (×1.12) and the cliff dissolves (×3.5–5); the affine matrix shows the same idiom emerges under a wider grammar and matters _more_ there. But the headline is the **compression/reusability divergence**: greedy MDL over train-DL prefers the largest compressor, which is not the reusable one. The type-scoping that recovers `mirror_index` is _anti-open-ended_ (can only invent what the search already composes, foreclosing new-type / layered vocabulary) — hence a **stopgap**. The general fixes are **search-aware / transfer-aware governance** (score by usefulness, not node-count) or **library refactoring** (compress the _library_, not just the corpus — the missing half of iteration; ≈ Stitch's core). Full approach catalog in `MACHINERY.md` F4.
- **Next:** the general fix — search-aware governance, or library refactoring **via Stitch** (deferred to real-ARC scale per MACHINERY-STRATEGY's "not yet"); and the standing move — point the loop at a real ARC slice.

## 2026-07-08 — Stitch spike: two orthogonal ways it dissolves the E8 divergence (library refactoring vs. higher-order)

- **Commit:** b5268b5 (offline spike, docs only). Full write-up + scripts: [experiments/2026-07-08-stitch-spike/](experiments/2026-07-08-stitch-spike/).
- **Question:** E8 predicted "a compression-optimal inventor (**Stitch**) would hit [the compression/reusability divergence] too." Does _real_ Stitch, fed the D4 `build_grid` programs, prefer the unreusable `COLOR` read-body idiom (reproduce the divergence) or recover `mirror_index` (dissolve it)? Load-bearing because MACHINERY F4 marks library refactoring `🔜 via Stitch` as the general fix, while E8 predicts Stitch reproduces the problem.
- **Ran:** Wrote a 6-case `Program → Stitch s-expr` serializer (the keystone paid off — `Var/Param/Lam` already print `$i`/`#j`/`lam`; only `Apply` needed prefix form; oracle-checked against `to_dict`). Fed `stitch_core.compress` (ephemeral `uv --with`, no dep added) along **two orthogonal axes**: **what you feed it** {raw corpus of the 6 `_d4_targets(input())`; the two minted read-body _definitions_ = library refactoring} × **hole expressiveness** {first-order (`no_curried_metavars`); higher-order (default)}. Cross-checked {default cost prim=100; node-count cost all=1 ≈ TwoPartMDL} and `allow_single_task`.
- **Result:**
  - **The two axes are the whole story (top abstraction per cell):**

    | feed ↓ / holes → | first-order | higher-order |
    | --- | --- | --- |
    | **raw corpus** | `COLOR` read-body → **divergence** (E8 confirmed) | `mirror_index` (perceiver hoisted) → dissolved |
    | **minted defs (refactor)** | **general `mirror_index(n,k)`** → dissolved | `mirror_index` (perceiver hoisted) → dissolved |

  - **Library refactoring is the architecture-relevant fix (bottom-left) — and it works FIRST-ORDER.** Feeding the two read-body definitions back through compression extracts the clean, general `(sub (sub #0 #1) 1)` = `mirror_index(n,k)` — no higher-order needed, because once the read-body _is_ the definition, the bigger competing subtree is gone. This is precisely the capability the wake–sleep loop lacks: the proposer walks corpus **call-sites** (`[program for _, program in corpus]`), never abstraction **definitions** (`.template`), so once the read-bodies bury `sub(sub(·,·),1)` it can never be re-mined. = the MACHINERY F4 `library refactoring` row, ≈ Stitch's core.
  - **Higher-order invention is a SEPARATE, additive mechanism (top-right).** On the _raw_ corpus, higher-order holing hoists the perceiver `#1 ∈ {width,height}` into a function-typed hole, unifying both axis-reflections into one abstraction reused across all 5 reflection members, so `mirror_index` becomes the top compressor _before_ any read-body is minted. It **prevents** the burial rather than **curing** it. Bonus, not a replacement for refactoring.
  - **On the raw corpus, first-order Stitch reproduces the divergence** (top-left): TOP = `(read input (sub (sub (height input) #0) 1))`, the `COLOR` read-body; `mirror_index` drops to a lower, width-specialised `fn_4`. So E8's "Stitch would hit this too" is **correct for first-order raw-corpus compression** — refactoring (or higher-order) is what breaks it.
  - **Not the lever:** node-count vs default cost, and `allow_single_task` on/off, leave every top pick unchanged.
  - **Reusability nuance:** the _higher-order_ `mirror_index` has a function-typed arg + closes over `input`, so the current `INT^n→INT`-only `BuildGridSearch` can't compose it as-is; the _refactored first-order_ `mirror_index(n,k)` is directly composable (same signature the type-scoping stopgap yields).
  - **Metrics** (Stitch's own cost units; tiny corpus — directional, not a benchmark):
    - raw corpus: first-order → read-body (ratio 2.80 default / 2.64 node-count); higher-order → `mirror_index` (3.37 / 3.63)
    - refactor (read-body defs): first-order → general `mirror_index(n,k)` (ratio 1.55); higher-order → perceiver-hoisted `mirror_index` (1.89)

- **Interpretation:** two independent capabilities, each dissolving the divergence at a different failure point. **(1) Library refactoring** — compress the _library_ (walk definitions), not just the corpus — is the piece the current loop lacks and the piece the architecture needs: it _cures the burial_ after read-bodies are minted, and works **first-order** (recovers the clean, search-composable `mirror_index(n,k)`). This is the F4 `library refactoring` row, **confirmed** (an earlier draft of this entry wrongly demoted it — corrected). **(2) Higher-order invention** — a distinct, additive Stitch capability — _prevents the burial_ on the raw corpus. E8's prediction stands for first-order raw-corpus compression; either capability breaks it. Corollary: the in-house `FrequentSubtree` (first-order, Lam-free, sound Var-holing) would _itself_ recover `mirror_index` if simply fed the `.template` bodies and allowed to rewrite definitions — so the refactoring capability isn't intrinsically Stitch-shaped ("feed the proposer the library, rewrite the library"); Stitch is the mature, at-scale, De Bruijn-native implementation of it.
- **Next:** implement **library refactoring** (the F4 row) as the concrete next machinery — either (a) minimal in-house (feed `.template`s to the existing proposer + let `_sleep` rewrite definitions; determinism/no-dep, proves it on the microworld), or (b) adopt Stitch (branch-and-bound, hierarchy-building, De Bruijn-native) as the at-scale engine per MACHINERY-STRATEGY. Standing move unchanged: point the loop at a real ARC slice.

## 2026-07-08 — compression↔transfer correlation (the measurement layer's first read)

- **Commit:** cda7c91 (the transfer-measurement layer — `heldout_transfer` grade + train-side `Usefulness` + `compression_transfer_correlation`). Full write-up + scripts: [experiments/2026-07-08-compression-transfer-correlation/](experiments/2026-07-08-compression-transfer-correlation/).
- **Question:** held-out transfer is now measurable (the grade, previously an IOU). Does **compression predict transfer** across E1–E9, and does the instrument read the **E8 divergence** — does the compression-greedy abstraction score worse on transfer than the reusable one?
- **Ran:** `heldout_transfer` at the shallow enablement budget (an abstraction counts only if it collapses depth enough to bring a held-out task into reach); the correlation harness over E1–E9; a within-experiment control (E8 naive `FrequentSubtree` vs. search-scoped proposer, same 6 held-out); a per-experiment held-out base-vs-L2 decomposition.
- **Result:**
  - **Compression does not predict transfer.** E7 is the witness: worst compression (×0.79 — six verbose-but-correct D4 abstractions inflate the tiny train DL) yet perfect transfer (6/6); E2 best compression (×6.42), transfer 2/2. Train-DL shrinkage and held-out enablement measure different things and can point opposite ways.
  - **The instrument reads the E8 divergence, within-experiment:** naive proposer → transfer **0** (two unreusable `COLOR` read-bodies), search-scoped → transfer **5** (the reusable `mirror_index`), same 6 held-out. The compression-greedy pick transfers to nothing.
  - **Decomposition** (transfer = L2 − base solves, on held-out): deep gap + good abstraction → 100% (E2–E5, E7); E1 = 1/4 because the base already solves 3/4 (rot90 is 2 steps from the floor — a shallow gap, not a bad abstraction); E6 = 1/6 (naive broken abstractions); E8/E9 = 5/6 (base already solves the shallow `transpose`).
  - **Metrics** (compress = L1→L2 DL ratio; full table in the folder): **E7 ×0.79, transfer 6/6** (the anti-correlation) vs **E2 ×6.42, 2/2**; **E8/E9 ×1.12, 5/6** at deep-speedup ×3.47/×5.00.
- **Interpretation:** the empirical case for **selection-correct governance** (score by train-side usefulness/transfer, not train-DL node-count), and a validation of the measurement-bottleneck thesis — the grade had to exist before the governance objective could be defined. Caveats: raw transfer counts are unnormalised (different held-out denominators) and budget-relative — the clean signal is the within-experiment naive-vs-scoped contrast (0 vs 5); the x-axis is full-corpus re-solve DL, not the train-DL greedy actually optimises (the divergence is sharper there); 9 microworld points are directional, not statistical.
- **Next:** **selection-correct governance** — a usefulness-scored selector vs `GreedyMDL` on E8/E9 (the queued _reusable-idiom governance_ row). Standing move unchanged: point the loop at a real ARC slice, where the grade becomes readable at scale.

## 2026-07-08 — E10: Stitch library refactoring recovers mirror_index (a first-order stopgap)

- **Commit:** working tree on b5268b5 (Phase A + B of the best-practices plan, uncommitted).
- **Question:** the _other_ general fix to the E8 divergence (sibling of the selection-correct-governance entry above): does **library refactoring via Stitch** — compress the library's own _definitions_, not just the corpus — recover a **composable** `mirror_index` **without** `SearchScopedFrequentSubtree`?
- **Ran:** Phase A lifted the sleep step behind a pluggable `SleepStrategy` (`GreedyMDLSleep` = the historical greedy-MDL machinery, behavior-identical: E1–E9 + dsl 7/19/11 zero drift, driven end-to-end on E8). Phase B added the `stitch_core` boundary (`learn/stitch_shim.py`: `to_sexpr`/`from_sexpr` with type re-inference; Stitch as a _proposer_ so our `TwoPartMDL` governs — full cost control) and a two-phase `RefactoringSleep`. **E10** (`arc-lab learn e10-stitch-refactor`): E8's sub-only env, `sleep=RefactoringSleep(FrequentSubtree(), StitchProposer(first_order=True))`.
- **Result:**
  - **Recovered, first-order.** Phase 1 (in-house `FrequentSubtree`) mints the two closed `COLOR` read-bodies; phase 2 (Stitch) _antiunifies their differing perceiver_ → `abs2 = sub(sub(#0,#1),1)` == **mirror_index** (matched, 0 missed), composed by `BuildGridSearch`. No type gag.
  - **The load-bearing caveat (probed directly):** Stitch _can_ mine the raw corpus — but the general reflect-across-a-_perceived_-dimension idiom it finds is **higher-order**: `fn_0 = (sub (sub (#1 input) #0) 1)`, perceiver `#1` a _function_ arg, in one pass. Our first-order substrate can't consume it. In **first-order** mode, mining the lambda-bearing corpus yields only partial-applications (`(read input X)`, `(read input)`, `(lam …)`) and a _width/height-specialised_ mirror — unusable. So the two-phase is a **labelled first-order stopgap** (sibling of the type-scope it replaces): in-house does sound bound-var corpus mining; Stitch does the antiunifying refactor the identical-subtree in-house proposer can't. The clean single-pass "Stitch mines the corpus" unlocks with the higher-order phase.
  - **Two dead-ends en route:** one-phase Stitch `iterations=5` → hierarchy `fn_k` refs skipped, greedy mints the specialised (uncomposable `GRID→INT`) mirror → DL ×0.95, enablement 0; `iterations=1` on the corpus → curried partial-app read-body invalid in our non-curried DSL → nothing mints. Both are the same first-order/lambda impedance.
  - **Metrics:** `make check` green (+8 tests, 4 skip without the optional wheel); E1–E9 + dsl locks unchanged.
    - compression L1→L2 DL 390→364 **×1.07** (vs E8 stopgap ×1.12 — e10 also keeps the two read-bodies)
    - speedup **×3.47**; enablement (tight-beam L2-only) **20 tasks**; held-out transfer **5** — E8's payoff, on merit
  - Determinism verified at `threads=1`; multithreading deferred to real-ARC scale.
- **Interpretation:** **library refactoring works and is the sibling general fix** to selection-correct governance (both dissolve the divergence). The pluggable `SleepStrategy` + the `stitch_core` boundary + `rewrite_library_definitions` are the reusable machinery; the two-phase `RefactoringSleep` is a knowingly-first-order stopgap. Straight version: **higher-order Stitch mines the corpus in one pass** — earns its place in the higher-order phase, where the two-phase collapses.
- **Next:** the higher-order substrate (polymorphic types → `AppFn`/`PrimRef` → general higher-order search), which turns "Stitch mines the corpus" from higher-order-only into consumable. Standing move unchanged: a real ARC slice.

## 2026-07-08 — Higher-order stack (C–F): Stitch invents a function-typed abstraction, the search consumes it

- **Commit:** working tree (Phases C–F of the best-practices plan, atop the committed A/B).
- **Question:** the E10 "Next" — build the higher-order substrate so the higher-order idiom Stitch finds becomes _representable, typed, and consumable_. Does the full stack (polymorphic types → `AppFn`/`PrimRef` → higher-order Stitch → higher-order search) work end to end?
- **Ran:**
  - **C** — polymorphic type language: `Type = ValueType | ArrowType | TypeVar` + Hindley-Milner `unify`/`apply_subst`/`instantiate` (base types stay the `ValueType` enum — a labelled compromise, see below).
  - **D** — higher-order representation: `AppFn` (apply a _computed_ function value, reusing `Closure.__call__`), `PrimRef` (a primitive as a first-class value); `Type` threaded through `Primitive`/AST nodes/`make_abstraction`/pools (annotation-widening, behavior-preserving).
  - **E** — general higher-order `Enumerate` (a `higher_order` flag): fills a function-typed hole from a library-derived `PrimRef` pool, pruned by arrow-type unification.
  - **F** — higher-order `from_sexpr` (HM inference solves each metavar's arrow across all its uses); `StitchProposer(first_order=False)`; `_is_useful` now counts `AppFn` as structure.
- **Result:** on a corpus of "apply a transform twice" (`rot90(rot90(input))`, `rot270(…)`, `flip_h(…)`), **higher-order Stitch invents `twice = (#0 (#0 input))`** by holing the repeated _function_; **first-order Stitch invents nothing** (a head is unholeable). Deserialized, `twice : (GRID→GRID, GRID) → GRID`. The **higher-order `Enumerate` then consumes it** — `twice(&rot90, input) = rot180` at depth 1 — which the **first-order search cannot** (rot180 needs depth 2). Genuine higher-order necessity at bounded depth, invention→consumption end to end.
  - **Metrics:** `make check` green throughout (156 → 164 tests + a gated Stitch/HOF suite of 9); every first-order lock byte-identical (E1–E9, dsl 7/19/11, E8 driven end-to-end) — the `higher_order` flag defaults off and `ValueType`-as-base-leaf keeps the first-order substrate unchanged.
- **Interpretation:** the higher-order paradigm is real _and consumable_. The very thing first-order can't do — hole a repeated function — is now invented (higher-order Stitch), represented (`AppFn`/`PrimRef`), typed (arrows, via HM inference), and reused by the search. Two knowing compromises remain, each queued: the type system is a union with `ValueType` base-leaf (Phase H unifies it into the `ArrowType`/`TypeVar` mechanism), and `Enumerate` HOF is PrimRef-filling only (Phase G adds `Lam`-synthesis of _new_ function values + function-behavioral dedup).
- **Next:** Phase G (Lam-synthesis) and Phase H (type-system unification). Standing move unchanged: point the loop at a real ARC slice.

## 2026-07-08 — Phases G + H: the last two higher-order compromises closed

- **Commit:** Phase G = `c66afca`; Phase H = working tree atop it. Closes the "two knowing compromises" the C–F entry flagged.
- **Question:** the C–F stack left two labelled stopgaps — (G) higher-order `Enumerate` could only _reference_ library functions (PrimRef-fill), never _synthesize_ new ones; (H) the type language was a `ValueType`-enum base-leaf grafted onto the `ArrowType`/`TypeVar` ADT. Close both, move no lock.
- **Ran:**
  - **G — `Lam`-synthesis.** `Enumerate(synthesize_functions=True)` builds _new_ function values bottom-up (`lam(body)`), not just `PrimRef`s, deduped by a **function-behavioral signature** (evaluate each candidate over a fixed grid battery; one survivor per behavior, the smaller wins). DoD is a strict-necessity case: over the cyclic library `{rot90, thrice}`, reaching `rot180` needs the _rot180 function itself_ in `thrice`'s hole (rot180³ = rot180) — no primitive provides it, so only a synthesized `lam(rot90(rot90($0)))` fills it. First-order (needs depth 2) and PrimRef-only (`thrice(&rot90,·) = rot270`) both provably fail; Lam-synthesis solves at depth 1.
  - **H — retire the `ValueType` enum.** Base types are now bare module singletons `GRID`/`COLOR`/`INT`/`FN : BaseType` (a frozen dataclass — DreamCoder's `tgrid`/`tint` idiom), so `Type = BaseType | ArrowType | TypeVar` is one uniform frozen-dataclass mechanism, no enum. `unify` gains a `BaseType` arm; serialization stays the bare string (backward-compatible with every artifact); a `_BASE_TYPES` registry + `base_type()` make base types shared **singletons** (identity round-trips through (de)serialization). ~130-site mechanical churn across 29 files (a scripted rename + hand-edited package API).
- **Result:**
  - Both compromises gone; the type language and the HOF search now sit at the plan's best-practice endpoint.
  - **Metrics:** `make check` green — **167 passed, 5 skipped** (the `stitch_core`-gated suite); mypy `--strict` + ruff clean. Every regression lock byte-identical: **dsl 7/19/11**, **E1–E9**, and the Stitch/HOF suite. Zero numeric drift — a pure representation refactor (H) plus an additive search capability (G, off by default).
- **Interpretation:** the higher-order library-learning stack is complete and compromise-free within its scope — invent (higher-order Stitch) → represent (`AppFn`/`PrimRef`) → type (uniform `BaseType`/`ArrowType`/`TypeVar` + HM) → search (PrimRef-fill **and** `Lam`-synthesis, behaviorally deduped, unification-pruned). The one remaining plan caveat is by design: the necessity proofs live on synthetic testbeds (twice/rot180, thrice/rot180).
- **Next:** point the loop at a real ARC slice — where invention-vs-search and the higher-order payoff become measurable at scale (unchanged standing move). The queued **selection-correct governance** and **library refactoring** rows remain the open research fronts.

## 2026-07-09 — Review of the higher-order/Stitch/type stack (corrects the "compromise-free" claim)

- **Commit:** working tree atop `6f38706`. Full ledger: [codebase_review/review-after-stitch-integration-2026-07-09.md](codebase_review/review-after-stitch-integration-2026-07-09.md) (the abstract here; findings + status there).
- **Ran:** a multi-agent adversarial review (three reviewers — Phase-H migration, higher-order search, Stitch shim/sleep — plus independent reading), sharpest claims re-probed against the real `stitch_core` wheel.
- **Result:**
  - **The Phases G+H "compromise-free within its scope" claim (above) was overstated.** The function-dedup battery was in fact _unsound_ — both probe grids were height-2, so `height` collapsed with a constant and a correct candidate could be silently dropped (order-dependent solve). Fixed by widening the battery + never deduping an unprobeable (`None`) signature; but it remains a **finite-battery observational-equivalence heuristic** (standard, sound-in-practice, not complete) — not "compromise-free".
  - **Also fixed** (all in tree, behavior-preserving; locks byte-identical): `from_sexpr` now rejects arity-invalid partial applications (first-order Stitch's "read-body" on the raw corpus _was_ one); De Bruijn `$i` scoping (a flat index→type map wrongly unified sibling `$0`s); deserialization fail-fast (`base_type` raises on an unknown tag, as the retired enum did); `BOOL`↔Stitch round-trip (`true`/`false` tokens); + three misleading docstrings (notably `RefactoringSleep`'s Stitch-necessity justification, which contradicted this log's own E10 finding) and a `PYTHONHASHSEED` ordering leak.
  - **Metrics:** `make check` green — 174 passed, 5 skipped; ruff + mypy `--strict` clean; dsl 7/19/11 + E1–E9 unchanged.
- **Interpretation:** the stack holds up — no correctness bug survived into a lock, and the first-order byte-identity is real — but "compromise-free" was the wrong word: the honest framing is _finite-battery observational equivalence_ + a handful of latent gaps that bite only as the polymorphic/higher-order roadmap lands (tracked in the review file).
- **Next:** the deferred `eq`/`if` search-cost reductions (commutative pruning; per-round budget) are queued in `MACHINERY.md` (F1). Standing move unchanged: a real ARC slice.

---

## 2026-07-09 — RunSpec × Config refactor (machinery as data)

- **Commit:** branch `refactor/runspec-config` (Phases 1–15)
- **Question:** (structural, not empirical) can the machinery be made _data_ — a frozen, hashable `Config` — so parameters decouple from wiring, runs are reproducible, and the activity model is explicit in the code?
- **Ran:** a 15-phase migration; `make check` green and the regression locks (`dsl`=7, `dsl-sym`=19, `dsl-synth`=11) re-verified at every lock-touching step.
- **Result:**
  - config-as-subclass solvers → `Config` + `PRESETS` (`ProgramSearchSolver` is the only solver class); `RunSpec = Config × Corpus` with a content-hashed `run_id` that now includes the search params (fixes a latent cache collision); provenance-agnostic `Corpus`/`AnnotatedTask`; content-addressed library store (`Library.from_dict`); one `execute()` core with a sleep knob (Eval vs Synthesize); transfer reducers moved to a read-side `analysis/transfer`; `Experiment`→`StudySpec`/`run_study`.
  - Behaviour preserved: E1–E10 study outputs unchanged.
- **Interpretation:** the machinery is now diffable / hashable / sweepable; the run/config/activity model is mapped in `ARCHITECTURE.md`.
- **Next:** fold `GeneratedTask` into a `Corpus` of `AnnotatedTask` (regenerate committed testbeds); put the sleep strategy into the run identity; CLI verb split + a config-file / `--set` override surface.

---

## 2026-07-11 — Execution overhaul lands; locks deliberately re-pinned on the new engine

- **Commit:** branch `refactor/runspec-config-2` (the execution-layer overhaul, uncommitted at run time; the new locks pin the numbers)
- **Question:** does the generic typed bottom-up engine + recorded-run execution layer (EXECUTION.md) reproduce the old bespoke-search behavior — and where exactly does it differ?
- **Ran:** each new preset (`execution/presets.py`) over the full `arc1-train` (400 tasks) via `run_search`; the E1 study end-to-end via `run_study`; locks re-pinned in `tests/program_search/test_locks.py`.
- **Result:**
  - **Exact continuity where the old searches were generic:** `d4` = the old `dsl` seven, identical task-ids; `synth` = the old `dsl-synth` eleven, identical — and the old "lock at reduced depth, same set" empirical finding replicates (depth-2 = depth-3 set, 1s vs 103s).
  - **Understood divergence where the old searches were bespoke:** `sym` = 10/400 vs old `dsl-sym` 19 — the D4 seven + all three overlay tasks; the missing nine are exactly the old TILE tasks. Cause: a 3x3 mosaic is nine variadic args (out of `max_arity=4`), and a tiling factor that is neither input dim is out of vocabulary under harvest constants. Budget/policy limits (data), not architecture; lift = structured-composition capability or budget policy, never a bespoke search. Full-corpus `sym` costs ~32 CPU-min (24.7M considered), so its lock runs a fixed curated 30-task slice (~40s).
  - **Two measured budget findings:** `finite-enumerate` constants explode variadic composition on large grids (one 30x30 task ≈ 6M candidates → `sym` uses harvest-from-instance); a 16-wide beam fills with size-1 constants and starves the GRID type entirely (0/400 → `beam` = harvest + width 32, solving 9 = `synth` minus the truncation's two).
  - **The learning loop locks green on the new stack:** E1 mints `abs0`, it behaviorally matches the withheld `rot90` target (probe-based semantic check), enablement 0→8 at the shallow budget, held-out transfer 4/4.
  - **Metrics:**
    - locks: `d4` 7/400 (= old) · `synth` 11/400 (= old) · `sym` 10/400 (old 19; −9 tile, understood) · `beam` 9/400 (newly locked) · E1 study transfer 4/4
    - gate: `make check` 377 passed, 5 skipped (optional stitch wheel), ~60s wall
- **Interpretation:** the generic engine reproduces every behavior the old system got from _general_ search and pays a visible, explainable cost exactly where the old system used _bespoke_ structure — which is now a capability/budget question on one engine instead of a zoo of strategies. The old locks keep guarding the old tree until its deletion pass.
- **Next:** recalibrate E2–E10 environments onto the new engine (queued); structured-composition capability for mosaic-scale variadics if/when tile tasks matter.

---

## 2026-07-11 — `eager_grounding_over_universe` cost-vs-depth on a real `map` recolor task

- **Commit:** branch `refactor/runspec-config-2` at 35a2685 (map/filter/fold/sort_by slice, uncommitted at run time)
- **Question:** `map`'s codomain type var is unshared by any sibling, so it can only be resolved via `unpinned_type_var_mode="eager_grounding_over_universe"` (grounds over `monotype_universe`, a full recursive body search per candidate type). How expensive is that in practice for a real end-to-end task, and is it driven by the `monotype_universe` list-nesting closure (a List-specific inflation) or something more general?
- **Ran:** `row_to_grid(map(lam(if(eq($0,3),7,$0)), cells(input)))` — recolor-one-color, single-row grid — under `BottomUpSearchEngine(unpinned_type_var_mode="eager_grounding_over_universe")` at increasing `max_depth`/library size (probe scripts, not committed).
- **Result:**
  - `monotype_universe` for the trimmed library (`map`/`cells`/`row_to_grid`/`eq`/`if`) is small — 10 types at closure depth 2 — so universe-size inflation from `List` nesting is _not_ the driver here.
  - The memo key (`scope, contexts, budget, enclosing_target`) collapses across all ~10 grounding candidates for `map`'s codomain in this task, because `enclosing_target` for this task never propagates through `_propagate_elementwise` (top-level target is a `Grid`, not tuple-shaped) — so eager grounding here is _not_ paying a 10x multiplier from redundant re-searches, contrary to the naive expectation.
  - **Metrics:**
    - full library (`+from_cells+width+height+read`), depth=4: 97,803 considered, 1.26s, unsolved
    - full library, depth=5: 17,590,552 considered, 116.0s, unsolved
    - trimmed library (no `read`/`width`/`height`, `row_to_grid` instead of `from_cells`), depth=5, pool=1000: 1,453,833 considered, 8.2s, unsolved
    - trimmed library, depth=6, pool=1000: 9,873,756 considered, unsolved (completed within a 280s window)
    - the target program was hand-built and evaluated directly (bypassing search) and is confirmed semantically correct — this is a search-budget shortfall, not an unreachable-program bug
  - `test_higher_order_primitives.py::test_map_solves_recolor_end_to_end` was rescoped to a plain `COLOR -> COLOR` primitive (`next_color`) instead of the synthesized `eq`/`if` body — solves in <10ms at depth=4 — trading away the "map composes with a synthesized conditional" claim (not this slice's core claim) to keep the payoff test fast rather than chasing the eq/if-body cost further.
- **Interpretation:** the real cost driver is ordinary bottom-up round-over-round growth (the same ~180x/depth pattern seen independently in the `fold` toy test), not `eager_grounding_over_universe`'s per-grounding multiplier, which turned out to be memoization-collapsed in this case. A _lambda body requiring composition depth ≥6_ is expensive regardless of whether an unpinned hole is involved — `eager_grounding_over_universe` only compounds this when `enclosing_target` propagation actually fires per grounding candidate (giving each one a genuinely distinct memo key), which didn't happen here.
- **Next:** if a future task needs both a genuinely-unpinned hole _and_ real depth (≥6) in its synthesized body, expect this same wall; worth revisiting whether `eager_grounding_over_universe` should cap/prioritize `state.universe` by relevance (e.g. atomic types before list-nested ones) if that combination becomes load-bearing rather than incidental.

---

## 2026-07-12 — E11: perceive→transform: recolor_bg derived from {map_color, most_common_color}

- **Commit:** working tree atop d53ca8f.
- **Notebook:** [experiments/2026-07-12-e11-e12-gap-climbing/](experiments/2026-07-12-e11-e12-gap-climbing/) — full write-up + run links
- **Question:** the first _perceiver-consuming_ abstraction (EXPERIMENT_QUEUE.md's gap-climbing row) — can the loop derive `recolor_bg(g,c) = map_color(g, most_common_color(g), c)` from the floor `{map_color, most_common_color}`, with `c` a genuine free parameter (not a hardcoded literal)?
- **Design finding en route (worth recording on its own):** the naive corpus design — one example per task, background _and_ target color both varying freely — cannot work under the current WAKE mechanics, and this generalizes beyond this experiment. `execute.py` keeps only `ranked_programs[0]`, the _cheapest_ solving program per task (`extraction.py` ranks by node count); once any `COLOR` constant source exists, `map_color(g, <literal-bg>, <literal-target>)` (1 application) is always cheaper than the composition through `most_common_color` (2 applications) and always reachable wherever the composition is — so WAKE never even retains the perceiving program, for any per-task variation strategy, as long as a task's goal test is satisfiable by one fixed pair of literals. The fix: a task's goal test is over _all_ its train examples at once (`sig == target` on the full training signature, `extraction.py`), so varying the **background across a task's own train examples** makes no single literal source work for that task at all — only `most_common_color(g)`, evaluated per example, can track it. Varying the **target color across different tasks** (fixed within each) then gives antiunify the one differing literal to hole into the free parameter. Background-within/target-across is not symmetric: target varying _within_ a task either leaves it unsolved (wasted, if uncorrelated with input) or collapses to a _different_, zero-free-param abstraction (if it does correlate) — never `recolor_bg(g,c)` with `c` free.
- **Ran:** new `taskgen` generator + `StudySpec` `perceive-transform` (`execution/studies.py`, `taskgen/generators.py`): library `{map_color, most_common_color}`, `constant_sources=("finite-enumerate",)` (needed so any target color is reachable, not just ones already present in an input — `harvest-from-instance` only reads inputs, never outputs). 5 train tasks (target colors {0,2,5,7,9}, 3 examples each, backgrounds {3,4,6} shared across every task) + 2 held-out tasks (unseen target colors {1,8}). `arc-lab run-study perceive-transform`; locked in `tests/program_search/test_locks.py`.
- **Result:**
  - Sleep mints exactly `abs0`, structurally `map_color(#0, most_common_color(#0), #1)` — **byte-identical to the target template**, not just a behavioral match (grid var-shared across both call sites, `_close_template`'s Input-collapsing — the "var-sharing (grid ×2)" abstractor demand, confirmed free).
  - **Enablement + full transfer**, shallow (depth-2, one-application) budget: raw `L1` solves **0/5 train, 0/2 eval**; learned `L2` solves **5/5 train, 2/2 eval** — including both held-out, _unseen-during-training_ target colors, confirming `c` is genuinely a free parameter, not memorized.
  - Deep (depth-3) budget: `L1` already solves 5/5 + 2/2 via raw composition (as expected — the composition is real, just unreachable at depth 2 without the abstraction).
  - **Metrics:** `make check` green (468 passed, 5 skipped); considered nodes at shallow budget: `L1` 590 (train) / 236 (eval) vs `L2` 640 / 256 (learned primitive adds negligible search cost).
- **Interpretation:** the loop derives a real perceiver-consuming abstraction end to end, confirming gap-climbing is runnable today for this phenomenon — but only once the corpus is designed around the WAKE-time cheapest-wins selection rule, which otherwise silently forecloses ever discovering a perceiving composition whenever an equally-valid literal substitution exists (a WAKE-time sibling of the E8 compression/reusability divergence, one step earlier in the pipeline). Multi-example-per-task corpora are the general tool for forcing derivation over literal substitution.
- **Next:** the two remaining queued gap-climbing rows — **layered abstraction** (L2 built on a learned L1) and **learned intermediate type** (`Mask`-constructing-and-consuming) — plus watch for the same cheapest-wins trap wherever a target abstraction has a free literal parameter alongside a derivable one.

---

## 2026-07-12 — E12: layered abstraction: L2 recolor_flipped minted using the L1 learned in the same run

- **Commit:** working tree atop d53ca8f (same session as perceive→transform, above).
- **Notebook:** [experiments/2026-07-12-e11-e12-gap-climbing/](experiments/2026-07-12-e11-e12-gap-climbing/) — full write-up + run links
- **Question:** the second queued gap-climbing row — can the wake-sleep loop build a **second-generation** abstraction directly on a first-generation one it _just learned_, in one recorded LEARN run: `abs0 = rot180 = flip_h(flip_v(g))`, then `abs1 = recolor_flipped(g,a,b) = map_color(rot180(g),a,b)` composed on `abs0` — not merely a corpus rewrite, but a genuine second WAKE search that needs the grown library to even reach the task?
- **Ran:** new `taskgen` generator + `StudySpec` `layered-abstraction`: library `{flip_h, flip_v, map_color}`, one fixed WAKE budget for the whole LEARN run (`max_depth=3`, two applications) chosen so raw composition reaches `rot180` (two applications) but not `recolor_flipped` (three) — only once `abs0` exists does `recolor_flipped` collapse to two applications and become reachable at the _same_ budget. Corpus mixes both task types: 4 train + 1 held-out `rot180` tasks (single example each — no literal-constant shortcut is possible for a pure `GRID→GRID` transform, so no perceive→transform-style corpus engineering was needed here), 4 train + 1 held-out `recolor_flipped` tasks (`(a,b)` fixed within a task, varied across tasks — the same free-parameter mechanism as `perceive→transform`, minus the var-sharing complication since each param is used once). `arc-lab run-study layered-abstraction`; locked in `test_locks.py`.
- **Result:**
  - Sleep mints `abs0 = flip_h(flip_v(#0))` in iteration 0 (from the 4 solved `rot180` tasks alone — `recolor_flipped` tasks are simply absent from that iteration's solved corpus, unreachable at the shared budget). Iteration 1's WAKE, now with `abs0` in the library, genuinely re-solves the `recolor_flipped` tasks (confirmed via the grid, not inferred): sleep then mints `abs1 = map_color(abs0(#0), #1, #2)` — **built directly on `abs0`**, both behaviorally matching their targets.
  - **Partial-then-full enablement**, at the one shared learn budget: raw `L1` solves **4/8 train, 1/2 eval** (the `rot180` subset only); learned `L2` solves **8/8 train, 2/2 eval** — both task types, including the held-out unseen `(a,b)` pair, confirming `recolor_flipped`'s parameters transfer.
  - Deep budget (`max_depth=4`, three applications): `L1` already solves 8/8 + 2/2 via raw composition, as expected — confirms the composition is real, just one application too deep to reach at the learn budget without `abs0`.
  - **Metrics:** `make check` green (469 passed, 5 skipped). Considered nodes at learn budget: `L1` 47,464 (train) / 11,866 (eval) vs `L2` 183,648 / 45,912 (the grown library's extra vocabulary costs ~4x search — `abs0`/`abs1` widen round-0 leaves without narrowing anything, unlike E1/perceive→transform's negligible deltas).
- **Interpretation:** multi-generation abstraction — L2 built on a _just-learned_ L1, within one recorded LEARN run — works end to end, confirming the wake-sleep loop's iteration structure (not just `GreedyMDLLearnEngine`'s internal corpus-rewrite loop) is what does the work here: `recolor_flipped` was absent from iteration 0's solved corpus entirely, so `abs1` could only be mined after a _second_ WAKE search that needed `abs0` to reach its target at all. The considered-count jump (unlike the two single-generation experiments) is the first measured cost signal of a growing library: unlike E1/perceive→transform where the learned primitive strictly _replaces_ search depth, `abs0`/`abs1` are additive vocabulary the round-0 leaf set must now carry on every task, including tasks that don't use them.
- **Next:** the last queued gap-climbing row — **learned intermediate type** (`Mask`-constructing-and-consuming, the deepest phenomenon: an abstraction that both builds and consumes a learned type). Watch whether the same considered-count growth compounds with three generations of vocabulary.

---

## 2026-07-13 — composed-signature fast path: reuse cached child signatures for `Apply` nodes

- **Commit:** working tree atop 2759b69 (same session as the new-layer restriction, previous commit)
- **Question:** `test_locks.py`'s heaviest regression locks were taking 44-74s each even after the new-layer restriction (§5.2, previous commit) stopped regenerating already-built programs across rounds. Where does the remaining time go?
- **Ran:** profiled `sym` on the 30-task lock slice via the existing `TraceSpec(profile=True)` cProfile harness (`execution/profiling.py`). Phase rollup: 70.5% of profiled time in `compute_signature` — `Apply.evaluate` walks a freshly-composed candidate's **entire subtree from the raw grids** every time (6.7M `evaluate()` calls, only 1.57M non-recursive), even though bottom-up composition's direct children are always already-pooled programs whose per-context `Signature` (`PoolEntry.sig`) was computed and cached the round they were absorbed. `combine_if_signature` already avoids this for `If` nodes (reuses cached cond/then/else signatures); ordinary `Apply` composition never got the same treatment.
- **Result:**
  - Added a fast path to `compute_signature` (`search/signature.py`): given an optional `child_signatures: Mapping[id(Program), Signature]`, an `Apply` node applies `primitive.impl` directly to each argument's cached per-context value instead of re-evaluating. Sound because `Apply.evaluate` calls `impl` on nothing but the fully-materialized argument values (no grid/env/scope leak-through), so `⊥` propagates from a `⊥` argument exactly as a raised exception would. `_enumerate` (`search_engine.py`) builds the `id(program) → sig` map once per depth from the whole pool, **excluding function-typed entries** (their cached signature is an argument-sampled behavioral fingerprint from `compute_function_signature`, a different shape) — a lookup miss (function-typed hole, or anything not a plain `Apply`) safely falls back to full evaluation.
  - **Metrics** (wall clock, `uv run pytest -m slow -q`, single-threaded, same machine, before → after):
    - `test_sym_solves_exactly_the_known_ten_on_the_lock_slice`: 43.59s → 18.98s (56% faster)
    - `test_layered_abstraction_study_locks_multi_generation_learning`: 73.95s → 60.03s (19% faster)
    - `test_beam_solves_exactly_the_known_nine`: 14.51s → 9.20s (37% faster)
    - `test_perceive_transform_study_locks_the_learning_loop`: 8.37s → 5.82s (30% faster)
    - All 15 `slow`-marked lock assertions unchanged (exact solved-id sets, exact minted-abstraction templates) — behavior-preserving, confirmed by full `make check`-equivalent run (`ruff` + `mypy --strict` + `pytest -n auto`) green.
  - Added `tests/program_search/search/test_signature.py` fast-path unit coverage: matches full evaluation, propagates `⊥` from a `⊥` argument, catches a raising `impl` as `⊥`, and falls back correctly when an argument's signature isn't cached.
- **Interpretation:** the dominant cost in bottom-up search was never enumeration or dedup bookkeeping — it was redundantly re-deriving already-known behavior on every new composition, an O(subtree size) cost per candidate instead of O(1) given its children's cached signatures. This is the same "cached child result, don't re-walk" pattern the new-layer restriction applied to *enumeration* (previous commit) and `combine_if_signature` already applied to `If` — now applied to the common case (`Apply`). `AppFn` (pooled function-value application, §8) and `compute_function_signature` are untouched and remain full re-evaluation; they're a smaller share of candidate volume in the profiled runs but are the natural next target if lock times still bottleneck `make check`.
- **Next:** if further speedup is wanted, profile again post-fix to see whether `Grid.__init__`'s per-construction min/max revalidation (the next-largest self-time item in the original profile) is now the dominant remaining cost, and whether it's worth a validated-by-construction fast path for pure-transform primitives (rot90/flip/transpose).
