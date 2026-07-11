"""``StudySpec``: orchestration data for a STUDY — it *generates* RunSpecs, it is not a run.

A study asks the abstraction-formation question: SEARCH + LEARN on the train corpus with the
starting library **L1** yields the grown **L2**; **L3** = L1 + the *target* abstractions. The
grid ``(L1, L2, L3) x budgets x (train corpus, eval corpus)`` is then plain SEARCH recorded
runs, and the report grades what was invented against the targets — behaviorally, as
observables only, never a training signal (EXECUTION.md).

Like ``RunSpec``, there is deliberately no ``from_dict``: :meth:`StudySpec.to_dict` is a
provenance payload (corpora appear by name + content hash, never embedded), and a ``Corpus``
is not reconstructible from its hash — specs are built from live corpora.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.dataset import Corpus
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.serde import to_data
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.substrate.program import Program


@dataclass(frozen=True, slots=True, kw_only=True)
class TargetAbstraction:
    """A named target: a *closed template* over the starting library's primitives.

    Targets are the study's ground truth for what sleep *should* invent. They are graded
    behaviorally (does an invented primitive compute the same function?) by the report —
    they are observables, and structurally cannot leak into learning: nothing on the
    execution path ever reads them.
    """

    name: str
    template: Program


@dataclass(frozen=True, slots=True, kw_only=True)
class StudySpec:
    """One study: a LEARN base config (library = L1) x budgets x two corpora x targets."""

    base_config: Config
    budgets: tuple[Budget, ...]
    train_corpus: Corpus
    eval_corpus: Corpus
    target_abstractions: tuple[TargetAbstraction, ...]

    def __post_init__(self) -> None:
        if self.base_config.learn is None:
            raise ValueError("a study's base_config must be a LEARN config (learn set)")
        if not self.budgets:
            raise ValueError("a study needs at least one budget")

    def to_dict(self) -> dict[str, object]:
        """The provenance payload (report header) — corpora by name + hash, never embedded."""
        return {
            "base_config": self.base_config.to_dict(),
            "budgets": [to_data(budget) for budget in self.budgets],
            "train_corpus": _corpus_provenance(self.train_corpus),
            "eval_corpus": _corpus_provenance(self.eval_corpus),
            "targets": [
                {"name": target.name, "template": target.template.to_dict()}
                for target in self.target_abstractions
            ],
        }


def _corpus_provenance(corpus: Corpus) -> dict[str, object]:
    return {
        "name": corpus.name,
        "content_hash": corpus.content_hash(),
        "task_count": len(corpus),
    }
