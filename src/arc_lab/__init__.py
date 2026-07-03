"""arc-lab: a sandbox for ARC-AGI experimentation and abstraction formation.

The package is organised so that solvers are pluggable strangers behind one
narrow interface (:mod:`arc_lab.solvers.base`). Everything else — the domain
model, the scorer, the runner, the visualiser — is solver-agnostic, so adding a
new approach never touches the harness.
"""

from arc_lab.core import Dataset, Example, Grid, Task, load_dataset

__all__ = ["Dataset", "Example", "Grid", "Task", "load_dataset"]
__version__ = "0.1.0"
