"""Concrete primitive libraries.

Each module here defines a group of related primitives and, optionally, a
ready-made :class:`~arc_lab.solvers.program_search.substrate.library.Library` bundling them.
Solvers pick a library to search over.
"""

from arc_lab.solvers.program_search.substrate.primitives.control import CONTROL_PRIMITIVES
from arc_lab.solvers.program_search.substrate.primitives.geometry import D4_LIBRARY

__all__ = ["CONTROL_PRIMITIVES", "D4_LIBRARY"]
