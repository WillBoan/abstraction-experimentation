"""Candidate primitive bundles: the checkable counterpart to the design reference in
``substrate/primitives/_PRIMITIVE_BUNDLES2.md`` (Fragments + Floors tables).

A row here is a **data question**, not a shipped decision — most entries never get promoted to
``presets.py::LIBRARIES`` (a bundle is a candidate to inspect with ``check_library_coherence``; a
named ``Library`` there is a decision to actually build/run a search preset with). Adding a new
candidate you're considering is one dict entry, no code elsewhere.

Two kinds, both included here on purpose:

- **Fragments** are reusable building blocks, most deliberately *not* closed alone (e.g.
  ``PERCEIVE_INT`` is an island without a ``CTRL``/consumer per the doc's Constraint 3) — checking
  them documents/regresses *why*, not just whether.
- **Floors** are meant to already satisfy all four hard constraints (type-closure,
  goal-directedness, goal-type, hole-fill) as runnable starting libraries.

Skipped: the Object domain (``OBJECT_OPS``/``OBJECT``) — unbuilt (no ``segment``/``render``
primitives exist yet), so there's nothing to resolve.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.registry import resolve_primitive


@dataclass(frozen=True, slots=True)
class BundleSpec:
    """A candidate bundle: the primitive names it's made of, and the constant-source policy to
    assume for it. Defaults to ``finite-enumerate`` (matching the CLI's own default) since most
    bundles are agnostic to *which* reasonable policy supplies their Int/Color leaves; override to
    ``()`` only where the doc records that as a load-bearing fact (e.g. the ``FLOOR*`` progression's
    deliberate "Const: none" — see _PRIMITIVE_BUNDLES2.md), or to ``harvest-from-instance`` where a
    bundle specifically needs instance-derived literals (``SYMMETRY``'s tiling/color counts)."""

    primitives: tuple[str, ...]
    constant_sources: tuple[ConstantSource, ...] = ("finite-enumerate",)


#: Fragments (_PRIMITIVE_BUNDLES2.md "Fragments" table) — reusable blocks, grouped by role.
_FRAGMENTS: dict[str, BundleSpec] = {
    "ARITH_BASIC": BundleSpec(("add", "sub", "mul")),
    "ARITH_DIV": BundleSpec(("floordiv", "mod")),
    "ARITH_FN": BundleSpec(("min", "max", "abs")),
    "IF": BundleSpec(("if",)),
    "BOOL_LOGIC": BundleSpec(("and", "or", "not")),
    "BOOL_CMP": BundleSpec(("eq", "lt", "gt")),
    "CTRL": BundleSpec(("if", "and", "or", "not", "eq", "lt", "gt")),
    "PAIR": BundleSpec(("pair", "fst", "snd")),
    "LIST_OPS": BundleSpec(("zip", "length", "head")),
    "HO_BASIC": BundleSpec(("map", "filter", "fold", "sort_by")),
    "HO_GRID": BundleSpec(("build_grid",)),
    "PERCEIVE_COLOR": BundleSpec(("most_common_color", "least_common_color")),
    "PERCEIVE_INT": BundleSpec(("count_color", "num_colors", "palette", "shape")),
    "CELL_IO": BundleSpec(("read", "set_cell", "cells", "from_cells")),
    "RECOLOR_OPS": BundleSpec(
        ("map_color", "swap_colors", "filter_color"), constant_sources=("finite-enumerate",)
    ),
    "MASK_INTRO": BundleSpec(("mask_by_color", "nonbg_mask", "bbox_mask")),
    "MASK_ALGEBRA": BundleSpec(
        ("mask_union", "mask_intersect", "mask_difference", "mask_complement")
    ),
    "MASK_ELIM": BundleSpec(("crop_to_mask", "paint_through_mask", "crop_to_content")),
    "COMBINATORS": BundleSpec(("overlay", "tile"), constant_sources=("finite-enumerate",)),
    "LAYOUT_OPS": BundleSpec(
        ("translate", "concat_h", "concat_v", "pad", "tile_repeat", "downsample", "blank"),
        constant_sources=("finite-enumerate",),
    ),
    "SCALE": BundleSpec(("scale",)),
    "D4_GEN": BundleSpec(("flip_h", "flip_v", "transpose")),
    "D4": BundleSpec(
        ("flip_h", "flip_v", "transpose", "rot90", "rot180", "rot270", "anti_transpose")
    ),
}

#: Floors (_PRIMITIVE_BUNDLES2.md "Floors" tables) — runnable starting libraries. Where a floor's
#: primitive set is identical to a fragment above (``D4``/``D4_GEN`` double as ``GEOM``/``GEOM_GEN``),
#: it isn't repeated here — see the doc for the floor-vs-fragment framing of the same set.
_FLOORS: dict[str, BundleSpec] = {
    # "Const: none" is the load-bearing point of this progression (ONTOLOGY.md's zero-cheating
    # ladder) — everything derives from grid dimensions, never a minted literal. Don't default it.
    "FLOOR": BundleSpec(("read", "build_grid", "width", "height", "sub"), constant_sources=()),
    "FLOOR_AFFINE": BundleSpec(
        ("read", "build_grid", "width", "height", "sub", "add", "mul"), constant_sources=()
    ),
    "FLOOR_DIV": BundleSpec(
        ("read", "build_grid", "width", "height", "sub", "add", "mul", "floordiv", "mod"),
        constant_sources=(),
    ),
    "UNIVERSAL_FLOOR": BundleSpec(
        (
            "read",
            "build_grid",
            "width",
            "height",
            "sub",
            "add",
            "mul",
            "floordiv",
            "mod",
            "if",
            "and",
            "or",
            "not",
            "eq",
            "lt",
            "gt",
        ),
        constant_sources=("finite-enumerate",),
    ),
    "SYMMETRY": BundleSpec(
        (
            "flip_h",
            "flip_v",
            "transpose",
            "rot90",
            "rot180",
            "rot270",
            "anti_transpose",
            "overlay",
            "tile",
            "scale",
        ),
        constant_sources=("harvest-from-instance",),
    ),
    "RECOLOR_GEN": BundleSpec(("map_color",), constant_sources=("finite-enumerate",)),
    "PERCEIVE_TRANSFORM": BundleSpec(
        ("map_color", "swap_colors", "filter_color", "most_common_color", "least_common_color"),
        constant_sources=("finite-enumerate",),
    ),
    "LAYOUT_GEN": BundleSpec(
        ("translate", "concat_h", "concat_v", "pad", "downsample", "blank"),
        constant_sources=("finite-enumerate",),
    ),
    "MASK_MIN": BundleSpec(("nonbg_mask", "crop_to_mask")),
    "MASK_BASIC": BundleSpec(
        (
            "mask_by_color",
            "nonbg_mask",
            "bbox_mask",
            "mask_union",
            "mask_intersect",
            "mask_difference",
            "mask_complement",
            "crop_to_mask",
            "paint_through_mask",
            "crop_to_content",
        ),
        constant_sources=("finite-enumerate",),
    ),
    "HO_RECOLOR": BundleSpec(
        (
            "map",
            "filter",
            "fold",
            "sort_by",
            "cells",
            "from_cells",
            "width",
            "height",
            "if",
            "and",
            "or",
            "not",
            "eq",
            "lt",
            "gt",
            "most_common_color",
            "least_common_color",
        ),
        constant_sources=("finite-enumerate",),
    ),
}

#: The full candidate sheet, addressed by name — both Fragments (mostly expected-incoherent, kept
#: to document/regress *why*) and Floors (expected-coherent).
BUNDLES: dict[str, BundleSpec] = {
    # **_FRAGMENTS,
    **_FLOORS,
}


def library_from_names(names: Sequence[str], *, library_name: str) -> Library:
    """Build an anonymous :class:`Library` by resolving each name against the base substrate
    registry — no ``presets.py`` registration required. Shared by the ad hoc ``--primitives`` CLI
    path and :func:`resolve_bundle`."""
    return Library(name=library_name, primitives=tuple(resolve_primitive(n) for n in names))


def resolve_bundle(name: str) -> tuple[Library, tuple[ConstantSource, ...]]:
    """Resolve a bundle-sheet name to its :class:`Library` and recommended ``constant_sources``."""
    try:
        spec = BUNDLES[name]
    except KeyError:
        known = ", ".join(sorted(BUNDLES))
        raise KeyError(f"unknown bundle {name!r}; known: {known}") from None
    return library_from_names(spec.primitives, library_name=name), spec.constant_sources
