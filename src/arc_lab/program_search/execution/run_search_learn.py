"""The SEARCH + LEARN activity: one learn run + its derived SEARCH runs (EXECUTION.md).

The learn run (the wake-sleep loop) is ONE recorded run on the **train corpus**; its
artifact is the grown library. The **final evaluation** is then plain SEARCH recorded
runs with that library — the final wake — one per provided corpus:

- x train corpus  -> **train-usefulness**
- x eval corpus   -> **transfer** (only if provided; the loop never touches it)

The derived runs are constructed *after* the learn run completes (the grown library's
content hash cannot be known earlier); being ordinary recorded runs, a study's grid
reuses them from cache by ``run_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arc_lab.core.dataset import Corpus

from .execute import execute
from .model.config import Config
from .model.run_record import RunRecord
from .model.run_spec import RunSpec
from .model.trace_spec import TraceSpec


@dataclass(frozen=True, slots=True)
class LearnActivityResult:
    """The 2-3 recorded runs a SEARCH + LEARN activity produces."""

    learn: RunRecord
    train_usefulness: RunRecord
    transfer: RunRecord | None = None


def run_search_learn(
    config: Config,
    train_corpus: Corpus,
    eval_corpus: Corpus | None = None,
    *,
    runs_root: Path | None = None,
    trace: TraceSpec | None = None,
    force_recapture: bool = False,
) -> LearnActivityResult:
    """Execute the learn run, then the derived SEARCH runs with the grown library.

    ``trace``/``force_recapture`` apply uniformly to all 2-3 recorded runs (outside run
    identity — see ``TraceSpec``'s docstring): tracing the loop usually means tracing what it
    produced too.
    """
    if config.learn is None:
        raise ValueError("run_search_learn takes a LEARN config (learn set); use run_search")

    learn_record = execute(
        RunSpec(config=config, corpus=train_corpus),
        runs_root=runs_root,
        trace=trace,
        force_recapture=force_recapture,
    )
    grown = learn_record.learned_library()

    derived = config.with_(library=grown, learn=None)  # provenance is not identity
    train_record = execute(
        RunSpec(config=derived, corpus=train_corpus),
        runs_root=runs_root,
        trace=trace,
        force_recapture=force_recapture,
    )
    eval_record = (
        execute(
            RunSpec(config=derived, corpus=eval_corpus),
            runs_root=runs_root,
            trace=trace,
            force_recapture=force_recapture,
        )
        if eval_corpus is not None
        else None
    )
    return LearnActivityResult(
        learn=learn_record, train_usefulness=train_record, transfer=eval_record
    )
