"""Library learning: the wake-sleep loop that invents abstractions from solved programs.

This package sits atop `search` (wake) and `analysis` (the compression governance + run
artifacts), and grows a `Library` via `Library.extended`. It never touches the narrow
`Solver.predict` contract — learning is a meta-process over solvers, not a solver.

* :mod:`antiunify` — propose abstraction candidates (least-general-generalization).
* :mod:`selection` — governance: which candidate earns a name (the `AbstractionSelector` plug point).
* :mod:`loop` — the wake-sleep generations orchestrating proposer + selector.
* :mod:`harness` — the three-library comparison + behavioral (observational) checker.
* :mod:`taskgen` — deterministic synthetic testbeds (tasks + recipe manifest).
"""

from arc_lab.solvers.dsl.learn.antiunify import AbstractionProposer, AntiunifyPairs
from arc_lab.solvers.dsl.learn.harness import (
    CheckResult,
    check_abstractions,
    compare_libraries,
    enablement_transfer,
)
from arc_lab.solvers.dsl.learn.loop import (
    EachGeneration,
    GenerationRecord,
    LearnResult,
    LearnTrigger,
    learn,
    wake_sleep,
)
from arc_lab.solvers.dsl.learn.selection import AbstractionSelector, GreedyMDL
from arc_lab.solvers.dsl.learn.taskgen import GeneratedTask, make_task, write_testbed

__all__ = [
    "AbstractionProposer",
    "AbstractionSelector",
    "AntiunifyPairs",
    "CheckResult",
    "EachGeneration",
    "GeneratedTask",
    "GenerationRecord",
    "GreedyMDL",
    "LearnResult",
    "LearnTrigger",
    "check_abstractions",
    "compare_libraries",
    "enablement_transfer",
    "learn",
    "make_task",
    "wake_sleep",
    "write_testbed",
]
