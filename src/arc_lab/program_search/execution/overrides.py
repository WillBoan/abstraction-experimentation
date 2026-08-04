"""Dotted-path ``Config`` overrides: the ``--set`` / config-file surface (EXECUTION.md).

**Precedence:** ``dataclass defaults < named preset < config file < CLI --set``. A preset
is already a fully-built ``Config`` (defaults filled), so precedence reduces to applying
override layers in order — each layer a mapping of dotted paths to values:

    apply_overrides(preset, {"budget.depth_limit": 3, "attempts_per_test": 1})

Paths navigate frozen-dataclass fields (``budget.depth_limit``, ``search_engine.beam_width``);
every application is a ``dataclasses.replace``, so the result is a new frozen ``Config``
with its own content-hashed ``run_id`` — overridden runs can never collide with the preset's
cache. Three conveniences: ``library`` accepts a *name* resolved via the preset library
registry, a component field accepts a serde ``kind`` (``learn.learn_engine.proposer=StitchProposer``
— built with its defaults, then tunable by path), and a JSON-ish scalar string (``"4"``,
``"true"``, ``"[1, 2]"``) parses to its value (CLI values arrive as strings). Unknown fields and
type mismatches fail loudly with the available options — an override typo must never silently
no-op.
"""

from __future__ import annotations

import abc
import dataclasses
import json
from collections.abc import Mapping
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from arc_lab.program_search.substrate.library import Library

from .model.config import Config


def parse_set_values(assignments: list[str]) -> dict[str, object]:
    """Parse CLI ``--set path=value`` strings into an override mapping."""
    overrides: dict[str, object] = {}
    for assignment in assignments:
        path, sep, raw = assignment.partition("=")
        if not sep or not path:
            raise ValueError(f"malformed --set {assignment!r} (expected path=value)")
        overrides[path.strip()] = _parse_value(raw.strip())
    return overrides


def apply_overrides(config: Config, overrides: Mapping[str, object]) -> Config:
    """``config`` with each dotted-path override applied (a new frozen ``Config``)."""
    result = config
    for path, value in overrides.items():
        parts = path.split(".")
        if not all(parts):
            raise ValueError(f"malformed override path {path!r}")
        result = _set_path(result, parts, value, path)
    assert isinstance(result, Config)
    return result


def _parse_value(raw: str) -> object:
    """A JSON-ish scalar (``4`` / ``true`` / ``[1, 2]`` / quoted string), else the raw string."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _set_path(obj: object, parts: list[str], value: object, full_path: str) -> Any:
    """Rebuild ``obj`` with ``parts`` (a dotted-path prefix of ``full_path``) set to ``value``."""
    if obj is None:
        raise ValueError(
            f"cannot set {full_path!r}: an intermediate component is None "
            "(e.g. `learn.*` on a SEARCH config — start from a LEARN config)"
        )
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        raise ValueError(f"cannot set {full_path!r}: {type(obj).__name__} is not a component")
    name = parts[0]
    field_names = {field.name for field in dataclasses.fields(obj)}
    if name not in field_names:
        raise ValueError(
            f"unknown field {name!r} in {full_path!r}; "
            f"{type(obj).__name__} has: {', '.join(sorted(field_names))}"
        )
    current = getattr(obj, name)
    if len(parts) > 1:
        return dataclasses.replace(obj, **{name: _set_path(current, parts[1:], value, full_path)})
    if value is None:
        # Clearing an optional field back to its unset state (`--set budget.solution_limit=null`).
        # `_coerce` cannot decide this: it sees only the CURRENT value, so a field holding `1` looks
        # like a plain `int`. The declared type is the only thing that knows the field is optional.
        if not _admits_none(obj, name):
            raise ValueError(
                f"cannot set {full_path!r} to null: "
                f"{type(obj).__name__}.{name} is not an optional field"
            )
        return dataclasses.replace(obj, **{name: None})
    return dataclasses.replace(obj, **{name: _coerce(current, value, full_path)})


def _admits_none(obj: object, name: str) -> bool:
    """Whether ``obj``'s ``name`` field is declared optional, so ``None`` is a legal value."""
    try:
        hint = get_type_hints(type(obj)).get(name)
    except (NameError, TypeError):  # an unresolvable forward reference: assume not optional
        return False
    # `int | None` and `Optional[int]` both normalise to a union containing `NoneType`.
    return get_origin(hint) in (Union, UnionType) and type(None) in get_args(hint)


def _coerce(current: object, value: object, full_path: str) -> object:
    """Fit ``value`` to the field's current shape; fail loudly on a type mismatch."""
    if isinstance(current, Library):
        if isinstance(value, str):  # a library NAME, resolved via the preset registry
            from .presets import LIBRARIES

            try:
                return LIBRARIES[value]
            except KeyError:
                known = ", ".join(sorted(LIBRARIES))
                raise ValueError(
                    f"unknown library {value!r} for {full_path!r}; known: {known}"
                ) from None
        raise ValueError(f"{full_path!r} takes a library name (string), got {value!r}")
    if (
        isinstance(value, str)
        and dataclasses.is_dataclass(current)
        and not isinstance(current, type)
    ):
        return _component(current, value, full_path)
    if isinstance(current, tuple) and isinstance(value, list):
        return tuple(value)
    if isinstance(current, bool) or isinstance(value, bool):
        if isinstance(current, bool) and isinstance(value, bool):
            return value
        raise ValueError(f"type mismatch for {full_path!r}: expected bool, got {value!r}")
    if isinstance(current, float) and isinstance(value, int):
        return float(value)
    if current is not None and not isinstance(value, type(current)):
        raise ValueError(
            f"type mismatch for {full_path!r}: expected {type(current).__name__}, got {value!r}"
        )
    return value


def _component(current: object, kind: str, full_path: str) -> object:
    """Swap in the machinery component named by its serde ``kind``, built with its defaults.

    A component field (search engine, proposer, learn engine, cost, ...) is set by *naming a kind* —
    the same string ``to_data`` emits — so ``--set`` and a `.ladder` ``config`` block speak the
    registry's own vocabulary rather than needing a constructed object. To vary the new component's
    own fields, set them by path afterwards. The replacement must satisfy the field's interface
    (the abstract base its current value implements), so a proposer can never become an engine.
    """
    from .model.config import default_registry

    registry = default_registry()
    replacement = registry.get(kind)
    if replacement is None:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown component {kind!r} for {full_path!r}; known: {known}")
    # `ABC` and `object` are shared by every component, so neither constrains anything.
    interfaces = tuple(base for base in type(current).__mro__[1:] if base not in (object, abc.ABC))
    if interfaces and not issubclass(replacement, interfaces):
        raise ValueError(
            f"{kind!r} is not a {interfaces[0].__name__}, which {full_path!r} requires"
        )
    try:
        return replacement()
    except TypeError as exc:
        raise ValueError(
            f"cannot build {kind!r} for {full_path!r} from defaults ({exc}); "
            "it needs explicit arguments"
        ) from None
