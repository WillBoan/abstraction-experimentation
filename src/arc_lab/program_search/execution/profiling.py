"""Opt-in cProfile of a run's execution, rendered to a readable phase rollup.

Enabled by ``TraceSpec.profile`` (telemetry, so outside run identity — ``model/trace_spec.py``):
``execute()`` wraps the run body in a ``cProfile.Profile`` and, at the end, dumps the raw stats
(``profile/stats.prof`` — explore with ``pstats``/``snakeviz``) plus a human ``profile/summary.txt``.

The summary's phase rollup maps a handful of load-bearing functions to the logical stages of
bottom-up search (generation / evaluation / dedup / tracking / cost). It is **best-effort and
diagnostic**: the mapping is a hand-maintained list of ``(file, function)`` anchors, an
``other / unattributed`` row always closes the gap to the profiled total (so the table never
falsely claims to account for 100%), and a missing anchor simply reads as ``0`` rather than
erroring. The stages were chosen to sit on *disjoint* call subtrees under ``_enumerate`` so their
cumulative times can be summed without double-counting; if the engine's shape changes, re-check
that property here rather than trusting the numbers.

A hard caveat, printed in the artifact itself: cProfile adds per-call overhead (inflating absolute
wall time several-fold and over-weighting high-call-count Python glue), so the rollup's *shares*
are directional, not exact accounting.
"""

from __future__ import annotations

import cProfile
import io
import pstats
from pstats import SortKey

from .model.run_record import RunRecord

#: Logical search stages -> a ``(file-basename-substring, function-name)`` anchor whose cumulative
#: time stands in for that stage. Order is the funnel order a candidate flows through. These anchors
#: are deliberately on disjoint subtrees (``_compose`` builds the frontier; ``compute_signature``
#: evaluates it; the rest run inside ``_absorb_one`` as siblings) so summing their cumtime is sound.
_PHASE_ANCHORS: tuple[tuple[str, str, str], ...] = (
    ("generation: _compose (enumerate + type-check candidates)", "search_engine.py", "_compose"),
    (
        "evaluation: compute_signature (run programs on train grids)",
        "signature.py",
        "compute_signature",
    ),
    ("dedup: add_dedup (pool insert + signature hash)", "pool.py", "add_dedup"),
    ("tracking: primitive_keys (capability tree walk)", "tracking.py", "primitive_keys"),
    ("record: tracker.record (outcome + per-primitive tallies)", "tracking.py", "record"),
    ("cost: Cost.of (program size)", "cost.py", "of"),
    ("frontier: cheapest (round truncation)", "pool.py", "cheapest"),
)

_UNATTRIBUTED = "other / unattributed (enumerate, predict, IO, startup)"

#: How many functions the self-time (``tottime``) table lists.
_TOP_N = 15


def _cumtime(stats: pstats.Stats, file_sub: str, func: str) -> float:
    """Cumulative time of the ``func`` defined in a file whose path contains ``file_sub`` (``0.0``
    if absent). A function has one ``(file, line, name)`` key, so at most one entry matches."""
    total = 0.0
    for (path, _lineno, name), values in stats.stats.items():  # type: ignore[attr-defined]
        if name == func and file_sub in path:
            total += values[3]  # (cc, nc, tt, ct, callers) -> cumulative time
    return total


def render_profile_summary(stats: pstats.Stats) -> str:
    """A readable ``profile/summary.txt``: the caveat, the total, the phase rollup, then the
    standard top-``_TOP_N``-by-self-time table."""
    total = stats.total_tt  # type: ignore[attr-defined]
    rows = [(label, _cumtime(stats, file_sub, func)) for label, file_sub, func in _PHASE_ANCHORS]
    attributed = sum(cumtime for _, cumtime in rows)
    rows.append((_UNATTRIBUTED, max(0.0, total - attributed)))
    width = max(len(label) for label, _ in rows)

    def pct(value: float) -> float:
        return 100.0 * value / total if total else 0.0

    lines = [
        "# Search execution profile (cProfile)",
        "#",
        "# CAVEAT: cProfile adds per-call overhead - it inflates absolute wall time several-fold",
        "# and over-weights high-call-count Python glue. Read the shares as DIRECTIONAL, not exact.",
        "# The phase rollup is best-effort; 'other / unattributed' closes the gap to the total.",
        "",
        f"total profiled wall time: {total:.3f}s",
        "",
        "phase rollup (cumulative time; anchors chosen to be non-overlapping):",
    ]
    lines += [
        f"  {label:<{width}}  {cumtime:8.3f}s  {pct(cumtime):5.1f}%" for label, cumtime in rows
    ]
    lines += ["", f"top {_TOP_N} functions by self time (tottime):", ""]

    buffer = io.StringIO()
    stats.stream = buffer  # type: ignore[attr-defined]
    stats.sort_stats(SortKey.TIME).print_stats(_TOP_N)
    lines.append(buffer.getvalue())
    return "\n".join(lines)


def write_profile_artifacts(profiler: cProfile.Profile, record: RunRecord) -> None:
    """Dump the raw ``profile/stats.prof`` and the rendered ``profile/summary.txt`` for ``record``."""
    record.profile_dir.mkdir(parents=True, exist_ok=True)
    profiler.dump_stats(str(record.profile_stats_path))
    stats = pstats.Stats(str(record.profile_stats_path))
    record.profile_summary_path.write_text(render_profile_summary(stats), encoding="utf-8")
