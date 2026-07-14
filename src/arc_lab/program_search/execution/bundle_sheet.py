"""Candidate primitive bundles: the checkable counterpart to the design reference in
``substrate/primitives/_PRIMITIVE_BUNDLES.md`` (Fragments + Floors tables).

A row here is a **data question**, not a shipped decision — most entries never get promoted to
``presets.py::LIBRARIES`` (a bundle is a candidate to inspect with ``check_library_coherence``; a
named ``Library`` there is a decision to actually build/run a search preset with). Adding a new
candidate you're considering is one dict entry, no code elsewhere.

Three kinds, matching the doc's three tiers:

- **Fragments** are reusable building blocks, most deliberately *not* closed alone (e.g.
  ``PERCEIVE_INT`` is an island without a ``CTRL``/consumer per the doc's Constraint 3). They are
  defined here for name-resolution (``check-library-coherence <FRAGMENT>``) but **not wired into**
  ``BUNDLES`` — batch-checking them only prints expected-INCOHERENT noise.
- **Floors** are meant to already satisfy all four hard constraints (type-closure,
  goal-directedness, goal-type, hole-fill) as runnable starting libraries. These are ``BUNDLES``:
  the batch check is a clean "every floor should be COHERENT" regression.
- **Gap-Exposing Bundles** deliberately *don't* close — each names the missing primitive that would
  close it. Defined for reference, not wired into ``BUNDLES`` (expected-incoherent by design).

Skipped entirely: the Object domain (``OBJECT``) — unbuilt (no ``segment``/``render`` primitives
exist yet), so its names don't resolve.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.registry import resolve_primitive

#: The full D4 group, one application each (excludes ``identity`` — dominated by the free
#: ``Input()`` leaf; see _PRIMITIVE_BUNDLES.md Constraint 5). Reused by several floors.
_D4 = ("flip_h", "flip_v", "transpose", "rot90", "rot180", "rot270", "anti_transpose")


@dataclass(frozen=True, slots=True)
class BundleSpec:
    """A candidate bundle: the primitive names it's made of, and the constant-source policy to
    assume for it. Defaults to ``finite-enumerate`` (matching the CLI's own default) since most
    bundles are agnostic to *which* reasonable policy supplies their Int/Color leaves; override to
    ``()`` only where the doc records that as a load-bearing fact (e.g. the ``FLOOR*`` progression's
    deliberate "Const: none" — see _PRIMITIVE_BUNDLES.md), or to ``harvest-from-instance`` where a
    bundle specifically needs instance-derived literals (``SYMMETRY``'s tiling/color counts)."""

    primitives: tuple[str, ...]
    constant_sources: tuple[ConstantSource, ...] = ("finite-enumerate",)


#: Fragments (_PRIMITIVE_BUNDLES.md "Fragments" table) — reusable blocks, grouped by role.
#: Defined for name-resolution only; NOT wired into ``BUNDLES`` (most are non-closed by design).
_FRAGMENTS: dict[str, BundleSpec] = {
    "ARITH_BASIC": BundleSpec(("add", "sub", "mul")),
    "ARITH_DIV": BundleSpec(("floordiv", "mod")),
    "ARITH_FN": BundleSpec(("min", "max", "abs")),
    "EQ": BundleSpec(("eq",)),
    "ORDERING": BundleSpec(("lt", "gt")),
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
    "CELLS_IO": BundleSpec(("cells", "from_cells")),
    "CELL_STATEFUL": BundleSpec(("read", "set_cell")),
    "CELL_TARGETS": BundleSpec(("swap_cells", "move_cell")),
    "RECOLOR_OPS": BundleSpec(("map_color", "swap_colors", "filter_color")),
    "MASK_INTRO": BundleSpec(("mask_by_color", "nonbg_mask", "bbox_mask")),
    "MASK_ALGEBRA": BundleSpec(
        ("mask_union", "mask_intersect", "mask_difference", "mask_complement")
    ),
    "MASK_ELIM": BundleSpec(("crop_to_mask", "paint_through_mask", "crop_to_content")),
    "COMBINATORS": BundleSpec(("overlay", "tile")),
    "LAYOUT_OPS": BundleSpec(
        ("translate", "concat_h", "concat_v", "pad", "tile_repeat", "downsample", "blank")
    ),
    "SCALE": BundleSpec(("scale",)),
    # Verified-minimal generating pair (BFS: {flip_h, transpose} reaches all 8 D4 elements;
    # flip_v derivable at depth 2) vs. the conventional 3-generator set. See _PRIMITIVE_BUNDLES.md.
    "D4_GEN_MIN": BundleSpec(("flip_h", "transpose")),
    "D4_GEN": BundleSpec(("flip_h", "flip_v", "transpose")),
    "D4": BundleSpec(_D4),
}

#: Floors (_PRIMITIVE_BUNDLES.md "Floors" tables) — runnable starting libraries, organized by
#: domain. These ARE ``BUNDLES``: batch-checked, every one expected COHERENT.
_FLOORS: dict[str, BundleSpec] = {
    # -- Coordinate / pixel (grain lattice, low -> complete). "Const: none" is load-bearing for the
    #    FLOOR* progression (ONTOLOGY's zero-cheating ladder) — everything derives from grid dims.
    "FLOOR": BundleSpec(("read", "build_grid", "width", "height", "sub"), constant_sources=()),
    "FLOOR_AFFINE": BundleSpec(
        ("read", "build_grid", "width", "height", "sub", "add", "mul"), constant_sources=()
    ),
    "FLOOR_DIV": BundleSpec(
        ("read", "build_grid", "width", "height", "sub", "add", "mul", "floordiv", "mod"),
        constant_sources=(),
    ),
    # The "zero added prior" completeness witness: if+eq+mined literals express any per-cell lookup
    # table. finite-enumerate is REQUIRED (must mine every coordinate literal eq compares).
    "MINIMAL_COMPLETE_FLOOR": BundleSpec(("build_grid", "read", "if", "eq")),
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
    ),
    # -- Geometry
    "GEOM": BundleSpec(_D4, constant_sources=()),
    "ATOMIC": BundleSpec((*_D4, "map_color", "scale")),
    "SYMMETRY": BundleSpec(
        (*_D4, "overlay", "tile", "scale"), constant_sources=("harvest-from-instance",)
    ),
    "SYMMETRY_PERCEIVED": BundleSpec((*_D4, "overlay", "least_common_color"), constant_sources=()),
    # -- Color / perception
    "RECOLOR_GEN": BundleSpec(("map_color",)),
    "RECOLOR": BundleSpec(("map_color", "swap_colors", "filter_color")),
    "PERCEIVE_TRANSFORM": BundleSpec(
        ("map_color", "swap_colors", "filter_color", "most_common_color", "least_common_color")
    ),
    # -- Cell. Needs finite-enumerate for Int COORDINATES: no width/height here, so read/set_cell's
    #    row/col args have no other source (the coherence check catches const=() as INCOHERENT; E2
    #    likewise needed Enumerate(coord_ints=True)).
    "CELL_FLOOR": BundleSpec(("read", "set_cell")),
    "CELL_FLOOR_WITH_TARGETS": BundleSpec(("read", "set_cell", "swap_cells", "move_cell")),
    # -- Region / mask
    "MASK_MIN": BundleSpec(("nonbg_mask", "crop_to_mask"), constant_sources=()),
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
    ),
    "MASK_PERCEIVED": BundleSpec(
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
            "most_common_color",
            "palette",
        ),
        constant_sources=(),
    ),
    "SELECT_AND_CROP": BundleSpec(
        ("nonbg_mask", "crop_to_content", "crop_to_mask", *_D4, "map_color")
    ),
    # -- Spatial / layout
    "LAYOUT_GEN": BundleSpec(("translate", "concat_h", "concat_v", "pad", "downsample", "blank")),
    "LAYOUT_FULL": BundleSpec(
        (
            "translate",
            "concat_h",
            "concat_v",
            "pad",
            "tile_repeat",
            "downsample",
            "blank",
            "scale",
            "width",
            "height",
        ),
    ),
    # -- Higher-order & list
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
    ),
    "HOF_COLOR": BundleSpec(
        (
            "map",
            "filter",
            "cells",
            "from_cells",
            "width",
            "height",
            "eq",
            "most_common_color",
            "least_common_color",
        ),
        constant_sources=(),
    ),
    "LIST_ALGEBRA": BundleSpec(
        ("cells", "from_cells", "zip", "length", "head", "pair", "fst", "snd", "fold", "sort_by"),
        constant_sources=(),
    ),
}

