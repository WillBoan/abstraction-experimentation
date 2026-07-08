"""The wake-sleep learning loop: solve, compress the solutions into abstractions, repeat.

Each generation **wakes** (solves the task set with the current library, collecting the
chosen program per solved task) then **sleeps** — turns that corpus into named abstractions
via a pluggable :class:`~...sleep.SleepStrategy` (default :class:`~...sleep.GreedyMDLSleep`,
the historical greedy-MDL machinery). Adding an abstraction bumps the library version, so the
next generation searches a shorter/shallower space.

The loop owns only the wake step and the cross-generation guards (dry-stop, and discarding a
generation that does not lower the strategy's ``score``); *how* abstractions are invented,
governed, and folded in — and how the outcome is scored — is the strategy's concern.
TODO(trigger alternatives): DL-plateau, frequency-threshold, online.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.analysis.compression import CorpusEntry
from arc_lab.solvers.dsl.learn.antiunify import AntiunifyPairs
from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep, SleepStrategy
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.substrate.library import Library, Primitive
from arc_lab.solvers.dsl.trace import task_context


class LearnTrigger(ABC):
    """Decides, per generation, whether to run the sleep (abstraction) step."""

    @abstractmethod
    def should_learn(self, generation: int, corpus: list[CorpusEntry]) -> bool: ...


class EachGeneration(LearnTrigger):
    """Always attempt to learn (termination is handled by 'no candidate compresses')."""

    def should_learn(self, generation: int, corpus: list[CorpusEntry]) -> bool:
        return bool(corpus)


@dataclass(frozen=True, slots=True)
class GenerationRecord:
    generation: int
    solved: int
    description_length: float
    learned: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LearnResult:
    library: Library
    abstractions: tuple[Primitive, ...]
    history: tuple[GenerationRecord, ...]


def learn(
    *,
    library: Library,
    search: Search,
    tasks: list[Task],
    sleep: SleepStrategy | None = None,
    cost: Cost | None = None,
    trigger: LearnTrigger | None = None,
    max_generations: int = 5,
) -> LearnResult:
    """Run wake-sleep generations until no abstraction compresses (or the cap is hit)."""
    cost = cost or ProgramSize()
    sleep = sleep or GreedyMDLSleep(AntiunifyPairs())
    trigger = trigger or EachGeneration()
    added: list[Primitive] = []
    history: list[GenerationRecord] = []

    prev_score: float | None = None
    for generation in range(max_generations):
        corpus = _solve_corpus(search, cost, library, tasks)
        if not trigger.should_learn(generation, corpus):
            break
        outcome = sleep.run(corpus, library, len(added))
        if not outcome.added:
            break  # dry: nothing new to learn
        # Convergence guard: a generation that does not *lower* the strategy's score is discarded
        # and ends the loop. Without it, re-waking each round can re-inflate the corpus and the
        # library grows while the score climbs (observed in E3).
        if prev_score is not None and outcome.score >= prev_score:
            break
        library = outcome.library
        added.extend(outcome.added)
        history.append(
            GenerationRecord(
                generation=generation,
                solved=len(outcome.corpus),
                description_length=outcome.score,
                learned=tuple(p.name for p in outcome.added),
            )
        )
        prev_score = outcome.score

    return LearnResult(library=library, abstractions=tuple(added), history=tuple(history))


def _solve_corpus(
    search: Search, cost: Cost, library: Library, tasks: list[Task]
) -> list[CorpusEntry]:
    """Wake: the min-cost program found per solved task (mirrors predict's ranking)."""
    corpus: list[CorpusEntry] = []
    for task in tasks:
        with task_context(task.task_id):
            programs = search.find(task, library).programs
        if not programs:
            continue
        chosen = min(programs, key=lambda p: cost.of(p, task, library))
        corpus.append((task, chosen))
    return corpus
