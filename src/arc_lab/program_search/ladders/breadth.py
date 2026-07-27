"""The floor-breadth census: what a rung's search space costs in WIDTH, computed, never run.

The depth sandwich prices one axis (rounds of composition). This prices the other
([BREADTH-AXIS-2026-07-24.md]): how many choices each round has. Both are needed, because cost goes
as ``(choices)^(rounds)`` -- and the 2026-07-25 ``dae9d2b5`` build spent hours treating a breadth
problem as a depth one, with the attribution data sitting unread the whole time.

Two exact quantities per rung, both pure functions of ``(grids, library, constant_sources)``:

- **the constant battery**, per type -- ``leaves.policy_constants`` gates each base type on whether
  ANY primitive in the library mentions it (``_type_in_use``), so a floor carrying one
  ``COLOR``-taking primitive mints all ten colours for every rung, including rungs that never take
  a colour. Reported against what the rung's own program actually uses, which is the "10 minted,
  0 used" line that makes a fat floor obvious.
- **round-1 composition counts**, under four prunings -- the same typed-census model the cost
  forecaster runs on (``execution/forecast_cost.round_terms``), so variadic arities and polymorphic
  slots are handled exactly as the engine handles them.

**An indicator, never a prediction.** Round 1 is exact, and it UNDERSTATES badly, because the tax
compounds with depth. Calibration point (``dae9d2b5-halves-union`` rung 1): this census reads
**1,211x** at round 1; the probe MEASURED **~5.3e6** at depth 3. Round 1 understated the real tax
about 4,000-fold -- and still made the defect obvious in a second, which is the whole point. Read
these numbers to RANK floors and to compare a ladder against itself, never as a forecast of what a
run will cost. The probe's ``FloorTax`` measures; this estimates -- and says which it is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from arc_lab.core.grid import Grid
from arc_lab.program_search.execution.forecast_cost import round_terms
from arc_lab.program_search.search.leaves import ConstantSource, policy_constants
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Const, Program
from arc_lab.program_search.substrate.types import GRID, Type


@dataclass(frozen=True, slots=True)
class TypeBattery:
    """One base type's constant leaves: how many the floor mints, how many the rung needs."""

    type_name: str
    minted: int
    used: int
    #: The floor primitives whose signatures put this type "in use", i.e. why it is minted at all.
    minted_because: tuple[str, ...]

    @property
    def wasted(self) -> int:
        return max(0, self.minted - self.used)


@dataclass(frozen=True, slots=True)
class RungBreadth:
    """One rung's breadth reading, at the level its search actually runs at.

    The four round-1 corners differ in WHAT is pruned, and are all exact:

    - ``b1_full`` -- the floor as the climb has it.
    - ``b1_primitive_pruned`` -- only the primitives the rung's program references. Constants fall
      with them for free (a dropped type stops being minted).
    - ``b1_constant_pruned`` -- the full primitive set, but only the constant VALUES the program
      uses.
    - ``b1_min`` -- both. The irreducible round-1 width of this rung on this floor.

    ``b1_full - b1_min`` does NOT split into the two single-pruning taxes: the marginals overlap,
    because dropping a primitive can also drop the type that made its constants mintable.
    """

    level: int
    name: str
    battery: tuple[TypeBattery, ...]
    b1_full: int
    b1_primitive_pruned: int
    b1_constant_pruned: int
    b1_min: int
    kept: tuple[str, ...]
    dropped: tuple[str, ...]

    @property
    def ratio(self) -> float | None:
        """``b1_full / b1_min`` -- the round-1 breadth tax as a factor."""
        return None if self.b1_min <= 0 else self.b1_full / self.b1_min

    @property
    def wasted_constants(self) -> int:
        return sum(entry.wasted for entry in self.battery)


