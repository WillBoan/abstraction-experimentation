"""The DSL value type system.

Programs pass *values* between primitives, and every value has a type.

Primitive signatures are typed from the start, because types are what will make
search over a larger, more atomic vocabulary tractable: typed enumeration only
ever composes type-compatible pieces, pruning the otherwise-explosive space of
programs before it is ever evaluated.

Right now there is only one value type — a grid — because the seed vocabulary is
entirely whole-grid transforms.

Future value types (colors, integers, boolean masks, extracted objects, ...) slot
in here as the vocabulary grows.
"""

from __future__ import annotations

from enum import Enum


class ValueType(Enum):
    """The type of a value flowing through a DSL program."""

    GRID = "grid"
    COLOR = "color"  # a cell color, integer 0-9
    INT = "int"  # a small non-negative integer (e.g. a tiling dimension)
    FN = "fn"  # a function value (a lambda's closure) — opaque for now, no arrow types yet
    # Future (maybe): COORD, BOOL, MASK, OBJECTS, ...
