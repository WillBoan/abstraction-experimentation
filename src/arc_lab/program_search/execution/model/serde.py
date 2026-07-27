"""The component serialization contract: ``kind`` discriminator + params.

Mirrors ``Program.from_dict``'s dispatch-on-``"op"`` pattern at the component level:
a machinery component (engine, cost, constraint, learn spec) serialises to
``{"kind": <class name>, **fields}`` and reconstructs by looking ``kind`` up in a
registry. Frozen dataclasses serialise generically (fields recursed, tuples as
lists); plain no-field classes (``ProgramSize``) serialise as their ``kind`` alone.

``Library`` is *not* serialised here — it has its own richer round-trip
(``Library.to_dict`` / ``from_dict``, resolving primitive impls by name against the
substrate registry); ``Config`` delegates to it directly.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import TypeAlias

#: kind -> component class; the deserialisation side of the contract.
Registry: TypeAlias = Mapping[str, type]


def to_data(component: object) -> dict[str, object]:
    """Serialise a component to ``{"kind": <class name>, **fields}``.

    Dataclass fields recurse; tuples become lists; only JSON-compatible leaves are
    allowed — anything else raises ``TypeError`` so a non-serialisable component
    can never silently corrupt a ``run_id``.

    A class may declare ``SERDE_OMIT_WHEN_NONE`` (a ``ClassVar`` of field names) to have those
    fields **left out entirely when they are ``None``**. This exists so a new field can be added
    to a component WITHOUT moving every existing ``run_id``: run identity should be semantic, and
    a field whose ``None`` provably means "no effect" contributes nothing to what a run did.
    ``from_data`` reconstructs from present keys only, so an omitted field simply takes its
    dataclass default — the round trip is unchanged.

    **The bar for using it is high**, because it hides a field from run identity: ``None`` must
    mean the component behaves exactly as if the field did not exist. It is NOT a general
    omit-defaults rule (that would move existing hashes, since fields like
    ``Budget.solution_limit`` are already ``None`` and emitted).
    """
    data: dict[str, object] = {"kind": type(component).__name__}
    if dataclasses.is_dataclass(component) and not isinstance(component, type):
        omit: frozenset[str] = getattr(type(component), "SERDE_OMIT_WHEN_NONE", frozenset())
        for field in dataclasses.fields(component):
            value = getattr(component, field.name)
            if value is None and field.name in omit:
                continue
            data[field.name] = _value_to_data(value)
    return data


def from_data(data: Mapping[str, object], registry: Registry) -> object:
    """Reconstruct a component from :func:`to_data` output via ``registry``."""
    kind = data.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"component data has no 'kind': {data!r}")
    try:
        component_cls = registry[kind]
    except KeyError:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown component kind {kind!r}; registered: {known}") from None
    kwargs = {
        name: _value_from_data(value, registry) for name, value in data.items() if name != "kind"
    }
    return component_cls(**kwargs)


def _value_to_data(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_data(value)
    if isinstance(value, tuple):
        return [_value_to_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(
        f"component field value {value!r} ({type(value).__name__}) is not serialisable; "
        "allowed: dataclasses, tuples, str/int/float/bool/None"
    )


def _value_from_data(value: object, registry: Registry) -> object:
    if isinstance(value, Mapping):
        return from_data(value, registry)
    if isinstance(value, list):
        return tuple(_value_from_data(item, registry) for item in value)
    return value
