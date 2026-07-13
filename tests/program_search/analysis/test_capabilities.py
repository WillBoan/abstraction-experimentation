"""Read-time capability groupings: category / provenance classification and matrix regrouping."""

from __future__ import annotations

from arc_lab.program_search.analysis.capabilities import describe_key, group_outcomes
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Const
from arc_lab.program_search.substrate.types import COLOR


def test_node_kind_pseudo_key_is_structural() -> None:
    info = describe_key("__if__")
    assert info.category == "control"
    assert info.provenance == "structural"


def test_base_primitive_is_categorized_by_its_defining_module() -> None:
    info = describe_key("rot90")  # substrate/primitives/geometry.py
    assert info.category == "geometry"
    assert info.provenance == "base"


def test_unknown_key_without_a_library_is_unknown() -> None:
    info = describe_key("not_a_real_primitive")
    assert info.category == "unknown"
    assert info.provenance == "unknown"


def test_invented_primitive_is_classified_via_the_library() -> None:
    template = Const(value=5, value_type=COLOR)
    empty = Library(name="empty", primitives=())
    library = Library(name="t", primitives=(make_abstraction("abs0", template, empty),))
    info = describe_key("abs0", library=library)
    assert info.category == "invented"
    assert info.provenance == "invented"


def test_group_outcomes_merges_counts_per_category() -> None:
    by_key = {
        "rot90": {"accepted": 1, "pruned": 2},
        "flip_h": {"pruned": 1},
        "__if__": {"evicted": 3},
    }
    by_category = group_outcomes(by_key, by="category")
    assert by_category["geometry"] == {"accepted": 1, "pruned": 3}
    assert by_category["control"] == {"evicted": 3}


def test_group_outcomes_rejects_an_unknown_axis() -> None:
    try:
        group_outcomes({}, by="nonsense")
    except ValueError:
        return
    raise AssertionError("expected a ValueError for an unrecognized 'by' axis")
