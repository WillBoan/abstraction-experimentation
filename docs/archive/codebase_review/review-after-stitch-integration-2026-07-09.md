# Review — higher-order + Stitch + type-system stack (2026-07-09)

A multi-agent adversarial review of the higher-order / Stitch / polymorphic-type stack, run after the
Stitch integration (Phases A–H) landed and while the parallel `BOOL`/`eq`/`if` + `type_directed` work
was in the tree. Method: three focused reviewer agents (Phase-H migration, higher-order search, Stitch
shim/sleep) + independent reading of the crown-jewel files, cross-verified, and the sharpest claims
re-probed against the real `stitch_core` wheel.

**Status legend:** ✅ fixed (in tree) · ➿ superseded by other work · 🕒 deferred (tracked) · 📝 doc-only /
by-design · ⚪ not worth fixing.

All fixes below are in the **working tree** (uncommitted as of this date, atop commit `6f38706`).

---

## Verified sound (no action)

- **First-order byte-identity holds.** With `higher_order`/`synthesize_functions` off (the defaults),
  enumeration is byte-identical to pre-higher-order behavior (verified three ways incl. the `dsl`=7/19/11
  locks). The `type_directed` refactor is behavior-preserving.
- **Metavar unification in `from_sexpr` is correct** (uses shared across occurrences, resolved via subst).
- **The serialization asymmetry** (`Param`→`x{j}` in, `#j`→`Param` out) is coherent and tested.
- **`RefactoringSleep` phase-2 mechanics are correct** (only its *justification* docstring was off — see H).

---

## Tier 1 — real defects (all fixed)

| id | finding | fix | where |
| --- | --- | --- | --- |
| **A** | ✅ Function-dedup battery **unsound** — both `_SYNTH_GRIDS` were height-2, so `height` ≡ a constant on the battery → a correct candidate silently dropped (order-dependent solve). `None`-sig used as a dedup key collapsed unprobeable candidates. | Battery now varies height/width/content independently + spans all colors/ints; `None` sig never dedups (keep both); smallest witness wins by explicit size compare. | `search/enumerate.py` `_domain_battery`, `_dedup_functions` |
| **B** | ✅ `from_sexpr` did **no arity check** → real first-order Stitch partial applications (a 2-arg `read`) decoded into malformed, unevaluable `Apply` nodes; a green test was certifying one. | Arity check rejects partial applications (a `ValueError` the proposer catches + skips). The B1 "read-body on the raw corpus" test premise was corrected — that "read-body" *was* the partial-app; the well-formed one arises via the hierarchical sleep path. | `learn/stitch_shim.py` `_infer`; `tests/test_stitch_shim.py` |
| **C** | ✅ Phase-H weakened deserialization **fail-fast** — `base_type` fabricated a junk `BaseType("gird")` where the retired enum raised. | `base_type` is strict (raises on unknown name) at the untrusted-input boundary; a new base type is added by registering a singleton, not fabricating. + test. | `substrate/types.py` `base_type`; `tests/test_types.py` |

## Tier 2 — latent correctness (fixed or superseded)

| id | finding | fix | where |
| --- | --- | --- | --- |
| **D** | ✅ `boundvars` was a **flat global map**, ignoring De Bruijn scope — two `$0`s under different binders wrongly unified. Not reachable today (`build_grid` uses distinct indices) but real for `map`/`fold`. | Replaced with a binder **stack**; `$i` reads `bound[-1-i]`; out-of-scope `$i` fails fast. + sibling-lambda test. | `learn/stitch_shim.py` `_InferCtx.bound`, `_bound_var_type` |
| **E** | ✅/➿ `unify` without `instantiate` (var capture once polymorphic primitives ship). | `from_sexpr` now instantiates each primitive signature fresh (`_instantiate_sig`). The enumerator side was **superseded** by the parallel `type_directed` helper (fresh `instantiate` per application). | `learn/stitch_shim.py`; `search/type_directed.py` (parallel) |
| **F** | ✅ `AppFn.result_type` vs `evaluate` disagreed for a `Lam`-headed node (`Lam` types as opaque `FN`); `from_sexpr` hard-coded `(lam …)`→`FN` and discarded `expected`. | Documented the `AppFn` contract (head is `Param`/`PrimRef`, arrow-carrying; a `Lam` head is intentionally unsupported by `result_type`). `from_sexpr` lam now seeds its binder from an expected arrow hole and unifies its body with the codomain. | `substrate/program.py` `AppFn`; `learn/stitch_shim.py` `_infer` lam case |
| **G** | ➿ `pools[expected]` could `KeyError`-crash the search for a non-`{GRID,COLOR,INT}` return type. | Superseded by the parallel refactor (`pools.setdefault(expected, {})` + `signature_matches_type`). | `search/enumerate.py` (parallel) |

