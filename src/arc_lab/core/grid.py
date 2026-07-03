"""The :class:`Grid` — the atomic unit of every ARC task.

A grid is a small (usually <=30x30) rectangle of integer "colors" in the range
0-9. We wrap a numpy array rather than exposing it directly so that a grid is:

* **immutable** — the backing array is frozen, so grids are safe to share, cache,
  and use as dict keys;
* **validated** — construction rejects non-rectangular, empty, or out-of-range
  data, so an invalid grid can never enter the pipeline;
* **hashable and comparable by value** — exact-match scoring and de-duplication
  are one operator away.

Solvers work in whatever representation they like internally; :class:`Grid` is
the shared currency at the boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast

import numpy as np
import numpy.typing as npt

MIN_COLOR: Final = 0
MAX_COLOR: Final = 9
NUM_COLORS: Final = 10


class Grid:
    """An immutable 2-D grid of ARC colors (integers 0-9)."""

    __slots__ = ("_data", "_hash")

    def __init__(self, data: npt.ArrayLike) -> None:
        arr = np.asarray(data, dtype=np.int64)
        if arr.ndim != 2:
            raise ValueError(f"grid must be 2-D, got {arr.ndim}-D")
        if arr.size == 0:
            raise ValueError("grid must be non-empty")
        lo, hi = int(arr.min()), int(arr.max())
        if lo < MIN_COLOR or hi > MAX_COLOR:
            raise ValueError(f"grid colors must be in [{MIN_COLOR}, {MAX_COLOR}], got [{lo}, {hi}]")
        frozen = arr.astype(np.int8, copy=True)
        frozen.flags.writeable = False
        self._data = frozen
        self._hash: int | None = None

    # -- constructors ----------------------------------------------------

    @classmethod
    def from_list(cls, rows: Sequence[Sequence[int]]) -> Grid:
        """Build a grid from a list-of-lists (the ARC JSON representation)."""
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
    def array(self) -> npt.NDArray[np.int8]:
        """A **writable copy** of the backing array, for solvers to mutate freely."""
        return self._data.copy()

    def to_list(self) -> list[list[int]]:
        """Convert back to the ARC JSON representation (list of rows of ints)."""
        return cast("list[list[int]]", self._data.tolist())

    def __getitem__(self, index: tuple[int, int]) -> int:
        return int(self._data[index])

    # -- value semantics -------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Grid):
            return NotImplemented
        return self._data.shape == other._data.shape and bool(
            np.array_equal(self._data, other._data)
        )

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash((self._data.shape, self._data.tobytes()))
        return self._hash

    def __repr__(self) -> str:
        return f"Grid({self.height}x{self.width})"

    def to_text(self) -> str:
        """Compact human/LLM-readable form: one row per line, digits packed together."""
        return "\n".join("".join(str(c) for c in row) for row in self._data.tolist())
