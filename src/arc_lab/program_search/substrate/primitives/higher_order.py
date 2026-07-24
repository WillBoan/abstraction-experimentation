"""Higher-order list primitives: ``map``/``filter``/``fold``/``sort_by`` (§7 of ARCHITECTURE.md).

Each shares one shape: a function-typed hole whose type variable(s) are also present in a *sibling*
`List[a]` parameter — so the hole gets pinned by unifying against a concrete sibling candidate
(`search/composition.py::hole_assignments`), not by the primitive's own signature alone (contrast
with `build_grid`, whose coordinate hole is concrete from the start). Once pinned, the body search
proceeds exactly as it does for `build_grid`.

``map``/``filter`` attempt propagation via the recursively-threaded ``enclosing_target`` (§7/§8);
``fold``/``sort_by`` are baseline-only by design — their target (the running accumulator, the sort
key) is latent, not derivable from training I/O alone.
"""

from __future__ import annotations

from arc_lab.core.task import TrainExamples, train_with_output
from arc_lab.program_search.substrate.library import (
    EnclosingTarget,
    Library,
    Primitive,
    RawContext,
    Value,
    apply_function_value,
)
from arc_lab.program_search.substrate.primitives.addressing import OFFSET_OF
from arc_lab.program_search.substrate.primitives.build import HEIGHT, WIDTH
from arc_lab.program_search.substrate.primitives.cells import CELLS, FROM_CELLS
from arc_lab.program_search.substrate.types import BOOL, ArrowType, TypeVar, list_type

_A = TypeVar("a")
_B = TypeVar("b")
_ACC = TypeVar("acc")
_K = TypeVar("k")
_LIST_A = list_type(_A)
_LIST_B = list_type(_B)


# -- impls ---------------------------------------------------------------------------------------


def _map_impl(f: Value, xs: Value) -> Value:
    if not isinstance(xs, tuple):
        raise TypeError(f"map expects a list, got {type(xs).__name__}")
    return tuple(apply_function_value(f, (x,)) for x in xs)


def _filter_impl(f: Value, xs: Value) -> Value:
    if not isinstance(xs, tuple):
        raise TypeError(f"filter expects a list, got {type(xs).__name__}")
    kept: list[Value] = []
    for x in xs:
        keep = apply_function_value(f, (x,))
        if not isinstance(keep, bool):
            raise TypeError(f"filter predicate must yield bool, got {type(keep).__name__}")
        if keep:
            kept.append(x)
    return tuple(kept)


def _fold_impl(f: Value, seed: Value, xs: Value) -> Value:
    if not isinstance(xs, tuple):
        raise TypeError(f"fold expects a list, got {type(xs).__name__}")
    acc = seed
    for x in xs:
        acc = apply_function_value(f, (acc, x))
    return acc


def _sort_by_impl(f: Value, xs: Value) -> Value:
    if not isinstance(xs, tuple):
        raise TypeError(f"sort_by expects a list, got {type(xs).__name__}")
    keyed: list[tuple[int, Value]] = []
    for x in xs:
        key = apply_function_value(f, (x,))
        if not isinstance(key, int):  # covers INT, COLOR, and BOOL's runtime representations
            raise TypeError(f"sort_by key must be orderable, got {type(key).__name__}")
        keyed.append((key, x))
    keyed.sort(key=lambda pair: pair[0])
    return tuple(value for _, value in keyed)


# -- body samplers ---------------------------------------------------------------------------------


def _list_sibling_contexts(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
) -> tuple[RawContext, ...]:
    """One context per ``(input, (element,))`` — the shared shape for a single-``List[a]``-sibling
    hole (``map``/``filter``/``sort_by``). Contexts where the sibling wasn't total there are skipped
    (§8's partial-tolerance — see ``_evaluate_siblings`` in ``search_engine.py``).

    ``sibling_arg_values`` is index-aligned with *training examples* only when this call is at (or
    under a context-preserving hole of) the top level — nested under a *different* hole's body
    search (§9), the contexts there are reshaped (e.g. per-element, not per-example), so a length
    mismatch means this hole isn't meaningfully synthesizable at this nesting; the safe response is
    no contexts, same as ``raw_contexts == ()`` anywhere else.
    """
    examples = train_with_output(train_examples)
    if len(examples) != len(sibling_arg_values):
        return ()
    contexts: list[RawContext] = []
    for example, values in zip(examples, sibling_arg_values, strict=True):
        if values is None:
            continue
        (xs,) = values
        if not isinstance(xs, tuple):
            continue
        for element in xs:
            contexts.append((example.input, (element,)))
    return tuple(contexts)


