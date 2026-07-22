"""Depth: the generation a program is composed at, and the budget that puts it in reach.

Two quantities, which coincide on first-order programs and diverge once a ``Lam`` appears:

* :func:`compositional_depth` — the **generation** (composition round) the engine builds it at.
  Leaf = 0, ``flip_h(input)`` = 1, ``flip_h(flip_v(input))`` = 2 — the same unit as
  ``SearchStats.solved_at_generation``. This is the ``d_i`` / ``d_raw`` unit the Abstraction
  Ladder design doc speaks.
* :func:`min_depth_limit` — the smallest ``Budget.depth_limit`` that puts it in reach.

Per node kind, within one frame (measured against the engine, 2026-07-22):

* ``Input`` / ``Const`` / ``Param`` / ``Var`` / ``PrimRef`` cost 0 — all are leaves, and a
  ``PrimRef`` is seeded straight into the round-0 frontier (``_function_leaves``), so filling a
  function hole *point-free* costs no generation at all.
* ``Apply`` / ``If`` / ``AppFn`` cost ``1 + max(children)`` — each is composed at a round >= 1
  (``_compose``, ``_branch_candidates``, and the ``AppFn`` composition step respectively).
* A ``Lam`` costs **1**, and a maximal curried chain (``Lam(Lam(body))``) still costs 1:
  ``_synthesize_for_hole`` wraps every binder and yields the whole chain as ONE candidate. A
  synthesized lambda is *not* a leaf — it is composed into the pool at a round >= 1 and can only
  be consumed the round after, so filling a hole *with a lambda* costs one generation.

**Frames.** A lambda's body is not built in this round loop at all: it comes from a nested
sub-search that ``budget.descend()`` hands ``depth_limit - 1``. So the body is its own frame, one
descent deeper, and the budget it needs is its own depth PLUS its descent. That is what
:func:`min_depth_limit` maximises over, and why no single tree measure can answer it — a program
of generation 2 can require a ``depth_limit`` of 4 (a depth-3 body, one descent down).

For a first-order program there is exactly one frame at descent 0, so everything collapses back to
the classic ``depth == generation == minimum depth_limit``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from arc_lab.program_search.substrate.program import Lam, Program


@dataclass(frozen=True, slots=True)
class Frame:
    """One enumeration context: the top level (``descent`` 0), or a lambda body one deeper."""

    depth: int
    descent: int


def frames(program: Program, _descent: int = 0) -> tuple[Frame, ...]:
    """``program``'s frames: the top level first, then every lambda body, depth-first."""
    out = [Frame(depth=_frame_depth(program), descent=_descent)]
    for lam in _outermost_lams(program):
        body: Program = lam
        while isinstance(body, Lam):  # a curried chain is ONE hole fill, so ONE descend
            body = body.body
        out.extend(frames(body, _descent + 1))
    return tuple(out)


def compositional_depth(program: Program) -> int:
    """The generation at which the engine composes `program` (a leaf is generation 0).

    Once lambdas are involved, this is NOT the same as the minimum `Budget.depth_limit` that
    is required to put it in reach — that is :func:`min_depth_limit`.
    """
    return frames(program)[0].depth


def min_depth_limit(program: Program) -> int:
    """The smallest ``Budget.depth_limit`` that puts ``program`` in reach.

    **Necessary, not sufficient.** Below it the program cannot be built — the direction every
    tractability claim rests on. At or above it the program may still never be found: a cheaper
    observationally-equivalent program can take its pool slot, ``max_pool`` can evict a needed
    sub-part, ``considered_limit`` can censor the run, and a higher-order primitive nested under a
    wrapper can have its lambda body filtered out by example propagation (measured 2026-07-22:
    unreachable at *any* depth, which no depth function can express).
    """
    return max(frame.depth + frame.descent for frame in frames(program))


def syntactic_depth(program: Program) -> int:
    """The raw tree depth, entering lambda bodies and counting each ``Lam`` node.

    Reporting only: it predicts neither quantity (a program of syntactic depth 6 can be
    generation 2). Kept because it is the shape a reader of a printed program sees.
    """
    if isinstance(program, Lam):
        return 1 + syntactic_depth(program.body)
    children = program.children()
    return 1 + max(syntactic_depth(child) for child in children) if children else 0


def _frame_depth(program: Program) -> int:
    """Depth within ONE frame: a ``Lam`` chain costs 1 and its body is not entered."""
    if isinstance(program, Lam):
        return 1
    children = program.children()
    return 1 + max(_frame_depth(child) for child in children) if children else 0


def _outermost_lams(program: Program) -> Iterator[Lam]:
    """Every ``Lam`` reachable without passing through another ``Lam`` — one per hole fill."""
    if isinstance(program, Lam):
        yield program
        return
    for child in program.children():
        yield from _outermost_lams(child)
