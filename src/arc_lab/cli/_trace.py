"""Shared CLI parsing for ``TraceSpec`` flags: ``--sample``, ``--track-all``, ``--capture-max``.

Kept out of run identity on purpose (``TraceSpec``'s own docstring has the determinism
argument) — these flags only ever reach ``execute()``'s ``trace`` keyword, never ``Config``.
"""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.model.trace_spec import TraceSpec
from arc_lab.program_search.search.tracking import SampleSpec


def parse_sample_spec(raw: str) -> SampleSpec:
    """Parse one ``--sample`` value: ``"k:mode"``, e.g. ``"2:first_k"``."""
    k_str, _, mode = raw.partition(":")
    if not mode:
        raise typer.BadParameter(f"expected 'k:mode' (e.g. '2:first_k'), got {raw!r}")
    try:
        k = int(k_str)
    except ValueError as exc:
        raise typer.BadParameter(f"k must be an int, got {k_str!r}") from exc
    if mode == "first_k":
        return SampleSpec(k=k, mode="first_k")
    if mode == "cheapest_k":
        return SampleSpec(k=k, mode="cheapest_k")
    raise typer.BadParameter(f"mode must be 'first_k' or 'cheapest_k', got {mode!r}")


def build_trace_spec(
    samples: list[str], track_all: bool, capture_max: int, profile: bool = False
) -> TraceSpec:
    """The ``TraceSpec`` a CLI command's ``--sample``/``--track-all``/``--capture-max``/``--profile``
    flags name.

    No ``--sample`` at all keeps ``TraceSpec``'s own default sampler (small, deterministic,
    cheap enough to always be on) rather than turning sampling off.
    """
    parsed_samples = tuple(parse_sample_spec(spec) for spec in samples)
    if not samples:
        return TraceSpec(capture_all=track_all, capture_all_max=capture_max, profile=profile)
    return TraceSpec(
        samples=parsed_samples,
        capture_all=track_all,
        capture_all_max=capture_max,
        profile=profile,
    )
