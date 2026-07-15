# E13: fundamental-floor grain contrast

EXPERIMENT_QUEUE.md's reframed top row (2026-07-14 rewrite): read the search-behavior object for
the *same* rot180 target across three floor "grains" — `GEOM` (direct D4 primitive) →
`UNIVERSAL_FLOOR` (build_grid + full coordinate arithmetic/comparison) → `MINIMAL_COMPLETE_FLOOR`
(build_grid + read + if + eq only, no arithmetic — the "zero added prior" completeness witness) —
on both a designed task and a real `arc1-train` task, decomposing **expressible → findable →
cheap**.

## Design

- **Target: rot180**, chosen over `transpose` (needs zero arithmetic in any floor — a poor
  differentiator) and over a single-axis flip. `read`'s two coordinate args are independent
  expressions, so a 2D reflection decomposes into two independent 1D lookup chains rather than a
  combined 2D table — cheaper than first feared.
- **Real task:** `3c9b0459` — the only fixed-shape (3x3 everywhere, train+test), multi-example
  (4, genuinely varied) rot180 task among tonight's known-solved D4 tasks.
- **Designed task:** a new `taskgen` generator (`grain-contrast`, `taskgen/generators.py`) — one
  task at fixed 3x3, one at fixed 10x10, 4 varied train examples each, rot180. Multiple varied
  examples are load-bearing: with only one example, the cheapest solving program in
  `MINIMAL_COMPLETE_FLOOR` would be a hardcoded per-cell literal-output table that ignores `input`
  entirely (same trap as the 2026-07-12 perceive-transform experiment), not the intended
  coordinate remap.
- **Machinery added** (per the session's "Library + preset + registered generator" convention,
  not a generic `--bundle` CLI flag): 3 new presets in `execution/presets.py` (`geom`,
  `universal-floor`, `minimal-complete-floor`), each `resolve_bundle(...)`-built from
  `bundle_sheet.py`; 1 new `taskgen` generator (`grain-contrast`).

## A generator bug, found and fixed mid-investigation

The first designed-task pattern, `(row*3 + col*7 + offset) % 10`, has `3+7=10` — which makes
`transpose` **algebraically identical** to `rot180` for that formula, at any grid size or offset
(verified numerically against all 7 other D4 members). The first `geom` run "solved" both tasks,
but the winning program was `transpose(input)`, not `rot180(input)` — a false positive, not a real
result. Fixed to `(row*1 + col*2 + offset) % 10` (verified collision-free against all 7 other D4
members, both sizes, 10 offsets) and regenerated the testbed. **Lesson:** a deterministic
"varied content" formula needs checking for accidental algebraic symmetries under the specific
modulus/coefficients chosen, not just "looks different by eye."

## Runs

All against `arc1-train`'s commit at the time (working tree atop 6066040). Designed-task runs use
the `grain-contrast` testbed (2 tasks: `grain-rot180-3x3`, `grain-rot180-10x10`) via
`arc-lab search <preset> --corpus grain-contrast --track-all`; the real-task leg uses
[artifacts/grain_contrast_real_task_probe.py](artifacts/grain_contrast_real_task_probe.py) (a
1-task `arc1-train` slice, no CLI single-task selection exists).

**Invalid (buggy testbed, corpus_hash `f269decad964f084`) — discarded:**
- `geom`, depth2/arity1/pool100: [runs/2026-07-15/20260715_012546_33fa25ca1ed11711/](../../runs/2026-07-15/20260715_012546_33fa25ca1ed11711/) — "solved 2/2" via `transpose(input)`, not `rot180` — invalid.
- `universal-floor`, depth6/arity2/pool1000 (preset default): [runs/2026-07-15/20260715_012552_bb4569afddfd2265/](../../runs/2026-07-15/20260715_012552_bb4569afddfd2265/) — killed after several minutes, 0/2 tasks even started (`trace.jsonl` empty) — never completed.
- `universal-floor`, depth3/pool200: [runs/2026-07-15/20260715_013824_7d4d5c07e2e058a0/](../../runs/2026-07-15/20260715_013824_7d4d5c07e2e058a0/) — "solved 1/2" via the same `transpose`≈`rot180` collision — invalid.

