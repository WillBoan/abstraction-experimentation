"""`proposer-compat`'s capability table must match what the proposers ACTUALLY offer.

The table is a hand-written claim about machinery that lives in another module, so it can drift from
the machinery silently -- and when it does, the failure mode is the worst kind: the lint PASSES a
ladder no configured proposer can climb, and the stall only shows up as unrecovered rungs after a
full run. It did drift (2026-07-27): the `FrequentSubtree` family was credited with `FULL_SOLUTION`,
which `propose`'s root exclusion makes structurally impossible.

So these tests drive the real proposers rather than restating the table.
"""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.checks.learnability import _PROPOSER_CAPABILITIES
from arc_lab.program_search.ladders.spec import DemonstrationKind
from arc_lab.program_search.learn.antiunify import (
    AbstractionProposer,
    AntiunifyPairs,
    FrequentSubtree,
    SearchScopedFrequentSubtree,
    TypeScopedFrequentSubtree,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Input, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import GRID

LIBRARY = Library(name="registry", primitives=tuple(BASE_PRIMITIVES.values()))

#: The demonstrated idiom, as it appears inside a solution (over the task `Input`).
DEMONSTRATED = Apply("crop_to_mask", (Input(), Apply("nonbg_mask", (Input(),))))

#: The same idiom as a proposer would OFFER it: closed, with the `Input` lifted to a parameter.
_G = Param(0, GRID)
TARGET = Apply("crop_to_mask", (_G, Apply("nonbg_mask", (_G,))))

#: A rung shown as a whole solution: the demonstrating programs ARE the template instantiated.
FULL_SOLUTION_DEMOS: list[Program] = [DEMONSTRATED, DEMONSTRATED]

#: A rung shown as a fragment: the template recurs inside DISTINCT larger solutions. The wrappers
#: must differ -- that is what `fragment_identical` means, and with identical ones the whole root is
#: itself the best compressor, which makes compression-driven proposers look incapable when they
#: are not.
FRAGMENT_DEMOS: list[Program] = [
    Apply("flip_h", (DEMONSTRATED,)),
    Apply("flip_v", (DEMONSTRATED,)),
]

PROPOSERS: list[AbstractionProposer] = [
    AntiunifyPairs(),
    FrequentSubtree(),
    TypeScopedFrequentSubtree(result_type=GRID),
    SearchScopedFrequentSubtree(composes=lambda _params, _ret: True),
]


def _offers_target(proposer: AbstractionProposer, programs: list[Program]) -> bool:
    return TARGET in proposer.propose(list(programs), LIBRARY)


@pytest.mark.parametrize("proposer", PROPOSERS, ids=lambda p: type(p).__name__)
@pytest.mark.parametrize(
    ("kind", "demos"),
    [
        (DemonstrationKind.FULL_SOLUTION, FULL_SOLUTION_DEMOS),
        (DemonstrationKind.FRAGMENT_IDENTICAL, FRAGMENT_DEMOS),
    ],
    ids=lambda k: k.value if isinstance(k, DemonstrationKind) else "",
)
def test_the_capability_table_matches_what_the_proposer_actually_offers(
    proposer: AbstractionProposer, kind: DemonstrationKind, demos: list[Program]
) -> None:
    claimed = kind in _PROPOSER_CAPABILITIES[type(proposer).__name__]
    assert _offers_target(proposer, demos) == claimed, (
        f"{type(proposer).__name__} is claimed to "
        f"{'serve' if claimed else 'not serve'} {kind.value}, but it does the opposite"
    )


def test_the_two_miners_are_complementary_rather_than_nested() -> None:
    """The regression this guards: treating `FrequentSubtree` as a superset of `AntiunifyPairs`.

    Each is blind exactly where the other sees, which is why no single-proposer ladder can mix
    demonstration kinds across its rungs -- only `StitchProposer` spans both.
    """
    antiunify, subtree = AntiunifyPairs(), FrequentSubtree()
    assert _offers_target(antiunify, FULL_SOLUTION_DEMOS)
    assert not _offers_target(antiunify, FRAGMENT_DEMOS)
    assert not _offers_target(subtree, FULL_SOLUTION_DEMOS)
    assert _offers_target(subtree, FRAGMENT_DEMOS)


@pytest.mark.parametrize(
    ("kind", "demos"),
    [
        (DemonstrationKind.FULL_SOLUTION, FULL_SOLUTION_DEMOS),
        (DemonstrationKind.FRAGMENT_IDENTICAL, FRAGMENT_DEMOS),
    ],
    ids=lambda k: k.value if isinstance(k, DemonstrationKind) else "",
)
def test_the_capability_table_matches_stitch(kind: DemonstrationKind, demos: list[Program]) -> None:
    """Stitch is dep-gated, so it sits outside the main sweep -- but its row is the one claiming to
    serve EVERY kind, which is exactly the claim worth checking when the dep is present."""
    shim = pytest.importorskip("arc_lab.program_search.learn.stitch_shim")
    proposer = shim.StitchProposer()
    assert kind in _PROPOSER_CAPABILITIES["StitchProposer"]
    assert _offers_target(proposer, demos)


def test_frequent_subtree_cannot_offer_a_root_because_it_mines_proper_subtrees_only() -> None:
    """The MECHANISM behind the table entry, pinned separately so a change to `propose`'s mining
    set fails here with a readable reason rather than as a puzzling ladder stall."""
    offered = FrequentSubtree().propose(list(FULL_SOLUTION_DEMOS), LIBRARY)
    assert TARGET not in offered
    # It still sees strictly inside the root -- so this is root exclusion, not total blindness.
    assert Apply("nonbg_mask", (_G,)) in offered
