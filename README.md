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
             dsl/                             program search: substrate · search ·
                                              analysis (run artifacts, MDL metrics) ·
                                              learn (abstraction-learning loop)
             llm/                             Claude-backed rule induction (optional)
  cli.py                                      datasets · show · eval · analyze · learn · runs
data/        arc-agi-1, arc-agi-2             the datasets, as git submodules
testbeds/    committed synthetic task sets for the learn experiments
runs/        run artifacts — a gitignored, regenerable cache
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
uv run arc-lab analyze dsl-synth --dataset arc1-train   # run artifact: programs + metrics
uv run arc-lab learn e1-rot90           # run an abstraction-formation experiment
uv run arc-lab runs                     # list recorded run artifacts
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

## Extending

Solvers are pluggable: subclass [`Solver`](src/arc_lab/solvers/base.py) and
register it in [`solvers/__init__.py`](src/arc_lab/solvers/__init__.py) — the
scorer, runner, and CLI pick it up automatically. Recipes for adding
primitives, searches, constraints/costs, and learn experiments live in
[CLAUDE.md](CLAUDE.md).

## Documentation

Details live in the canonical files, not here:

| File | What it holds |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | working conventions: commands, definition of done, mental model, recipes |
| [EXPERIMENTS.md](EXPERIMENTS.md) | the experiment event log — findings, including dead ends |
| [EXPERIMENT_QUEUE.md](EXPERIMENT_QUEUE.md) | planned experiments (drain-only queue) |
| [ONTOLOGY.md](ONTOLOGY.md) | map of the primitive / abstraction space (the vocabulary lever) |
| [MACHINERY.md](MACHINERY.md) | map of the search / scoring / learning mechanisms (the machinery lever) |
| [RESEARCH-2026-07-07.md](RESEARCH-2026-07-07.md) | the research frame — a dated snapshot the maps are read against (supersedes 2026-07-06) |
| [MACHINERY-STRATEGY-2026-07-07.md](MACHINERY-STRATEGY-2026-07-07.md) | build strategy — how we decide what machinery to build, adopt, or defer (dated) |

## Development

```bash
make check          # ruff + mypy --strict + pytest
make format         # auto-fix
```
