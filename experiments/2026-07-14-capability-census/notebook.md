# Capability census — investigation notebook

Shared home for the three queued "census" experiments (EXPERIMENT_QUEUE.md Active): **preset partition** (this entry), **region-logic**, **perceiver-recolor**. All three read the partition of an as-shipped `Config` over the full `arc1-train` corpus via `arc-lab search` + `arc-lab analyze-run` — no new code, so they share this one notebook rather than each getting a dedicated folder.

## Experiment 1 — arc1 preset partition census (`d4`, `synth`; `sym` deferred)

**Goal:** read the partition (solve count, `by_category`/`by_provenance`, outcome mix) for the `d4` and `synth` presets over full `arc1-train`, as a sanity-anchored baseline before the region-logic/perceiver-recolor censuses. `sym` deferred to a follow-up (full-corpus cost ~32 CPU-min per EXPERIMENT_LOG.md 2026-07-08).

**Runs:**
- `d4` search, `arc1-train` (400 tasks): [runs/2026-07-14/20260714_205844_18e7562f44036326/](../../runs/2026-07-14/20260714_205844_18e7562f44036326/) — [analyze-run output](artifacts/d4_analysis.json)
- `synth` search, `arc1-train` (400 tasks): [runs/2026-07-14/20260714_205849_6ef6f65b7e10d299/](../../runs/2026-07-14/20260714_205849_6ef6f65b7e10d299/) — [analyze-run output](artifacts/synth_analysis.json)

**Sanity check:** both match the locks exactly — `d4` 7/400, `synth` 11/400, and `synth`'s solved set is a strict superset of `d4`'s (the same 7 D4 tasks + 4 atomic tasks), reproducing the EXPERIMENT_LOG.md 2026-07-08 finding byte-for-byte.

**Findings:**

- **`d4` partition is trivial by construction.** Single library = single category (`geometry`) and single provenance (`base`) — there's no capability-family split to read when the bag holds one family. `by_primitive`: every one of the 8 D4 ops gets considered (`deduped` 4–400 each — `identity` dedupes against all 400 inputs trivially), but only `flip_h`/`flip_v`/`rot90`/`rot180`/`transpose` ever `accepted` (win a task); `anti_transpose` and `rot270` are considered/deduped on every task but never the cheapest solving program for any of the 400 — live vocabulary, zero payoff on this corpus (not "dead" in the Table-A island sense — they're reachable and fire — just non-winning here).
- **`synth`'s cost is almost entirely `map_color` x constant-leaf combinatorics.** `by_category` considered-adjacent totals (`deduped`+`evicted`+`goal_unmatched`+`accepted`): `constant` (leaf pool) ~2.68M and `color` (`map_color`) ~2.61M, vs `geometry` ~504K and `scaling` ~389K, out of 2.70M total considered. The `finite-enumerate` constant policy (10 colors + 0..max-dim ints) pairing with `map_color`'s 2-arg signature is the dominant cost driver, concretely confirming the "multiplicative under variadics" cost note in `docs/CONFIG-DEFAULTS-2026-07-11.md` — this is the first run that puts a number on it rather than a qualitative warning.
- **`evicted` only appears once constants exist.** `d4` (`constant_sources=()`): 0 evicted, 0 pruned. `synth` (finite-enumerate): 431,052 evicted, still 0 pruned (no `Constraint`s registered on either preset, matching the `()` default). Eviction is pool-cap pressure (`max_pool=500`) biting once the constant leaves blow up the per-round frontier — `d4`'s `max_pool=100` never fills.
- **The 4 synth-only solves are exactly `map_color`/`scale` singletons** (`9172f3a0`→`scale(input,3)`, `b1948b0a`→`map_color(input,6,2)`, `c59eb873`→`scale(input,2)`, `c8f0f002`→`map_color(input,7,5)`) — one-hop compositions the D4-only bag can't reach at all (an island-free, direct on-ramp/off-ramp path per SEARCH-SPACE.md's Table A).

**Decisions / open questions:**
- "Dead primitive" needs a sharper definition before the region-logic/perceiver-recolor censuses: *zero-accepted-but-considered* (this run's `anti_transpose`/`rot270`) is a different, weaker claim than *zero-considered* (true Table-A island dead weight, not observed in either run here). Use the empirical `by_primitive` `accepted` count as the signal, and only reach for `check-library-coherence` if a primitive shows zero `considered` entirely (a structural, not corpus-outcome, question).
- `sym` (harvest constants, arity 4, full `arc1-train`) still queued — expect the `by_category` story to be dominated by geometry x combinator (`overlay`/`tile`) arity blowup rather than constant-leaf multiplicity, per the existing "missing nine are exactly the TILE tasks" historical finding (EXPERIMENT_LOG.md 2026-07-13).

**Next:** run `sym` full-corpus (background, ~32 CPU-min) and append its partition here; then region-logic (`MASK_BASIC`) and perceiver-recolor (`PERCEIVE_TRANSFORM`) censuses land in this same folder once their `Config`/bundle-search machinery gap is closed.
