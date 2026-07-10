from __future__ import annotations

from dataclasses import dataclass

from ..learn.learn_engine import LearnEngine
from ..search.constraints import Constraint
from ..search.cost import Cost
from ..search.search_engine import SearchEngine
from ..substrate.library import Library


@dataclass(frozen=True, slots=True)
class Config:
    """The configuration for a single program search run."""

    library: Library
    search_engine: SearchEngine
    constraints: tuple[Constraint, ...]
    cost: Cost
    learn_engine: LearnEngine | None = None

    def to_dict(self) -> dict:
        """Serialize"""
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, config_dict: dict) -> Config:
        """Deserialize"""
        raise NotImplementedError()
