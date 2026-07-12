"""The :class:`Mask` — a boolean cell-selection over a grid (ONTOLOGY.md's L3 region type).

The bridge from "grid" to "object": a mask selects a set of cells (same height x width as the grid
it was perceived from), to be cropped to, painted through, or combined set-wise. Mirrors
:class:`~arc_lab.core.grid.Grid`'s design exactly — immutable (frozen backing array), validated
(2-D, non-empty), and hashable/comparable by value — so masks are valid observational-equivalence
signature keys in the search pool with no special handling.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np
import numpy.typing as npt


class Mask:
    """An immutable 2-D boolean cell selection."""

    __slots__ = ("_data", "_hash")

    def __init__(self, data: npt.ArrayLike) -> None:
        arr = np.asarray(data)
        if arr.ndim != 2:
            raise ValueError(f"mask must be 2-D, got {arr.ndim}-D")
        if arr.size == 0:
            raise ValueError("mask must be non-empty")
        frozen = arr.astype(np.bool_, copy=True)
        frozen.flags.writeable = False
        self._data = frozen
        self._hash: int | None = None

    # -- constructors ----------------------------------------------------

    @classmethod
    def from_list(cls, rows: Sequence[Sequence[bool | int]]) -> Mask:
        """Build a mask from a list-of-lists of booleans (or 0/1 ints)."""
        return cls(rows)

    # -- shape -----------------------------------------------------------

    @property
    def height(self) -> int:
        return int(self._data.shape[0])

    @property
    def width(self) -> int:
        return int(self._data.shape[1])

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    # -- data access -----------------------------------------------------

    @property
    def array(self) -> npt.NDArray[np.bool_]:
        """A **writable copy** of the backing array, for callers to mutate freely."""
        return self._data.copy()

    def to_list(self) -> list[list[bool]]:
        """Convert to a list of rows of booleans."""
        return cast("list[list[bool]]", self._data.tolist())

    def __getitem__(self, index: tuple[int, int]) -> bool:
        return bool(self._data[index])

    # -- value semantics -------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mask):
            return NotImplemented
        return self._data.shape == other._data.shape and bool(
            np.array_equal(self._data, other._data)
        )

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash((self._data.shape, self._data.tobytes()))
        return self._hash

    def __repr__(self) -> str:
        return f"Mask({self.height}x{self.width})"
