"""Read-time capability groupings for a run's per-key (primitive-name / node-kind) outcome
breakdown (``search/tracking.py``'s ``SearchStats.by_key``).

Category and provenance are analysis-side *opinions*, applied when reading a run's stats —
never baked into the tracked keys themselves, never stored in a run artifact, and never a field
on ``Primitive`` (the library is run identity; a category field would perturb every
content-hashed ``run_id`` and the locks). Re-grouping under a revised taxonomy is then just
re-reading an existing run, not re-running it.

Category is derived from a primitive's defining Python module (``primitives/*.py``'s file
name) — the grouping the codebase already uses, so there is nothing new to hand-maintain.
Provenance (``"base"`` vs ``"invented"``) falls out of the same lookup: a base primitive's
``impl`` is resolved by name against ``registry.py::BASE_PRIMITIVES``; an invented one's
``impl`` is instead the closure ``substrate/abstraction.py::make_abstraction`` builds from its
template — a different defining module, reliably distinct even after a library round-trips
through serialization (``registry.py``'s docstring: base atoms resolve by name, abstractions
rebuild from their template).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..substrate.library import Library, Primitive
from ..substrate.registry import BASE_PRIMITIVES

#: Structural node-kind pseudo-keys (``search/tracking.py``) — categorized directly, since
#: they're never looked up in ``BASE_PRIMITIVES`` or any ``Library``.
_NODE_KIND_CATEGORY: Mapping[str, str] = {
    "__if__": "control",
    "__lam__": "higher-order",
    "__appfn__": "higher-order",
    "__const__": "constant",
}

#: Where ``make_abstraction`` defines an invented primitive's ``impl`` — the provenance tell.
_INVENTED_MODULE = "arc_lab.program_search.substrate.abstraction"


@dataclass(frozen=True, slots=True)
class KeyInfo:
    """One tracked key's read-time classification."""

    category: str
    provenance: str  # "base" | "invented" | "structural" | "unknown"


def describe_key(key: str, library: Library | None = None) -> KeyInfo:
    """Classify one ``by_key`` key. ``library`` resolves an invented primitive not (yet) in
    ``BASE_PRIMITIVES`` — omit it and an invented key falls back to ``"unknown"``."""
    node_category = _NODE_KIND_CATEGORY.get(key)
    if node_category is not None:
        return KeyInfo(category=node_category, provenance="structural")
    primitive = BASE_PRIMITIVES.get(key)
    if primitive is not None:
        return KeyInfo(category=_module_category(primitive), provenance="base")
    if library is not None and key in library:
        primitive = library.get(key)
        if primitive.impl.__module__ == _INVENTED_MODULE:
            return KeyInfo(category="invented", provenance="invented")
        return KeyInfo(category=_module_category(primitive), provenance="base")
    return KeyInfo(category="unknown", provenance="unknown")


def _module_category(primitive: Primitive) -> str:
    return primitive.impl.__module__.rsplit(".", 1)[-1]


def group_outcomes(
    by_key: Mapping[str, Mapping[str, int]],
    *,
    by: str,
    library: Library | None = None,
) -> dict[str, dict[str, int]]:
    """Re-key a per-key outcome matrix by ``"category"`` or ``"provenance"`` (read-time only —
    the result is never persisted back into a run artifact)."""
    if by not in ("category", "provenance"):
        raise ValueError(f"by must be 'category' or 'provenance', got {by!r}")
    grouped: dict[str, dict[str, int]] = {}
    for key, counts in by_key.items():
        info = describe_key(key, library)
        group = info.category if by == "category" else info.provenance
        bucket = grouped.setdefault(group, {})
        for outcome, count in counts.items():
            bucket[outcome] = bucket.get(outcome, 0) + count
    return grouped
