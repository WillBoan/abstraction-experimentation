"""Learn-axis specs: each builds the expected live strategy and round-trips through JSON."""

from __future__ import annotations

import pytest
from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, TwoPartMDL
from arc_lab.solvers.dsl.config import MetricSpec, ProposerSpec, SleepSpec
from arc_lab.solvers.dsl.learn.antiunify import (
    AntiunifyPairs,
    FrequentSubtree,
    SearchScopedFrequentSubtree,
)
from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep
from arc_lab.solvers.dsl.search.build_grid_search import BuildGridSearch
from arc_lab.solvers.dsl.search.enumerate import Enumerate


def test_metric_spec_builds_and_round_trips() -> None:
    assert type(MetricSpec(kind="flat").build()) is CompressionMetric
    assert isinstance(MetricSpec(kind="two-part").build(), TwoPartMDL)
    spec = MetricSpec(kind="two-part", bits_per_primitive=2.0)
    assert MetricSpec.from_dict(spec.to_dict()) == spec


def test_proposer_spec_builds_each_kind() -> None:
    search = BuildGridSearch()  # has composes_signature, needed for search-scoped
    safe = ProposerSpec(kind="antiunify-pairs", bound_var_safe=True).build(search)
    assert isinstance(safe, AntiunifyPairs) and safe.bound_var_safe is True
    assert isinstance(ProposerSpec(kind="frequent-subtree").build(search), FrequentSubtree)
    assert isinstance(ProposerSpec(kind="search-scoped").build(search), SearchScopedFrequentSubtree)
    spec = ProposerSpec(kind="stitch", iterations=1, first_order=True)
    assert ProposerSpec.from_dict(spec.to_dict()) == spec


def test_search_scoped_needs_a_composing_search() -> None:
    with pytest.raises(ValueError):
        ProposerSpec(kind="search-scoped").build(Enumerate())  # Enumerate has no composes_signature


def test_default_sleep_spec_matches_the_historical_default() -> None:
    # SleepSpec() must build exactly GreedyMDLSleep(AntiunifyPairs()) with a flat metric.
    sleep = SleepSpec().build(Enumerate())
    assert isinstance(sleep, GreedyMDLSleep)
    assert isinstance(sleep.proposer, AntiunifyPairs) and sleep.proposer.bound_var_safe is False
    assert type(sleep.metric) is CompressionMetric


def test_sleep_spec_round_trips() -> None:
    for spec in (
        SleepSpec(),
        SleepSpec(
            kind="refactoring",
            proposer=ProposerSpec(kind="frequent-subtree"),
            refactor_proposer=ProposerSpec(kind="stitch", first_order=True, iterations=1),
            metric=MetricSpec(kind="two-part"),
        ),
    ):
        assert SleepSpec.from_dict(spec.to_dict()) == spec


def test_refactoring_sleep_needs_a_refactor_proposer() -> None:
    with pytest.raises(ValueError):
        SleepSpec(kind="refactoring").build(Enumerate())