#: Gap-Exposing Bundles (_PRIMITIVE_BUNDLES.md third tier) — deliberately non-closed, each naming
#: the missing primitive. Defined for reference; NOT wired into ``BUNDLES`` (expected incoherent).
_GAP_EXPOSING: dict[str, BundleSpec] = {
    # Missing a MASK->INT cardinality primitive (e.g. mask_count): tests faking
    # segment_by_color + select_largest without ever inventing an Object type.
    "OBJECT_PRECURSOR": BundleSpec(
        ("palette", "map", "mask_by_color", "crop_to_mask", "sort_by", "fold")
    ),
}


#: The batch-checked sheet: Floors only (expected COHERENT). Fragments and gap-exposing bundles are
#: defined above for name-resolution but intentionally excluded — both are non-closed by design.
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
    """Resolve a bundle-sheet name to its :class:`Library` and recommended ``constant_sources``.

    Resolves against Floors first (the batch-checked set), then the reference-only Fragments and
    Gap-Exposing bundles, so ``check-library-coherence <NAME>`` works for any named bundle."""
    for table in (_FLOORS, _FRAGMENTS, _GAP_EXPOSING):
        if name in table:
            spec = table[name]
            return library_from_names(spec.primitives, library_name=name), spec.constant_sources
    known = ", ".join(sorted({*_FLOORS, *_FRAGMENTS, *_GAP_EXPOSING}))
    raise KeyError(f"unknown bundle {name!r}; known: {known}") from None
