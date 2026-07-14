"""``check_library_coherence``: a static, no-execution "is this bundle even usable" diagnostic.

Reads a :class:`~arc_lab.program_search.substrate.library.Library` (only — no ``Corpus``, no
``SearchEngine``) and answers three questions a bare primitive list can't answer by inspection:

1. **Type-closure.** A non-scalar type a primitive *consumes* (``mask``, and any parametric
   container) must be *produced* by something else in the bundle, or by a leaf mechanism —
   ``grid`` always is (``search/leaves.py``'s unconditional ``Input()``); ``int``/``color``/``bool``
   are *if* ``constant_sources`` supplies them (a policy knob, so flagged as a softer warning, not a
   hard island). Nothing else has a leaf source — a primitive needing an unproduced ``mask`` is
   structurally dead, same shape as the MACHINERY.md "unreachable-primitive" gap this command names.
2. **Goal-directedness.** ARC solves grid->grid: a bundle can be perfectly closed among itself and
   still never produce a ``grid`` (pure arithmetic/control/pair primitives, say) — internally closed
   is not the same as useful.
3. **Hole-fill sufficiency.** A function-typed hole (``build_grid``/``map``/``filter``/``fold``/
   ``sort_by``) needs enough body vocabulary reachable *inside* it (coordinate ops, comparisons, a
   perceiver) or its body search degenerates to identity/const — present-in-the-library is necessary
   but not sufficient.

**What this deliberately approximates** (flagged, not silently precise — this repo's convention,
see ``estimate_cost.py``): reachability is computed over type-constructor *names* only (``grid``,
``mask``, ``list``, ``pair``, ...), not full Hindley-Milner unification against parametric
arguments — ``list[color]`` and ``list[a]`` are both just "a list of something." This is a
deliberate, documented simplification: the base types the three checks care about (``grid``,
``mask``, ``color``, ``int``, ``bool``) are all nullary, so the approximation only loosens matching
for the secondary ``list``/``pair`` vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.types import ArrowType, Type, TypeCon, TypeVar

#: The library's branching token (mirrors ``estimate_cost.py``'s ``_BRANCHING_ENTRY``): present as
#: a name to summon short-circuit ``If``, never applied as an ordinary primitive — excluded from the
#: closure/production computation, but still counted as body vocabulary (§3) when present.
_BRANCHING_TOKEN = "if"

#: Type-constructor names with an intrinsic leaf source, independent of any library content.
_ALWAYS_LEAF_NAMES = frozenset({"grid"})

#: Below this many distinct body-vocabulary primitives, a hole-fill is flagged as "thin" (§3) — a
#: named, not-derived threshold: 0 means "can only ever be identity/const", 1 means one lone
#: primitive with no way to combine it with anything else.
_THIN_VOCABULARY_THRESHOLD = 2

Severity = Literal["error", "warning"]
Check = Literal["type-closure", "goal-directedness", "hole-fill"]


@dataclass(frozen=True, slots=True)
class CoherenceFinding:
    """One diagnostic: a severity-tagged, human-readable statement about one primitive."""

    severity: Severity
    check: Check
    primitive: str
    message: str


@dataclass(frozen=True, slots=True)
class CoherenceReport:
    """The full coherence picture for one library under one ``constant_sources`` assumption."""

    library_name: str
    constant_sources: tuple[ConstantSource, ...]
    reachable_types: tuple[str, ...]
    dead_primitives: tuple[str, ...]
    goal_directed: bool
    findings: tuple[CoherenceFinding, ...]

    @property
    def is_coherent(self) -> bool:
        """No ``error``-severity finding survived — ``warning``s (e.g. thin hole-fill) don't fail it."""
        return not any(finding.severity == "error" for finding in self.findings)


def _leaf_seed_names(constant_sources: tuple[ConstantSource, ...]) -> frozenset[str]:
    """Type-constructor names available at round 0 without any primitive: ``grid`` always; the
    scalar leaves ``constant_sources`` actually mints (mirrors ``leaves.py::seed_leaves`` exactly)."""
    names = set(_ALWAYS_LEAF_NAMES)
    if "finite-enumerate" in constant_sources:
        names |= {"int", "color", "bool"}
    if "harvest-from-instance" in constant_sources:
        names |= {"int", "color"}
    return frozenset(names)


