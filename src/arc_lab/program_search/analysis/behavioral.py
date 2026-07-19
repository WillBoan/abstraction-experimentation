"""Behavioral equivalence of learned primitives against a target template — shared by the study
report and the ladder rung-recovery report.

Grades an invented primitive against an intended abstraction by *behavior*, not syntax: identical
templates match immediately; otherwise both are evaluated over probe inputs (train-example grids
for GRID params; the full 0-9 range for COLOR; small canonical ranges for INT/BOOL) under every
type-compatible argument permutation, capped at :data:`MAX_PROBE_COMBOS` (reported, never silent).
Lifted out of ``execution/run_study.py`` so both readers use one implementation.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Primitive, Value
from arc_lab.program_search.substrate.types import BOOL, COLOR, GRID, INT, Type

#: Cap on probe-argument combinations per behavioral comparison. Deterministic (a prefix of the
#: probe product) and reported, so a capped check is visible, never silent.
MAX_PROBE_COMBOS = 512

_COLOR_PROBES: tuple[Value, ...] = tuple(range(10))  # the full COLOR domain
_INT_PROBES: tuple[Value, ...] = (0, 1, 2, 3, 4)
_BOOL_PROBES: tuple[Value, ...] = (False, True)


def matches_target(candidate: Primitive, target: Primitive, probe_grids: tuple[Grid, ...]) -> bool:
    """True iff ``candidate`` behaves as ``target`` — syntactic identity, else probing.

    Identical templates match immediately. Otherwise both are applied to probe-argument tuples
    under every argument permutation that lines the types up — a factoring that merely reorders its
    parameters is still the target. Variadic primitives (no fixed arity to probe) match by template
    identity only. A parameter type with no probe source (arrow / parametric container) likewise
    falls back to template identity — extend the probe sources when such targets become expressible.
    """
    if candidate.template is not None and candidate.template == target.template:
        return True
    if candidate.return_type != target.return_type:
        return False
    if candidate.is_variadic or target.is_variadic:
        return False  # template-identity fallback already tried
    if len(candidate.param_types) != len(target.param_types):
        return False
    per_param: list[tuple[Value, ...]] = []
    for param_type in target.param_types:
        values = _probe_values(param_type, probe_grids)
        if values is None or not values:
            return False  # some parameter is not probeable
        per_param.append(values)
    probe_tuples = list(itertools.islice(itertools.product(*per_param), MAX_PROBE_COMBOS))
    for permutation in _type_matched_permutations(candidate.param_types, target.param_types):
        if all(_agree(candidate, target, permutation, args) for args in probe_tuples):
            return True
    return False


def _probe_values(param_type: Type, probe_grids: tuple[Grid, ...]) -> tuple[Value, ...] | None:
    if param_type == GRID:
        return probe_grids
    if param_type == COLOR:
        return _COLOR_PROBES
    if param_type == INT:
        return _INT_PROBES
    if param_type == BOOL:
        return _BOOL_PROBES
    return None


def _type_matched_permutations(
    candidate_params: tuple[Type, ...], target_params: tuple[Type, ...]
) -> Iterator[tuple[int, ...]]:
    """Permutations ``p`` with ``candidate_params[i] == target_params[p[i]]``, identity first."""
    for permutation in itertools.permutations(range(len(target_params))):
        if all(candidate_params[i] == target_params[j] for i, j in enumerate(permutation)):
            yield permutation


def _agree(
    candidate: Primitive,
    target: Primitive,
    permutation: tuple[int, ...],
    args: tuple[Value, ...],
) -> bool:
    """Both impls succeed and produce equal values on ``args`` (candidate's reordered)."""
    try:
        expected = target.impl(*args)
        actual = candidate.impl(*(args[j] for j in permutation))
    except Exception:  # a probe outside either impl's domain is a disagreement
        return False
    result: bool = expected == actual
    return result
