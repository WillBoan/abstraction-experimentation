"""Tests for the code-level search logging (format_program + trace log sites).

The trace is silent by default and only surfaces when the ``arc_lab.solvers.dsl``
logger is lowered to DEBUG/INFO — these tests use ``caplog`` to assert both the
content of the trace and the quiet-by-default contract.
"""

from __future__ import annotations

import logging

import pytest

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search import Enumerate, SingleApply
from arc_lab.solvers.dsl.solver import ATOMIC_LIBRARY
from arc_lab.solvers.dsl.substrate import (
    Apply,
    Const,
    Input,
    ValueType,
    format_program,
    is_consistent,
)
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY

_DSL_LOGGER = "arc_lab.solvers.dsl"


def _flip_task() -> Task:
    # Output is the horizontal flip of the input: solved by flip_h(input).
    return Task.from_dict(
        "flip",
        {
            "train": [
                {"input": [[1, 2, 3]], "output": [[3, 2, 1]]},
                {"input": [[4, 5, 6]], "output": [[6, 5, 4]]},
            ],
            "test": [{"input": [[7, 8, 9]], "output": [[9, 8, 7]]}],
        },
    )


def _symmetric_task() -> Task:
    # Input is invariant under rot180/transpose, so several D4 transforms collapse
    # to the same behaviour — exercising the observational-equivalence dedup.
    return Task.from_dict(
        "sym",
        {
            "train": [{"input": [[1, 2], [2, 1]], "output": [[9, 0], [0, 9]]}],
            "test": [{"input": [[1, 2], [2, 1]], "output": [[9, 0], [0, 9]]}],
        },
    )


# -- format_program (pure, no logging) ----------------------------------


def test_format_program_renders_nested() -> None:
    program = Apply(
        "overlay",
        (
            Const(0, ValueType.COLOR),
            Apply("identity", (Input(),)),
            Apply("rot90", (Input(),)),
        ),
    )
    assert format_program(program) == "overlay(0, identity(input), rot90(input))"


def test_format_program_renders_leaves() -> None:
    assert format_program(Input()) == "input"
    assert format_program(Const(5, ValueType.INT)) == "5"
    assert format_program(Apply("flip_h", (Input(),))) == "flip_h(input)"


# -- trace log sites ----------------------------------------------------


def test_single_apply_logs_accept(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=_DSL_LOGGER)
    SingleApply().find(_flip_task(), D4_LIBRARY)
    assert any(
        "SingleApply accept" in r.message and "flip_h(input)" in r.message for r in caplog.records
    )


def test_enumerate_logs_dedup(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=_DSL_LOGGER)
    Enumerate(max_depth=1).find(_symmetric_task(), ATOMIC_LIBRARY)
    assert any("reject (dup of" in r.message for r in caplog.records)


def test_is_consistent_logs_mismatch(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=_DSL_LOGGER)
    # rot90 does not reproduce a horizontal flip: the first pair already mismatches.
    wrong: Apply = Apply("rot90", (Input(),))
    assert is_consistent(wrong, _flip_task(), D4_LIBRARY) is False
    assert any(
        "inconsistent" in r.message and "at train[0]" in r.message for r in caplog.records
    )


def test_silent_by_default(caplog: pytest.LogCaptureFixture) -> None:
    # With no level lowering (default WARNING), the search emits nothing.
    SingleApply().find(_flip_task(), D4_LIBRARY)
    Enumerate(max_depth=1).find(_symmetric_task(), ATOMIC_LIBRARY)
    assert caplog.records == []
