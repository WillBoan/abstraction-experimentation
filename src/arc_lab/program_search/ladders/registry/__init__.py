"""The Ladder registry: named :class:`LadderSpec` builders for ``arc-lab run-ladder <name>``.

Each ladder (or family of related ladders) is a builder module here; ``LADDERS`` aggregates them.
Mirrors ``execution/studies.py::STUDIES`` -- a zero-arg factory per name, resolved by
:func:`make_ladder`. Per-ladder *artifacts* (rendered tables, notes) live under
``docs/abstraction_ladders/ladders/<name>/``, not here.
"""

from __future__ import annotations

from collections.abc import Callable

from arc_lab.program_search.ladders.registry import al1_mirror
from arc_lab.program_search.ladders.spec import LadderSpec

#: LadderSpec builder registry for the CLI (`arc-lab run-ladder <name>`).
LADDERS: dict[str, Callable[[], LadderSpec]] = {
    "al1-mirror": al1_mirror.build,
}


def make_ladder(name: str) -> LadderSpec:
    """Resolve a ladder name to a freshly built :class:`LadderSpec`."""
    try:
        return LADDERS[name]()
    except KeyError:
        known = ", ".join(sorted(LADDERS))
        raise KeyError(f"unknown ladder {name!r}; known: {known}") from None
