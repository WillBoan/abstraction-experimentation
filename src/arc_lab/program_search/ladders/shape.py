"""``LadderShape``: the static, derived shape of a Ladder — the output of ``LadderSpec.lint()``.

Everything here is computed from ``(LadderSpec, reference config)`` by the substrate atoms
(``compositional_depth`` / ``unfold_program``) and simple corpus reads — never a search, never run
identity. Kept as its own type (chosen vs derived, mirroring ``RunSpec`` vs ``RunRecord``): the
report, certificate, and pretty-printer all consume these quantities together.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.ladders.diagnostics import Range


@dataclass(frozen=True, slots=True)
class Occurrence:
    """What a finding is ABOUT, structurally -- never a string to be parsed back apart.

    ``subject`` is the named entity the finding anchors to: a rung name, a task id, a floor
    primitive. ``params`` narrows it to specific free-parameter positions (1-based), for the checks
    that speak about a rung's arguments rather than the rung itself.

    Its string form is the historical occurrence spelling -- ``rot180``, ``sym_both#1``,
    ``mirror_recolor#1,#2`` -- so slugs are unchanged; but nothing has to take that spelling apart
    again, which is what the editor's anchor lookup used to do.
    """

    subject: str
    params: tuple[int, ...] = ()

    def __str__(self) -> str:
        return f"{self.subject}{','.join(f'#{index}' for index in self.params)}"


@dataclass(frozen=True, slots=True)
class LintFinding:
    """One static check's result. ``severity`` is ``"error"`` (fails ``ok``) or ``"warn"``."""

    #: The stable code of the check that produced it -- see ``checks/plan.py::CHECK_PLAN``.
    code: str
    ok: bool
    detail: str
    severity: str = "error"
    #: The subject, when the check speaks about one; ``None`` for a whole-file finding.
    occurrence: Occurrence | None = None
    #: An EXACT source range, when the check knew one outright (the ``SYNTAX`` checks hold the
    #: parsed document, so they do). ``None`` means "anchor me by subject", which is what every
    #: spec-level check does -- it has no spans, only names.
    anchor: Range | None = None

    @property
    def slug(self) -> str:
        """``code`` or ``code[occurrence]`` -- the display spelling, for humans and locks."""
        return self.code if self.occurrence is None else f"{self.code}[{self.occurrence}]"


@dataclass(frozen=True, slots=True)
class RungShape:
    """The derived static quantities of one bridging rung."""

    level: int
    name: str
    #: ``compositional_depth`` of the rung TEMPLATE over ``L_{i-1}``: the program SLEEP must
    #: recover and mint. NOT the affordability quantity -- the wake searches for the rung's
    #: demonstrations, which is what ``jump_depth`` measures. The two coincide exactly when every
    #: demonstration is a full solution (wrapper depth 1), which is the common case.
    template_depth: int
    #: ``min_depth_limit`` of the template -- the mint-side twin of ``jump_needs``.
    template_needs: int
    #: ``compositional_depth`` of the DEEPEST demonstration target over ``L_{i-1}`` -- the program
    #: the WAKE at this rung actually searches for. Falls back to ``template_depth`` when the rung
    #: declares no demonstrations (a draft lint); ``depth_source`` says which.
    jump_depth: int
    #: ``min_depth_limit`` of the same: the smallest ``Budget.depth_limit`` that puts the rung's
    #: hardest demonstration in REACH. Equal to ``jump_depth`` for a first-order target; larger
    #: when a lambda body needs its own descended budget. Every affordability claim, and the
    #: validity window's lower bound, is stated in THIS one.
    jump_needs: int
    #: ``"demonstrations"``, or ``"template"`` when the rung declares none and the two fields above
    #: fell back. Named rather than silent: a template-sourced depth is an assumption, not a
    #: measurement of what the climb will search for.
    depth_source: str
    #: The demonstration ``jump_needs`` was taken from -- the one that binds. ``None`` under the
    #: template fallback.
    deepest_demonstration: str | None
    #: Inlined depth of the shallowest program above that calls this rung, with its calls expanded
    #: one level: a higher rung's DEMONSTRATION TARGET, or a top reference solution. What skipping
    #: this rung would cost in depth.
    double_jump_depth: int | None
    #: ``min_depth_limit`` of that same shallowest inlined program -- the quantity the validity
    #: window's upper bound is stated in (``double_jump_depth`` is the display number).
    double_jump_needs: int | None
    #: Calls the template makes to ANY lower rung, with multiplicity (floor primitives don't
    #: count): 0 = floor-only (typical for r_1), 1 throughout = pure telescope, > 1 = recombining.
    fan_in: int
    demonstration_count: int
    #: ``True`` if the template contains a ``Lam``. The depth claims still hold (they are stated
    #: in ``jump_needs`` / ``double_jump_needs``); what stays advisory is reachability under
    #: example propagation.
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
