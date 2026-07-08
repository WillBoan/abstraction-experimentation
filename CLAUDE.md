# CLAUDE.md

Operational guide for agents working in this repo. Human-facing overview is in [README.md](README.md); this file is the agent contract — conventions, gotchas, and recipes. Keep it lean and pointer-heavy (it loads every session).

## What this is

`arc-lab`: a sandbox for the ARC-AGI benchmarks and, more broadly, ML / program-synthesis / abstraction-formation experimentation. The load-bearing design decision: **solvers are pluggable strangers behind one narrow interface** (`Solver.predict` in `src/arc_lab/solvers/base.py`). The harness (core / eval / viz) never knows which solver it runs.

## The one command that matters

```
make check      # ruff + mypy --strict + pytest — the gate
make format     # auto-fix ruff lint + format
```

`uv` runs everything (`uv run …`); deps live in `pyproject.toml`. Never invoke `python`/`pytest` bare.

## Definition of done

1. `make check` is green (ruff clean, mypy `--strict` clean, all tests pass).
2. **Regression locks preserved.** `dsl`=7, `dsl-sym`=19, `dsl-synth`=11 solved on `arc1-train` — pinned as exact task-id sets in `tests/test_integration.py`. A behavior-preserving change must not move these; a feature that changes them updates the lock deliberately.
3. For changes with runtime behavior, actually drive it: `uv run arc-lab eval <solver> --dataset arc1-train`.

## Experiment log

When you run a meaningful experiment or reach a finding — **including dead ends** — append a terse, commit-anchored entry to [EXPERIMENTS.md](EXPERIMENTS.md). It's the shared human+AI record of what's been tried and what it meant. It's an *event log, not a state mirror* — read its header for the discipline before adding to it. Planned experiments queue in [EXPERIMENT_QUEUE.md](EXPERIMENT_QUEUE.md) (drain-only; see its header) — when you log a run, delete its queue entry.

For a **non-trivial investigation**, also keep a detailed lab notebook under [experiments/](experiments/) — the full write-up + the throwaway probe scripts and their outputs, which EXPERIMENTS.md (the curated abstract) points to. See [experiments/README.md](experiments/README.md); it's a catch-basin to *capture* the thinking, **not** to constrain how you explore — save probes into the folder as you go, write up the notebook when it's natural.

## Mental model

A solver is **`(library × search × constraints × cost)`**. Search is a **propose → filter → rank** pipeline:
- **library** — the typed vocabulary of `Primitive`s (`solvers/dsl/substrate/`).
- **search** — proposes candidate programs (`solvers/dsl/search/`).
- **constraints** — the filter; `ConsistentWithTraining` is the spec (`search/constraints.py`).
- **cost** — the rank; `ProgramSize` is the Occam prior (`search/cost.py`).

Programs are **data**: a `Program` ABC with virtual-dispatch nodes `Input | Param | Const | Apply` (`substrate/program.py`); `Param` is the hole that makes learned abstractions possible (`substrate/abstraction.py`).

**Library learning** (`solvers/dsl/learn/`) is a meta-process over solvers, not a solver: wake (solve the corpus) → sleep (antiunify proposals → greedy-MDL governance) → `Library.extended` → repeat. Targets in experiments are **observables** (behavioral checker), never a training signal. `analysis/` is the instrument: content-hashed run artifacts + MDL compression metrics.

Layers: `core/` (grid·task·dataset) · `viz/` · `eval/` (scoring·runner) · `solvers/` (`base.py`, `dsl/`, `llm/`); inside `dsl/`: `substrate/` · `search/` · `analysis/` · `learn/`.

## Key commands

```
uv run arc-lab datasets | solvers | show <id> --dataset <ds> | eval <solver> --dataset <ds>
uv run arc-lab analyze <solver> --dataset <ds>   # run artifact: per-task programs + search effort + DL (cached under runs/)
uv run arc-lab learn <experiment>                # abstraction-formation experiment (names: learn/experiments.py)
uv run arc-lab runs                              # list recorded run artifacts
uv run arc-lab -vv eval <solver> ...     # -v INFO / -vv DEBUG search trace (stderr, silent by default)
ARC_LAB_LOG=DEBUG uv run pytest -k <x>   # same trace under pytest
```

## Conventions & gotchas

- **mypy** `python_version = "3.12"` is intentional — only so numpy 2.5's PEP-695 stubs parse; the runtime targets 3.11+. Keep `--strict` clean.
- **ruff** `E203` on numpy slices is `noqa`'d for ruff-format compatibility — don't "fix" it.
- **Datasets are git submodules** under `data/`; integration tests skip cleanly if absent (`git submodule update --init --recursive`).
- **Immutable & deterministic:** `Grid` and programs are frozen; solvers use no RNG — behavior is reproducible, which is what makes the locks meaningful.
- **Logging** is silent by default; use `%s` lazy args and guard hot paths with `if debug:` (`logger.isEnabledFor`).
- **Don't commit or push unless asked.** Throwaway analysis scripts go in the session scratchpad, not the repo.
- `_notes/` is the user's private notes — off-limits (denied in `.claude/settings.json`).

## Recipes

- **Add a primitive** → define a typed `Primitive` in `solvers/dsl/substrate/primitives/*.py`; bundle it into a `Library` (see `solver.py` for `D4_LIBRARY.extended(...)`).
- **Add a search strategy** → subclass `Search` (`search/base.py`); export in `search/__init__.py`.
- **Add a solver** → subclass `ProgramSearchSolver` (or `Solver`); register it in `solvers/__init__.py` `REGISTRY`.
- **Add a constraint / cost** → `search/constraints.py` / `search/cost.py`.
- **Add a learn experiment** → generate tasks via `learn/taskgen.py`, define + register it in `learn/experiments.py` (`make_experiment`); drive with `uv run arc-lab learn <name>`. Testbeds are committed under `testbeds/`; run artifacts are a gitignored cache under `runs/`.

## Sources of truth (don't duplicate — point here)

- Solver registry: `src/arc_lab/solvers/__init__.py`
- Learn-experiment registry: `src/arc_lab/solvers/dsl/learn/experiments.py`
- Behavior locks: `tests/test_integration.py`
- Commands: `Makefile`
- Experiment history & findings: `EXPERIMENTS.md`
- Planned experiments: `EXPERIMENT_QUEUE.md`
- Lever maps (primitives / machinery): `ONTOLOGY.md` / `MACHINERY.md`
- Research frame (dated snapshot the maps are read against): `RESEARCH-2026-07-07.md` (supersedes `RESEARCH-2026-07-06.md`)
- Machinery build strategy (build vs. adopt vs. defer; dated): `MACHINERY-STRATEGY-2026-07-07.md`
