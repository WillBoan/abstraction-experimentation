# Experiments

A shared human+AI **event log** of experiments and findings for arc-lab. Append-only, newest last. This records _what happened at a point in time_ — it does not mirror current state (that lives in the code, the regression locks, and `CLAUDE.md`).

**Discipline** (or this rots into noise):

- **Terse.** Hypothesis / what ran / result / interpretation / next. Not essays.
- **Record dead ends.** Negative results are as valuable as wins — often more.
- **Anchor to a commit** so the numbers stay reproducible.
- **Events, not state.** "On date X, measured Y" never goes stale; "current best is Y" does.

Entry template:

```
## YYYY-MM-DD — <short title>
- **Commit:** <hash>
- **Question:** ...
- **Ran:** ...
- **Result:** ...
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
