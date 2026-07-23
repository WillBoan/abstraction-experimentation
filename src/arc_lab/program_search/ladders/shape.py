"""``LadderShape``: the static, derived shape of a Ladder — the output of ``LadderSpec.lint()``.

Everything here is computed from ``(LadderSpec, reference config)`` by the substrate atoms
(``compositional_depth`` / ``unfold_program``) and simple corpus reads — never a search, never run
identity. Kept as its own type (chosen vs derived, mirroring ``RunSpec`` vs ``RunRecord``): the
report, certificate, and pretty-printer all consume these quantities together.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LintFinding:
    """One static check's result. ``severity`` is ``"error"`` (fails ``ok``) or ``"warn"``."""

    check: str
    ok: bool
    detail: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class RungShape:
    """The derived static quantities of one bridging rung."""

    level: int
    name: str
    #: ``compositional_depth`` of the rung template over ``L_{i-1}`` (affordable iff
    #: ``jump_depth <= Budget.depth_limit``).
    jump_depth: int
    #: ``min_depth_limit`` of the same template: the smallest ``Budget.depth_limit`` that puts it
    #: in REACH. Equal to ``jump_depth`` for a first-order template; larger when a lambda body
    #: needs its own descended budget. Every affordability claim is stated in THIS one.
    jump_needs: int
    #: Inlined depth of the layer above over ``L_{i-1}`` (this rung's calls expanded one level):
    #: the next rung's template, or -- for the last bridging rung -- the shallowest top reference
    #: solution. What skipping this rung would cost in depth.
    double_jump_depth: int | None
    #: Calls the template makes to ANY lower rung, with multiplicity (floor primitives don't
    #: count): 0 = floor-only (typical for r_1), 1 throughout = pure telescope, > 1 = recombining.
    fan_in: int
    demonstration_count: int
    #: ``True`` if the template contains a ``Lam``. The depth claims still hold (they are stated
    #: in ``jump_needs``); what stays advisory is reachability under example propagation.
    involves_lambda: bool


@dataclass(frozen=True, slots=True)
class LadderShape:
    """The whole Ladder's derived shape + the lint verdict."""

    height: int  # len(bridging rungs) + 1 (the Top)
    #: Per-top-task ``d_raw`` = ``compositional_depth`` of the reference solution unfolded to the
    #: floor (the top solutions can differ, so this is a profile, not a scalar).
    raw_depth_profile: tuple[int, ...]
    rungs: tuple[RungShape, ...]
    #: ``(lower, upper)`` — inclusive, in ``depth_limit`` units: the ``depth_limit`` values at
    #: which every jump is affordable and no inlined double-jump (nor the raw top) is reachable.
    #: Empty as ``(lo, hi)`` with ``lo > hi`` when no budget satisfies both (a degenerate ladder).
    validity_window: tuple[int, int]
    #: ``True`` iff the rung dependency edges form the simple spine ``r_1 <- ... <- r_k`` (each
    #: rung consumed only by its immediate successor). ``False`` is a DAG: a rung feeds more than
    #: one consumer, or a non-adjacent one. Derived, not declared -- a fact about the templates.
    is_chain: bool
    findings: tuple[LintFinding, ...]
    #: Check families NOT run because they need the task grids (``lint(corpus_backed=False)`` on a
    #: draft over assumed primitives). Empty on a full run. Named, never silently dropped, so a
    #: clean structural lint is never mistaken for a verified-sound ladder.
    skipped_checks: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True iff no error-severity finding fired."""
        return all(finding.ok for finding in self.findings if finding.severity == "error")
