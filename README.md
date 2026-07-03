# arc-lab

A sandbox for experimenting with the [ARC-AGI](https://arcprize.org) benchmarks
(ARC-AGI-1 and ARC-AGI-2) — and, from there, with ML, program synthesis, and
abstraction formation more broadly.

The design principle is that **solvers are pluggable strangers behind one narrow
interface**. The harness — data model, scorer, runner, visualiser — never knows
which kind of solver it's running, so LLM solvers, DSL/program-search solvers,
neural solvers, and anything you invent next all coexist without touching it.

## Layout

```
src/arc_lab/
  core/      grid.py · task.py · dataset.py   immutable, validated domain model
  viz/       render.py                        render grids/tasks (official palette)
  eval/      scoring.py · runner.py           ARC top-2 scoring + experiment runner
  solvers/   base.py (the interface)
             baseline.py                      identity (the scoring floor)
             dsl/                             program search over grid transforms
             llm/                             Claude-backed rule induction (optional)
  cli.py                                      datasets · show · eval
data/        arc-agi-1, arc-agi-2             the datasets, as git submodules
tests/                                        unit + end-to-end tests
```

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
make setup          # init submodules + install (dev + llm extras)
# or manually:
git submodule update --init --recursive
uv sync --extra llm
```

## Quick start

```bash
uv run arc-lab datasets                 # list datasets and task counts
uv run arc-lab show 007bbfb7 --dataset arc1-train   # render a task to PNG
uv run arc-lab eval dsl --dataset arc1-eval         # score a solver
uv run arc-lab solvers                  # list registered solvers
```

The **LLM solver** needs the optional `anthropic` dependency and credentials
(`ANTHROPIC_API_KEY`, or an `ant auth login` profile):

```bash
uv sync --extra llm
uv run arc-lab eval llm --dataset arc1-eval --limit 10
```

## Datasets

| Name         | Contents                          |
|--------------|-----------------------------------|
| `arc1-train` | ARC-AGI-1 training (400 tasks)    |
| `arc1-eval`  | ARC-AGI-1 evaluation (400 tasks)  |
| `arc2-train` | ARC-AGI-2 training (1000 tasks)   |
| `arc2-eval`  | ARC-AGI-2 evaluation (120 tasks)  |

Both use the same JSON schema, so one loader handles both.

## Manual play

The ARC-AGI-1 repo ships its official testing interface, vendored here at
[`data/arc-agi-1/apps/testing_interface.html`](data/arc-agi-1/apps/testing_interface.html).
Open it in Chrome and load any task JSON from `data/` to solve it by hand.

## Adding a solver

Subclass [`Solver`](src/arc_lab/solvers/base.py), implement `predict(task)`
(return a ranked list of candidate grids per test input), and register it in
[`solvers/__init__.py`](src/arc_lab/solvers/__init__.py). The scorer, runner, and
CLI pick it up automatically.

## Development

```bash
make check          # ruff + mypy --strict + pytest
make format         # auto-fix
```
