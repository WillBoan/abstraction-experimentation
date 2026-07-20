"""Every kind in ``default_registry`` round-trips through the component serde.

Registered components are run identity: a kind that serialises asymmetrically — or a
newly registered kind with no covering exemplar here — would let a serde regression
pass CI silently, because the preset round-trip tests only exercise the components
presets actually use. ``SearchScopedFrequentSubtree`` is deliberately unregistered
(its ``composes`` callable is programmatic-only), so it has no exemplar either.

Exemplars use non-default field values where cheap, so a renamed or dropped field
fails the round-trip, not just the construction.
"""

from __future__ import annotations

import pytest

from arc_lab.program_search.analysis.compression import CompressionMetric, TwoPartMDL
from arc_lab.program_search.execution.model.config import default_registry
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.serde import from_data, to_data
from arc_lab.program_search.learn.antiunify import (
    AntiunifyPairs,
    FrequentSubtree,
    TypeScopedFrequentSubtree,
)
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine, RefactoringLearnEngine
from arc_lab.program_search.learn.selection import GreedyMDL
from arc_lab.program_search.learn.stitch_shim import StitchProposer
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.substrate.types import GRID, INT, ArrowType, TypeCon, TypeVar

_EXEMPLARS: dict[str, object] = {
    "BottomUpSearchEngine": BottomUpSearchEngine(
        constant_sources=("harvest-from-instance",),
        function_hole_fill_mode="point-free",
        polymorphism_instantiation="bounded",
        unpinned_type_var_mode="reject",
    ),
    "BeamBottomUpSearchEngine": BeamBottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
        beam_width=32,
    ),
    # Every stop-limit field set to a NON-default: a defaulted field round-trips trivially whether
    # or not serde actually carries it, so only non-defaults exercise the path.
    "Budget": Budget(
        depth_limit=2,
        max_arity=2,
        max_pool=64,
        considered_limit=1000,
        considered_limit_mode="generation-end",
        solution_limit=3,
        solution_limit_mode="immediate",
    ),
    "ProgramSize": ProgramSize(),
    "LearnSpec": LearnSpec(
        learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
        iterations=2,
        score_each_wake=True,
    ),
    "GreedyMDLLearnEngine": GreedyMDLLearnEngine(
        proposer=AntiunifyPairs(bound_var_safe=True), metric=TwoPartMDL()
    ),
    "RefactoringLearnEngine": RefactoringLearnEngine(
        corpus_proposer=AntiunifyPairs(),
        refactor_proposer=FrequentSubtree(min_frequency=3),
        metric=TwoPartMDL(),
    ),
    "GreedyMDL": GreedyMDL(),
    "CompressionMetric": CompressionMetric(bits_per_primitive=2.0),
    "TwoPartMDL": TwoPartMDL(),
    "AntiunifyPairs": AntiunifyPairs(bound_var_safe=True),
    "FrequentSubtree": FrequentSubtree(min_frequency=3),
    "TypeScopedFrequentSubtree": TypeScopedFrequentSubtree(result_type=INT),
    "StitchProposer": StitchProposer(iterations=7),
    "TypeCon": TypeCon("list", (GRID,)),
    "ArrowType": ArrowType((INT,), GRID),
    "TypeVar": TypeVar("a"),
}


def test_exemplars_cover_the_registry_exactly() -> None:
    """A newly registered kind must gain an exemplar here (and vice versa)."""
    assert set(_EXEMPLARS) == set(default_registry())


@pytest.mark.parametrize("kind", sorted(_EXEMPLARS))
def test_registered_kind_round_trips(kind: str) -> None:
    component = _EXEMPLARS[kind]
    rebuilt = from_data(to_data(component), default_registry())
    assert rebuilt == component
    assert type(rebuilt) is type(component)


def test_a_record_predating_a_new_field_still_deserializes() -> None:
    """``from_data`` splats only the keys present, so a ``Budget`` stored before the stop limits
    existed rebuilds on their defaults. This is what keeps already-recorded runs readable across a
    field addition -- their ``run_id``s move, but the artifacts stay loadable."""
    stored = {"kind": "Budget", "depth_limit": 2, "max_arity": 2, "max_pool": 64}
    rebuilt = from_data(stored, default_registry())
    assert rebuilt == Budget(depth_limit=2, max_arity=2, max_pool=64)
