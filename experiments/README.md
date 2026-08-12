# experiments/ — lab notebooks

A home for the **detailed record of an investigation**: the thinking, the data, and the throwaway code that get produced while running experiments — and currently evaporate. [EXPERIMENT_LOG.md](../EXPERIMENT_LOG.md) is the terse chronological record; [EXPERIMENTS.md](../EXPERIMENTS.md) is the rigor-reviewed current synthesis. A folder here is the full write-up and data appendix they can point to.

## The point (read this first)

This exists to **capture** what's otherwise lost — not to **govern** how you experiment. The research is the exploration; a logging ritual that turns exploration into form-filling would be a bug, not a feature. So:

- **Experiment however the problem demands.** This folder is a catch-basin for what that produces.
- Everything below is a **default to reduce friction, not a process to follow.** Use what helps; ignore, reorder, or replace what doesn't. A small investigation gets a small folder.
- If the structure ever starts steering the exploration, the structure is wrong.

## When

Make a folder when an investigation turns **non-trivial** — there's tuning, probing, comparing, or a decision trail worth keeping. A one-line experiment doesn't need one; it is fine to log it straight to `EXPERIMENT_LOG.md`.

## Investigation vs. experiment

A folder here is an **investigation**: the higher-level question or research thread. It can hold **one experiment or several** — grouping multiple experiments in one folder is exactly what makes cross-experiment comparison easy (shared setup, one notebook synthesizing across them). An **experiment** is what gets an **E-number** (minted in `EXPERIMENT_LOG.md` when it runs); a folder isn't required to enumerate every E-number it contains in its own name (see naming below) — the notebook is the authoritative index of which experiments live here.

## What a folder usually holds

```
experiments/<YYYY-MM-DD>-<short-name>/
  notebook.md      # the anchor: goal, what you ran & found, decisions, dead-ends,
                    # and — per experiment — the list of its runs, linked to runs/
  artifacts/       # any code/scripts/data produced, with their outputs
```

- **Naming:** date-first (sorts chronologically, parallels `EXPERIMENT_LOG.md`'s dated entries), then a short thematic name. Including the E-number(s) is fine for a tight **contrast pair** sharing one folder (e.g. `2026-07-07-e8-e9-mirror-index-bootstrap/`) — but don't force every E-number an investigation later accumulates into the dirname; an open-ended investigation (three, four, more experiments over time) just gets a thematic name, and `notebook.md` carries the E-number ↔ run mapping.
- **`artifacts/`** holds **anything the investigation produced worth reproducing** — probe scripts (`.py`, `.sh`, …), their outputs, comparison tables, CSVs, charts, whatever came up — not just code. Pair a script with its output by **matched basename** (`beam_sweep.py` + `beam_sweep.out`, captured with `… 2>&1 | tee artifacts/beam_sweep.out`). It's optional: a tiny investigation might be just a `notebook.md` with an inline snippet.
- **`notebook.md` is a prompt, not a form.** Things often worth capturing — the goal/question, the setup, a running log of _what you ran and what it showed_ (dead-ends included), the findings and metrics, and the decisions and open questions — but shape it however the investigation calls for. Link out to the `artifacts/` and back to the `EXPERIMENT_LOG.md` entry; do not duplicate the log entry. For each experiment in the investigation, also list its **runs** — one line per run naming what it was (budget, corpus, library) and a relative link to its `runs/<started_at>_<run_id>/` dir — so a reader can jump straight from the write-up to the actual recorded artifacts (`runspec.json` / `results.json` / `trace.jsonl`).

## How it interacts with the rest

- **`runs/` (gitignored cache) vs. `experiments/` (committed record).** Structured, voluminous output the _experiment runner_ generates (`analyze`/`run_experiment` — per-task programs, search effort, DL) lives in `runs/` and does **not** get copied here. What lands here is the **ad-hoc** stuff _you_ make while investigating (a bespoke beam sweep, a cross-run comparison) — usually small, and the interesting bit _is_ the data, so keep it verbatim.
- **`EXPERIMENT_LOG.md`** stays the terse chronological event log and gains a one-line pointer to the folder. **`EXPERIMENTS.md`** changes only when the reviewed interpretation changes.

## Rhythm (so it doesn't cost flow)

- **Artifacts accrete as you go** — the only change from a throwaway probe is the _destination_ (`artifacts/` instead of the scratchpad), so nothing is lost even if a session ends abruptly.
- **The notebook is written when it's natural** — jot a one-liner per probe if it's cheap; write the real synthesis (findings, decisions) at the end. Never interrupt a hot thread to document.
- **A light cleanup at the end** — drop pure noise (a typo'd probe you immediately rewrote); keep anything informative, including dead-ends (they're part of the record).
