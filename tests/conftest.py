"""Shared pytest wiring.

Honors ``ARC_LAB_LOG`` the same way the CLI's ``-v``/``-vv`` does (CLAUDE.md's documented
``ARC_LAB_LOG=DEBUG uv run pytest -k <x>`` recipe) — off by default, so tests pay nothing for it.
"""

from __future__ import annotations

import logging
import os
import sys

#: Mirrors ``cli/main.py``'s ``_TRACE_LOGGER``/``_LOG_FORMAT`` — only this subtree is lowered.
_TRACE_LOGGER = "arc_lab.program_search"
_LOG_FORMAT = "%(name)s %(levelname)s %(message)s"

_env = os.environ.get("ARC_LAB_LOG")
if _env:
    _level = logging.getLevelNamesMapping().get(_env.upper(), logging.INFO)
    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT, stream=sys.stderr)
    logging.getLogger(_TRACE_LOGGER).setLevel(_level)
