"""The type-constructor-name reachability closure shared by ``check_coherence.py`` and
``library_graph.py`` — one fixed-point algorithm, two read-side views over the same computation
(a coherence report; a visual type DAG).

Reachability is computed over type-constructor *names* only (``grid``, ``mask``, ``list``,
``pair``, ...), not full Hindley-Milner unification against parametric arguments — ``list[color]``
and ``list[a]`` are both just "a list of something." Documented, deliberate simplification (this
repo's convention: flag an approximation rather than claim false precision — see
``estimate_cost.py``); the base types the coherence checks care about (``grid``, ``mask``,
``color``, ``int``, ``bool``) are all nullary, so it only loosens matching for the secondary
``list``/``pair`` vocabulary.
"""

from __future__ import annotations

from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import ArrowType, Type, TypeCon

#: The library's branching token (mirrors ``estimate_cost.py``'s ``_BRANCHING_ENTRY``): present as
#: a name to summon short-circuit ``If``, never applied as an ordinary primitive — excluded from
#: the closure/production computation.
BRANCHING_TOKEN = "if"

#: Type-constructor names with an intrinsic leaf source, independent of any library content.
_ALWAYS_LEAF_NAMES = frozenset({"grid"})


def leaf_seed_names(constant_sources: tuple[ConstantSource, ...]) -> frozenset[str]:
    """Type-constructor names available at round 0 without any primitive: ``grid`` always; the
    scalar leaves ``constant_sources`` could mint.

    An *over*-approximation of ``leaves.py::seed_leaves``, which gates each base-type leaf on
    whether the library actually uses that type (``_type_in_use``) — this function has no library
    to check against, so it assumes every scalar type a source *could* mint is present. Harmless for
    a reachability closure: a spuriously-"reachable" type can never wrongly activate a primitive
    that needs something else too, only ever be over-generous about a type nothing consumes anyway.
    """
    names = set(_ALWAYS_LEAF_NAMES)
    if "finite-enumerate" in constant_sources:
        names |= {"int", "color", "bool"}
    if "harvest-from-instance" in constant_sources:
        names |= {"int", "color"}
    return frozenset(names)


def required_names(primitive: Primitive) -> tuple[str, ...]:
    """The type-constructor names ``primitive`` needs reachable — ``TypeVar``/``ArrowType`` params
    are excluded (a type variable is satisfiable by anything already reachable; a function-typed
    hole is a search-time body slot, not a data-flow consumption)."""
    types: list[Type] = list(primitive.param_types)
    if primitive.variadic_param is not None:
        types.append(primitive.variadic_param)
    return tuple(t.name for t in types if isinstance(t, TypeCon))


def compute_closure(
    primitives: tuple[Primitive, ...], seed_names: frozenset[str]
) -> tuple[frozenset[str], tuple[Primitive, ...]]:
    """Fixed-point reachability: the type names reachable from ``seed_names`` by repeatedly applying
    any primitive whose required names are all already reachable, plus the primitives that turned
    out applicable (in library order) — a primitive not in the second tuple is a type-closure
    island: something it consumes is never produced anywhere in this bundle."""
    reachable = set(seed_names)
    activated: dict[str, Primitive] = {}
    changed = True
    while changed:
        changed = False
        for primitive in primitives:
            if primitive.name == BRANCHING_TOKEN or primitive.name in activated:
                continue
            if all(name in reachable for name in required_names(primitive)):
                activated[primitive.name] = primitive
                changed = True
                if isinstance(primitive.return_type, TypeCon):
                    reachable.add(primitive.return_type.name)
    return frozenset(reachable), tuple(activated.values())


def flatten_arrow(arrow: ArrowType) -> tuple[tuple[Type, ...], Type]:
    """Peel a curried ``ArrowType`` chain (``build_grid``'s ``(int) -> (int) -> color``) down to its
    flat parameter list and final result type."""
    params: list[Type] = list(arrow.params)
    result: Type = arrow.result
    while isinstance(result, ArrowType):
        params.extend(result.params)
        result = result.result
    return tuple(params), result
