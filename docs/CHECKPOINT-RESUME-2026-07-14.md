# Checkpoint/resume for `Budget.max_depth` · 2026-07-14

> **Design plan, not yet implemented.** Tracked as an unbuilt lever in [MACHINERY.md](../MACHINERY.md) (F1 — search). Motivated by: we're often unsure how long a SEARCH run will take before starting it, and this repo deliberately keeps wall-clock time out of `Budget`/`RunSpec` (a time cap would make the recorded, content-hashed run artifact machine-dependent — see `trace_spec.py`'s docstring). This plan gets the practical benefit ("start shallow, inspect, go deeper") a different way: by making depth itself cheaply resumable, entirely outside run identity.
>
> Related but distinct from MACHINERY.md's "Iterative deepening at the driver" row: that row is about *automatic*, *single-process* early-stop (one `run()` call internally trying increasing depths, stopping once the goal is found, sharing recursive sub-search memo entries via the existing §9 `_RunState.memo` cache). This plan is about *user-controlled*, *cross-process* warm-starting — separate CLI invocations, possibly days apart, at increasing `max_depth`, with the user inspecting `results.json` in between. The two are complementary, not overlapping: the §9 memo cache is keyed on `(scope, contexts, budget, enclosing_target)` — `budget` in the key means it does **not** let a shallower top-level frontier be reused at a different depth, which is exactly the gap this plan fills for the top-level pool.

## Context

Bottom-up search already enumerates round-by-round *by depth* (`BottomUpSearchEngine._enumerate`, `search/search_engine.py:286-349`), so "run shallow, look at results, go deeper" is a natural fit for the existing algorithm — except today, `max_depth` is content-hashed into `Config`/`RunSpec` (`model/config.py`, `model/run_spec.py:31-39`), so a `max_depth=3` run and a `max_depth=4` run are two fully independent runs, and the deeper one silently re-enumerates rounds 1–3 from scratch.

The goal: let a `max_depth=4` run warm-start from a completed `max_depth=3` run's frontier instead of recomputing it — **without** touching `RunSpec`/`run_id`/content-hash logic, so every existing invariant (regression locks, resumability, "recorded run is deterministic") stays exactly as-is. This is additive, opt-in infrastructure, not a change to what a run *is*.

## Design overview

Add a **new, separate, opt-in checkpoint cache**, independent of `runs/<run_id>/`, keyed by everything that determines `_enumerate`'s pool content **except `max_depth`** (library, search-engine config, `max_arity`/`max_pool`, cost, goal type, task content). It stores one full `Pool` snapshot per completed enumeration round per task. When a caller opts in (`warm_start=True`), the engine looks up the highest cached round ≤ `max_depth - 1` and enters enumeration there instead of round 0. A `max_depth=4` warm-started run and a cold `max_depth=4` run always find the **same solved-task-id set** — the only thing that changes is compute path, never content that regression locks or downstream tooling assert on.

This works because `_select_frontier` (`search_engine.py:744-752`, `pool.cheapest(n)` in `pool.py`) is a pure function of `(pool, budget.max_pool)` only — it never consults `max_depth` or rounds-remaining — and `Pool` is already documented as engine scratch "never hashed, never part of the run identity" (`pool.py:8`). Persisting it as a side-cache is a natural extension of that existing boundary, not a new kind of coupling.

**v1 explicitly does not warm-start nested lambda-body sub-searches** (the recursive calls from `_synthesize_for_hole` via `budget.descend()`, `search_engine.py:566-568`, `budget.py:29-31`). Every locked preset runs with `function_hole_fill_mode="none"`, so this path is dormant today; nested sub-search pools are keyed into a different, more entangled cache (`_RunState.memo`, keyed by per-hole `scope`/`contexts`), and warm-starting them correctly is a separate design problem. This is enforced structurally — only the single `top_level=True` call in `run()` (`search_engine.py:257`) receives checkpoint params; every recursive `_enumerate` call is untouched.

**Non-serializable pool entries (closures/primitives) are handled all-or-nothing per round.** A `Signature` can contain a `Closure`/`Primitive` nested inside a container-typed `Value` (e.g. `list[fn]`) — not JSON-serializable. If *any* entry in a round's `Pool` is non-serializable, that round's checkpoint write is skipped entirely (logged, not an error) and the run proceeds normally — this only forfeits a future speed-up, never risks a silent under-search from partially-dropped entries. All locked presets are unaffected (no function-hole-fill today).

