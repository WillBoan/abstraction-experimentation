"""The wake-sleep learning loop: solve, compress the solutions into abstractions, repeat.

Each generation **wakes** (solves the task set with the current library, collecting the
chosen program per solved task) then **sleeps** (proposes abstraction candidates, and
greedily adds the one that most reduces the corpus's two-part description length, rewriting
the corpus to use it, until no candidate compresses further). Adding an abstraction bumps
the library version, so the next generation searches a shorter/shallower space.

Governance — which candidate earns a name — is an :class:`~...selection.AbstractionSelector`
(default :class:`~...selection.GreedyMDL`), scored by the :class:`CompressionMetric` family.
TODO(trigger alternatives): DL-plateau, frequency-threshold, online. TODO(library cost):
charge a learned abstraction its template size, not the flat ``bits_per_primitive`` (see
`analysis/compression.py`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, CorpusEntry
from arc_lab.solvers.dsl.learn.antiunify import AbstractionProposer, rewrite_with
from arc_lab.solvers.dsl.learn.selection import AbstractionSelector, GreedyMDL
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
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
    proposer: AbstractionProposer,
    cost: Cost | None = None,
    metric: CompressionMetric | None = None,
    trigger: LearnTrigger | None = None,
    selector: AbstractionSelector | None = None,
    max_generations: int = 5,
    name_prefix: str = "abs",
) -> LearnResult:
    """Run wake-sleep generations until no abstraction compresses (or the cap is hit)."""
    cost = cost or ProgramSize()
    metric = metric or CompressionMetric()
    trigger = trigger or EachGeneration()
    selector = selector or GreedyMDL()
    added: list[Primitive] = []
    history: list[GenerationRecord] = []

    prev_dl: float | None = None
    for generation in range(max_generations):
        corpus = _solve_corpus(search, cost, library, tasks)
        if not trigger.should_learn(generation, corpus):
            break
        grown, new_prims, grown_corpus = _sleep(
            corpus, library, proposer, metric, selector, name_prefix, len(added)
        )
        if not new_prims:
            break  # dry: nothing new to learn
        dl = metric.describe(grown_corpus, grown).total
        # Convergence guard: a generation that does not *lower* total DL is discarded and
        # ends the loop. Without it, re-waking each round can re-inflate the corpus and the
        # library grows while DL climbs (observed in E3).
        if prev_dl is not None and dl >= prev_dl:
            break
        library = grown
        added.extend(new_prims)
        history.append(
            GenerationRecord(
                generation=generation,
                solved=len(grown_corpus),
                description_length=dl,
                learned=tuple(p.name for p in new_prims),
            )
        )
        prev_dl = dl

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


def _sleep(
    corpus: list[CorpusEntry],
    library: Library,
    proposer: AbstractionProposer,
    metric: CompressionMetric,
    selector: AbstractionSelector,
    name_prefix: str,
    start_index: int,
) -> tuple[Library, list[Primitive], list[CorpusEntry]]:
    """Greedily add the best-compressing abstraction, rewrite, repeat until dry."""
    added: list[Primitive] = []
    index = start_index
    while True:
        best = selector.select(corpus, library, proposer, metric)
        if best is None:
            break
        name = f"{name_prefix}{index}"
        index += 1
        primitive = make_abstraction(name, best, library)
        library = library.extended(name=f"{library.name}+{name}", extra=(primitive,))
        corpus = [(task, rewrite_with(program, name, best)) for task, program in corpus]
        added.append(primitive)
    return library, added, corpus