def _propagate_elementwise(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget,
) -> tuple[Value, ...] | None:
    """``map``'s propagation (§7): a positional zip of each context's element against the enclosing
    target's aligned output list — sound only when the target is itself list-shaped and
    length-matches the evaluated ``xs`` at every context (an order/count-preserving
    correspondence); ``None`` (deferring to the baseline) otherwise."""
    examples = train_with_output(train_examples)
    if len(examples) != len(enclosing_target.values):
        return None
    target: list[Value] = []
    for values, output in zip(sibling_arg_values, enclosing_target.values, strict=True):
        if values is None:
            continue
        (xs,) = values
        if not isinstance(xs, tuple) or not isinstance(output, tuple) or len(xs) != len(output):
            return None
        target.extend(output)
    return tuple(target) if target else None


def _map_body_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    contexts = _list_sibling_contexts(train_examples, sibling_arg_values)
    if not contexts:
        return (), None
    if enclosing_target is not None:
        propagated = _propagate_elementwise(train_examples, sibling_arg_values, enclosing_target)
        if propagated is not None:
            return contexts, propagated
    return contexts, None


def _propagate_keep_mask(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget,
) -> tuple[Value, ...] | None:
    """``filter``'s propagation (§7): the ``BOOL`` keep-mask, derived by a two-pointer merge of
    ``xs`` against the target list — matching each target element to the next equal ``xs`` element
    in order. Sound only when this consumes the *whole* target as a genuine subsequence of ``xs``
    (the "unambiguous surviving set" §7 requires); ``None`` (baseline) otherwise."""
    examples = train_with_output(train_examples)
    if len(examples) != len(enclosing_target.values):
        return None
    mask: list[Value] = []
    for values, output in zip(sibling_arg_values, enclosing_target.values, strict=True):
        if values is None:
            continue
        (xs,) = values
        if not isinstance(xs, tuple) or not isinstance(output, tuple):
            return None
        survivor = 0
        for element in xs:
            if survivor < len(output) and element == output[survivor]:
                mask.append(True)
                survivor += 1
            else:
                mask.append(False)
        if survivor != len(output):
            return None  # the target wasn't a genuine subsequence of xs
    return tuple(mask) if mask else None


def _filter_body_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    contexts = _list_sibling_contexts(train_examples, sibling_arg_values)
    if not contexts:
        return (), None
    if enclosing_target is not None:
        propagated = _propagate_keep_mask(train_examples, sibling_arg_values, enclosing_target)
        if propagated is not None:
            return contexts, propagated
    return contexts, None


def _fold_body_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    """``fold``'s body search: contexts pair the seed (standing in for the latent running
    accumulator) with each element — baseline only (§7): the true running accumulator isn't
    observable from training I/O alone, so there's nothing to propagate; the baseline (§8) carries
    correctness regardless of sample adequacy. Same nesting caveat as ``_list_sibling_contexts``: a
    length mismatch against training examples means this hole isn't synthesizable at this nesting.
    """
    examples = train_with_output(train_examples)
    if len(examples) != len(sibling_arg_values):
        return (), None
    contexts: list[RawContext] = []
    for example, values in zip(examples, sibling_arg_values, strict=True):
        if values is None:
            continue
        seed, xs = values
        if not isinstance(xs, tuple):
            continue
        for element in xs:
            contexts.append((example.input, (seed, element)))
    return tuple(contexts), None


def _sort_by_body_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    """``sort_by``'s body search: baseline only (§7) — the sort key is latent."""
    return _list_sibling_contexts(train_examples, sibling_arg_values), None


# -- primitives ------------------------------------------------------------------------------------

MAP = Primitive(
    name="map",
    param_types=(ArrowType((_A,), _B), _LIST_A),
    return_type=_LIST_B,
    impl=_map_impl,
    body_sampler=_map_body_sampler,
)
FILTER = Primitive(
    name="filter",
    param_types=(ArrowType((_A,), BOOL), _LIST_A),
    return_type=_LIST_A,
    impl=_filter_impl,
    body_sampler=_filter_body_sampler,
)
FOLD = Primitive(
    name="fold",
    param_types=(ArrowType((_ACC,), ArrowType((_A,), _ACC)), _ACC, _LIST_A),
    return_type=_ACC,
    impl=_fold_impl,
    body_sampler=_fold_body_sampler,
)
#: The sort key ``k`` is genuinely polymorphic — unshared with any sibling, so it's resolved by
#: ``unpinned_type_var_mode`` (grounded over the monotype universe under
#: ``eager_grounding_over_universe``), not fixed to a single type here.
SORT_BY = Primitive(
    name="sort_by",
    param_types=(ArrowType((_A,), _K), _LIST_A),
    return_type=_LIST_A,
    impl=_sort_by_impl,
    body_sampler=_sort_by_body_sampler,
)

#: `map` + a minimal real list vocabulary (`cells`/`from_cells`, row-major, mirroring `build_grid`'s
#: convention) + dimension perceivers — enough to demonstrate `map` solving a real task end-to-end.
# `offset` is what carries int -> grid now that `from_cells` takes an extent rather than two
# ints: without an Offset producer the int<->grid cycle this library exists to show is broken.
HOF_LIBRARY = Library(name="hof", primitives=(MAP, CELLS, FROM_CELLS, WIDTH, HEIGHT, OFFSET_OF))