def _required_names(primitive: Primitive) -> tuple[str, ...]:
    """The type-constructor names ``primitive`` needs reachable — ``TypeVar``/``ArrowType`` params
    are excluded (a type variable is satisfiable by anything already reachable; a function-typed
    hole is owned by the hole-fill check, §3, not type-closure)."""
    types: list[Type] = list(primitive.param_types)
    if primitive.variadic_param is not None:
        types.append(primitive.variadic_param)
    return tuple(t.name for t in types if isinstance(t, TypeCon))


def _closure(
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
            if primitive.name == _BRANCHING_TOKEN or primitive.name in activated:
                continue
            if all(name in reachable for name in _required_names(primitive)):
                activated[primitive.name] = primitive
                changed = True
                if isinstance(primitive.return_type, TypeCon):
                    reachable.add(primitive.return_type.name)
    return frozenset(reachable), tuple(activated.values())


def _flatten_arrow(arrow: ArrowType) -> tuple[tuple[Type, ...], Type]:
    """Peel a curried ``ArrowType`` chain (``build_grid``'s ``(int) -> (int) -> color``) down to its
    flat parameter list and final result type."""
    params: list[Type] = list(arrow.params)
    result: Type = arrow.result
    while isinstance(result, ArrowType):
        params.extend(result.params)
        result = result.result
    return tuple(params), result


def _type_closure_findings(
    primitives: tuple[Primitive, ...], reachable: frozenset[str], activated_names: frozenset[str]
) -> list[CoherenceFinding]:
    findings: list[CoherenceFinding] = []
    for primitive in primitives:
        if primitive.name == _BRANCHING_TOKEN or primitive.name in activated_names:
            continue
        missing = sorted({name for name in _required_names(primitive) if name not in reachable})
        for name in missing:
            if name in {"int", "color", "bool"}:
                findings.append(
                    CoherenceFinding(
                        severity="warning",
                        check="type-closure",
                        primitive=primitive.name,
                        message=(
                            f"needs a {name!r} leaf that nothing in this bundle produces; only "
                            "reachable if the run's constant_sources policy supplies it "
                            "(finite-enumerate / harvest-from-instance)"
                        ),
                    )
                )
            else:
                findings.append(
                    CoherenceFinding(
                        severity="error",
                        check="type-closure",
                        primitive=primitive.name,
                        message=(
                            f"needs {name!r}, which nothing else in this bundle produces and no "
                            "leaf mechanism supplies — structurally unreachable (an island)"
                        ),
                    )
                )
    return findings


def _goal_directedness_finding(
    activated: tuple[Primitive, ...], goal_type_name: str = "grid"
) -> tuple[bool, CoherenceFinding | None]:
    goal_directed = any(
        isinstance(primitive.return_type, TypeCon) and primitive.return_type.name == goal_type_name
        for primitive in activated
    )
    if goal_directed:
        return True, None
    return False, CoherenceFinding(
        severity="error",
        check="goal-directedness",
        primitive="<bundle>",
        message=(
            f"no primitive in this bundle ever produces {goal_type_name!r} (ARC solves "
            "grid->grid) — the bundle may be internally closed but can only ever emit the "
            "unmodified input, never a transformed solution"
        ),
    )


def _is_vocabulary_primitive(primitive: Primitive, local_reachable: frozenset[str]) -> bool:
    """Whether ``primitive`` is usable, non-trivial vocabulary inside a hole's body: every consumed
    type is locally reachable (``TypeVar`` params make it polymorphic, so always usable regardless
    of the hole's own element type)."""
    return all(
        isinstance(t, TypeVar) or (isinstance(t, TypeCon) and t.name in local_reachable)
        for t in primitive.param_types
    )


def _generic_vocabulary(
    hof: Primitive, library: tuple[Primitive, ...], reachable: frozenset[str]
) -> list[str]:
    """Body vocabulary for a *generic* hole (``map``/``filter``/``fold``/``sort_by``'s element type
    is an unpinned ``TypeVar`` — no concrete bound type to seed a local closure with). The only
    primitives that can meaningfully consume a value of unknown type are themselves polymorphic
    (``eq``, ``if``, ...); their other, concrete params still need to be globally reachable."""
    vocabulary: list[str] = []
    for primitive in library:
        if primitive.name == hof.name or primitive.body_sampler is not None:
            continue
        if not any(isinstance(t, TypeVar) for t in primitive.param_types):
            continue  # monomorphic: can't accept a value of the hole's unknown element type
        if all(
            isinstance(t, TypeVar) or (isinstance(t, TypeCon) and t.name in reachable)
            for t in primitive.param_types
        ):
            vocabulary.append(primitive.name)
    return vocabulary


def _hole_fill_findings(
    hof: Primitive,
    library: tuple[Primitive, ...],
    seed_names: frozenset[str],
    reachable: frozenset[str],
) -> list[CoherenceFinding]:
    findings: list[CoherenceFinding] = []
    for param in hof.param_types:
        if not isinstance(param, ArrowType):
            continue
        bound_types, result_type = _flatten_arrow(param)
        is_generic = any(isinstance(t, TypeVar) for t in (*bound_types, result_type))

        if is_generic:
            vocabulary = _generic_vocabulary(hof, library, reachable)
        else:
            local_seed = set(seed_names) | {t.name for t in bound_types if isinstance(t, TypeCon)}
            local_reachable, local_activated = _closure(library, frozenset(local_seed))
            if isinstance(result_type, TypeCon) and result_type.name not in local_reachable:
                findings.append(
                    CoherenceFinding(
                        severity="error",
                        check="hole-fill",
                        primitive=hof.name,
                        message=(
                            f"the function-hole's body must yield {result_type.name!r}, but "
                            "nothing reachable from its bound arguments + leaves ever produces "
                            "one — the body search has no way to reach a valid body at all"
                        ),
                    )
                )
                continue
            vocabulary = [
                p.name for p in local_activated if p.name != hof.name and p.body_sampler is None
            ]

        if len(vocabulary) < _THIN_VOCABULARY_THRESHOLD:
            findings.append(
                CoherenceFinding(
                    severity="warning",
                    check="hole-fill",
                    primitive=hof.name,
                    message=(
                        f"only {len(vocabulary)} usable body primitive(s) reachable inside this "
                        f"function-hole ({', '.join(sorted(vocabulary)) or 'none'}) — likely too "
                        "thin to do more than identity/const; needs coordinate ops, comparisons, "
                        "or a perceiver to build a non-trivial body"
                    ),
                )
            )
    return findings


def check_library_coherence(
    library: Library,
    *,
    constant_sources: tuple[ConstantSource, ...] = ("finite-enumerate",),
) -> CoherenceReport:
    """The full coherence report for ``library`` under an assumed ``constant_sources`` policy."""
    primitives = library.primitives
    seed_names = _leaf_seed_names(constant_sources)
    reachable, activated = _closure(primitives, seed_names)
    activated_names = frozenset(p.name for p in activated)

    findings: list[CoherenceFinding] = []
    findings.extend(_type_closure_findings(primitives, reachable, activated_names))

    goal_directed, goal_finding = _goal_directedness_finding(activated)
    if goal_finding is not None:
        findings.append(goal_finding)

    for primitive in primitives:
        if any(isinstance(t, ArrowType) for t in primitive.param_types):
            findings.extend(_hole_fill_findings(primitive, primitives, seed_names, reachable))

    dead = tuple(
        sorted(
            p.name
            for p in primitives
            if p.name != _BRANCHING_TOKEN and p.name not in activated_names
        )
    )

    findings.sort(key=lambda f: (f.severity != "error", f.check, f.primitive))
    return CoherenceReport(
        library_name=library.name,
        constant_sources=constant_sources,
        reachable_types=tuple(sorted(reachable)),
        dead_primitives=dead,
        goal_directed=goal_directed,
        findings=tuple(findings),
    )
