"""``LadderCheck``: the shared parent class every static ladder check subclasses.

One check is one class. Its identity and metadata are ``ClassVar``s in the class body -- the code
it reports under, which family it belongs to, what model it reads (its :class:`CheckStage`), the
severity it defaults to, and a one-line summary -- and its logic is the single abstract
:meth:`LadderCheck.run`. Metadata and logic sit together, so a check cannot exist without a code,
and a code cannot drift from the check that emits it.

Checks are *instances* held in an explicit ordered tuple (``checks/plan.py::CHECK_PLAN``), the
same machinery-as-data shape as ``PRESETS`` and ``STUDIES``: no decorator registry, no
subclass-discovery, no import-order dependence. Order is a value you can read.

A check yields :class:`~..shape.LintFinding`\\ s through :meth:`Check.finding`, which stamps the
code and default severity from the class body. Yielding *nothing* is a legitimate result for the
advisory checks that speak only when they have something to say.

Two families, split by what they read: :class:`DocumentCheck` is a pure predicate over the parsed
document (``stage=SYNTAX``, runs before resolution, so it can speak about a file that will never
load), and :class:`LadderCheck` reads a resolved spec through the :class:`~.context.CheckContext`.
:class:`Check` is what they share.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from arc_lab.program_search.ladders.diagnostics import Range
from arc_lab.program_search.ladders.shape import LintFinding, Occurrence

if TYPE_CHECKING:
    from arc_lab.program_search.ladders.checks.context import CheckContext
    from arc_lab.program_search.ladders.lang.parse import LadderDocument


@dataclass(frozen=True, slots=True)
class Verdict:
    """One check outcome BEFORE it is stamped with the code of the check that owns it.

    What the expensive evaluation-backed cores in :mod:`..checks.evaluation` return. They are plain
    functions over plain data -- deliberately ignorant of the check machinery -- so they say what
    they found (about which subject, at what severity) and the owning :class:`LadderCheck` supplies
    the code. That keeps the code declared in exactly one place: the class body.
    """

    #: The named entity this outcome is about (a rung, a task id) -- ``None`` for a file-level one.
    subject: str | None
    ok: bool
    detail: str
    #: Overrides the owning check's ``default_severity`` when the severity is itself a verdict.
    severity: str | None = None


class CheckStage(enum.Enum):
    """Which model a check reads -- and therefore when it can run at all.

    ``SYNTAX`` checks read the parsed ``LadderDocument`` alone, before anything is resolved against
    the substrate: they are pure predicates over what the file says. ``STRUCTURAL`` checks read the
    resolved templates, stated solutions, demonstration kinds and config -- everything a *draft*
    over assumed primitives has. ``CORPUS`` checks read the generated task grids or evaluate a
    subterm on them, so they cannot run before the primitives exist; they are skipped and named
    (``LadderShape.skipped_checks``) rather than silently dropped.
    """

    SYNTAX = "syntax"
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


class Check(ABC):
    """The shared parent of every ladder check: its identity, and how it states a finding.

    Two families descend from it, split by *what they read* -- :class:`DocumentCheck` over the
    parsed document, :class:`LadderCheck` over a resolved spec. Everything else about a check --
    the code it reports under, the family it belongs to, the severity it defaults to, how a finding
    is stamped -- is shared, and lives here.
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

    def finding(
        self,
        ok: bool,
        detail: str,
        *,
        subject: str | None = None,
        params: tuple[int, ...] = (),
        severity: str | None = None,
        anchor: Range | None = None,
    ) -> LintFinding:
        """One finding stamped with this check's code and default severity.

        ``subject`` names the entity the finding is about (a rung, a task id) and ``params`` narrows
        it to free-parameter positions -- together they become a structured
        :class:`~..shape.Occurrence`, not a slug string somebody has to parse back apart.

        ``severity`` overrides the class default for the checks whose severity is itself a
        *verdict* rather than a property of the check: ``constant-subterm`` (does the beating
        literal exist in this ladder's own search?) and ``proposer-compat`` (is the proposer's
        capability statically known?).

        ``anchor`` pins the finding to an exact source range. Only the ``SYNTAX`` checks set it
        (they hold the parsed document, so they know the span outright); a spec-level finding
        leaves it ``None`` and is anchored by subject lookup through the ``AnchorIndex`` instead.
        """
        return LintFinding(
            code=self.code,
            ok=ok,
            detail=detail,
            severity=severity if severity is not None else self.default_severity,
            occurrence=None if subject is None else Occurrence(subject, params),
            anchor=anchor,
        )

    def stamp(self, verdicts: Iterable[Verdict]) -> Iterator[LintFinding]:
        """Stamp this check's code onto the outcomes an evaluation core returned."""
        for verdict in verdicts:
            yield self.finding(
                verdict.ok,
                verdict.detail,
                subject=verdict.subject,
                severity=verdict.severity,
            )


class DocumentCheck(Check):
    """A check that is a pure predicate over the parsed document -- ``stage=SYNTAX``.

    These run BEFORE resolution, so they can speak about a file that will never load: duplicate
    names, an empty floor. That is exactly why they are worth separating -- the editor can report
    all of them at once with precise spans, where the strict loader can only raise the first.

    A rule belongs here only if it needs nothing but the document. Most load-time errors do not
    qualify: they are raised *while constructing* the library, elaborating a template or applying
    config, so there is no completed model to run a predicate over. Those become checks when the
    tolerant resolver (plan Phase E2) gives them one, not before.
    """

    stage: ClassVar[CheckStage] = CheckStage.SYNTAX

    @abstractmethod
    def run(self, document: LadderDocument) -> Iterator[LintFinding]:
        """Yield this check's findings about ``document`` -- zero or more, failures only."""


class LadderCheck(Check):
    """A check over a resolved :class:`~..spec.LadderSpec` -- ``stage=STRUCTURAL`` or ``CORPUS``.

    Subclasses set the ``ClassVar``s and implement :meth:`run`. Instances are stateless and
    shared -- all per-run state lives in the :class:`~.context.CheckContext` passed to ``run``.
    """

    @abstractmethod
    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        """Yield this check's findings -- passing and failing alike, zero or more."""
