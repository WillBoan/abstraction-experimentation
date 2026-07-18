"""Named machinery presets: the ``Config`` registry the CLI drives (EXECUTION.md).

Successor to the old solver ``REGISTRY`` — there are no solver classes; a preset is a
frozen ``Config`` (library x engine x budget x cost). The old presets mapped bespoke
search strategies (``single_apply`` / ``composite`` / ``enumerate``); here one generic
bottom-up engine covers them all and presets differ only in *library*, *budget*, and
*policies* — which is the point of the overhaul.

Depth accounting: ``Budget.depth_limit`` is the inclusive compositional-depth cap
(leaf = 0), so the old ``single_apply`` (one application) is ``depth_limit=1`` and the
old ``enumerate(max_depth=2)`` (two nested applications) is ``depth_limit=2``.
"""

from __future__ import annotations

from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.build import BUILD_AFFINE_LIBRARY, BUILD_LIBRARY
from arc_lab.program_search.substrate.primitives.cells import CELL_LIBRARY
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.combinators import COMBINATORS
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.higher_order import HOF_LIBRARY
from arc_lab.program_search.substrate.primitives.mask import MASK_PRIMITIVES
from arc_lab.program_search.substrate.primitives.scaling import SCALE

from .bundle_sheet import resolve_bundle
from .model.config import Config

#: D4 transforms plus the overlay and tile combinators (the old ``symmetry`` library).
SYMMETRY_LIBRARY = D4_LIBRARY.extended(name="d4+combinators", extra=COMBINATORS)
#: D4 transforms plus atomic color and scaling primitives (the old ``atomic`` library).
ATOMIC_LIBRARY = D4_LIBRARY.extended(name="atomic", extra=(MAP_COLOR, SCALE))
#: The L3 mask floor, standalone (mask intro/elim + set algebra) — not yet in any search preset.
MASK_LIBRARY = Library(name="mask", primitives=MASK_PRIMITIVES)

#: The three rungs of the `fundamental-floor grain contrast` ladder (EXPERIMENT_QUEUE.md):
#: GEOM (a direct D4 primitive, no build_grid) -> UNIVERSAL_FLOOR (build_grid + full coordinate
#: arithmetic/comparison) -> MINIMAL_COMPLETE_FLOOR (build_grid + read + if + eq only, no
#: arithmetic, no width/height — the "zero added prior" completeness witness). Each
#: ``resolve_bundle`` also yields the bundle sheet's own recommended ``constant_sources``.
GEOM_LIBRARY, GEOM_CONSTANTS = resolve_bundle("GEOM")
UNIVERSAL_FLOOR_LIBRARY, UNIVERSAL_FLOOR_CONSTANTS = resolve_bundle("UNIVERSAL_FLOOR")
MINIMAL_COMPLETE_FLOOR_LIBRARY, MINIMAL_COMPLETE_FLOOR_CONSTANTS = resolve_bundle(
    "MINIMAL_COMPLETE_FLOOR"
)

#: The vocabulary axis, addressed by name.
LIBRARIES: dict[str, Library] = {
    "d4": D4_LIBRARY,
    "symmetry": SYMMETRY_LIBRARY,
    "atomic": ATOMIC_LIBRARY,
    "build": BUILD_LIBRARY,
    "build-affine": BUILD_AFFINE_LIBRARY,
    "cells": CELL_LIBRARY,
    "hof": HOF_LIBRARY,
    "mask": MASK_LIBRARY,
}


def _bottom_up() -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )


def _bottom_up_with_constants() -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=("finite-enumerate",),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )


#: The machinery presets, addressed by name (`arc-lab search <preset> ...`).
PRESETS: dict[str, Config] = {
    # Single D4 application (the old `dsl`): geometry-only, one composition round.
    "d4": Config(
        library=D4_LIBRARY,
        search_engine=_bottom_up(),
        budget=Budget(depth_limit=1, max_arity=1, max_pool=100),
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
            unpinned_type_var_mode="reject",
        ),
        budget=Budget(depth_limit=2, max_arity=4, max_pool=500),
    ),
    # Atomic composition (the old `dsl-synth`): two nested applications over D4 + color + scale.
    "synth": Config(
        library=ATOMIC_LIBRARY,
        search_engine=_bottom_up_with_constants(),
        budget=Budget(depth_limit=2, max_arity=2, max_pool=500),
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
            unpinned_type_var_mode="reject",
            beam_width=32,
        ),
        budget=Budget(depth_limit=2, max_arity=2, max_pool=500),
    ),
    # Geometry floor via the bundle sheet's GEOM (D4 minus `identity`) — the trivial grain rung
    # for `fundamental-floor grain contrast` (EXPERIMENT_QUEUE.md): rot180 is a direct
    # 1-application primitive here, so no build_grid/lambda-synthesis is needed.
    "geom": Config(
        library=GEOM_LIBRARY,
        search_engine=BottomUpSearchEngine(
            constant_sources=GEOM_CONSTANTS,
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=Budget(depth_limit=1, max_arity=1, max_pool=100),
    ),
    # UNIVERSAL_FLOOR: build_grid + full coordinate arithmetic/comparison — the "grain contrast"
    # middle rung. Same budget as `minimal-complete-floor` deliberately, so the two are directly
    # comparable on the same task.
    "universal-floor": Config(
        library=UNIVERSAL_FLOOR_LIBRARY,
        search_engine=BottomUpSearchEngine(
            constant_sources=UNIVERSAL_FLOOR_CONSTANTS,
            function_hole_fill_mode="lambda-synthesis",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=Budget(depth_limit=5, max_arity=2, max_pool=1000),
    ),
    # MINIMAL_COMPLETE_FLOOR: build_grid + read + if + eq only (no arithmetic, no width/height)
    # -- the "zero added prior" completeness witness. Same budget as `universal-floor`
    # deliberately: whether it solves at this depth (and how expensive) IS the grain-contrast
    # measurement, not a known input (see EXPERIMENT_QUEUE.md / EXPERIMENTS.md E13).
    "minimal-complete-floor": Config(
        library=MINIMAL_COMPLETE_FLOOR_LIBRARY,
        search_engine=BottomUpSearchEngine(
            constant_sources=MINIMAL_COMPLETE_FLOOR_CONSTANTS,
            function_hole_fill_mode="lambda-synthesis",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=Budget(depth_limit=5, max_arity=2, max_pool=1000),
    ),
}


def resolve_config(name: str) -> Config:
    """Resolve a preset name to its frozen :class:`Config`."""
    try:
        return PRESETS[name]
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise KeyError(f"unknown config preset {name!r}; known: {known}") from None


def resolve_library(name: str) -> Library:
    """Resolve a library name to its frozen :class:`Library`: a vocabulary-axis name, a preset name
    (``sym``/``synth``/``beam``, via its ``.library``), or a candidate name from the bundle sheet
    (``bundle_sheet.py::BUNDLES`` — e.g. ``FLOOR``, ``MASK_BASIC``), in that order."""
    if name in LIBRARIES:
        return LIBRARIES[name]
    if name in PRESETS:
        return PRESETS[name].library
    from .bundle_sheet import BUNDLES, library_from_names

    if name in BUNDLES:
        return library_from_names(BUNDLES[name].primitives, library_name=name)
    known = ", ".join(sorted({*LIBRARIES, *PRESETS, *BUNDLES}))
    raise KeyError(f"unknown library {name!r}; known: {known}")
