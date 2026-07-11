"""The run data model: serde contract, Config/RunSpec round-trip, run-identity properties.

Phase-1 tests run against FAKE components (Sync point A of EXECUTION.md): the model
layer's contract is `kind` + params via `to_data`/`from_data`, so fakes exercise it
fully without depending on the in-flux real engine fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples
from arc_lab.program_search.execution.model import Config, LearnSpec, RunSpec, TaskResult, TaskScore
from arc_lab.program_search.execution.model.serde import from_data, to_data
from arc_lab.program_search.learn.learn_engine import LearnEngine, WakeSolutions
from arc_lab.program_search.search.constraints import Constraint
from arc_lab.program_search.search.cost import Cost
from arc_lab.program_search.search.search_engine import SearchEngine
from arc_lab.program_search.search.search_result import SearchResult, SearchStats
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Program

# -- fakes --------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FakeInner:
    limit: int = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class FakeEngine(SearchEngine):
    depth: int = 2
    names: tuple[str, ...] = ("a", "b")
    inner: FakeInner = field(default_factory=FakeInner)

    def run(
        self,
        *,
        train_examples: TrainExamples,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        return SearchResult(ranked_programs=(), stats=SearchStats(engine="FakeEngine"))


@dataclass(frozen=True, slots=True)
class FakeCost(Cost):
    def of(self, program: Program, train_examples: TrainExamples, library: Library) -> float:
        return 0.0


@dataclass(frozen=True, slots=True)
class FakeLearnEngine(LearnEngine):
    def run(self, library: Library, solutions: WakeSolutions) -> Library:
        return library


REGISTRY: dict[str, type] = {
    cls.__name__: cls for cls in (FakeInner, FakeEngine, FakeCost, FakeLearnEngine, LearnSpec)
}

_LIBRARY = D4_LIBRARY


def _config(**overrides: object) -> Config:
    base = Config(library=_LIBRARY, search_engine=FakeEngine(), cost=FakeCost())
    return base.with_(**overrides) if overrides else base


def _corpus(name: str = "c", value: int = 1) -> Corpus:
    grid = Grid.from_list([[value, 0], [0, value]])
    example = Example(input=grid, output=grid)
    return Corpus.of(name, [Task(task_id="t", train=(example,), test=(example,))])


# -- serde --------------------------------------------------------------------


def test_serde_round_trips_nested_dataclass() -> None:
    engine = FakeEngine(depth=5, names=("x",), inner=FakeInner(limit=9))
    assert from_data(to_data(engine), REGISTRY) == engine


def test_serde_no_field_component_is_kind_only() -> None:
    assert to_data(FakeCost()) == {"kind": "FakeCost"}
    assert isinstance(from_data({"kind": "FakeCost"}, REGISTRY), FakeCost)


@dataclass(frozen=True, slots=True)
class _Unserialisable:
    payload: object = print  # a callable field can never hash into a run_id


def test_serde_rejects_unknown_kind_and_unserialisable_field() -> None:
    with pytest.raises(ValueError, match="unknown component kind"):
        from_data({"kind": "Nope"}, REGISTRY)
    with pytest.raises(TypeError, match="not serialisable"):
        to_data(_Unserialisable())


# -- Config -------------------------------------------------------------------


def test_config_round_trip() -> None:
    config = _config(
        attempts_per_test=3,
        learn=LearnSpec(learn_engine=FakeLearnEngine(), iterations=4),
    )
    rebuilt = Config.from_dict(config.to_dict(), registry=REGISTRY)
    assert rebuilt == config


def test_config_with_returns_new_frozen_copy() -> None:
    base = _config()
    derived = base.with_(attempts_per_test=1)
    assert base.attempts_per_test == 2
    assert derived.attempts_per_test == 1


# -- run identity -------------------------------------------------------------


def test_search_and_learn_runs_never_collide() -> None:
    corpus = _corpus()
    search = RunSpec(config=_config(), corpus=corpus)
    learn = RunSpec(
        config=_config(learn=LearnSpec(learn_engine=FakeLearnEngine(), iterations=2)),
        corpus=corpus,
    )
    assert search.run_id != learn.run_id


def test_machinery_changes_move_run_id() -> None:
    corpus = _corpus()
    base = RunSpec(config=_config(), corpus=corpus)
    assert base.run_id != RunSpec(config=_config(attempts_per_test=1), corpus=corpus).run_id
    assert (
        base.run_id
        != RunSpec(config=_config(search_engine=FakeEngine(depth=9)), corpus=corpus).run_id
    )


def test_corpus_content_not_name_moves_run_id() -> None:
    config = _config()
    base = RunSpec(config=config, corpus=_corpus(name="a", value=1))
    renamed = RunSpec(config=config, corpus=_corpus(name="b", value=1))
    changed = RunSpec(config=config, corpus=_corpus(name="a", value=2))
    assert base.run_id == renamed.run_id
    assert base.run_id != changed.run_id


def test_runspec_payload_carries_identity_and_provenance() -> None:
    spec = RunSpec(config=_config(), corpus=_corpus(name="prov"))
    payload = spec.to_dict()
    assert payload["run_id"] == spec.run_id
    assert payload["corpus_name"] == "prov"
    assert payload["task_count"] == 1


# -- results records ----------------------------------------------------------


def test_task_result_round_trip() -> None:
    result = TaskResult(
        task_id="t1", score=TaskScore(solved=True, per_test=(True, True)), seconds=0.5
    )
    assert TaskResult.from_dict(result.to_dict()) == result
    failed = TaskResult(
        task_id="t2", score=TaskScore(solved=False, per_test=(False,)), seconds=0.1, error="boom"
    )
    assert TaskResult.from_dict(failed.to_dict()) == failed
