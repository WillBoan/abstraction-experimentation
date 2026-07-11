"""Library learning: the sleep side of wake-sleep — inventing abstractions from solved programs.

This package sits atop `search` (wake) and `analysis` (compression governance), and grows a
`Library` via `Library.extended`. The wake-sleep *loop* lives in the execution layer
(`run_search_learn`, per EXECUTION.md); this package owns one *sleep*:

* :mod:`learn_engine` — the :class:`LearnEngine` ABC + :class:`LearnOutcome` (Sync C).
* :mod:`engines` — concrete engines: :class:`GreedyMDLLearnEngine`, :class:`RefactoringLearnEngine`.
* :mod:`antiunify` — propose abstraction candidates (least-general-generalization).
* :mod:`selection` — governance: which candidate earns a name (the `AbstractionSelector` plug point).
* :mod:`stitch_shim` — the sole Stitch boundary: s-expression codec + :class:`StitchProposer`.
"""

from arc_lab.program_search.learn.antiunify import (
    AbstractionProposer,
    AntiunifyPairs,
    FrequentSubtree,
    SearchScopedFrequentSubtree,
    TypeScopedFrequentSubtree,
    match,
    rewrite_with,
)
from arc_lab.program_search.learn.engines import (
    GreedyMDLLearnEngine,
    RefactoringLearnEngine,
    rewrite_library_definitions,
)
from arc_lab.program_search.learn.learn_engine import LearnEngine, LearnOutcome
from arc_lab.program_search.learn.selection import AbstractionSelector, GreedyMDL

__all__ = [
    "AbstractionProposer",
    "AbstractionSelector",
    "AntiunifyPairs",
    "FrequentSubtree",
    "GreedyMDL",
    "GreedyMDLLearnEngine",
    "LearnEngine",
    "LearnOutcome",
    "RefactoringLearnEngine",
    "SearchScopedFrequentSubtree",
    "TypeScopedFrequentSubtree",
    "match",
    "rewrite_library_definitions",
    "rewrite_with",
]
