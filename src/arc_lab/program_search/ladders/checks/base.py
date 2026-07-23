"""``LadderCheck``: the shared parent class every static ladder check subclasses.

One check is one class. Its identity and metadata are ``ClassVar``s in the class body -- the code
it reports under, which family it belongs to, what model it reads (its :class:`CheckStage`), the
severity it defaults to, and a one-line summary -- and its logic is the single abstract
:meth:`LadderCheck.run`. Metadata and logic sit together, so a check cannot exist without a code,
and a code cannot drift from the check that emits it.

Checks are *instances* held in an explicit ordered tuple (``checks/plan.py::CHECK_PLAN``), the
same machinery-as-data shape as ``PRESETS`` and ``STUDIES``: no decorator registry, no
subclass-discovery, no import-order dependence. Order is a value you can read.

A check reads one thing -- the :class:`~.context.CheckContext` -- and yields
:class:`~..shape.LintFinding`\\ s through :meth:`LadderCheck.finding`, which stamps the code and
default severity from the class body. Yielding *nothing* is a legitimate result for the advisory
checks that speak only when they have something to say.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from arc_lab.program_search.ladders.shape import LintFinding

if TYPE_CHECKING:
    from arc_lab.program_search.ladders.checks.context import CheckContext


@dataclass(frozen=True, slots=True)
class Verdict:
    """One check outcome BEFORE it is stamped with the code of the check that owns it.

    What the expensive evaluation-backed cores in :mod:`..checks.evaluation` return. They are plain
    functions over plain data -- deliberately ignorant of the check machinery -- so they say what
    they found (about which subject, at what severity) and the owning :class:`LadderCheck` supplies
    the code. That keeps the code declared in exactly one place: the class body.
    """

    #: The subject this outcome is about (a rung name, a task id), or ``None`` for a file-level one.
    occurrence: str | None
    ok: bool
    detail: str
    #: Overrides the owning check's ``default_severity`` when the severity is itself a verdict.
    severity: str | None = None


class CheckStage(enum.Enum):
    """Which model a check reads -- and therefore when it can run at all.

    ``STRUCTURAL`` checks read only templates, stated solutions, demonstration kinds and config:
    everything a *draft* over assumed primitives has. ``CORPUS`` checks read the generated task
    grids or evaluate a subterm on them, so they cannot run before the primitives exist; they are
    skipped and named (``LadderShape.skipped_checks``) rather than silently dropped.
    """

    STRUCTURAL = "structural"
    CORPUS = "corpus"


class Category(enum.Enum):
    """The check family, as the design doc groups them (the letters used in its section names)."""

    STRUCTURE = "S"  # levels, reachability, distinctness -- is this a ladder at all?
    DEPTH = "D"  # the tractability sandwich: every affordability / intractability claim
    LEARNABILITY = "L"  # can the configured proposer + governance actually mint the rung?
    DEMONSTRATION = "P"  # what the tasks themselves show: variation, degeneracy, collapse
    ADVISORY = "A"  # shape observations that are not defects
    VOCABULARY = "V"  # config coherence: is the declared floor reachable by this machinery?


class LadderCheck(ABC):
    """One static check over a :class:`~..spec.LadderSpec`.

    Subclasses set the ``ClassVar``s and implement :meth:`run`. Instances are stateless and
    shared -- all per-run state lives in the :class:`~.context.CheckContext` passed to ``run``.
    """

    #: The stable slug this check reports under. Per-subject findings append ``[occurrence]``.
    code: ClassVar[str]
    #: The design-doc family this check belongs to.
    category: ClassVar[Category]
    #: The model this check reads -- and the tier it is gated behind.
    stage: ClassVar[CheckStage]
    #: Severity for findings that do not override it. ``"error"`` fails the lint; ``"warn"`` does
    #: not (``LadderShape.ok`` counts only failed errors).
    default_severity: ClassVar[str] = "error"
    #: One line, for the generated check register and editor hovers.
    summary: ClassVar[str]

    @abstractmethod
    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        """Yield this check's findings -- passing and failing alike, zero or more."""

    def finding(
        self,
        ok: bool,
        detail: str,
        *,
        occurrence: str | None = None,
        severity: str | None = None,
    ) -> LintFinding:
        """One finding stamped with this check's code and default severity.

        ``occurrence`` names the subject (a rung, a task id, a parameter position); ``severity``
        overrides the class default for the checks whose severity is a *verdict*, not a property of
        the check -- ``constant-subterm`` (does the beating literal exist in this ladder's own
        search?) and ``proposer-compat`` (is the proposer's capability statically known?).
        """
        return LintFinding(
            check=self.code if occurrence is None else f"{self.code}[{occurrence}]",
            ok=ok,
            detail=detail,
            severity=severity if severity is not None else self.default_severity,
        )

    def stamp(self, verdicts: Iterable[Verdict]) -> Iterator[LintFinding]:
        """Stamp this check's code onto the outcomes an evaluation core returned."""
        for verdict in verdicts:
            yield self.finding(
                verdict.ok,
                verdict.detail,
                occurrence=verdict.occurrence,
                severity=verdict.severity,
            )
