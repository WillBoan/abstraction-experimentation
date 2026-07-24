"""Name -> base :class:`Primitive` registry.

A base primitive's ``impl`` is Python code that :meth:`Primitive.to_dict` deliberately drops.
Reconstructing a serialised library therefore resolves base atoms *by name* against the in-code
definitions gathered here (learned abstractions instead carry a serialisable ``template`` and are
rebuilt from it — see :func:`~arc_lab.program_search.substrate.abstraction.make_abstraction`). This
registry is the single place that knows every hand-coded primitive.
"""

from __future__ import annotations

from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.primitives.addressing import ADDRESSING_PRIMITIVES
from arc_lab.program_search.substrate.primitives.arithmetic import ARITHMETIC_PRIMITIVES
from arc_lab.program_search.substrate.primitives.build import BUILD_AFFINE_LIBRARY
from arc_lab.program_search.substrate.primitives.cells import (
    CELL_LIBRARY,
    CELLS,
    FROM_CELLS,
    MOVE_CELL,
    SWAP_CELLS,
)
from arc_lab.program_search.substrate.primitives.color import FILTER_COLOR, MAP_COLOR, SWAP_COLORS
from arc_lab.program_search.substrate.primitives.combinators import COMBINATORS
from arc_lab.program_search.substrate.primitives.control import CONTROL_PRIMITIVES
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.higher_order import FILTER, FOLD, MAP, SORT_BY
from arc_lab.program_search.substrate.primitives.layout import LAYOUT_PRIMITIVES
from arc_lab.program_search.substrate.primitives.lists import LIST_PRIMITIVES
from arc_lab.program_search.substrate.primitives.mask import MASK_PRIMITIVES
from arc_lab.program_search.substrate.primitives.pairs import PAIR_PRIMITIVES
from arc_lab.program_search.substrate.primitives.perceive import PERCEIVE_PRIMITIVES
from arc_lab.program_search.substrate.primitives.regions import REGION_PRIMITIVES
from arc_lab.program_search.substrate.primitives.scaling import SCALE
from arc_lab.program_search.substrate.primitives.tiles import TILE_PRIMITIVES


def _gather() -> dict[str, Primitive]:
    groups: tuple[tuple[Primitive, ...], ...] = (
        D4_LIBRARY.primitives,
        (MAP_COLOR, SWAP_COLORS, FILTER_COLOR, SCALE),
        COMBINATORS,
        CELL_LIBRARY.primitives,
        (CELLS, FROM_CELLS, SWAP_CELLS, MOVE_CELL),
        BUILD_AFFINE_LIBRARY.primitives,  # superset of BUILD_LIBRARY (adds add, mul)
        CONTROL_PRIMITIVES,
        (MAP, FILTER, FOLD, SORT_BY),
        PERCEIVE_PRIMITIVES,
        PAIR_PRIMITIVES,
        LIST_PRIMITIVES,
        ARITHMETIC_PRIMITIVES,
        MASK_PRIMITIVES,
        LAYOUT_PRIMITIVES,
        TILE_PRIMITIVES,  # reference impls for the cfb2ce5a floor; resolvable, in no preset
        ADDRESSING_PRIMITIVES,
        REGION_PRIMITIVES,
    )
    registry: dict[str, Primitive] = {}
    for group in groups:
        for prim in group:
            # Groups legitimately OVERLAP (`read`/`set_cell` are listed by two bundles), so a
            # re-listing of the same primitive is fine. A same-name/different-primitive collision is
            # not: this used to `setdefault`, which resolved it silently first-wins, so a new bundle
            # could have its primitive quietly dropped. In a flat global namespace of ~110 names
            # that is a live hazard, and a name clash must be loud.
            existing = registry.get(prim.name)
            if existing is not None and existing != prim:
                raise ValueError(
                    f"duplicate primitive name {prim.name!r} in the substrate registry: two "
                    "different primitives claim it; rename one"
                )
            registry[prim.name] = prim
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