**Valid (fixed testbed, corpus_hash `6fd5ac0ff40b403d`):**
- `geom`, depth2/arity1/pool100: [runs/2026-07-15/20260715_015212_cb344322a642aaea/](../../runs/2026-07-15/20260715_015212_cb344322a642aaea/) — solved 2/2, `rot180(input)` both, considered=16.
- `universal-floor`, depth3/pool200: [runs/2026-07-15/20260715_014121_4872c55969a968ec/](../../runs/2026-07-15/20260715_014121_4872c55969a968ec/) — 0/2, considered=70,718, ~2.6s.
- `universal-floor`, depth4/pool200: [runs/2026-07-15/20260715_014138_c1cc1e4549816224/](../../runs/2026-07-15/20260715_014138_c1cc1e4549816224/) — 0/2, considered=1,290,178 (3x3: 190,054 / 10x10: 1,100,124), ~4.5min.
- `minimal-complete-floor`, depth3/pool200: [runs/2026-07-15/20260715_015227_44f40f1c5681acba/](../../runs/2026-07-15/20260715_015227_44f40f1c5681acba/) — 0/2, considered=4,329, 0.7s.
- `minimal-complete-floor`, depth4/pool200: [runs/2026-07-15/20260715_015237_97f00de2dd0637aa/](../../runs/2026-07-15/20260715_015237_97f00de2dd0637aa/) — 0/2, considered=102,982 (3x3: 14,001 / 10x10: 88,981), 9.9s.
- `minimal-complete-floor`, depth5/pool200: [runs/2026-07-15/20260715_015254_1ff1ce427f10a30c/](../../runs/2026-07-15/20260715_015254_1ff1ce427f10a30c/) — 0/2, considered=1,729,406 (3x3: 679,288 / 10x10: 1,050,118), ~2m13s.
- Real task `3c9b0459`, depth4/pool200 (except `geom` at its preset default depth2): [runs/2026-07-15/20260715_015651_a9c3b8688aec9512/](../../runs/2026-07-15/20260715_015651_a9c3b8688aec9512/) (`geom`, solved 1/1, considered=8), [runs/2026-07-15/20260715_015651_d2818abfd6850662/](../../runs/2026-07-15/20260715_015651_d2818abfd6850662/) (`universal-floor`, 0/1, considered=210,758), [runs/2026-07-15/20260715_015659_791706b1a6d0fb65/](../../runs/2026-07-15/20260715_015659_791706b1a6d0fb65/) (`minimal-complete-floor`, 0/1, considered=19,973).

## Findings

- **`GEOM` solves trivially, as expected** — rot180 is a direct 1-application primitive; 8-16
  candidates considered regardless of task source or size.
- **Designed and real 3x3 tasks track each other closely at matched depth** — `universal-floor`:
  190,054 (designed) vs 210,758 (real), within ~10%; `minimal-complete-floor`: 14,001 vs 19,973,
  same order of magnitude. The designed task is a faithful stand-in for the real one here — the
  "does the designed wall match the real task" question the queue row asked, answered yes at this
  depth.
- **Neither `universal-floor` nor `minimal-complete-floor` solved rot180 within a depth budget
  cheap enough to be practical** — `universal-floor` unsolved through depth 4 (4.5 min,
  ~18-22x/round growth, broad-based across every `by_category` bucket, not one mechanism);
  `minimal-complete-floor` unsolved through depth 5 (2m13s) for *either* grid size. Per-round
  growth ~17-24x throughout, consistent with ordinary exponential composition, not a runaway bug.
  This is itself the finding for these two rungs: `lambda-synthesis`'s recursive body search
  (re-triggered from scratch every outer round `build_grid` is a candidate — see
  `search_engine.py::_synthesized_lambdas`'s docstring, "re-offered each round") makes even a
  modest target expensive to *find* well before any grid-size effect specific to
  `MINIMAL_COMPLETE_FLOOR`'s missing `lt`/`gt` (predicted to force a linear rather than balanced
  lookup chain) has a chance to show up.
- **3x3-vs-10x10 scaling at this shallow depth is a similar ~6x for both floors** (`universal-floor`
  190,054→1,100,124; `minimal-complete-floor` 14,001→88,981) — the predicted floor-specific
  divergence (linear lookup chain forced by no `lt`/`gt`) hasn't kicked in yet; what's visible so
  far is the generic literal-leaf-count effect (more distinct harvested `Int` constants at larger
  sizes), not the depth-cliff difference. Neither floor got deep enough to actually attempt the
  full coordinate-remap construction.
- **A large, growing fraction of considered candidates error out** (out-of-domain coordinate
  expressions) rather than productively explore — e.g. `universal-floor`'s `build` category:
  9,222 errored at depth 3 → 176,116 at depth 4, roughly tracking the category's own growth rate.

## Decisions / open questions

- Did not chase a full solve for `universal-floor`/`minimal-complete-floor` (depth 5/6) —
  the cost trajectory (~18-24x/round) made that expensive for uncertain payoff; the "expensive
  and still unsolved at a modest depth" result is treated as the finding for this pass.
- Open: is `max_pool=200`'s cap (rather than depth) the actual bottleneck for
  `minimal-complete-floor` — the 3x3-vs-10x10 considered counts converging (679,288 vs 1,050,118
  at depth 5, only ~1.5x apart) rather than diverging as my hand-derived linear-lookup-chain
  argument predicted suggests pool eviction may be truncating the correct partial construction
  before it can combine, independent of whether more depth would help. Worth a pool-size sweep
  before concluding anything stronger about `MINIMAL_COMPLETE_FLOOR`'s true depth requirement.
- The 3 new presets (`geom`/`universal-floor`/`minimal-complete-floor`) and the `grain-contrast`
  generator are now permanent, reusable machinery (`execution/presets.py`,
  `taskgen/generators.py`) — available for any future experiment on this floor ladder.
