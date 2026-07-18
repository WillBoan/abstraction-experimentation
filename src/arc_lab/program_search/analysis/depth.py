"""Compositional depth: the *generation-count* depth of a program (leaf = 0).

The one depth measure in the codebase (the old ``Program.depth()``, leaf = 1 and unused, was
removed to avoid two off-by-one conventions). This one matches the bottom-up engine's own
*generation* accounting: a leaf is generation 0, ``flip_h(input)`` is generation 1,
``flip_h(flip_v(input))`` is generation 2 (``SearchStats.solved_at_generation``). A program of
compositional depth ``d`` is first built at generation ``d`` and therefore needs
``budget.max_depth >= d + 1`` (rounds include the round-0 leaves — see the E1 note in
``execution/studies.py``).

``lam_as_leaf=True`` (the default) treats a ``Lam`` as a leaf: a synthesized lambda's body is
built in a *descended sub-search* (``budget.descend()``), so its internal depth is paid there,
not in the top-level composition rounds, and at the top level the finished ``Lam`` is injected as
a function value and composed in like an atom. Counting it as a leaf is what keeps depth equal to
top-level generation on higher-order floors. (Pass ``lam_as_leaf=False`` for the raw syntactic
depth, which recurses into lambda bodies.) On HO floors depth still does not predict *search cost*
(the sub-search's considered count is depth-invisible); prefer non-HO floors where depth =
generation = a valid cost exponent.
"""

from __future__ import annotations

from arc_lab.program_search.substrate.program import Lam, Program


def compositional_depth(program: Program, *, lam_as_leaf: bool = True) -> int:
    """The compositional (generation-count) depth of ``program`` — leaves are 0, each
    constructor node (``Apply``/``If``/``AppFn``/``Lam``) adds 1. See the module docstring for
    the ``lam_as_leaf`` convention and the ``max_depth >= d + 1`` budget relationship."""
    if lam_as_leaf and isinstance(program, Lam):
        return 0
    children = program.children()
    if not children:
        return 0
    return 1 + max(compositional_depth(child, lam_as_leaf=lam_as_leaf) for child in children)
