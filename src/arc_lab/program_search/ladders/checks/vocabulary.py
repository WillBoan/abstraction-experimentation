"""Vocabulary (V): is the declared floor actually reachable by THIS machinery?

A config-coherence question, not a library question. A higher-order floor primitive whose holes the
configured engine can never fill is not rejected -- it is silently skipped, costing exactly nothing
-- so the ladder runs clean and never once exercises the capability it declares.

(The sibling coherence question for BRANCHING -- a template that branches over a floor lacking the
``if`` summoner -- is a load error raised at the conditional in ``ladders/lang/expr.py``, so a
branch is unreachable only if the ladder does not load at all.)
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.types import ArrowType, Type, TypeVar


class HofHolesFillable(LadderCheck):
    code = "hof-holes-fillable"
    category = Category.VOCABULARY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "Every higher-order floor primitive has fillable holes under this config."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        engine = ctx.spec.reference_config.search_engine
        for detail in unfillable_function_holes(ctx.spec.floor(), engine):
            yield self.finding(
                False,  # one finding per affected primitive: all failures
                f"declared but unfillable: {detail}",
            )


def unfillable_function_holes(library: Library, engine: object) -> tuple[str, ...]:
    """Floor primitives whose FUNCTION HOLES cannot be filled under this engine's policies.

    A higher-order primitive whose hole can never be filled is not an error the engine reports --
    it is simply skipped, costing exactly nothing (measured 2026-07-22, micro-probes battery E:
    ``map @ none`` is byte-identical to a floor without ``map``). So a ladder can declare a
    higher-order floor, run clean, and never once exercise it. Two ways that happens:

    - ``function_hole_fill_mode='none'`` -- no hole is ever filled, point-free or synthesized.
    - ``unpinned_type_var_mode='reject'`` (the default in EVERY preset) with lambda synthesis on --
      a hole whose ultimate RESULT type is a type variable that no ordinary sibling argument pins
      cannot have its binder type resolved, so synthesis is skipped for it and only pooled
      function values remain. ``map : ((a) -> b, list[a]) -> list[b]`` is the case in point: ``a``
      is pinned by ``list[a]``, ``b`` by nothing. Measured: relaxing the mode moves ``map`` from
      140 to 625 considered at depth 3 while ``filter``/``fold`` (pinned hole results) do not move
      at all.

    Returns one ``"name: reason"`` per affected primitive, sorted.
    """
    fill_mode = getattr(engine, "function_hole_fill_mode", "none")
    unpinned_mode = getattr(engine, "unpinned_type_var_mode", "reject")
    findings: list[str] = []
    for primitive in library.primitives:
        arrows = [t for t in primitive.param_types if isinstance(t, ArrowType)]
        if not arrows:
            continue
        if fill_mode == "none":
            findings.append(f"{primitive.name}: function_hole_fill_mode='none' fills no hole")
            continue
        if fill_mode != "lambda-synthesis" or unpinned_mode != "reject":
            continue
        pinned = {
            name
            for t in primitive.param_types
            if not isinstance(t, ArrowType)
            for name in _type_vars(t)
        }
        loose = sorted(
            str(_final_result(arrow))
            for arrow in arrows
            if isinstance(_final_result(arrow), TypeVar) and str(_final_result(arrow)) not in pinned
        )
        if loose:
            findings.append(
                f"{primitive.name}: hole result {', '.join(loose)} is pinned by no sibling "
                "argument, so unpinned_type_var_mode='reject' skips synthesis (point-free fill "
                "only)"
            )
    return tuple(sorted(findings))


def _final_result(vtype: Type) -> Type:
    """An arrow's ultimate result, chasing curried arrows (``(a) -> (b) -> c`` gives ``c``)."""
    while isinstance(vtype, ArrowType):
        vtype = vtype.result
    return vtype


def _type_vars(vtype: Type) -> set[str]:
    """Every :class:`TypeVar` name occurring anywhere in ``vtype``."""
    if isinstance(vtype, TypeVar):
        return {vtype.name}
    if isinstance(vtype, ArrowType):
        return {*_type_vars(vtype.result), *(n for p in vtype.params for n in _type_vars(p))}
    return {name for arg in getattr(vtype, "args", ()) for name in _type_vars(arg)}
