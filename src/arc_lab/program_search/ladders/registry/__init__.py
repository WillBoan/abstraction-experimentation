"""The Ladder registry: the `.ladder` source files, discovered by scanning this directory.

Each ladder is one `<name>.ladder` file beside this module -- its single source of truth
(``docs/abstraction_ladders/LADDER-FORMAT.md``), driving both its :class:`LadderSpec` and its
generated testbed. Adding a ladder is adding a file: there is nothing to register.

Per-ladder *artifacts* (rendered tables, worksheets, results) live under
``docs/abstraction_ladders/ladders/<name>/``, not here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from arc_lab.program_search.ladders.lang.load import LoadedLadder, ladder_spec, resolve
from arc_lab.program_search.ladders.lang.parse import LADDER_SUFFIX, parse_ladder_file
from arc_lab.program_search.ladders.spec import LadderSpec

#: Where the `.ladder` sources live -- this package's own directory.
LADDER_ROOT = Path(__file__).resolve().parent


def ladder_paths() -> dict[str, Path]:
    """Every `.ladder` source, by ladder name (its filename stem -- spec STR-1)."""
    return {path.stem: path for path in sorted(LADDER_ROOT.glob(f"*{LADDER_SUFFIX}"))}


def load_ladder(name: str) -> LoadedLadder:
    """Parse and resolve one ladder's source file (raises :class:`KeyError` for an unknown name)."""
    paths = ladder_paths()
    try:
        path = paths[name]
    except KeyError:
        known = ", ".join(sorted(paths))
        raise KeyError(f"unknown ladder {name!r}; known: {known}") from None
    return resolve(parse_ladder_file(path))


def make_ladder(name: str) -> LadderSpec:
    """Resolve a ladder name to a freshly built :class:`LadderSpec`."""
    return ladder_spec(load_ladder(name))


def _builder(name: str) -> Callable[[], LadderSpec]:
    return lambda: make_ladder(name)


#: LadderSpec builder registry for the CLI (`arc-lab run-ladder <name>`).
LADDERS: dict[str, Callable[[], LadderSpec]] = {name: _builder(name) for name in ladder_paths()}
