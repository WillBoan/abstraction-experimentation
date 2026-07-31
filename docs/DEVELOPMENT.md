# Running arc-lab

The operational front door: setup, the commands, the layout, and where each doc lives. What the project is _studying_, and what it has found, is the landing page — [README.md](../README.md).

A sandbox for experimenting with the [ARC-AGI](https://arcprize.org) benchmarks (ARC-AGI-1 and ARC-AGI-2) — and, from there, with ML, program synthesis, and abstraction formation more broadly.

The load-bearing idea: **machinery is data**. There are no solver classes — a run is a frozen, content-hashed `RunSpec = Config × Corpus`, where `Config` is the machinery itself (`library × search_engine × budget × constraints × cost × attempts_per_test × learn?`) expressed as data. The execution layer drives it directly: every run gets a `run_id` that is a pure function of its spec, is executed exactly once, and lands in `runs/` — a gitignored, regenerable cache — crash-safe and resumable. Rerunning anything already computed is free.

On top of search sits **wake–sleep library learning**: wake = program search over a corpus; sleep = a learn engine compressing the found solutions into new library abstractions under MDL governance. Studies then grid learned vs. hand-written vs. target libraries across budgets and corpora to measure enablement, search-effort speedup, and transfer.

The activity/run model (RunSpec · activities · `runs/` layout) is [EXECUTION.md](EXECUTION.md); the search-engine and substrate design is [ARCHITECTURE.md](ARCHITECTURE.md).

## Layout

```
src/arc_lab/
  core/                grid · task · annotation · dataset (Corpus) · hashing
  eval/                ARC scoring rules (top-2), paradigm-neutral
  program_search/
    substrate/         the language: types · programs · library · primitives
    search/            typed bottom-up search engine + constraints · cost · budget
    learn/             sleep: learn engines · proposers (antiunify · Stitch) · MDL
    analysis/          read-side metrics (compression, MDL, effort)
    execution/         RunSpec/Config model · execute() · activities · presets · studies
    ladders/           Abstraction Ladders: `.ladder` language · lint checks · probe · certificate
  taskgen/             synthetic-corpus generators (writes testbeds/)
  cli/                 thin: arg-parse + dispatch only
  viz/                 render grids/tasks (official palette)
data/                  arc-agi-1, arc-agi-2 — the datasets, as git submodules
testbeds/              committed synthetic task sets for the learn experiments
runs/                  run artifacts — a gitignored, regenerable cache
experiments/           lab notebooks for non-trivial investigations
docs/                  run model · architecture · lever maps · Ladder docs (+ archive/)
editors/               VS Code extension + language server for `.ladder` files
tests/                 fast functionality tests + slow regression locks
```

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
make setup          # init submodules + install
# or manually:
git submodule update --init --recursive
uv sync
```

Everything runs through `uv` (`uv run …`); never invoke `python`/`pytest` bare.

```bash
make test           # fast tests — the dev inner loop (~seconds)
make check          # ruff + mypy --strict + FULL suite incl. slow locks — the gate
make format         # auto-fix lint + formatting
```

## Quick start

```bash
uv run arc-lab search d4 --corpus arc1-train        # one SEARCH recorded run (cached)
uv run arc-lab learn synth --corpus e1-rot90:train --eval-corpus e1-rot90:heldout
                                                    # wake-sleep loop: 2-3 recorded runs
uv run arc-lab run-study e1-rot90                   # study grid + report (cache hits free)
uv run arc-lab analyze-run <run_id>                 # read-only metrics over a completed run
uv run arc-lab taskgen e1-rot90                     # (re)generate a committed testbed
```

Utilities:

```bash
uv run arc-lab configs                              # list machinery presets
uv run arc-lab datasets                             # list datasets and task counts
uv run arc-lab runs                                 # list recorded runs
uv run arc-lab show 007bbfb7 --dataset arc1-train   # render a task to PNG
uv run arc-lab estimate d4 --corpus arc1-train      # worst-case search-cost ceiling, no execution
uv run arc-lab -vv search ...                       # -v INFO / -vv DEBUG trace on stderr
```

**Presets** are named `Config`s in `execution/presets.py` — four ARC-benchmark machineries (`d4` · `sym` · `synth` · `beam`) and three floor-grain contrast floors (`geom` · `universal-floor` · `minimal-complete-floor`). `arc-lab configs` lists them. A `--corpus` is a dataset (`arc1-train`), a testbed (`e1-rot90`), or a testbed split (`e1-rot90:train` / `:heldout`).

**Overrides:** any `Config` field is settable by dotted path — `--set budget.depth_limit=3` — and the `<config>` argument may also be a JSON file `{"preset": ..., "set": {...}}`. Precedence: `defaults < preset < config file < --set`. Every override mints its own `run_id`, so the cache never collides.

## Abstraction Ladders

An **Abstraction Ladder** makes one authored learning trajectory explicit and testable: a declared primitive floor, a sequence of intermediate routines the loop has to learn on the way up, and a held-out Top task. Each Ladder is a single `.ladder` file in [`ladders/registry/`](../src/arc_lab/program_search/ladders/registry) — that file is the whole thing (spec, tasks, config), and the directory is scanned, so there is nothing to register. [ABSTRACTION-LADDERS.md](abstraction_ladders/ABSTRACTION-LADDERS.md) is the concept; [LADDERS.md](abstraction_ladders/LADDERS.md) carries every Ladder's verdict and why.

The authoring loop runs cheapest gate first:

```bash
uv run arc-lab new-ladder <name>          # draft a .ladder file (refuses to overwrite)
uv run arc-lab ladder-seeds --variant 3   # paste-ready input grids
uv run arc-lab lint-ladder <name>         # static checks, ~1s, no search — works before the testbed exists
uv run arc-lab probe-ladder <name>        # drives the REAL engine per rung: catches collapses and skip paths
uv run arc-lab taskgen <name>             # commit the testbed
uv run arc-lab run-ladder <name>          # the full climb + oracle chain + certificate
```

**The probe convicts; only the certificate acquits.** A collapse or skip path the probe finds is a real defect, but an `INCONCLUSIVE` cell is a non-result by design — raising `--guard` buys a longer search, never a verdict.

`.ladder` files get syntax highlighting and live diagnostics from the bundled language server (`arc-lab lsp`) and the VS Code extension in [`editors/vscode-ladder/`](../editors/vscode-ladder).

## Datasets

| Name         | Contents                         |
| ------------ | -------------------------------- |
| `arc1-train` | ARC-AGI-1 training (400 tasks)   |
| `arc1-eval`  | ARC-AGI-1 evaluation (400 tasks) |
| `arc2-train` | ARC-AGI-2 training (1000 tasks)  |
| `arc2-eval`  | ARC-AGI-2 evaluation (120 tasks) |

Both use the same JSON schema, so one loader handles both.

## Manual play

The ARC-AGI-1 repo ships its official testing interface, vendored here at [`data/arc-agi-1/apps/testing_interface.html`](../data/arc-agi-1/apps/testing_interface.html). Open it in Chrome and load any task JSON from `data/` to solve it by hand.

## Extending

Recipes — add a primitive, a search engine, a machinery preset, a constraint or cost, a learn engine, a study, a ladder, a CLI command — live in [CLAUDE.md](../CLAUDE.md#recipes), the working contract for this repo.

## Documentation

Details live in the canonical files, not here:

| File | What it holds |
| --- | --- |
| [README.md](../README.md) | what the project studies and what it has found — the report |
| [CLAUDE.md](../CLAUDE.md) | working conventions: commands, definition of done, mental model, recipes |
| [EXECUTION.md](EXECUTION.md) | the activity / run model: RunSpec · Config · activities · `runs/` layout · CLI |
| [ARCHITECTURE.md](ARCHITECTURE.md) | search-engine & substrate design (types, enumeration, deliberate limits) |
| [abstraction_ladders/](abstraction_ladders/) | Abstraction Ladders: the concept, the register, the `.ladder` format spec, the generated lint-check register, and the plans |
| [ONTOLOGY.md](ONTOLOGY.md) | map of the primitive / abstraction space (the vocabulary lever) |
| [MACHINERY.md](MACHINERY.md) | map of the search / scoring / learning mechanisms (the machinery lever) |
| [SEARCH-SPACE.md](SEARCH-SPACE.md) | map of the search-space-control levers |
| [EXPERIMENTS.md](../EXPERIMENTS.md) | the experiment event log — findings, including dead ends |
| [experiments/](../experiments/) | lab notebooks: full write-ups, probe scripts, and their raw outputs |
| [EXPERIMENT_QUEUE.md](EXPERIMENT_QUEUE.md) | planned experiments (drain-only backlog) |
| [archive/RESEARCH-2026-07-08.md](archive/RESEARCH-2026-07-08.md) | the research frame — the dated snapshot the maps are read against |
| [archive/MACHINERY-STRATEGY-2026-07-07.md](archive/MACHINERY-STRATEGY-2026-07-07.md) | build strategy — what machinery to build, adopt, or defer (dated) |
| [archive/CONFIG-DEFAULTS-2026-07-11.md](archive/CONFIG-DEFAULTS-2026-07-11.md) | config/param defaults review — every param's options, cost, and rationale (dated) |

Superseded dated snapshots live in [archive/](archive/).
