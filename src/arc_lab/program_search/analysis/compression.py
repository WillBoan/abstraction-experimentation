"""Compression: the two-part description length of a solved corpus under a library.

This is the *governance objective* made measurable. An abstraction earns its place
by **compressing** the set of solutions — shortening many programs by more than it
costs to carry. So we measure

    DL(corpus | library) = library_bits + Σ_program  program_bits

A richer library lowers ``Σ program_bits`` (programs get shorter) but raises
``library_bits`` (you pay to carry each primitive). That tension is the whole point:
a *useful* abstraction (shortens many programs) lowers total DL; a *memorised* one
(helps a single task but still costs its keep) does not. Comparing the same corpus's
DL under two libraries gives the **compression ratio** — the headline governance signal.

Design (per the (library x search x constraints x cost) model):

* **Per-program complexity is the swappable :class:`Cost` family** (``search/cost.py``).
  v1 uses :class:`ProgramSize` (node count); a bit-weighted cost drops in unchanged.
* **This class is the corpus-level aggregate** parameterised by that ``Cost`` — swap
  the cost, get a different compression number, for free.

Refinement path (deliberately not v1): weight each ``Apply`` node by ``log2(|library|)``
real bits, and charge a *learned* abstraction its defining sub-program's size rather
than the flat ``bits_per_primitive`` used here.

Only *observations* (programs, sizes) belong in a run artifact — never a derived ratio;
recompute ratios offline from two runs' recorded description lengths.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.task import Task
from arc_lab.program_search.search.cost import Cost, ProgramSize
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program


@dataclass(frozen=True, slots=True)
class SolvedTask:
    """One solved entry: a task (with its metadata) and the program found to solve it.

    Holds the :class:`AnnotatedTask` so an oracle/label and the found ``program`` stay
    co-located (no join by id). ``task`` exposes the pure task for the cost / DL computation.
    """

    annotated: AnnotatedTask
    program: Program

    @property
    def task(self) -> Task:
        return self.annotated.task


@dataclass(frozen=True, slots=True)
class DescriptionLength:
    """The two parts of a corpus's code length, kept separate (store observations)."""

    library_bits: float
    program_bits: float

    @property
    def total(self) -> float:
        return self.library_bits + self.program_bits


@dataclass(frozen=True)
class CompressionMetric:
    """Two-part MDL of a solved corpus, parameterised by a per-program :class:`Cost`."""

    cost: Cost = field(default_factory=ProgramSize)
    #: Flat code length charged per primitive carried in the library.
    bits_per_primitive: float = 1.0

    def library_bits(self, library: Library) -> float:
        """The cost of *carrying* the vocabulary — a flat name cost per primitive.

        This baseline ignores an abstraction's *definition* size, which lets the loop hoard
        marginal specialisations (observed in E3). :class:`TwoPartMDL` charges the definition
        and is the anti-bloat variant; kept separate so the two governance regimes compare.
        """
        return self.bits_per_primitive * len(library.primitives)

    def program_bits(self, entries: Iterable[SolvedTask], library: Library) -> float:
        """Total code length of the solution programs under ``library``."""
        # Costs are train-side machinery: they see train examples, never the task.
        return sum(self.cost.of(entry.program, entry.task.train, library) for entry in entries)

    def describe(self, entries: Iterable[SolvedTask], library: Library) -> DescriptionLength:
        """The two-part description length of ``entries`` solved under ``library``."""
        corpus = list(entries)
        return DescriptionLength(
            library_bits=self.library_bits(library),
            program_bits=self.program_bits(corpus, library),
        )


@dataclass(frozen=True)
class TwoPartMDL(CompressionMetric):
    """Compression that also charges each learned abstraction its template's definition size.

    Proper two-part code: ``DL(library) = flat names + Σ (learned) template sizes``. That
    definition term is the **anti-bloat** force — a marginal specialisation (an existing
    abstraction applied to constants) must save more than it costs to define, so the loop
    stops hoarding them. Base primitives have no template and pay only the flat cost (they are
    the prior). Compare against the flat :class:`CompressionMetric` to see the effect (E3→E4).
    """

    def library_bits(self, library: Library) -> float:
        flat = super().library_bits(library)
        definitions = sum(p.template.size() for p in library.primitives if p.template is not None)
        return flat + definitions


def compression_ratio(baseline: float, candidate: float) -> float:
    """How much a corpus shrank: ``baseline / candidate``.

    ``> 1`` means ``candidate`` described the same corpus more compactly than
    ``baseline`` (the win we want from a learned library). ``inf`` if ``candidate`` is 0.
    """
    return baseline / candidate if candidate else float("inf")


def speedup_ratio(baseline_considered: float, candidate_considered: float) -> float:
    """Search speedup: ``baseline / candidate`` nodes considered (same shape as compression).

    ``> 1`` means the candidate library reached the solutions with less search effort — the
    bootstrap payoff, where a learned abstraction collapses depth. ``inf`` if candidate is 0.
    """
    return baseline_considered / candidate_considered if candidate_considered else float("inf")
