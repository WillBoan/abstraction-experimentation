"""The SEARCH activity: one recorded run on one corpus (EXECUTION.md).

Thin by design — ``execute`` owns the loop, scoring, and recording; this is the
activity-level entry the CLI's ``arc-lab search`` dispatches to.
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.core.dataset import Corpus

from .execute import execute
from .model.config import Config
from .model.run_record import RunRecord
from .model.run_spec import RunSpec


def run_search(config: Config, corpus: Corpus, *, runs_root: Path | None = None) -> RunRecord:
    """Execute (or serve from cache) one SEARCH recorded run.

    ``config.learn`` must be ``None`` — a learn run is a different activity
    (``run_search_learn``), and silently stripping the learn spec would execute a
    different run than the caller named.
    """
    if config.learn is not None:
        raise ValueError("run_search takes a SEARCH config (learn=None); use run_search_learn")
    return execute(RunSpec(config=config, corpus=corpus), runs_root=runs_root)