## Tier 3 — inaccurate claims / determinism / quality (all fixed)

| id | finding | fix |
| --- | --- | --- |
| **H** | ✅ Misleading docstrings. (1) `RefactoringSleep` justified phase-2 Stitch as the refactor "the in-house proposer cannot" — contradicting the lab's own recorded finding that in-house `FrequentSubtree` would recover `mirror_index` if fed the definitions; the real seam is *call-sites vs definitions*. (2) "logged never silent" logs at `DEBUG` (silent by default). (3) `_compress` "threads chosen by the caller's determinism check" — no such check. | All three reworded to match reality. `learn/sleep.py`, `learn/stitch_shim.py` |
| **I** | ✅ `_dedup_functions` comment said "a PrimRef, being smaller, wins ties" but the code kept *first-seen*. | Now keeps the smallest witness by explicit size compare; comment corrected. |
| **J** | ✅ `_needed_arrows` returned a `set` iterated to build the pool → `PYTHONHASHSEED`-dependent order (against the repo's determinism discipline). | Insertion-ordered dict (library order). |

## Minor / deferred / by-design

| id | finding | status |
| --- | --- | --- |
| **BOOL↔Stitch** | ✅ `to_sexpr(Const(True, BOOL))` emitted `"True"`, which `from_sexpr` couldn't parse — a bool-bearing program (`eq`/`if`) could not round-trip through Stitch. | Fixed: `true`/`false` tokens ↔ `BOOL` `Const`. + round-trip test. `learn/stitch_shim.py` |
| **L** | `_lam_bodies` had no `max_pool` guard (unbounded synthesis); the function pool is rebuilt per-`find` though it depends only on the library. | Partial: added a `max_pool` bound to `_lam_bodies`. 🕒 Per-task memoization left as a pure optimization (cost, not correctness). |
| **K** | `threads` is exposed with no guard; `> 1` silently forfeits reproducibility (locks would go flaky). | 📝 Documented in the `_compress` docstring (only `threads=1` is guaranteed reproducible); not hard-enforced. |
| **M** | `from_sexpr` defaults a literal to `INT` when `expected` is a non-`BaseType` (e.g. a metavar arg) — a `COLOR` literal there would be tagged `INT`. | ⚪ Harmless today (a `Const` returns its value regardless of tag; not reached by `build_grid` corpora). Left as-is. |

## Deferred optimizations (tracked in MACHINERY.md, F1 table)

The first-order-polymorphic control floor (`eq`/`if`) makes each enumeration round ~O(pool²) — `eq(a,a)`
ranges over every same-typed pair — so today it's bounded only by `beam_width` (why `BuildGridBodySearch`'s
default beam is a *minimum*, not research-grade). Two principled reductions, ⚪ unbuilt:

- **(a)** reflexive/symmetric pruning via a `Primitive.commutative` flag (skip `eq(x,x)` + `eq(b,a)` dupes).
- **(b)** a cost-bounded **per-round candidate budget** (expand cheapest-first to a hard cap).

---

## Record correction (for EXPERIMENT_LOG.md)

The committed **Phases G + H** EXPERIMENT_LOG.md entry (in `6f38706`) called the stack "compromise-free
within its scope." That is **overstated**: finding **A** showed the function-dedup battery was actually
*unsound* (now fixed), and even fixed it remains a **finite-battery observational-equivalence heuristic**
(standard, sound-in-practice, but not complete). Worth a terse walk-back entry that points here.
