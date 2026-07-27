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
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.ladders.certificate import (
    LadderCertificate,
    certify,
    search_censored_ids,
)
from arc_lab.program_search.ladders.spec import (
    Demonstration,
    DemonstrationKind,
    Rung,
    TopRung,
)
from arc_lab.program_search.substrate.program import Apply, Input, Program


@dataclass(frozen=True)
class _Spec:
    """Stand-in for ``LadderSpec``: ``certify`` reads only ``rungs`` and ``top``, but reads them
    STRUCTURALLY (templates and stated solutions, for the consumer graph), so those are the real
    types -- a bare ``task_id`` bag would no longer tell it who consumes whom."""

    rungs: tuple[Rung, ...]
    top: TopRung


@dataclass(frozen=True)
class _Result:
    spec: _Spec
    oracle_chain: dict[int, RunRecord]


def _call(name: str, inner: Program | None = None) -> Program:
    return Apply(primitive=name, args=(inner or Input(),))


def _rung(name: str, level: int, template: Program, *task_ids: str) -> Rung:
    """A rung whose demonstrations ARE the rung applied to the input (kind FULL_SOLUTION)."""
    return Rung(
        level=level,
        target_abstraction=TargetAbstraction(name=name, template=template),
        demonstrations=tuple(
            Demonstration(
                task_id=task_id, kind=DemonstrationKind.FULL_SOLUTION, solution=_call(name)
            )
            for task_id in task_ids
        ),
    )


#: One bridging rung: L_0 must solve `rung1a`/`rung1b`, and must NOT solve the top task `top1`
#: (that would be a skip path). Minimal shape that exercises every verdict.
_SPEC = _Spec(
    rungs=(_rung("r1", 1, _call("rot90", _call("rot90")), "rung1a", "rung1b"),),
    top=TopRung(task_ids=("top1",), reference_solutions=(_call("flip_h", _call("r1")),)),
)


#: Two INDEPENDENT branches under one top: `east` is level 2 but never calls `west`. Every
#: level-adjacent reading (`rungs[i]`, `rungs[level-2]`) names a sibling here, not a consumer.
_DAG_SPEC = _Spec(
    rungs=(
        _rung("west", 1, _call("crop_left"), "west-a", "west-b"),
        _rung("east", 2, _call("crop_right"), "east-a", "east-b"),
    ),
    top=TopRung(
        task_ids=("top1",),
        reference_solutions=(Apply(primitive="overlay", args=(_call("west"), _call("east"))),),
    ),
)


def _record(
    tmp_path: Path,
    name: str,
    rows: dict[str, tuple[bool, bool]],
    programs: dict[str, Program] | None = None,
) -> RunRecord:
    """A RunRecord whose trace says, per task id, ``(solved, censored)`` -- plus, optionally, the
    retained cheapest program (what ``demonstration_health`` reads)."""
    run_dir = tmp_path / name
    run_dir.mkdir(parents=True, exist_ok=True)
    retained = programs or {}
    lines = [
        json.dumps(
            {
                "task_id": task_id,
                "search_stats": {
                    "solved_at_generation": 1 if solved else None,
                    "censored": censored,
                },
                **({"programs": [retained[task_id].to_dict()]} if task_id in retained else {}),
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


def test_a_sibling_branch_is_not_a_consumer(tmp_path: Path) -> None:
    """The DAG fix. `east` is rung 2 but composes over the bare floor, and the only thing consuming
    either branch is the top. Read by level, `no_skip[1]` would probe `east`'s tasks (a sibling, so
    the answer says nothing about whether `west` is skippable) and `demonstration_health[2]` would
    demand `east`'s retained solution call `west` -- scoring a correct ladder 0.0."""
    cert = _certify(
        _Result(
            spec=_DAG_SPEC,
            oracle_chain={
                0: _record(
                    tmp_path,
                    "L0",
                    {"west-a": (True, False), "west-b": (True, False), "top1": (False, False)},
                ),
                1: _record(
                    tmp_path,
                    "L1",
                    {"east-a": (True, False), "east-b": (True, False), "top1": (False, False)},
                ),
                2: _record(tmp_path, "L2", {"top1": (True, False)}),
            },
        )
    )
    assert cert.tractable_jumps == {1: True, 2: True}
    assert cert.no_skip_paths == {1: True, 2: True}  # both probe the top, their actual consumer
    assert cert.demonstration_health == {1: 1.0, 2: 1.0}  # neither branch depends on the other
    assert cert.admitted


def test_health_still_demands_the_dependencies_a_rung_does_have(tmp_path: Path) -> None:
    """The other side of the same read: on a real chain, a retained solution that routes AROUND the
    rung below is still unhealthy -- the demonstration then teaches a shortcut, not the composition.
    `r2`'s template calls `r1`, so its demonstrations must be solved THROUGH `r1` at `L_1`."""
    spec = _Spec(
        rungs=(
            _rung("r1", 1, _call("rot90", _call("rot90")), "rung1a"),
            _rung("r2", 2, _call("flip_h", _call("r1")), "rung2a", "rung2b"),
        ),
        top=TopRung(task_ids=("top1",), reference_solutions=(_call("flip_v", _call("r2")),)),
    )
    cert = _certify(
        _Result(
            spec=spec,
            oracle_chain={
                0: _record(tmp_path, "L0", {"rung1a": (True, False), "rung2a": (False, False)}),
                1: _record(
                    tmp_path,
                    "L1",
                    {"rung2a": (True, False), "rung2b": (True, False), "top1": (False, False)},
                    programs={
                        "rung2a": _call("flip_h", _call("r1")),  # routes through r1
                        "rung2b": _call("transpose"),  # a floor-only shortcut
                    },
                ),
                2: _record(tmp_path, "L2", {"top1": (True, False)}),
            },
        )
    )
    assert cert.demonstration_health[2] == 0.5


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
