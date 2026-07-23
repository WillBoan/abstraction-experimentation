"""The ladder lint: every static well-formedness check a `.ladder` file is held to.

One check is one :class:`~.base.LadderCheck` subclass -- code, family, stage and severity declared
as ``ClassVar``s in the class body, logic in ``run(ctx)`` -- and the lint is the explicit ordered
tuple of them in :data:`~.plan.CHECK_PLAN`. There is no registry to register with and no import
order to respect: the plan IS the order, the same machinery-as-data shape as ``PRESETS``.

Layering, bottom up:

- ``base`` -- the ``LadderCheck`` parent class, ``CheckStage``, ``Category``, ``Verdict``.
- ``graph`` -- the rung dependency graph (pure functions; also read by ``LadderSpec.render()``).
- ``evaluation`` -- the three expensive evaluation-backed cores (constancy, conditionals,
  equational rewrite), plain functions over plain data, independently unit-testable.
- ``context`` -- ``CheckContext``: everything the checks read, derived once and lazily.
- ``structure`` / ``depth`` / ``learnability`` / ``demonstrations`` / ``advisories`` /
  ``vocabulary`` -- the checks themselves, one module per family.
- ``plan`` -- ``CHECK_PLAN``, the order; ``run`` -- ``lint_spec``, the four-line runner.

Adding a check: write the subclass in its family's module and add an instance to ``CHECK_PLAN``.
Nothing else -- the skipped-checks list, the gating and the finding codes all follow from it.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.checks.base import (
    Category,
    CheckStage,
    LadderCheck,
    Verdict,
)
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.checks.evaluation import (
    conditional_verdicts,
    constancy_verdicts,
    rewrite_verdicts,
)
from arc_lab.program_search.ladders.checks.plan import CHECK_PLAN, CORPUS_CODES
from arc_lab.program_search.ladders.checks.run import lint_spec

__all__ = [
    "CHECK_PLAN",
    "CORPUS_CODES",
    "Category",
    "CheckContext",
    "CheckStage",
    "LadderCheck",
    "Verdict",
    "conditional_verdicts",
    "constancy_verdicts",
    "lint_spec",
    "rewrite_verdicts",
]
