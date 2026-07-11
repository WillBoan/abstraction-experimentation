"""Name -> base :class:`Primitive` registry.

A base primitive's ``impl`` is Python code that :meth:`Primitive.to_dict` deliberately drops.
Reconstructing a serialised library therefore resolves base atoms *by name* against the in-code
definitions gathered here (learned abstractions instead carry a serialisable ``template`` and are
rebuilt from it — see :func:`~arc_lab.solvers.program_search.substrate.abstraction.make_abstraction`). This
registry is the single place that knows every hand-coded primitive.
"""

from __future__ import annotations

from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.primitives.build import BUILD_AFFINE_LIBRARY
from arc_lab.program_search.substrate.primitives.cells import CELL_LIBRARY
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.combinators import COMBINATORS
from arc_lab.program_search.substrate.primitives.control import CONTROL_PRIMITIVES
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.scaling import SCALE


def _gather() -> dict[str, Primitive]:
    groups: tuple[tuple[Primitive, ...], ...] = (
        D4_LIBRARY.primitives,
        (MAP_COLOR, SCALE),
        COMBINATORS,
        CELL_LIBRARY.primitives,
        BUILD_AFFINE_LIBRARY.primitives,  # superset of BUILD_LIBRARY (adds add, mul)
        CONTROL_PRIMITIVES,
    )
    registry: dict[str, Primitive] = {}
    for group in groups:
        for prim in group:
            registry.setdefault(prim.name, prim)
    return registry


#: Every hand-coded base primitive, keyed by name.
BASE_PRIMITIVES: dict[str, Primitive] = _gather()


def resolve_primitive(name: str) -> Primitive:
    """Resolve a base primitive name to its live (impl-carrying) :class:`Primitive`."""
    try:
        return BASE_PRIMITIVES[name]
    except KeyError:
        known = ", ".join(sorted(BASE_PRIMITIVES))
        raise KeyError(
            f"unknown base primitive {name!r}; not in the substrate registry (known: {known})"
        ) from None
