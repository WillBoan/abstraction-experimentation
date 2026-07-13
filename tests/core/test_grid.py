from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid


def test_construction_and_shape() -> None:
    g = Grid.from_list([[0, 1, 2], [3, 4, 5]])
    assert g.shape == (2, 3)
    assert g.height == 2
    assert g.width == 3
    assert g[1, 2] == 5


def test_immutable_backing_array() -> None:
    g = Grid.from_list([[1, 2]])
    # .array hands back a writable copy; mutating it must not affect the grid.
    a = g.array
    a[0, 0] = 9
    assert g[0, 0] == 1


def test_value_equality_and_hash() -> None:
    a = Grid.from_list([[1, 2], [3, 4]])
    b = Grid.from_list([[1, 2], [3, 4]])
    c = Grid.from_list([[1, 2], [3, 5]])
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert len({a, b, c}) == 2


def test_roundtrip_to_list() -> None:
    rows = [[0, 9], [5, 5]]
    assert Grid.from_list(rows).to_list() == rows


def test_to_text() -> None:
    assert Grid.from_list([[0, 1], [2, 3]]).to_text() == "01\n23"


@pytest.mark.parametrize(
    "bad",
    [
        [],  # empty
        [[]],  # empty row
        [1, 2, 3],  # 1-D
        [[0, 1], [2, 10]],  # out of range high
        [[0, -1]],  # out of range low
    ],
)
def test_invalid_grids_rejected(bad: object) -> None:
    with pytest.raises(ValueError):
        Grid(bad)  # type: ignore[arg-type]
