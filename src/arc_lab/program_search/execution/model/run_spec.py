"""``RunSpec``: the recorded-run atom — ``Config x Corpus`` → content-hashed ``run_id``.

Exactly ONE corpus (train-vs-eval evaluation is two separate runs). The ``run_id``
hashes the config's canonical serialisation and the corpus's *content* hash; the
corpus *name* and the git commit are provenance — recorded in ``runspec.json``,
never hashed (an unrelated commit must not bust the cache; identical corpus content
under two names is the same corpus).

There is deliberately no ``from_dict``: ``runspec.json`` records a run's identity
and provenance, but a ``Corpus`` is not reconstructible from its hash — specs are
built from live corpora, records are read via ``RunRecord``.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.dataset import Corpus
from arc_lab.core.hashing import content_id

from .config import Config


@dataclass(frozen=True, slots=True, kw_only=True)
class RunSpec:
    """One recorded run: the machinery (``config``) x the content (``corpus``)."""

    config: Config
    corpus: Corpus

    @property
    def run_id(self) -> str:
        """The content-addressed run identity — the cache key ``execute()`` dedupes on.

        Not the ``runs/`` dirname on its own: the on-disk dir is
        ``<date>/<started_at>_<run_id>`` (see ``model.run_record.find_run_dir``), so ``runs/``
        groups by date and sorts chronologically. The two are deliberately decoupled.
        """
        return content_id({"config": self.config.to_dict(), "corpus": self.corpus.content_hash()})

    def to_dict(self) -> dict[str, object]:
        """The ``runspec.json`` payload: identity + provenance (name recorded, not hashed)."""
        return {
            "run_id": self.run_id,
            "config": self.config.to_dict(),
            "corpus_hash": self.corpus.content_hash(),
            "corpus_name": self.corpus.name,
            "task_count": len(self.corpus),
        }
