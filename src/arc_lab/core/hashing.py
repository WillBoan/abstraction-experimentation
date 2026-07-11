"""Deterministic content hashing — the basis of run identity.

A ``run_id`` must be stable across processes and machines, so identity hashes a
*canonical* JSON serialisation (sorted keys, tight separators) rather than Python's
per-process salted ``hash()``. Anything that serialises to JSON-compatible data
(via ``to_dict`` / ``to_list``) can be hashed here.
"""

from __future__ import annotations

import hashlib
import json

#: Length of a content id: a sha256 prefix. 16 hex chars = 64 bits — collision-safe
#: for the corpus/config counts this project will ever see, short enough for dir names.
ID_LENGTH = 16


def canonical_json(data: object) -> str:
    """A stable JSON string for ``data``: sorted keys, no insignificant whitespace.

    ``data`` must be JSON-compatible (dict/list/str/int/float/bool/None); anything
    else raises ``TypeError`` — deliberately, so non-canonical objects (sets, live
    components) never silently hash by repr.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_id(data: object, *, length: int = ID_LENGTH) -> str:
    """A content-addressed id: sha256 of ``data``'s canonical JSON, truncated."""
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    return digest[:length]
