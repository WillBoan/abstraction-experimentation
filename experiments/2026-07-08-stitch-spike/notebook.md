# 2026-07-08 — Stitch spike: does library-refactoring recover `mirror_index`?

Full write-up for the terse [EXPERIMENT_LOG.md](../../EXPERIMENT_LOG.md) entry
*"Stitch spike: two orthogonal ways it dissolves the E8 divergence"* (commit `b5268b5`).
Verbatim scripts + captured outputs in [`artifacts/`](artifacts/).

> **Reviewed interpretation (2026-08-12).** Raw first-order Stitch output over the original corpus has a non-unary interface and is not callable as an AE `Grid → Grid` transform; it cannot serve as independent evidence for a reusable AE abstraction. The valid historical probes are (a) first-order refactoring over learned definitions, which extracts a callable coordinate routine, and (b) higher-order invention, which can preserve the reusable structure. These are historically traceable probes without modern `RunSpec` identity. See the [reviewed synthesis](../../EXPERIMENTS.md).

## The question

Two of the repo's own docs disagreed about what adopting Stitch would do for the E8
compression/reusability divergence:

- **MACHINERY.md F4** — library refactoring "≈ Stitch's core … the open-ended general fix" (`🔜 via Stitch`).
- **Historical E8 log entry** — *"Train-DL ≠ reusability — and a compression-optimal inventor (Stitch) would hit this too."*

Load-bearing because the answer decides whether the `🔜 via Stitch` arrow is real. An offline spike could
settle it cheaply: the substrate was built Stitch-compatible (`$i`/`#j`/`lam` already print), so
`Program → s-expr` is a solved 6-case recursion; `stitch_core` pulls in via `uv run --with` (no dep added).

## What I ran (the log)

Corpus throughout: the 6 `_d4_targets(Input())` `build_grid` programs (5 contain the `_mirror` sub-term).

1. **`artifacts/stitch_spike.py`** — Run A (feed the raw corpus) + Run B (feed the two minted read-body
   *definitions*). First pass, Stitch defaults (higher-order allowed). Run A's top abstraction came back as
   `(sub (sub (#1 input) #0) 1)` — behaviorally `mirror_index` with the *perceiver* hoisted into a
   function-typed hole; Run B recovered it too. **Initial (over-)reading: "higher-order invention is the
   root fix."**

2. **`artifacts/stitch_matrix.py`** — pressure-tested that reading with a 2×2:
   `{stitch-default cost, node-count cost ≈ TwoPartMDL} × {higher-order, first-order (no_curried_metavars)}`,
   `tasks=` D4 members. Result: **the flip is entirely first-order vs higher-order, robust to the cost model**
   (and to `allow_single_task`). Higher-order → `mirror_index` top; first-order → the `COLOR` read-body top
   (the divergence, reproduced — E8's prediction confirmed *within the first-order class*).

3. **`artifacts/stitch_refactor.py`** — the decisive test I'd skipped: **first-order** library refactoring
   (feed the two read-body *definitions*, `no_curried_metavars=True`). It extracts the clean, general,
   first-order `(sub (sub #0 #1) 1)` = `mirror_index(n,k)` — **no higher-order needed**, because once the
   read-body *is* the definition, the bigger competing subtree is gone.

## Historical findings, subject to the arity correction above

Two **orthogonal axes** (I initially conflated them):

| feed ↓ / holes → | first-order | higher-order |
| --- | --- | --- |
| **raw corpus** | `COLOR` read-body → divergence | `mirror_index` (perceiver hoisted) |
| **minted defs (refactor)** | **general `mirror_index(n,k)`** | `mirror_index` (perceiver hoisted) |

- **Library refactoring is the architecture-relevant fix** (bottom-left) and works **first-order** — the
  capability the wake–sleep loop lacks (the proposer walks corpus call-sites, never `.template`s). = the F4
  row, ≈ Stitch's core.
- **Higher-order invention is a separate, additive mechanism** (top-right): it *prevents* the burial on the
  raw corpus rather than *curing* it. A bonus, not a replacement.
- Numbers (Stitch's own cost units; tiny corpus, directional): raw corpus first-order → read-body (ratio
  2.80 / 2.64), higher-order → mirror (3.37 / 3.63); refactor first-order → general mirror (1.55).

## Dead-end / correction (kept, per the discipline)

My first synthesis — *"neither library refactoring nor governance is the root fix; higher-order invention
is"* — was **wrong / overstated**, from testing on the *raw corpus* only. The user pushed back (the whole
point of Stitch was walking definitions), and `stitch_refactor.py` confirmed first-order refactoring alone
recovers the clean `mirror_index`. The historical log entry was corrected to the two-axis framing.

## Decisions this drove

- Confirmed the `🔜 via Stitch` arrow **and** re-attributed *why* it works (library refactoring, first-order;
  higher-order is orthogonal).
- Reshaped the implementation plan into the full best-practices route (pluggable `SleepStrategy` → Stitch as
  a cost-controlled proposer + library refactoring → polymorphic type system → general higher-order search),
  captured at `~/.claude/plans/help-me-with-some-structured-map.md`. Phase A (the `SleepStrategy` refactor)
  is done and behavior-identical; Phase B is the first Stitch integration.

## Open questions carried forward

- Does Stitch stay deterministic at `threads > 1`? (Verify with a twice-run identity test in Phase B1.)
- Cost-model control: Stitch's utility is a fixed weighted-construct form → use it as a *proposer* + our
  selector for full governance control (Phase B).
