"""The oracle-chain library builder: ``L_0 .. L_k``, gifting one intended rung at a time.

Shared by :class:`~arc_lab.program_search.ladders.spec.LadderSpec` (which needs the chain to lint
and to run the oracle columns) and by the ladder task generators (which need ``L_{i-1}`` to
*evaluate* rung ``i``'s template when generating its demonstrating tasks). Keeping one builder means
the libraries a ladder is linted against are the same ones its tasks were generated against.
"""

from __future__ import annotations

from collections.abc import Sequence

from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program


def oracle_libraries(floor: Library, rungs: Sequence[tuple[str, Program]]) -> tuple[Library, ...]:
    """``(L_0, .., L_k)`` -- index ``i`` is the Floor plus the intended rungs ``r_1..r_i`` gifted.

    Each rung's template is resolved over the library immediately below it, so a template may refer
    to the rung beneath by name (exactly the canonical form sleep is expected to mint).
    """
    libraries = [floor]
    for name, template in rungs:
        below = libraries[-1]
        primitive = make_abstraction(name, template, below)
        libraries.append(below.extended(name=f"{below.name}+{name}", extra=(primitive,)))
    return tuple(libraries)
