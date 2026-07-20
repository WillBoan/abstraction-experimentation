"""The Ladder certificate's verdicts -- above all, that a censored probe is never read as a pass.

``tractable_jumps`` and ``no_skip_paths`` are both derived from *unsolved* sets, and a search cut
short by ``Budget.considered_limit`` is unsolved too. That coincidence is the hazard these tests
exist for: untreated, it converts "we ran out of budget" into a skip-path PASS and admits a ladder
whose skip path the search merely never reached.

Fast unit tests over synthesized trace files (``test_run.py`` owns the slow end-to-end lock).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders.certificate import (
    LadderCertificate,
    certify,
    search_censored_ids,
)


@dataclass(frozen=True)
class _Demo:
    task_id: str


@dataclass(frozen=True)
class _Rung:
    name: str
    demonstrations: tuple[_Demo, ...]


@dataclass(frozen=True)
class _Top:
    task_ids: tuple[str, ...]


@dataclass(frozen=True)
class _Spec:
    rungs: tuple[_Rung, ...]
    top: _Top


@dataclass(frozen=True)
class _Result:
    spec: _Spec
    oracle_chain: dict[int, RunRecord]


#: One bridging rung: L_0 must solve `rung1a`/`rung1b`, and must NOT solve the top task `top1`
#: (that would be a skip path). Minimal shape that exercises every verdict.
_SPEC = _Spec(
    rungs=(_Rung(name="r1", demonstrations=(_Demo("rung1a"), _Demo("rung1b"))),),
    top=_Top(task_ids=("top1",)),
)


def _record(tmp_path: Path, name: str, rows: dict[str, tuple[bool, bool]]) -> RunRecord:
    """A RunRecord whose trace says, per task id, ``(solved, censored)``."""
    run_dir = tmp_path / name
    run_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "task_id": task_id,
                "search_stats": {
                    "solved_at_generation": 1 if solved else None,
                    "censored": censored,
                },
            }
        )
        for task_id, (solved, censored) in rows.items()
    ]
    (run_dir / "trace.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return RunRecord(run_id=name, run_dir=run_dir)


def _certify(result: _Result) -> LadderCertificate:
    """``certify`` reads only ``spec.rungs``/``spec.top`` and ``oracle_chain``, so the stand-in
    above satisfies it structurally. The cast is confined here rather than repeated per call."""
    return certify(cast(Any, result))


def test_a_clean_chain_is_admitted(tmp_path: Path) -> None:
    cert = _certify(
        _Result(
            spec=_SPEC,
            oracle_chain={
                0: _record(
                    tmp_path,
                    "L0",
                    {
                        "rung1a": (True, False),
                        "rung1b": (True, False),
                        "top1": (False, False),  # searched to completion, no skip path
                    },
                ),
                1: _record(tmp_path, "L1", {"top1": (True, False)}),
            },
        )
    )
    assert cert.tractable_jumps == {1: True}
    assert cert.no_skip_paths == {1: True}
    assert cert.admitted


def test_a_censored_top_probe_is_inconclusive_not_a_pass(tmp_path: Path) -> None:
    """THE hazard. ``top1`` is unsolved under L_0 -- but only because the search was cut short, so
    whether a skip path exists was never established. Reporting ``True`` here would admit the
    ladder on the strength of a search that never ran."""
    cert = _certify(
        _Result(
            spec=_SPEC,
            oracle_chain={
                0: _record(
                    tmp_path,
                    "L0",
                    {
                        "rung1a": (True, False),
                        "rung1b": (True, False),
                        "top1": (False, True),  # unsolved AND censored
                    },
                ),
                1: _record(tmp_path, "L1", {"top1": (True, False)}),
            },
        )
    )
    assert cert.no_skip_paths == {1: None}  # not True
    assert not cert.admitted  # and `None` fails the gate exactly as `False` would


def test_a_real_skip_path_is_still_reported_when_the_probe_was_censored(tmp_path: Path) -> None:
    """Censoring can only ever weaken a negative, never overturn a positive: if the floor SOLVED
    the top task, that is a skip path regardless of the search having been cut short afterwards."""
    cert = _certify(
        _Result(
            spec=_SPEC,
            oracle_chain={
                0: _record(
                    tmp_path,
                    "L0",
                    {
                        "rung1a": (True, False),
                        "rung1b": (True, False),
                        "top1": (True, True),  # solved, and censored after the fact
                    },
                ),
                1: _record(tmp_path, "L1", {"top1": (True, False)}),
            },
        )
    )
    assert cert.no_skip_paths == {1: False}  # a defect, not softened to inconclusive
    assert not cert.admitted


def test_a_censored_demonstration_is_not_a_tractable_jump(tmp_path: Path) -> None:
    """We never showed ``L_0`` can solve ``rung1b`` -- we stopped paying. Not tractable."""
    cert = _certify(
        _Result(
            spec=_SPEC,
            oracle_chain={
                0: _record(
                    tmp_path,
                    "L0",
                    {
                        "rung1a": (True, False),
                        "rung1b": (False, True),
                        "top1": (False, False),
                    },
                ),
                1: _record(tmp_path, "L1", {"top1": (True, False)}),
            },
        )
    )
    assert cert.tractable_jumps == {1: False}
    assert not cert.admitted


def test_stopped_early_is_not_censored(tmp_path: Path) -> None:
    """``solution_limit`` runs succeeded and merely stopped paying, so their verdicts are sound and
    must NOT be downgraded to inconclusive -- only ``censored`` means the search was cut short."""
    run_dir = tmp_path / "early"
    run_dir.mkdir()
    (run_dir / "trace.jsonl").write_text(
        json.dumps(
            {
                "task_id": "t",
                "search_stats": {
                    "solved_at_generation": 1,
                    "censored": False,
                    "stopped_early": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert search_censored_ids(RunRecord(run_id="early", run_dir=run_dir)) == set()
