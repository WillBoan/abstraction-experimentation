"""``check_library_coherence``: type-closure, goal-directedness, hole-fill sufficiency."""

from __future__ import annotations

from arc_lab.program_search.execution.check_coherence import check_library_coherence
from arc_lab.program_search.execution.presets import (
    ATOMIC_LIBRARY,
    LIBRARIES,
    SYMMETRY_LIBRARY,
)
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.primitives.build import ADD, BUILD_LIBRARY, MUL, SUB
from arc_lab.program_search.substrate.primitives.combinators import OVERLAY
from arc_lab.program_search.substrate.primitives.control import AND, EQ, IF
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.higher_order import HOF_LIBRARY
from arc_lab.program_search.substrate.primitives.mask import CROP_TO_MASK, MASK_BY_COLOR
from arc_lab.program_search.substrate.primitives.pairs import PAIR_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, GRID, INT


def test_d4_alone_is_coherent_and_goal_directed() -> None:
    report = check_library_coherence(D4_LIBRARY)
    assert report.is_coherent
    assert report.goal_directed
    assert report.dead_primitives == ()
    assert report.findings == ()


def test_mask_consumer_without_an_intro_is_a_hard_island() -> None:
    """Nothing in ``d4`` + the mask *elims* produces a ``Mask`` — no leaf mechanism supplies one
    either (unlike Int/Color's ``constant_sources``), so both elims are structurally dead."""
    library = Library(name="mask-consumer-only", primitives=(*D4_LIBRARY.primitives, CROP_TO_MASK))
    report = check_library_coherence(library)
    assert not report.is_coherent
    assert report.dead_primitives == ("crop_to_mask",)
    (finding,) = report.findings
    assert finding.severity == "error"
    assert finding.check == "type-closure"
    assert finding.primitive == "crop_to_mask"
    assert "mask" in finding.message


def test_mask_intro_closes_the_bundle() -> None:
    library = Library(
        name="mask-closed", primitives=(*D4_LIBRARY.primitives, MASK_BY_COLOR, CROP_TO_MASK)
    )
    report = check_library_coherence(library)
    assert report.is_coherent
    assert report.dead_primitives == ()
    assert "mask" in report.reachable_types


def test_int_color_islands_are_warnings_not_errors_and_depend_on_constant_sources() -> None:
    """``overlay``/``tile`` need an Int/Color leaf only ``constant_sources`` can supply — softer
    than Mask's hard island (MACHINERY.md's 2026-07-14 finding, reproduced statically here). The
    bundle stays coherent regardless: the plain D4 transforms are still activated and grid-producing,
    so goal-directedness doesn't depend on the (warning-only) combinators."""
    without_constants = check_library_coherence(SYMMETRY_LIBRARY, constant_sources=())
    assert without_constants.is_coherent  # a missing Int/Color leaf is a warning, not an error
    assert set(without_constants.dead_primitives) == {"overlay", "tile"}
    assert all(f.severity == "warning" for f in without_constants.findings)

    with_constants = check_library_coherence(
        SYMMETRY_LIBRARY, constant_sources=("finite-enumerate",)
    )
    assert with_constants.is_coherent
    assert with_constants.dead_primitives == ()


def test_arithmetic_only_bundle_is_closed_but_not_goal_directed() -> None:
    """Closed among Int/Bool/pair, with no ``build_grid``/``read``: nothing ever reaches Grid —
    internally closed is not the same as useful, for a benchmark that solves grid->grid."""
    library = Library(name="arith-only", primitives=(ADD, SUB, MUL, EQ, AND, IF, *PAIR_PRIMITIVES))
    report = check_library_coherence(library)
    assert not report.is_coherent
    assert not report.goal_directed
    errors = [f for f in report.findings if f.check == "goal-directedness"]
    assert len(errors) == 1
    assert errors[0].severity == "error"


def test_map_alone_with_no_per_element_vocabulary_is_a_thin_hole_fill() -> None:
    """``hof`` (map + cells/from_cells/width/height): nothing in the bundle can act on a generic
    per-element value — type-reachable (``map`` isn't dead), but practically inert."""
    report = check_library_coherence(HOF_LIBRARY)
    assert report.is_coherent  # a soft/warning finding, not a hard error
    hole_fill = [f for f in report.findings if f.check == "hole-fill"]
    assert len(hole_fill) == 1
    assert hole_fill[0].severity == "warning"
    assert hole_fill[0].primitive == "map"


