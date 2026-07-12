"""Dotted-path ``Config`` overrides: the ``--set`` / config-file surface (EXECUTION.md).

**Precedence:** ``dataclass defaults < named preset < config file < CLI --set``. A preset
is already a fully-built ``Config`` (defaults filled), so precedence reduces to applying
override layers in order — each layer a mapping of dotted paths to values:

    apply_overrides(preset, {"budget.max_depth": 4, "attempts_per_test": 1})

Paths navigate frozen-dataclass fields (``budget.max_depth``, ``search_engine.beam_width``);
every application is a ``dataclasses.replace``, so the result is a new frozen ``Config``
with its own content-hashed ``run_id`` — overridden runs can never collide with the preset's
cache. Two conveniences: ``library`` accepts a *name* resolved via the preset library
registry, and a JSON-ish scalar string (``"4"``, ``"true"``, ``"[1, 2]"``) parses to its
value (CLI values arrive as strings). Unknown fields and type mismatches fail loudly with
the available options — an override typo must never silently no-op.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from typing import Any

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
    return dataclasses.replace(obj, **{name: _coerce(current, value, full_path)})


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
