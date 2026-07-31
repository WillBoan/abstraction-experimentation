"""Abstraction Ladder Experiments (docs/abstraction_ladders/ABSTRACTION-LADDERS-SPEC.md).

A **Ladder** is a Floor (``L_0``) + an ordered chain of learnable **bridging Rungs**
(``r_1..r_k``, each an abstraction over the previous cumulative library) + a **Top Rung** (the
goal tasks, whose solutions *use* ``r_k`` as a fragment but are never minted). The batch measures
raw cost (Floor -> Top, no learning; usually intractable) against laddered cost (Floor -> Top via
the bridging rungs, with learning), plus a matrix of derived metrics.

Layers, spec/derived/executed/read like the rest of the codebase:
- ``spec`` -- ``LadderSpec`` / ``Rung`` / ``TopRung`` (chosen; content-hashable provenance).
- ``shape`` -- ``LadderShape`` (derived by ``LadderSpec.lint()``; never in run identity).
- ``run`` / ``certificate`` / ``report`` -- executed + read side (built on ``execute()``).
"""