def test_map_with_a_polymorphic_comparison_clears_the_thin_warning() -> None:
    """Adding a polymorphic op that can act on the unknown element type (``eq``, paired with
    ``if`` for a real decision) is enough generic body vocabulary to clear the threshold."""
    library = HOF_LIBRARY.extended(name="hof+control", extra=(EQ, IF, AND))
    report = check_library_coherence(library)
    hole_fill = [f for f in report.findings if f.check == "hole-fill"]
    assert hole_fill == []


def test_build_grid_has_enough_coordinate_vocabulary_to_reach_color() -> None:
    """``build`` (``read``/``set_cell``/``width``/``height``/``sub``/``build_grid``): the hole's
    body can combine ``sub`` + ``read`` to reach ``color`` — no hole-fill finding."""
    report = check_library_coherence(BUILD_LIBRARY)
    assert report.is_coherent
    assert [f for f in report.findings if f.check == "hole-fill"] == []


def test_build_grid_without_read_cannot_reach_color_in_its_body() -> None:
    """Strip ``read`` from the coordinate floor: nothing left in the body can ever produce a
    ``color`` from the bound (row, col) ints — a hard hole-fill error, not just thin vocabulary.
    ``constant_sources=()`` so a seeded Color leaf doesn't paper over the missing producer."""
    trimmed = tuple(p for p in BUILD_LIBRARY.primitives if p.name != "read")
    library = Library(name="build-no-read", primitives=trimmed)
    report = check_library_coherence(library, constant_sources=())
    assert not report.is_coherent
    hole_fill = [f for f in report.findings if f.check == "hole-fill"]
    assert len(hole_fill) == 1
    assert hole_fill[0].severity == "error"
    assert hole_fill[0].primitive == "build_grid"


def test_atomic_library_is_coherent() -> None:
    report = check_library_coherence(ATOMIC_LIBRARY)
    assert report.is_coherent
    assert report.goal_directed


def test_every_registered_library_resolves_and_reports() -> None:
    """Smoke test: every named library in the registry produces a report without raising."""
    for name, library in LIBRARIES.items():
        report = check_library_coherence(library)
        assert report.library_name == library.name, name


def test_report_is_coherent_ignores_warnings() -> None:
    """A dead, Int-starved primitive alongside an already-activated grid producer: the missing Int
    is a warning, and goal-directedness holds through the *other*, unaffected primitive."""
    needs_int = Primitive(name="needs_int", param_types=(INT,), return_type=GRID, impl=lambda x: x)
    library = Library(name="warn-only", primitives=(*D4_LIBRARY.primitives, needs_int))
    report = check_library_coherence(library, constant_sources=())
    assert report.goal_directed  # via the D4 transforms, independent of needs_int
    assert report.dead_primitives == ("needs_int",)
    assert all(f.severity == "warning" for f in report.findings)
    assert report.is_coherent


def test_variadic_param_is_included_in_type_closure() -> None:
    """``overlay``'s variadic ``Grid`` slot is satisfied by the always-seeded grid leaf, same as a
    fixed param — it's the *fixed* ``Color`` param that's missing without ``constant_sources``."""
    library = Library(name="overlay-only", primitives=(*D4_LIBRARY.primitives, OVERLAY))
    without_constants = check_library_coherence(library, constant_sources=())
    assert without_constants.dead_primitives == ("overlay",)
    (finding,) = without_constants.findings
    assert "color" in finding.message  # not "grid" — the variadic slot alone is satisfiable

    with_constants = check_library_coherence(library, constant_sources=("finite-enumerate",))
    assert with_constants.is_coherent
    assert with_constants.dead_primitives == ()


def test_color_leaf_message_names_the_missing_type() -> None:
    """Alongside an already-activated grid producer, so goal-directedness isn't also in play —
    isolates the type-closure warning's message content."""
    recolor = Primitive(
        name="recolor", param_types=(GRID, COLOR), return_type=GRID, impl=lambda g, c: g
    )
    library = Library(name="recolor-only", primitives=(*D4_LIBRARY.primitives, recolor))
    report = check_library_coherence(library, constant_sources=())
    assert report.is_coherent  # a missing Int/Color leaf is a warning, not an error
    (finding,) = report.findings
    assert finding.check == "type-closure"
    assert finding.severity == "warning"
    assert finding.primitive == "recolor"
    assert "color" in finding.message
