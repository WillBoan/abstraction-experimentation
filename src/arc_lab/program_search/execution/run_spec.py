from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.dataset import Corpus

from .config import Config


@dataclass(frozen=True, slots=True)
class RunSpec:
    """The configuration for a single program search run."""

    corpus: Corpus
    config: Config

    def to_dict(self) -> dict:
        """Serialize"""
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, run_spec_dict: dict[str, object]) -> RunSpec:
        """Deserialize"""
        raise NotImplementedError()
