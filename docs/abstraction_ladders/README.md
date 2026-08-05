# Abstraction Ladders — documentation

An Abstraction Ladder is an authored, measurable learning trajectory: a declared primitive floor, a sequence of reusable routines built above it, demonstrations from which those routines can be learned, and a harder Top task that reuses them. Start with [ABSTRACTION-LADDERS.md](ABSTRACTION-LADDERS.md).

**Naming convention.** Living documents — updated in place — carry no date. A dated document is a **snapshot**: it is superseded by writing the next one, never edited to stay current. Dates are always a suffix (`NAME-YYYY-MM-DD.md`). Completed plans and superseded snapshots move to [`../archive/abstraction_ladders/`](../archive/abstraction_ladders/).

**Where state lives (2026-08-03).** There are exactly two sources of truth about a Ladder, and both are machine-anchored:

- **What it is and why** — its `.ladder` file ([registry/](../../src/arc_lab/program_search/ladders/registry/)), including the finding when it was rejected.
- **What happened when it ran** — [BATCH-OF-RECORD.md](BATCH-OF-RECORD.md), generated from the runs.

The hand-maintained register (`LADDERS.md`), its worksheet template, and the six surviving worksheets were **deleted** on 2026-08-03: every fact in them was already in one of the two above, in `README.md`'s synthesis, in `EXPERIMENTS.md`'s event log, or executable in `ladders/batch.py` — while the worksheet discipline the register mandated was being honoured by 6 of 32 folders. A doc nobody reconciles is a doc that misinforms.

## Start here

| Doc | What it is |
| --- | --- |
| [ABSTRACTION-LADDERS.md](ABSTRACTION-LADDERS.md) | **The explainer.** What a Ladder is and why the object is worth having — the short read. |
| [ABSTRACTION-LADDERS-SPEC.md](ABSTRACTION-LADDERS-SPEC.md) | **The canonical spec.** Normative for concepts, terms, quantities and metrics; the detailed original design. Cite this for definitions. |

## Normative specs

| Doc | What it is |
| --- | --- |
| [LADDER-FORMAT.md](LADDER-FORMAT.md) | The `.ladder` file format — the declarative source a Ladder is authored in, and the single source of truth for a Ladder's identity. |
| [LINT-CHECKS.md](LINT-CHECKS.md) | Every static check a `.ladder` file is held to, in run order. **Generated** from `checks/plan.py` (`arc-lab lint-checks`); a test pins it. Never hand-edit. |

## Process and state

| Doc | What it is |
| --- | --- |
| [AL-PLAN-2026-08-04.md](AL-PLAN-2026-08-04.md) | **The active plan of record** — premises, parking decisions, the RQ portfolio, and the phased program that follows the completed MVE lineage. Consult before starting multi-step experimental work; supersede by writing the next one. |
| [LADDER-PROCESS.md](LADDER-PROCESS.md) | How to build a Ladder: order, judgement, and what each instrument can and cannot prove. The part machinery cannot enforce. |
| [BATCH-OF-RECORD.md](BATCH-OF-RECORD.md) | **The register, and it is generated** (`arc-lab run-batch`; never hand-edit). Every Ladder ever run in ONE pass: per-member verdict, rung recovery, top reachability, compromises — plus what the set **samples** on each axis, which cohorts license which comparisons, and the coherence checks. Read it before quoting any number, and before any cross-member comparison. |
| [ladders/](ladders/) | Per-Ladder committed artifacts: `spec.md` + `report.json`, both generated. (`results.md` is `report.json` rendered, so it is generated on demand and not committed.) |

## Concept snapshots (dated)

Each records a design discussion on the date it names. Still cited by the living docs; superseded only by writing a successor.

| Doc | What it settled |
| --- | --- |
| [LADDER-RELATIONSHIPS-2026-07-23.md](LADDER-RELATIONSHIPS-2026-07-23.md) | How two Ladders relate (cohorts, sub-cohorts) and what comparison each relationship licenses. |
| [BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md) | The two cost axes — depth vs. vocabulary breadth — and why the formalism instruments only one. |
| [CERTIFICATE-PROFILE-2026-07-24.md](CERTIFICATE-PROFILE-2026-07-24.md) | The certificate is a per-rung verdict profile, not a single pass/fail sandwich gate. |
| [LADDER-SET-DESIGN-2026-07-24.md](LADDER-SET-DESIGN-2026-07-24.md) | How a set of Ladders is structured: tasks, cohorts, sub-cohorts, spines. |

## Elsewhere

- **Findings** — [EXPERIMENTS.md](../../EXPERIMENTS.md) (the event log) and [experiments/](../../experiments/) (notebooks and raw outputs).
- **Completed plans and superseded snapshots** — [`../archive/abstraction_ladders/`](../archive/abstraction_ladders/), including the plan lineage that produced the results in [README.md](../../README.md): `AL-PLAN-2026-07-23` → `LADDER-SET-PLAN-2026-07-24` → `MVE-PLAN-2026-07-25`.
- **Running it** — [DEVELOPMENT.md](../DEVELOPMENT.md); the implementation is `src/arc_lab/program_search/ladders/`.
