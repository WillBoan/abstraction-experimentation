# E8/E9 — the mirror_index bootstrap (frequent-subtree proposer × coordinate grammar)

- **Date:** 2026-07-07
- **Experiments:** `e8-mirror-index-sub`, `e9-mirror-index-affine`
- **Status:** done
- **Commits:** `5f48bda` (add/mul) · `9554a78` (primitive-driven search) · `8051ad4` (proposer + E8/E9) · `b5268b5` (docs)
- **EXPERIMENTS.md:** [the curated abstract](../../EXPERIMENTS.md) — entry "pixels→D4 compresses …" (anchored `8051ad4`)

> This is the full write-up + data appendix. The `artifacts/` folder holds the probe scripts and their outputs; EXPERIMENTS.md has the terse version.

## Goal

E7 re-derived the full D4 ladder from the cell floor but _compression got worse_ (DL ×0.79): six separate whole-member abstractions, no shared idiom, because whole-program antiunification can't mine a recurring _subterm_. Question: does a **frequent-subtree proposer** invent the shared reflection idiom `mirror_index(n,k) = sub(sub(n,k),1)` and finally _compress_ the ladder — and _speed the search past its beam cliff_? Run as a **matrix**: grammar (`{sub}` vs the affine `{sub,add,mul}`) × learning (base search vs the invention loop).

## Setup & the two reframings (design dialogue)

The naïve plan was "just add a proposer." Two things reshaped it before any code:

1. **The payoff is coupled to the search.** `BuildGridSearch._coordinate_pool` was hardcoded to compose only `sub`, and never consulted the library — so a minted `mirror_index` would sit _unused_. Compression is measured by _re-solving_ with that search; the beam cliff is a property of that pool. → Make the coordinate grammar **primitive-driven** (compose every library `INT^n→INT` op, so the search reuses learned coordinates).
2. **Keep the search honest.** `sub`-only quietly narrows the space to where reflection is nearly the only expressible thing — flattering. `sub`/`add`/`mul` are the same family, same machinery, needed soon anyway. → Add `add`+`mul` (the affine family) and run the grammar expansion as a _measured variable_, not a hidden assumption. (`mod`/`div` are a different family — deferred.)

Also settled: adopt-Stitch is the F4 row's letter, but MACHINERY-STRATEGY says _"not yet — antiunify is correct for microworlds; adopt when the corpus outgrows it."_ So the proposer here is a focused hand-built miner (an antiunify extension), **not** the DreamCoder-grade engine; Stitch stays deferred to real-ARC scale.

## Log

### 1. The beam cliff is real, and mirror_index is depth-1 — [`artifacts/beam_cliff_sweep.py`](artifacts/beam_cliff_sweep.py) → [.out](artifacts/beam_cliff_sweep.out)

sub-only solves rot180 only at beam=128 (considered 14896); sub+mirror at beam=64 (2721). The pool dump shows _why_: `mirror_index($0,$1)` enters at **cost 3, depth 1**, where the raw `sub(sub(width,$1),1)` is cost 6, depth 2 — so at a tight beam the raw reflection is cut but the learned one survives. But `_TIGHT_BEAM=16` was **too** tight (the cost-4 `mirror_index(width,$1)` is crowded out by cost-1/3 exprs) — the discriminating beam is 64.

### 2. The clean per-member matrix — [`artifacts/member_matrix.py`](artifacts/member_matrix.py) → [.out](artifacts/member_matrix.out)

The headline visual. At **beam=128**: sub → all 6; **affine → only transpose** (all 5 reflections fail even at full beam — add/mul crowd the depth-2 reflection out); **aff+mir → all 6** (mirror_index rescues every reflection on affine).

### 3. Affine can't seed itself — [`artifacts/affine_threshold.py`](artifacts/affine_threshold.py) → [.out](artifacts/affine_threshold.out)

On affine, a reflection is solvable only at **beam ≥ 224** (≤192 fails). Chicken-and-egg for E9: at beam 128 the base search solves _only transpose_ → the wake corpus has no mirror example → the idiom can't be mined. So E9 needs a wider wake beam (224) just to produce one reflection to learn from — and that 128→224 gap _is_ the measured cost of add/mul.

### 4. E8 mints nothing → the rewrite bug — [`artifacts/wake_corpus_and_divergence.py`](artifacts/wake_corpus_and_divergence.py) → [.out](artifacts/wake_corpus_and_divergence.out), [`artifacts/dl_probe.py`](artifacts/dl_probe.py) → [.out](artifacts/dl_probe.out)

First E8 run learned **nothing**. The wake corpus is perfect (6 distinct members, all reflections in the consistent `sub(sub(n,k),1)` form) and `mirror_index` _is_ proposed — but `GreedyMDL.select` returned `None`. `dl_probe` showed why: **`folds?`=0 for every candidate**, program*bits pinned at 288 — `rewrite_with` wasn't descending into `Lam` bodies, so the mirror (which lives \_inside* the coordinate lambda) never folded. Fixed: `rewrite_with` now recurses into `Lam.body`. _(dl_probe.out is the pre-fix output — the historical bug-discovery run.)_

