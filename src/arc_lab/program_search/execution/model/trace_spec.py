"""``TraceSpec``: how much of a run's search to observe — deliberately OUTSIDE run identity.

Unlike ``LearnSpec`` (all in run identity, since loop params change *what's computed*),
``TraceSpec`` never touches ``Config``/``run_id`` at all: it governs what gets *recorded about*
a computation, never the computation itself. That's sound specifically because this codebase is
deterministic (no RNG anywhere) — re-executing a cached run with a different ``TraceSpec``
provably reproduces the identical search, so telemetry can be (re)attached to an existing run
directory without any risk that it describes a different execution than the one whose results
are already cached. ``execute()`` takes ``trace`` as a plain keyword argument, not a ``Config``
field.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.search.tracking import SampleSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceSpec:
    """What to observe, beyond the always-on outcome counts (``search/tracking.py``).

    ``samples`` and ``capture_all`` can both be set — they answer different questions. Sampling
    guarantees a few examples of *every* key/outcome bucket even if a run's considered candidates
    are truncated before reaching the global capture cap; full capture gives you the (capped) raw
    stream in arrival order. Neither perturbs the search itself — both are pure observers.
    """

    #: Reservoir samplers to keep — the default (small, deterministic ``first_k``) is cheap
    #: enough to run unconditionally, which is why it's the class default rather than `()`.
    samples: tuple[SampleSpec, ...] = (SampleSpec(k=2, mode="first_k"),)
    #: Stream every considered candidate to ``capture/<task_id>.jsonl`` — expensive at scale
    #: (a run can consider millions of candidates), so opt-in and off by default.
    capture_all: bool = False
    #: Hard cap on captured candidates once ``capture_all=True`` — stops *writing* once hit but
    #: never perturbs the search itself; truncation is recorded loudly in ``manifest.json``, never
    #: silent. No time-based cap exists on purpose: a wall-clock cap would make the artifact
    #: depend on which machine produced it, breaking the "recorded run is deterministic" invariant.
    capture_all_max: int = 1000
    #: Reserved — candidate provenance (which search mechanism produced it: composition,
    #: lambda-synthesis, branch injection, ...) is a distinct, not-yet-built tracked dimension;
    #: every current preset (`execution/presets.py`) leaves those mechanisms dormant anyway.
    mechanisms: bool = False
    #: Profile the run under cProfile and write ``profile/stats.prof`` + ``profile/summary.txt``
    #: (``execution/profiling.py``). Off by default: the profiler adds per-call overhead, so it is a
    #: diagnostic switch, not always-on. Like every other field here it stays outside run identity
    #: (profiling observes the search, never changes it), but its wall-clock output is inherently
    #: non-deterministic, so it lands only in ``profile/`` and never in ``results.json``. Only takes
    #: effect when the run actually executes (a fresh run, or a cached one with ``force_recapture``).
    profile: bool = False
