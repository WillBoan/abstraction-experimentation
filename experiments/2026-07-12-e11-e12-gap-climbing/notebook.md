# Gap-climbing: perceive→transform (E11) & layered abstraction (E12)

Investigation, not a single experiment — this folder holds two of the three queued gap-climbing rows (`RESEARCH-2026-07-08.md`'s axis 1 priority spine); the third, **learned intermediate type**, is still queued and will land here too once it runs. See each experiment's full `EXPERIMENT_LOG.md` entry for the historical write-up; this notebook is the run index + cross-experiment comparison.

- **E11:** [EXPERIMENT_LOG.md](../../EXPERIMENT_LOG.md) — entry "E11: perceive→transform …" — `recolor_bg(g,c) = map_color(g, most_common_color(g), c)` derived from `{map_color, most_common_color}`.
- **E12:** [EXPERIMENT_LOG.md](../../EXPERIMENT_LOG.md) — entry "E12: layered abstraction …" — `abs1 = recolor_flipped(g,a,b)` built on `abs0 = rot180`, learned in the same LEARN run.

## E11 — perceive→transform: runs

Study `perceive-transform` (`arc-lab run-study perceive-transform`); library `{map_color, most_common_color}`, `constant_sources=("finite-enumerate",)`. Shallow budget = depth-2 (one application, pre-abstraction unreachable); deep budget = depth-3.

| Library | Budget | Corpus | Solved | Considered | Run |
| --- | --- | --- | --- | --- | --- |
| — | learn (shallow, 5 iter cap) | train | mints `abs0`, converged @2 iterations | — | [20260713_163903_b7a75e343d4ea88b](../../runs/2026-07-13/20260713_163903_b7a75e343d4ea88b/) |
| L1 | shallow (depth-2) | train | 0/5 | 590 | [20260713_163908_fc9b6f403a8c4b8a](../../runs/2026-07-13/20260713_163908_fc9b6f403a8c4b8a/) |
| L1 | shallow (depth-2) | eval | 0/2 | 236 | [20260713_163908_c76b5cb4fc18936b](../../runs/2026-07-13/20260713_163908_c76b5cb4fc18936b/) |
| L2 | shallow (depth-2) | train | 5/5 | 640 | [20260713_163908_54b47760a7090875](../../runs/2026-07-13/20260713_163908_54b47760a7090875/) |
| L2 | shallow (depth-2) | eval | 2/2 | 256 | [20260713_163908_a4ab8044c225fd68](../../runs/2026-07-13/20260713_163908_a4ab8044c225fd68/) |
| L1 | deep (depth-3) | train | 5/5 | 28,650 | [20260713_163907_6146224d2e4e8260](../../runs/2026-07-13/20260713_163907_6146224d2e4e8260/) |
| L1 | deep (depth-3) | eval | 2/2 | 11,460 | [20260713_163908_9945c1abccca248a](../../runs/2026-07-13/20260713_163908_9945c1abccca248a/) |
| L2 | deep (depth-3) | train | 5/5 | 37,880 | [20260713_163905_6d0c22c88f60619a](../../runs/2026-07-13/20260713_163905_6d0c22c88f60619a/) |
| L2 | deep (depth-3) | eval | 2/2 | 15,152 | [20260713_163906_21eb1656c26f1910](../../runs/2026-07-13/20260713_163906_21eb1656c26f1910/) |
| L3 | shallow (depth-2) | train | 5/5 | 640 | [20260713_163910_38ff043163d8c0e3](../../runs/2026-07-13/20260713_163910_38ff043163d8c0e3/) |
| L3 | shallow (depth-2) | eval | 2/2 | 256 | [20260713_163910_2139034727659dce](../../runs/2026-07-13/20260713_163910_2139034727659dce/) |
| L3 | deep (depth-3) | train | 5/5 | 37,880 | [20260713_163908_10c3848f30823408](../../runs/2026-07-13/20260713_163908_10c3848f30823408/) |
| L3 | deep (depth-3) | eval | 2/2 | 15,152 | [20260713_163909_e94d6cb698a13682](../../runs/2026-07-13/20260713_163909_e94d6cb698a13682/) |

L3 (the hand-written target library) tracks L2 (the learned library) exactly at both budgets — `abs0` is behaviorally, not just structurally, equivalent to the target.

## E12 — layered abstraction: runs

Study `layered-abstraction` (`arc-lab run-study layered-abstraction`); library `{flip_h, flip_v, map_color}`. Learn budget = depth-3 (reaches `rot180`, not `recolor_flipped`, until `abs0` exists); deep budget = depth-4 (raw composition reaches both).

| Library | Budget | Corpus | Solved | Considered | Run |
| --- | --- | --- | --- | --- | --- |
| — | learn (depth-3, 5 iter cap) | train | mints `abs0` then `abs1`, converged @3 iterations | — | [20260713_163917_45fa1042a115b372](../../runs/2026-07-13/20260713_163917_45fa1042a115b372/) |
| L1 | learn budget (depth-3) | train | 4/8 | 47,464 | [20260713_163936_f8ac3391917c3fdd](../../runs/2026-07-13/20260713_163936_f8ac3391917c3fdd/) |
| L1 | learn budget (depth-3) | eval | 1/2 | 11,866 | [20260713_163936_585a199867be2188](../../runs/2026-07-13/20260713_163936_585a199867be2188/) |
| L2 | learn budget (depth-3) | train | 8/8 | 183,648 | [20260713_163922_4aaabcc5667e60c0](../../runs/2026-07-13/20260713_163922_4aaabcc5667e60c0/) |
| L2 | learn budget (depth-3) | eval | 2/2 | 45,912 | [20260713_163927_a1afb45f0e7e41a4](../../runs/2026-07-13/20260713_163927_a1afb45f0e7e41a4/) |
| L1 | deep (depth-4) | train | 8/8 | 279,208 | [20260713_163928_d1e0c3e51baf4463](../../runs/2026-07-13/20260713_163928_d1e0c3e51baf4463/) |
| L1 | deep (depth-4) | eval | 2/2 | 69,802 | [20260713_163934_946e6c6d1ccb0969](../../runs/2026-07-13/20260713_163934_946e6c6d1ccb0969/) |
| L2 | deep (depth-4) | train | 8/8 | 644,864 | [20260713_163937_14c615fdd47b1dae](../../runs/2026-07-13/20260713_163937_14c615fdd47b1dae/) |
| L2 | deep (depth-4) | eval | 2/2 | 161,216 | [20260713_163955_cb0e1971f18b6931](../../runs/2026-07-13/20260713_163955_cb0e1971f18b6931/) |
| L3 | learn budget (depth-3) | train | 8/8 | 183,648 | [20260713_164022_b864331e169a82d9](../../runs/2026-07-13/20260713_164022_b864331e169a82d9/) |
| L3 | learn budget (depth-3) | eval | 2/2 | 45,912 | [20260713_164026_65300bbc808c4224](../../runs/2026-07-13/20260713_164026_65300bbc808c4224/) |
| L3 | deep (depth-4) | train | 8/8 | 644,864 | [20260713_163959_892d053eeb18c192](../../runs/2026-07-13/20260713_163959_892d053eeb18c192/) |
| L3 | deep (depth-4) | eval | 2/2 | 161,216 | [20260713_164017_645a3120870c6c2a](../../runs/2026-07-13/20260713_164017_645a3120870c6c2a/) |

L2 and L3 are identical at both budgets (learned library == hand-written target library, both by considered-count and solve-rate) — `abs0`/`abs1` are behaviorally equivalent to `rot180`/`recolor_flipped`.

## Cross-experiment: the cost-of-growing-vocabulary signal

E11's learned primitive **replaces** search depth at negligible cost (L1 590 → L2 640 considered at the shallow budget, a ~1.1x delta). E12's two learned primitives are **additive** vocabulary that every task's round-0 leaf set now carries, including tasks that don't use them — L1 183,648 → L2 644,864 at the shared learn budget (~3.5x), similarly ~2.3x at the deep budget (279,208 → 644,864). This is the first measured instance of the "growing library costs search" tradeoff flagged as an open question in E12's `EXPERIMENT_LOG.md` entry; worth watching whether it keeps compounding once **learned intermediate type** (the third queued row here) adds a third generation.

## Retrofit note

Both studies were originally run before this repo tracked `run_started_at` / timestamped run dirs (see `EXECUTION.md`'s run-data-model section) — the runs above were re-executed after that change landed, to get real timestamps rather than backfilled ones. `make check` numbers were re-verified unchanged (5/5+2/2 and 8/8+2/2) before writing this notebook.
