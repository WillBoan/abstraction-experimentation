"""The content-addressed library store: round-trip by identity, idempotent save/load, and
rejection of an unknown base primitive on deserialisation. Ported from the pre-overhaul
``tests/test_library_store.py`` — the store module moved but had no direct new-world test."""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.build import BUILD_AFFINE_LIBRARY
from arc_lab.program_search.substrate.primitives.cells import CELL_LIBRARY
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.store import library_hash, load_library, save_library


def test_base_library_round_trips_by_identity() -> None:
    # Base primitives resolve to their singleton objects, so the library reconstructs equal.
    for lib in (D4_LIBRARY, CELL_LIBRARY, BUILD_AFFINE_LIBRARY):
        assert Library.from_dict(lib.to_dict()) == lib


def test_store_save_load_is_idempotent(tmp_path: Path) -> None:
    lib = D4_LIBRARY
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
