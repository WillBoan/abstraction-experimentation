"""Library serialisation: round-trip base + learned libraries; the content-addressed store."""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.cells import CELL_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Input, Param
from arc_lab.solvers.dsl.substrate.store import library_hash, load_library, save_library
from arc_lab.solvers.dsl.substrate.types import GRID


def _learned_library() -> Library:
    # transpose(flip_h(#0)) — the codebase's canonical learned rot90 (mirrors a wake_sleep mint).
    template = Apply("transpose", (Apply("flip_h", (Param(0, GRID),)),))
    learned = make_abstraction("abs0", template, D4_LIBRARY)
    return D4_LIBRARY.extended(name="d4+abs0", extra=(learned,))


def test_base_library_round_trips_by_identity() -> None:
    # Base primitives resolve to their singleton objects, so the library reconstructs equal.
    for lib in (D4_LIBRARY, CELL_LIBRARY, BUILD_AFFINE_LIBRARY):
        assert Library.from_dict(lib.to_dict()) == lib


def test_learned_library_round_trips() -> None:
    lib = _learned_library()
    restored = Library.from_dict(lib.to_dict())
    # Structural: the serialised form is stable across the round trip.
    assert restored.to_dict() == lib.to_dict()
    # Behavioural: the reconstructed abstraction computes what the original did.
    grid = Grid.from_list([[1, 2], [3, 4]])
    prog = Apply("abs0", (Input(),))
    assert prog.evaluate_grid(grid, restored) == prog.evaluate_grid(grid, lib)


def test_store_save_load_is_idempotent(tmp_path: Path) -> None:
    lib = _learned_library()
    digest = save_library(lib, store_dir=tmp_path)
    assert (tmp_path / f"{digest}.json").is_file()
    assert load_library(digest, store_dir=tmp_path).to_dict() == lib.to_dict()
    assert save_library(lib, store_dir=tmp_path) == digest  # same content -> same hash
    assert library_hash(lib) == digest


def test_unknown_base_primitive_raises() -> None:
    bad = {
        "name": "x",
        "version": 1,
        "primitives": [
            {
                "name": "nonesuch",
                "param_types": ["grid"],
                "return_type": "grid",
                "variadic_param": None,
            }
        ],
    }
    with pytest.raises(KeyError):
        Library.from_dict(bad)
