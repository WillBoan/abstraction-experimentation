"""arc-lab: a sandbox for ARC-AGI experimentation and abstraction formation.

Machinery is data: there are no solver classes. A run is a frozen, content-hashed
``RunSpec = Config x Corpus``, and :mod:`arc_lab.program_search.execution` drives the
``Config`` directly — so an experiment is a value, not a subclass. The domain model
(:mod:`arc_lab.core`), the scorer (:mod:`arc_lab.eval`) and the visualiser
(:mod:`arc_lab.viz`) are all downstream of it.
"""

from arc_lab.core import Corpus, Example, Grid, Task, load_dataset

__all__ = ["Corpus", "Example", "Grid", "Task", "load_dataset"]
__version__ = "0.1.0"