## On-disk format

```
<runs_root>/_checkpoints/<cache_key>/meta.json         # plaintext key payload, for debugging
<runs_root>/_checkpoints/<cache_key>/round_<N>.json    # cumulative Pool snapshot after round N
```

- `<runs_root>` is the same parameter `execute()`/`run_search()` already accept — this means `test_locks.py`'s `tmp_path`-scoped runs automatically get an isolated checkpoint cache too, no extra plumbing needed for test cleanliness.
- `_checkpoints` is a leading-underscore sibling of the date-grouped run dirs; confirmed it won't collide with `find_run_dir`/`iter_run_dirs`'s globs (`model/run_record.py`), which only match `runspec.json`-containing or `*_{run_id}`-suffixed dirs.
- `cache_key = content_id(...)` (`core/hashing.py`) over `{schema_version, library, search_engine, max_arity, max_pool, cost, goal_type, task_id, task_train}` — deliberately omitting `max_depth` (the whole point), and also omitting `constraints`/`attempts_per_test`/`learn` (those only affect prediction/extraction, never pool-building).
- Each `round_<N>.json` is self-sufficient (not a diff), written atomically (`.tmp` + `Path.replace()`, mirroring `execute()`'s "write `results.json` last" idiom). A `schema_version` mismatch on read is treated as a clean cache miss, never a crash — the cache is gitignored/regenerable like `runs/` itself, no migration story needed.
- No TTL/cleanup in v1 — a changed key component just means a different `cache_key`; stale entries are harmless dead weight, same as `runs/`.

## Integration points

1. **Serialization layer** — `search/signature.py`: `value_to_json`/`value_from_json`/`signature_to_json`/`signature_from_json` + `ValueSerializationError` (raised on `Closure`/`Primitive`, recursed through tuples). `search/pool.py`: `PoolEntry.to_dict()`/`from_dict()`, `Pool.to_dict()`/`from_dict()`, reusing the existing `type_to_serializable`/`type_from_serializable` (`substrate/types.py`) and `Program.to_dict()`/`from_dict()` (`substrate/program.py:85-194`, already round-trip-locked by `tests/program_search/learn/test_codec_completeness.py`).
2. **`search/checkpoint.py`** (new, pure, no I/O) — a small `Checkpoint` dataclass: `initial_pool: Pool | None`, `initial_depth: int`, `on_round_complete: Callable[[int, Pool], None] | None`.
3. **`search/search_engine.py`** — `SearchEngine.run`/`BottomUpSearchEngine.run` gain `checkpoint: Checkpoint | None = None` (defaults preserve today's behavior everywhere). `_enumerate` gains `initial_pool`/`initial_depth`/`on_round_complete` params: seed `pool` from `initial_pool` when given (skip leaf-frontier rebuild), loop `for depth in range(initial_depth, budget.max_depth)`, call `on_round_complete(depth, pool)` after each `_select_frontier`. Only the `top_level=True` call site passes these through — nested `_enumerate` calls from `_synthesize_for_hole` are untouched, which is the structural enforcement of the v1 scoping decision above.
4. **`execution/checkpoint_cache.py`** (new) — `checkpoint_key(config, task, goal_type)`, `read(runs_root, key, max_round)`, `write(runs_root, key, round, pool)` (all-or-nothing, atomic, catches `ValueSerializationError` and logs+skips).
5. **`execution/execute.py`** — `execute()`/`run_search()` gain `warm_start: bool = False`. `_run_task` (the existing per-task integration point) builds a `Checkpoint` when `warm_start` is set: compute the key, `checkpoint_cache.read(...)`, wrap `checkpoint_cache.write` as `on_round_complete`. `runs_root` needs threading down to `_run_search`/`_run_task` (currently only `execute()` has it — small plumbing addition). **LEARN's `_wake` path is not wired up in v1** — its per-iteration searches don't vary `max_depth`, so there's no use case yet; the same `Checkpoint` plumbing would work unchanged if that changes later.
6. **CLI** — `src/arc_lab/cli/search.py`: add a `--warm-start` flag alongside the existing `--force-recapture`/`--profile` toggles, threaded into `run_search(...)`.

**Opt-in, not automatic**, matching the existing `force_recapture` precedent (`execute.py`): warm-starting depends on `_select_frontier`'s purity holding, which is true today but is an invariant a future change (e.g. the `stop_after_solutions` TODO already sitting in `budget.py:22`) could break — keeping it opt-in contains that risk to callers who ask for it. It also means `search_stats.considered`/`outcomes` will legitimately be smaller on a warm-started run (rounds 1–3's candidates were never (re-)considered by *this* run's tracker) — expected and disclosed, not a bug, but worth it being a deliberate choice rather than a silent change to existing dashboards.

## Regression-lock safety

`test_locks.py` only asserts solved-task-id sets (`_solved_ids`, reading `results.json`'s `score.solved`) — never `search_stats` — so warm-start's stats divergence is invisible to the locks by construction. New tests:

1. `tests/program_search/search/test_signature_codec.py` (or extend `test_pool.py`) — round-trip `Grid`/`Mask`/nested-tuple `Value`s through the new codec; verify the all-or-nothing skip when a `Closure`/`Primitive` is present; verify `schema_version` mismatch is a clean miss.
2. Engine-level equivalence test in `tests/program_search/search/test_search_engine.py` — run `_enumerate` cold to depth N on a small library/task, capture the `Pool` after round K<N via a test-only `on_round_complete` hook, feed it back as `initial_pool`/`initial_depth=K+1`, assert the resulting ranked-program set matches a fully-cold depth-N run. This is the cheapest, most direct validation of `_select_frontier` purity.
3. `tests/program_search/execution/test_checkpoint_cache.py` (new) — unit tests for `checkpoint_key`/`read`/`write`.
4. One end-to-end equivalence test (in `test_locks.py` or a sibling, `pytest.mark.slow`) — run `PRESETS["synth"]` at `max_depth=2` with `warm_start=True` against a `tmp_path` runs_root, then `max_depth=3` warm-started against the *same* runs_root, and separately `max_depth=3` cold against a fresh runs_root; assert `_solved_ids(warm) == _solved_ids(cold)`.
5. No existing lock assertions change — `Checkpoint | None = None` defaults make every current call site byte-for-byte on the old path structurally, not just by test coverage.

## Sequencing

1. Serialization layer (`signature.py`, `pool.py` codecs) + its unit tests — no engine behavior change.
2. `search/checkpoint.py` — pure dataclass, no behavior change.
3. Engine integration (`_enumerate`/`run()` params) + the engine-level equivalence test (item 2 above) — validates the core warm-start correctness claim in isolation, before any file I/O exists.
4. `execution/checkpoint_cache.py` + its unit tests.
5. `execute.py`/`run_search.py` wiring (`warm_start` param, `runs_root` threading to `_run_task`) + CLI `--warm-start` flag in `cli/search.py`.
6. End-to-end equivalence test (item 4 above) + a short doc addition to `EXECUTION.md`/wherever `TraceSpec`'s "outside run identity" rationale lives (`model/trace_spec.py:1-11`), giving the checkpoint cache the same one-paragraph treatment.

### Critical files
- `src/arc_lab/program_search/search/search_engine.py` — `_enumerate`, `run()`, checkpoint params
- `src/arc_lab/program_search/search/pool.py` — `Pool`/`PoolEntry` codec
- `src/arc_lab/program_search/search/signature.py` — `Value`/`Signature` codec
- `src/arc_lab/program_search/search/budget.py` — unchanged, referenced for context
- `src/arc_lab/program_search/execution/execute.py` — `_run_task`/`_run_search`, `warm_start` wiring
- `src/arc_lab/program_search/execution/run_search.py` — `warm_start` passthrough
- `src/arc_lab/cli/search.py` — `--warm-start` flag
- new: `src/arc_lab/program_search/search/checkpoint.py`
- new: `src/arc_lab/program_search/execution/checkpoint_cache.py`

## Verification (when implemented)

- `make check` green (ruff, mypy `--strict`, full pytest incl. new tests).
- Manually drive it: `uv run arc-lab search synth --corpus e1-rot90:train --set budget.max_depth=2 --warm-start`, inspect `results.json`, then rerun with `--set budget.max_depth=3 --warm-start` and confirm via `-vv` logging that round 3 alone was computed (not rounds 1–3) and the run completes noticeably faster than a cold `max_depth=3` run.
- Confirm `tests/program_search/execution/test_locks.py` passes unmodified (`make check` covers this; it's `slow`-marked so also worth a targeted `uv run pytest tests/program_search/execution/test_locks.py -m slow` if datasets are available locally).