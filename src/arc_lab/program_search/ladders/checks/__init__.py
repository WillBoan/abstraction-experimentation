"""The ladder lint: every static well-formedness check a `.ladder` file is held to.

One module per concern, mirroring the layering the checks already had inside the old monolithic
``LadderSpec.lint()``:

- ``evaluation`` -- the three expensive evaluation-backed cores (constancy, conditionals,
  equational rewrite), independently unit-testable and free of the check machinery.

Later commits in this phase add the shared ``LadderCheck`` parent class, the lazily-derived
``CheckContext`` every check reads, and the explicit ``CHECK_PLAN`` that orders them.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.checks.evaluation import (
    conditional_findings,
    constancy_findings,
    rewrite_findings,
)

__all__ = ["conditional_findings", "constancy_findings", "rewrite_findings"]
