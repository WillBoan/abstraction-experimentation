"""Named machinery presets: the ``Config`` registry the CLI drives (EXECUTION.md).

Successor to the old solver ``REGISTRY`` — there are no solver classes; a preset is a
frozen ``Config`` (library x engine x budget x cost). The old presets mapped bespoke
search strategies (``single_apply`` / ``composite`` / ``enumerate``); here one generic
bottom-up engine covers them all and presets differ only in *library*, *budget*, and
*policies* — which is the point of the overhaul.

Depth accounting: the new ``Budget.max_depth`` counts enumeration rounds INCLUDING the
round-0 leaves, so the old ``single_apply`` (one application) is ``max_depth=2`` and the
old ``enumerate(max_depth=2)`` (two nested applications) is ``max_depth=3``.
"""

from __future__ import annotations

from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.combinators import COMBINATORS
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.scaling import SCALE

from .model.config import Config

#: D4 transforms plus the overlay and tile combinators (the old ``symmetry`` library).
SYMMETRY_LIBRARY = D4_LIBRARY.extended(name="d4+combinators", extra=COMBINATORS)
#: D4 transforms plus atomic color and scaling primitives (the old ``atomic`` library).
ATOMIC_LIBRARY = D4_LIBRARY.extended(name="atomic", extra=(MAP_COLOR, SCALE))

#: The vocabulary axis, addressed by name.
LIBRARIES: dict[str, Library] = {
    "d4": D4_LIBRARY,
    "symmetry": SYMMETRY_LIBRARY,
    "atomic": ATOMIC_LIBRARY,
}


def _bottom_up() -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
    )


def _bottom_up_with_constants() -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=("finite-enumerate",),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
    )


#: The machinery presets, addressed by name (`arc-lab search <preset> ...`).
PRESETS: dict[str, Config] = {
    # Single D4 application (the old `dsl`): geometry-only, one composition round.
    "d4": Config(
        library=D4_LIBRARY,
        search_engine=_bottom_up(),
        budget=Budget(max_depth=2, max_arity=1, max_pool=100),
    ),
    # Symmetry reconstruction (the old `dsl-sym`): D4 copies glued by overlay / tile.
    # Variadic arity 4 admits up to 2x2 tilings; wider mosaics are a budget choice, not a wall.
    # Constants HARVEST from the instance (colors present + input dims): `finite-enumerate`'s
    # INT range 0..max-dim explodes the (rows x cols x grid^4) tile product on large grids —
    # measured at ~6M candidates on one 30x30 task. The trade: a tiling factor that is neither
    # input height nor width is out of vocabulary at this budget (a deliberate, pinned limit).
    "sym": Config(
        library=SYMMETRY_LIBRARY,
        search_engine=BottomUpSearchEngine(
            constant_sources=("harvest-from-instance",),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
        ),
        budget=Budget(max_depth=3, max_arity=4, max_pool=500),
    ),
    # Atomic composition (the old `dsl-synth`): two nested applications over D4 + color + scale.
    "synth": Config(
        library=ATOMIC_LIBRARY,
        search_engine=_bottom_up_with_constants(),
        budget=Budget(max_depth=3, max_arity=2, max_pool=500),
    ),
    # Beam-truncated variant of `synth` (the old `dsl-beam`). Constants HARVEST and the
    # beam must exceed the leaf-constant count: with `finite-enumerate` a 30-wide grid mints
    # 31 size-1 INT consts that fill a small beam entirely, starving the GRID type (measured:
    # beam 16 + finite-enumerate solves 0/400). Width 32 demonstrates the truncation honestly:
    # 9 solved vs `synth`'s 11 — the beam's cost, visible.
    "beam": Config(
        library=ATOMIC_LIBRARY,
        search_engine=BeamBottomUpSearchEngine(
            constant_sources=("harvest-from-instance",),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            beam_width=32,
        ),
        budget=Budget(max_depth=3, max_arity=2, max_pool=500),
    ),
}


def resolve_config(name: str) -> Config:
    """Resolve a preset name to its frozen :class:`Config`."""
    try:
        return PRESETS[name]
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise KeyError(f"unknown config preset {name!r}; known: {known}") from None
