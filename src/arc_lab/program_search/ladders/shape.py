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
    #: Inlined depth of the *next* rung over ``L_{i-1}`` (this rung's calls expanded one level);
    #: ``None`` for the last bridging rung (its "next" is the abstraction-less Top).
    double_jump_depth: int | None
    #: Distinct lower rung names the template references, with multiplicity (fan-in > 1 ==
    #: recombining, fan-in == 1 == a telescope link).
    fan_in: int
    demonstration_count: int
    #: ``True`` if the template contains a ``Lam`` -> depth checks are advisory (HO sub-search).
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
    findings: tuple[LintFinding, ...]

    @property
    def ok(self) -> bool:
        """True iff no error-severity finding fired."""
        return all(finding.ok for finding in self.findings if finding.severity == "error")