def rung_breadth(
    level: int,
    name: str,
    library: Library,
    program: Program,
    grids: Sequence[Grid],
    constant_sources: tuple[ConstantSource, ...],
    max_arity: int,
) -> RungBreadth:
    """Price ``program``'s round-1 search width over ``library``, four ways.

    ``program`` is the rung's DEMONSTRATION TARGET over ``L_{i-1}`` -- what the wake actually
    searches for -- so both the primitive set and the constant values are read off the thing that
    has to be found. ``grids`` are that demonstration's train inputs (the constant battery is a
    function of grid size).
    """
    pruned = _prune(library, program)
    used = _constants_used(program)

    battery = _battery(grids, constant_sources, library, used)
    leaves_full = _leaf_census(grids, constant_sources, library)
    leaves_pruned = _leaf_census(grids, constant_sources, pruned)
    leaves_needed = _needed_census(used)

    return RungBreadth(
        level=level,
        name=name,
        battery=battery,
        b1_full=_round_one(library, leaves_full, max_arity),
        b1_primitive_pruned=_round_one(pruned, leaves_pruned, max_arity),
        b1_constant_pruned=_round_one(library, leaves_needed, max_arity),
        b1_min=_round_one(pruned, leaves_needed, max_arity),
        kept=tuple(sorted(pruned.names())),
        dropped=tuple(sorted(set(library.names()) - set(pruned.names()))),
    )


def _round_one(library: Library, census: Mapping[Type, int], max_arity: int) -> int:
    return sum(count for _, count in round_terms(library, census, max_arity))


def _leaf_census(
    grids: Sequence[Grid], sources: tuple[ConstantSource, ...], library: Library
) -> dict[Type, int]:
    """Round-0 leaves per type: the input grid plus the DISTINCT policy constants.

    Distinct, not raw yield: two sources can mint the same literal and the pool dedups them, which
    is the same correction ``forecast_cost`` makes for the same reason.
    """
    census: dict[Type, int] = {GRID: 1}  # `Input()`; no bound variables at the top level
    seen: set[Program] = set()
    for leaf, leaf_type in policy_constants(grids, sources, library):
        if leaf in seen:
            continue
        seen.add(leaf)
        census[leaf_type] = census.get(leaf_type, 0) + 1
    return census


def _needed_census(used: Mapping[Type, set[object]]) -> dict[Type, int]:
    """The census a value-level allowlist would give: the input grid plus only the values used."""
    census: dict[Type, int] = {GRID: 1}
    for value_type, values in used.items():
        census[value_type] = census.get(value_type, 0) + len(values)
    return census


def _constants_used(program: Program) -> dict[Type, set[object]]:
    """The distinct constant VALUES the program contains, bucketed by type."""
    used: dict[Type, set[object]] = {}
    for node in program.walk():
        if isinstance(node, Const):
            used.setdefault(node.value_type, set()).add(node.value)
    return used


def _battery(
    grids: Sequence[Grid],
    sources: tuple[ConstantSource, ...],
    library: Library,
    used: Mapping[Type, set[object]],
) -> tuple[TypeBattery, ...]:
    """Per type: how many constants the floor mints, how many this rung uses, and which primitives
    put the type in use (so a fat battery names the primitive responsible)."""
    minted: dict[Type, int] = {}
    seen: set[Program] = set()
    for leaf, leaf_type in policy_constants(grids, sources, library):
        if leaf in seen:
            continue
        seen.add(leaf)
        minted[leaf_type] = minted.get(leaf_type, 0) + 1
    return tuple(
        TypeBattery(
            type_name=_type_name(value_type),
            minted=count,
            used=len(used.get(value_type, ())),
            minted_because=_mentions(library, value_type),
        )
        for value_type, count in sorted(minted.items(), key=lambda item: _type_name(item[0]))
    )


def _mentions(library: Library, value_type: Type) -> tuple[str, ...]:
    """Floor primitives whose signature mentions ``value_type`` -- why its battery is minted.

    Deliberately the SHALLOW reading (top-level parameter and return types), not
    ``leaves._type_in_use``'s full nested occurrence check: this is an explanation for a human
    ("`map_color` is why you have ten colours"), and a type buried inside a higher-order hole is
    not the answer anyone is looking for. The COUNT above always comes from the real gate.
    """
    return tuple(
        sorted(
            primitive.name
            for primitive in library.primitives
            if value_type in primitive.param_types or primitive.return_type == value_type
        )
    )


def _prune(library: Library, program: Program) -> Library:
    from arc_lab.program_search.ladders.probe import prune_library

    return prune_library(library, program)


def _type_name(value_type: Type) -> str:
    return getattr(value_type, "name", str(value_type))
