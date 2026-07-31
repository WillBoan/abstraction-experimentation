# `4093f84a` expressibility ladder — 2026-07-15

A worked case study in the gap between _type-closure completeness_ and _practical searchability_, using [`data/arc-agi-1/data/training/4093f84a.json`](../../data/arc-agi-1/data/training/4093f84a.json) against `UNIVERSAL_FLOOR` and two candidate extensions. Prompted by a design discussion in session; kept as a concrete referent for that distinction the next time it comes up (Constraint 7, [`_PRIMITIVE_BUNDLES.md`](../../src/arc_lab/program_search/substrate/primitives/_PRIMITIVE_BUNDLES.md)). Not a proposal, not wired into any preset — a worked example.

## The task

Each grid has one solid-color separator bar (color 5) — a full-height vertical band or full-width horizontal band — splitting it into two regions. Scattered in the two regions are single-color marker cells on background (0). Markers are erased; the bar **grows** on each line perpendicular to it (each row if the bar is vertical, each column if horizontal), on each side, by a run of length equal to the marker count on that side of that line — histogram bars growing out of a spine. Verified cell-for-cell against all 3 train pairs and the test pair (`solve()` walkthrough below reproduces every output exactly).

```python
def solve(g):
    H, W = len(g), len(g[0])
    is_bar = lambda r, c: g[r][c] == 5
    is_marker = lambda r, c: g[r][c] not in (0, 5)
    rows_bar = [all(is_bar(r, c) for c in range(W)) for r in range(H)]
    cols_bar = [all(is_bar(r, c) for r in range(H)) for c in range(W)]
    is_horizontal = any(rows_bar)

    out = [[5 if is_bar(r, c) else 0 for c in range(W)] for r in range(H)]

    if is_horizontal:
        lo, hi = min(r for r in range(H) if rows_bar[r]), max(r for r in range(H) if rows_bar[r])
        for c in range(W):
            above = sum(1 for r in range(lo) if is_marker(r, c))
            below = sum(1 for r in range(hi + 1, H) if is_marker(r, c))
            for r in range(H):
                if r < lo and lo - r <= above: out[r][c] = 5
                if r > hi and r - hi <= below: out[r][c] = 5
    else:
        lo, hi = min(c for c in range(W) if cols_bar[c]), max(c for c in range(W) if cols_bar[c])
        for r in range(H):
            left = sum(1 for c in range(lo) if is_marker(r, c))
            right = sum(1 for c in range(hi + 1, W) if is_marker(r, c))
            for c in range(W):
                if c < lo and lo - c <= left: out[r][c] = 5
                if c > hi and c - hi <= right: out[r][c] = 5
    return out
```

## Is it expressible?

**Yes, in `UNIVERSAL_FLOOR`'s strict closure sense** — over this task's fixed 14x14 grids, `build_grid` + `if` + `eq` + `CTRL`, fed by `finite-enumerate`-mined coordinate literals (0-13), is decision-tree/boolean-circuit-complete: any function from a bounded grid to a bounded grid can be unrolled as a sufficiently large nested `if`/`eq`/`and` expression per output cell. That's exactly what the floor's own design note claims ("the 'zero added prior' completeness witness... isolates completeness from what's added purely to shorten programs").

**But not practically searchable at that floor** — the honest reason is depth/cost (Constraint 7: _"type-reachable != reachable within a sane budget"_), not inexpressibility.

Two extensions were checked against the same task to see how much of that gap they close:

- **`UNIVERSAL_FLOOR + MASK_BASIC`** — the doc's own named composite ("global completeness plus cheap region logic"). Closes bar/orientation detection cheaply via `mask_by_color` + `crop_to_mask`, but not bar _position_ (masks return content, not offsets) or per-line _counting_ (no `MASK -> INT` cardinality primitive exists anywhere in the registry — confirmed directly from the Gap-Exposing Bundles section: `OBJECT_PRECURSOR`'s note).
- **`UNIVERSAL_FLOOR + HO_BASIC + CELLS_IO + PAIR`** — `fold` over `cells(grid)` with an accumulator that self-tracks its own position (the standard indexed-fold technique; `pair` supplies accumulator state). This recovers both bar-location and per-line counting as constant-size, width-independent expressions, without any `MASK` primitives. The `map`/`filter` no-positional-index dead end (their `f(x)` never gets an index) does not apply to `fold`, because `fold`'s accumulator can carry the index itself — the piece missed on the first pass through this problem, and the reason this floor doesn't need a new primitive at all to get the depth win. Caveat: `fold`'s body sampler is baseline-only (no target-propagation — see `higher_order.py`'s docstring), so this floor's depth advantage does not imply the engine would actually _find_ the needed accumulator shape without help.

## The abstraction ladder

Each row is a named quantity, defined only in terms of the row(s) above it, bottoming out in raw primitives. Two depth columns:

- **Total** — depth of the smallest program computing this quantity from _raw floor primitives only_, no reuse (nothing in these substrates lets a program name/reuse a subexpression except by defining a new primitive) — the real cost a from-scratch search faces.
- **Jump-only** — depth of _just this step_, assuming every prior row is already a saved, callable abstraction (cost 1 to invoke, internals hidden) — the cost if each rung got promoted to a library primitive before the next rung was attempted.

Depth convention: `depth(f(x1..xn)) = 1 + max(depth(xi))`; literals and bound variables are depth 0.

### Ladder 1 — pure `UNIVERSAL_FLOOR`