### 5. The divergence — the load-bearing finding

Post-fix, the naïve proposer + greedy MDL mints two **unreusable `COLOR` read-body idioms**, not mirror_index (see wake_corpus_and_divergence.out: `chosen: read(#0, #1, sub(sub(width(#0), #2), 1))`):

    abs0 = read(#0, #1, sub(sub(width(#0), #2), 1))   # "column mirrored on width"  → flip_h, rot90, rot180
    abs1 = read(#0, sub(sub(height(#0), #1), 1), #2)   # "row mirrored on height"    → flip_v, rot270, rot180

They're the two **axis half-reflections** — each covers 3 members, so greedy grabs them (bigger train compression). But they're `(GRID,INT,INT)→COLOR` — the coordinate search can't compose them → re-solve DL _worsens_ (×0.95), zero speedup. And they both _contain_ `sub(sub(·,·),1)` = mirror*index, the shared factor greedy missed. Iteration can't recover it: once the read-bodies absorb the mirror into their \_definitions*, the corpus-only proposer can't see it (that needs library refactoring). **Train-DL ≠ reusability** — a compression-optimal inventor (Stitch) would hit this too.

### 6. The fix, and why it's a stopgap (design dialogue)

`mirror_index` is "better" not by train-DL (read-bodies win there) but by (a) _reusability_ — it's `INT→INT`, the type the search composes; and (b) _factoring_ — it's the shared subterm of the read-bodies. Four families of fix (full catalog in MACHINERY.md F4): scope invention by type; make governance search-aware; library refactoring; joint selection (ruled out — read-bodies are the joint train-DL optimum too). Chosen for now: **scope invention to the signature the search composes**, `INT^n→INT`, **derived from the search itself** (`SearchScopedFrequentSubtree(composes=search.composes_signature)`) — _not_ a declared type (that felt like cheating). It's a labelled **stopgap**: _anti-open-ended_ (can only invent what the search already composes, foreclosing new-type / layered vocabulary). The general, open-ended fix (search-aware governance / library refactoring = Stitch) is queued.

Built four pluggable `AbstractionProposer`s (naïve `FrequentSubtree`, `TypeScoped`, `SearchScoped`, alongside `AntiunifyPairs`) so the divergence stays a _studied variable_, not a hidden filter.

### 7. The positive matrix — [`artifacts/run_e8e9.py`](artifacts/run_e8e9.py) → [.out](artifacts/run_e8e9.out)

E8 (sub, beam 128) and E9 (affine, beam 224) both invent mirror_index and the search reuses it.

## Findings

|  | invented | compression (L1→L2 DL) | speedup (considered) | enablement | base blowup (L1 considered) |
| --- | --- | --- | --- | --- | --- |
| **E8 (sub)** | `sub(sub(#0,#1),1)` | 390→348 **×1.12** | **×3.47** | 20 tasks | 77,148 |
| **E9 (affine)** | `sub(#0,add(#1,1))` — _same behavior_ | 392→350 **×1.12** | **×5.00** | 20 tasks | 234,828 (~3×) |

- **Bootstrap works:** shared factor invented, reused, ladder compresses (inverts E7's ×0.79), cliff dissolves (all 5 reflection members enabled at the tight beam).
- **Robust to grammar:** same idiom under both grammars — E9 expresses it via `add` (`n−(k+1)`), a different structural form the behavioral checker matches by signature.
- **add/mul cost:** ~3× the base search effort, and its speedup matters _more_ there (×5.00 vs ×3.47).

## Decisions & open questions

- The type-scoping is a **stopgap**, logged as such — it works but is anti-open-ended.
- **Queued (EXPERIMENT_QUEUE.md):** `reusable-idiom governance` — does search-aware / transfer-aware governance mint the reusable idiom over the read-bodies _without_ the type gag? The fully-general alternative — **library refactoring** (compress the library, extract the shared factor into a hierarchy) — is ≈ Stitch's core, deferred to real-ARC scale.
- Standing move (strategy): point the loop at a real ARC slice rather than another microworld.

## Artifacts index

- [`beam_cliff_sweep.py`](artifacts/beam_cliff_sweep.py) — beam × library sweep + the coordinate pool (mirror_index at depth-1).
- [`member_matrix.py`](artifacts/member_matrix.py) — per-D4-member × beam × library solvability grid.
- [`affine_threshold.py`](artifacts/affine_threshold.py) — the affine beam threshold (≤192 fails, ≥224 solves) + timings.
- [`wake_corpus_and_divergence.py`](artifacts/wake_corpus_and_divergence.py) — the wake corpus, proposals, and naïve selection (→ read-body, the divergence).
- [`dl_probe.py`](artifacts/dl_probe.py) — per-candidate two-part DL; caught the rewrite-fold bug (pre-fix `folds?`=0).
- [`run_e8e9.py`](artifacts/run_e8e9.py) — the E8/E9 runner + their raw reports.
