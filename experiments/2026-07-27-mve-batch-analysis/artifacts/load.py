"""Shared loader for the batch analysis: every committed ladder report, plus its static lint."""
from __future__ import annotations
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
LADDERS = ROOT / "docs" / "abstraction_ladders" / "ladders"

#: The real-ARC MVE members, by task. Everything else in the register is synthetic (al1-al21).
REAL = {
    "dae9d2b5": ["dae9d2b5-split-halves-lean", "dae9d2b5-split-asym-lean",
                 "dae9d2b5-split-recolor-lean", "dae9d2b5-split-recolor"],
    "94f9d214": ["94f9d214-nor-halves", "94f9d214-nor-recolor"],
    "fafffa47": ["fafffa47-nor-halves", "fafffa47-nor-recolor"],
}
REAL_NAMES = {n for v in REAL.values() for n in v}


def reports() -> dict[str, dict]:
    out = {}
    for p in sorted(LADDERS.glob("*/report.json")):
        out[p.parent.name] = json.loads(p.read_text())
    return out


def is_real(name: str) -> bool:
    return name in REAL_NAMES


def kind(name: str) -> str:
    return "real" if is_real(name) else "synthetic"