| Jump | Produces | Total depth | Jump-only depth |
| --- | --- | --- | --- |
| 1 | `is_bar(r,c)` / `is_marker(r,c)` | 2 / 4 | 2 / 4 |
| 2 | `row_is_bar` / `col_is_bar` (`AND_14` over `is_bar`) | 15 | 14 |
| 3 | `is_horizontal` (`OR_14` over `row_is_bar`) | 28 | 14 |
| 4 | `bar_row_lo/hi`, `bar_col_lo/hi` (`FIRST_14`/`LAST_14` over `row_is_bar`) | 28 | 14 |
| 5 | `count_above/below/left/right` (`SUM_14`) | 44 | 17 |
| 6 | `grow_above/below/left/right` | 47 | 5 |
| 7 | `cell_color` -> `SOLUTION` | ~52 | 6 |

`AND_14`/`OR_14`/`SUM_14` are right-nested chains over the 14 mined column/row literals; `FIRST_14`/`LAST_14` are the same shape as a nested `if`-cascade with a default. Fully expanded, e.g.:

```
AND_14(f) = and(f(0), and(f(1), and(f(2), ..., and(f(12), f(13))...)))
FIRST_14(f, default) = if(f(0), 0, if(f(1), 1, ..., if(f(13), 13, default)...))
```

Each jump re-embeds the _entire_ previous jump's expression at every leaf it touches, which is why total depth compounds rather than adds — not any single hard step, but the total absence of a memoization/reuse mechanism at this floor.

### Ladder 2 — `UNIVERSAL_FLOOR + MASK_BASIC`

| Jump | Produces | Total depth | Jump-only depth |
| --- | --- | --- | --- |
| 1 | `is_bar` / `is_marker` | 2 / 4 | 2 / 4 |
| 2 | `row_is_bar` / `col_is_bar` | 15 | 14 |
| 3 | `is_horizontal` (`mask_by_color` -> `crop_to_mask` -> `width` -> `eq`) | **4** | **4** |
| 4 | `bar_row_lo/hi`, `bar_col_lo/hi` — still `FIRST_14`/`LAST_14` (masks give no offset) | 28 | 14 |
| 5 | `count_above/below/left/right` — still `SUM_14` (no mask cardinality) | 44 | 17 |
| 6 | `grow_*` | 47 | 5 |
| 7 | `SOLUTION` | ~51 | 6 |

Row 3 is the only line that moves. Its _total_ drops sharply (28 -> 4), but nothing downstream references it, so total program depth barely changes — a real local win that doesn't touch the bottleneck (`count_*` / `grow_*`, driven by `bar_row_lo/hi`, unchanged).

### Ladder 3 — `UNIVERSAL_FLOOR + HO_BASIC + CELLS_IO + PAIR`

| Jump | Produces | Total depth | Jump-only depth |
| --- | --- | --- | --- |
| 1 | `is_bar` / `is_marker` | 2 / 4 | 2 / 4 |
| 2 | `count_left_of(...)` — one `fold`, `pair(pos, count)` accumulator | 9 | 9 |
| 3 | `is_horizontal`, `bar_*_lo/hi` — one `fold`, 3-slot accumulator (nested `pair`) | 13 | 13 |
| 4 | `grow_above/below/left/right` | 17 | 5 |
| 5 | `cell_color` -> `SOLUTION` | ~21 | 6 |

Sketch of the counting fold (accumulator `pair(pos, count)`, position self-tracked via `floordiv`/`mod` against `width(G)`, `bar_col_lo` and `row_target` passed in as parameters rather than re-embedded):

```
count_left_of(G, row_target, bar_col_lo, marker_color) =
  fst(fold(
    lam(acc, x.
      let r = floordiv(fst(acc), width(G)); c = mod(fst(acc), width(G))
      pair(add(fst(acc), 1),
           if(and(eq(r, row_target), and(lt(c, bar_col_lo), eq(x, marker_color))),
              add(snd(acc), 1), snd(acc)))),
    pair(0, 0), cells(G)))
```

Because a `fold` step function takes its bounds as _parameters_ rather than re-embedding their derivation, depth stays roughly additive per jump instead of compounding — final depth ~21 vs. ~51-52 for the other two ladders, and Ladder 1/2's depths scale with grid width where Ladder 3's do not.

## The actual finding

The jump-only column never exceeds ~17 in _any_ ladder, including Ladder 1. The large total-depth numbers aren't from one hard composition step — they're from paying the full cost of every underlying jump again at each use, with no way to name and reuse a subexpression short of it becoming a real primitive. That's the same problem the repo's `learn/` machinery (sleep phase: `LearnEngine.run` — antiunify / frequent-subtree / Stitch) exists to solve in general: promoting a repeatedly-re-derived subtree (`row_is_bar`, `count_left_of`) into a named library primitive is exactly the "treat the previous jump as already invented" move the jump-only column assumes. Ladder 3 gets this property "for free" from `fold`'s parameter-taking shape, without needing a learning pass first — Ladder 1's unrolled `AND_14`/`SUM_14` patterns do not.

## Open threads, not pursued here

- Whether `fold`'s body sampler could get target-propagation analogous to `map`/`filter`'s (or some other search-side guidance), which would matter more for actually finding Ladder 3's programs than any primitive addition would.
- Whether a `MASK -> INT` cardinality primitive (flagged separately by `OBJECT_PRECURSOR` in the bundles doc) is worth adding on its own merits — it wasn't load-bearing for this specific task once `fold` was in scope, but may be elsewhere.
