"""Content-addressed library store: ``libraries/<hash>.json``, hashed by canonical ``to_dict``.

A library's identity is a content hash of its serialised form, so equal libraries share one file.
A run spec references its starting library by that hash, and the store materialises it once. Base
atoms round-trip through the substrate registry; learned abstractions round-trip through their
templates (see :meth:`~arc_lab.solvers.program_search.substrate.library.Library.from_dict`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arc_lab.program_search.substrate.library import Library


def library_hash(library: Library) -> str:
    """Deterministic content hash (16 hex) of a library's serialised form."""
    payload = json.dumps(library.to_dict(), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def save_library(library: Library, *, store_dir: Path) -> str:
    """Write ``library`` into the content-addressed store; return its hash (idempotent)."""
    digest = library_hash(library)
    store_dir.mkdir(parents=True, exist_ok=True)
    path = store_dir / f"{digest}.json"
    if not path.exists():
        path.write_text(json.dumps(library.to_dict(), indent=2) + "\n", encoding="utf-8")
    return digest


def load_library(digest: str, *, store_dir: Path) -> Library:
    """Reconstruct a live library from the store by its hash."""
    path = store_dir / f"{digest}.json"
    if not path.is_file():
        raise FileNotFoundError(f"library {digest!r} not found in store {store_dir}")
    return Library.from_dict(json.loads(path.read_text(encoding="utf-8")))
