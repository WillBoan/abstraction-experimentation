"""The run data model: frozen, content-hashable specs + read-side records.

Layering rule (EXECUTION.md): this package holds only frozen data — importable by
anything; behaviour modules (`execute`, activities) import it, never the reverse.
"""

from arc_lab.program_search.execution.model.config import Config, default_registry
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.results import TaskResult, TaskScore
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.model.study_spec import StudySpec, TargetAbstraction

__all__ = [
    "Config",
    "LearnSpec",
    "RunRecord",
    "RunSpec",
    "StudySpec",
    "TargetAbstraction",
    "TaskResult",
    "TaskScore",
    "default_registry",
]
