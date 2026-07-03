"""LLM-based solvers.

These solvers serialise the grids to text and ask a language model to induce the
transformation rule and emit the test output. Requires the optional ``anthropic``
dependency: install with ``uv sync --extra llm``.
"""

from arc_lab.solvers.llm.claude import ClaudeSolver

__all__ = ["ClaudeSolver"]
