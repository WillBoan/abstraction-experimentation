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

When you run a meaningful experiment or reach a finding — **including dead ends** — append a terse, commit-anchored entry to [EXPERIMENTS.md](EXPERIMENTS.md). It's the shared human+AI record of what's been tried and what it meant. It's an *event log, not a state mirror* — read its header for the discipline before adding to it.

## Mental model

A solver is **`(library × search × constraints × cost)`**. Search is a **propose → filter → rank** pipeline:
- **library** — the typed vocabulary of `Primitive`s (`solvers/dsl/substrate/`).
- **search** — proposes candidate programs (`solvers/dsl/search/`).
- **constraints** — the filter; `ConsistentWithTraining` is the spec (`search/constraints.py`).
- **cost** — the rank; `ProgramSize` is the Occam prior (`search/cost.py`).

Programs are **data**: a `Program` ABC with virtual-dispatch nodes `Input | Const | Apply` (`substrate/program.py`). Layers: `core/` (grid·task·dataset) · `viz/` · `eval/` (scoring·runner) · `solvers/` (`base.py`, `dsl/`, `llm/`).

## Key commands

```
uv run arc-lab datasets | solvers | show <id> --dataset <ds> | eval <solver> --dataset <ds>
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

## Sources of truth (don't duplicate — point here)

- Solver registry: `src/arc_lab/solvers/__init__.py`
- Behavior locks: `tests/test_integration.py`
- Commands: `Makefile`
- Experiment history & findings: `EXPERIMENTS.md`