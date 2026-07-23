"""Program equivalence: is a ladder change / decomposition behaviour-preserving?

Two layers, keyed to the change type (docs/abstraction_ladders/LADDER-RELATIONSHIPS-2026-07-23.md):

- **Static** (no bodies, no grids): unfold both programs to the floor and compare terms; if unequal,
  compare their equational normal forms. Proves a REFACTOR within one floor -- e.g. cfb2ce5a
  ``v1 == v3`` -- with zero primitive implementations. Sound; incomplete (it misses reorderings the
  curated theory does not cover, and gives up on ``Lam``-bearing terms).
- **Observational** (needs bodies; EXACT mode): evaluate both on a battery of diverse + edge grids and
  compare. Refutation-sound, proof-incomplete. Because we want EXACT equality, ANY split is a real
  difference, so out-of-distribution grids help rather than hurt -- no in-distribution generation.

Library-first: everything operates on :class:`Program`\\ s (whole top solutions, chunks) or on
:class:`Primitive`\\ s (a reference impl vs a decomposition), so ``diff-ladder`` and ad-hoc Claude
checks share one core.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from arc_lab.core.grid import Grid
from arc_lab.program_search.analysis.behavioral import MAX_PROBE_COMBOS, _probe_values
from arc_lab.program_search.analysis.rewrite import RewriteLimits, normal_form
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.signature import BOTTOM, compute_signature
from arc_lab.program_search.substrate.abstraction import unfold_program
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Program

_LIMITS = RewriteLimits()


@dataclass(frozen=True, slots=True)
class StaticVerdict:
    """The static layer's result. ``proven_by`` is how equality was established, ``None`` when it
    could not be (which means "not proven equal", NOT "proven different")."""

    equivalent: bool
    proven_by: str | None  # "syntactic" (unfold-equal) | "equational" (normal-form-equal) | None


@dataclass(frozen=True, slots=True)
class ObservationalVerdict:
    """The observational layer's result -- refutation-sound, proof-incomplete: ``equivalent=True``
    means "no counterexample at ``cases_tested`` inputs", never "proven equal"."""

    equivalent: bool
    cases_tested: int
    counterexample: object | None  # first input (grid / arg-tuple) where the two diverge


def static_equivalent(
    a: Program, a_library: Library, b: Program, b_library: Library, floor: Library
) -> StaticVerdict:
    """Prove ``a`` and ``b`` compute the same function by unfolding both to ``floor`` and comparing.

    ``a_library`` / ``b_library`` are the libraries the two programs are stated over (their ``L_k``);
    both must unfold to the SAME ``floor``, so this is meaningful only for a same-floor (cohort) pair
    -- the caller gates on that. No evaluation, so it works even when the floor primitives have no
    bodies (the cfb2ce5a case). Any internal failure (e.g. a higher-order capture during unfold)
    yields "not proven", never a crash.
    """
    try:
        unfolded_a = unfold_program(a, a_library)
        unfolded_b = unfold_program(b, b_library)
    except (NotImplementedError, ValueError, KeyError):
        return StaticVerdict(False, None)
    if unfolded_a == unfolded_b:
        return StaticVerdict(True, "syntactic")
    norm_a = normal_form(unfolded_a, floor, _LIMITS)
    norm_b = normal_form(unfolded_b, floor, _LIMITS)
    if norm_a is not None and norm_b is not None and norm_a == norm_b:
        return StaticVerdict(True, "equational")
    return StaticVerdict(False, None)


def observationally_equivalent_programs(
    a: Program,
    a_library: Library,
    b: Program,
    b_library: Library,
    grids: Sequence[Grid],
) -> ObservationalVerdict:
    """Evaluate two ``Grid -> Grid`` programs on ``grids`` and compare, EXACT (partiality included).

    Per-program libraries, so this also works across floors when BOTH have bodies. A grid where both
    programs error is agreement (both undefined); one erroring where the other does not is a split.
    Returns the first differing grid as the counterexample.
    """
    contexts = tuple(Context(grid) for grid in grids)
    sig_a = compute_signature(a, contexts, a_library)
    sig_b = compute_signature(b, contexts, b_library)
    # `compute_signature` returns None iff the program errors on EVERY context (fully undefined).
    if sig_a is None and sig_b is None:
        return ObservationalVerdict(True, len(contexts), None)
    if sig_a is None or sig_b is None:
        defined = sig_b if sig_a is None else sig_a
        assert defined is not None  # not both None (handled above), so the other side is defined
        index = next(i for i, value in enumerate(defined) if value is not BOTTOM)
        return ObservationalVerdict(False, len(contexts), grids[index])
    for index, (value_a, value_b) in enumerate(zip(sig_a, sig_b, strict=True)):
        # BOTTOM == BOTTOM (both undefined here -> agree); BOTTOM != any concrete value (a split).
        if value_a != value_b:
            return ObservationalVerdict(False, len(contexts), grids[index])
    return ObservationalVerdict(True, len(contexts), None)


def observationally_equivalent_functions(
    a: Primitive, b: Primitive, grids: Sequence[Grid], *, max_combos: int = MAX_PROBE_COMBOS
) -> ObservationalVerdict:
    """Compare two primitives over typed argument tuples IN ORDER -- EXACT, no permutation.

    The decomposition-validation case: ``a`` a reference implementation of an assumed primitive, ``b``
    the same signature built from lower primitives. GRID params draw from ``grids``; COLOR / INT / BOOL
    from the behavioral probe batteries. Unlike ``behavioral.matches_target`` there is NO argument
    permutation -- exact equivalence must agree with the argument order. A combo where both error is
    agreement; a divergence returns the offending argument tuple.
    """
    if a.param_types != b.param_types:
        return ObservationalVerdict(False, 0, ("signature mismatch", a.param_types, b.param_types))
    per_param: list[tuple[object, ...]] = []
    for param_type in a.param_types:
        values = _probe_values(param_type, tuple(grids))
        if not values:
            raise ValueError(f"cannot probe a {param_type} parameter for exact equivalence")
        per_param.append(values)
    tested = 0
    for args in itertools.islice(itertools.product(*per_param), max_combos):
        tested += 1
        try:
            expected = a.impl(*args)
        except Exception:  # a probe outside a's domain
            try:
                b.impl(*args)
            except Exception:  # both undefined here: agreement
                continue
            return ObservationalVerdict(False, tested, args)
        try:
            actual = b.impl(*args)
        except Exception:  # b errors where a is defined: a split
            return ObservationalVerdict(False, tested, args)
        if expected != actual:
            return ObservationalVerdict(False, tested, args)
    return ObservationalVerdict(True, tested, None)
