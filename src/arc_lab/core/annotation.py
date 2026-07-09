"""Task annotations: provenance, split, and ground-truth label — kept OFF the pure Task.

A solver must never see a task's ground-truth label or its train/held-out split — that
would let search cheat. So this metadata rides *beside* the :class:`Task` in an
:class:`AnnotatedTask`, and the solver-facing seam only ever hands out the pure ``task``.
Provenance (real vs synthetic) is a property of the task, from which a corpus *derives*
whether it is real, synthetic, or mixed.

Everything here is core-clean — strings and enums only, no dependency on the DSL. The
ground-truth is an observable *name* (deliberately DSL-independent; see ``learn/taskgen``),
not a DSL ``Program``; Program-level targets live on a ``StudySpec``, not on a task.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from arc_lab.core.task import Task


@dataclass(frozen=True, slots=True)
class Real:
    """A task sourced from a real dataset (identified by its name)."""

    dataset: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": "real", "dataset": self.dataset}


@dataclass(frozen=True, slots=True)
class Synthetic:
    """A task produced by a deterministic testbed generator (identified by its id)."""

    generator: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": "synthetic", "generator": self.generator}


#: Where a task came from. ``real | synthetic | mixed`` is *derived* at the corpus level.
Provenance: TypeAlias = Real | Synthetic


def provenance_from_dict(data: Mapping[str, object]) -> Provenance:
    """Reconstruct a :data:`Provenance` from its serialized form."""
    kind = data.get("kind")
    if kind == "real":
        return Real(dataset=str(data["dataset"]))
    if kind == "synthetic":
        return Synthetic(generator=str(data["generator"]))
    raise ValueError(f"unknown provenance kind: {kind!r}")


class Split(enum.Enum):
    """The learning curriculum partition; held-out is the transfer grade's domain."""

    TRAIN = "train"
    HELDOUT = "heldout"


@dataclass(frozen=True, slots=True)
class TaskMeta:
    """Solver-invisible annotations for one task.

    ``label`` is the ground-truth operation's *name* — an observable never shown to the
    solver, and deliberately a string rather than a DSL ``Program`` (task generation is
    DSL-independent; Program-level targets live on a ``StudySpec``).
    """

    provenance: Provenance
    split: Split | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {"provenance": self.provenance.to_dict()}
        if self.split is not None:
            out["split"] = self.split.value
        if self.label is not None:
            out["label"] = self.label
        return out

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> TaskMeta:
        prov_raw = data["provenance"]
        if not isinstance(prov_raw, Mapping):
            raise ValueError(f"malformed provenance: {prov_raw!r}")
        split_raw = data.get("split")
        label_raw = data.get("label")
        return TaskMeta(
            provenance=provenance_from_dict(prov_raw),
            split=Split(split_raw) if isinstance(split_raw, str) else None,
            label=label_raw if isinstance(label_raw, str) else None,
        )


@dataclass(frozen=True, slots=True)
class AnnotatedTask:
    """A pure :class:`Task` paired with optional solver-invisible :class:`TaskMeta`."""

    task: Task
    meta: TaskMeta | None = None
