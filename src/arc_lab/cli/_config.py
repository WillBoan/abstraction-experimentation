"""Shared Config resolution for the CLI: preset name or config file, plus ``--set``.

**Precedence:** ``dataclass defaults < named preset < config file < CLI --set``.

The ``<config>`` argument is a preset name (``arc-lab configs``) or a path to a JSON
config file of the shape ``{"preset": "<name>", "set": {"<dotted.path>": <value>, ...}}``.
``--set path=value`` (repeatable) applies last.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.overrides import apply_overrides, parse_set_values
from arc_lab.program_search.execution.presets import PRESETS, resolve_config


def resolve_config_arg(config_arg: str, set_args: list[str]) -> Config:
    """Resolve ``<config>`` (preset or file) and apply ``--set`` overrides, in precedence order."""
    try:
        if config_arg in PRESETS:
            config = resolve_config(config_arg)
        else:
            config = _load_config_file(Path(config_arg))
        return apply_overrides(config, parse_set_values(set_args))
    except (KeyError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _load_config_file(path: Path) -> Config:
    if not path.is_file():
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"{path} is neither a config preset (known: {known}) nor a file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("preset"), str):
        raise ValueError(f'{path} must be {{"preset": "<name>", "set": {{...}}}}')
    config = resolve_config(data["preset"])
    overrides = data.get("set", {})
    if not isinstance(overrides, dict):
        raise ValueError(f'{path}: "set" must be a mapping of dotted paths to values')
    return apply_overrides(config, overrides)
