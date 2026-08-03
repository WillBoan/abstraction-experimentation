"""Per-cell provenance: which recorded runs a ladder report was actually built from.

A ladder report is a synthesis over ~10 recorded runs (the oracle chain, the climb's 2-3 runs,
the off-chain arm, the raw arm). Until 2026-08-03 it recorded **none** of them, so a committed
number could not be traced to the run behind it and staleness could not be detected at all --
`run_id` is a content hash of ``RunSpec``, but nothing said which hashes an artifact had used. The
2026-07-26 derived depth schedule moved eight ladders' ``run_id``s and no instrument could say
which artifacts had gone stale ([experiments/2026-08-03-run-store-census/]).

So: every cell the report reads is listed here with its identity (``run_id``) and the
**comparability key** -- the config fields that must match for two cells' costs to mean the same
thing (``LADDER-RELATIONSHIPS-2026-07-23.md``). Read off the recorded ``runspec.json``, never
re-derived, so this describes the run that happened rather than the run the current code would
produce -- which is exactly what makes comparing the two a staleness test.

Deliberately NOT stored: absolute paths (a committed artifact must not carry a developer's home
directory). ``run_dir`` is the directory *name*, which carries the timestamp; ``find_run_dir``
resolves a run by ``run_id`` suffix across date folders anyway.
"""

from __future__ import annotations

from typing import Any

from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders.run import LadderResult

#: Budget fields that change what a search COSTS, so two cells differing in any of them are not
#: cost-comparable (the `max_pool` 150 -> 30 pair measured 19.0x-25.6x apart at identical verdicts).
BUDGET_KEYS = (
    "depth_limit",
    "max_arity",
    "max_pool",
    "considered_limit",
    "considered_limit_mode",
    "solution_limit",
    "solution_limit_mode",
)


def _learn_key(config: dict[str, Any]) -> dict[str, Any] | None:
    """The learn-side comparability key, or ``None`` for a SEARCH run."""
    learn = config.get("learn")
    if not isinstance(learn, dict):
        return None
    engine = learn.get("learn_engine")
    engine = engine if isinstance(engine, dict) else {}
    proposer = engine.get("proposer")
    metric = engine.get("metric")
    return {
        "learn_engine": engine.get("kind"),
        "proposer": (proposer or {}).get("kind") if isinstance(proposer, dict) else None,
        "metric": (metric or {}).get("kind") if isinstance(metric, dict) else None,
        "iterations": learn.get("iterations"),
    }


def cell_provenance(cell: str, record: RunRecord) -> dict[str, Any]:
    """One cell's provenance row. Tolerant by design: a torn or absent ``runspec.json`` yields the
    identity fields with the rest ``None``, because a missing run is itself worth recording."""
    row: dict[str, Any] = {
        "cell": cell,
        "run_id": record.run_id,
        "run_dir": record.run_dir.name,
        "completed": record.completed,
        "commit": None,
        "corpus_name": None,
        "library": None,
        "budget": None,
        "learn": None,
    }
    try:
        spec = record.runspec()
    except (OSError, ValueError):
        return row
    config = spec.get("config")
    config = config if isinstance(config, dict) else {}
    budget = config.get("budget")
    budget = budget if isinstance(budget, dict) else {}
    library = config.get("library")
    row.update(
        commit=spec.get("commit"),
        corpus_name=spec.get("corpus_name"),
        library=(library or {}).get("name") if isinstance(library, dict) else None,
        budget={key: budget.get(key) for key in BUDGET_KEYS},
        learn=_learn_key(config),
    )
    return row


def ladder_provenance(result: LadderResult) -> list[dict[str, Any]]:
    """Every recorded run behind a ladder report, in the order the pipeline produced them.

    Cell names are stable identifiers, not prose -- a staleness checker keys on them:
    ``chain/L{i}`` (the oracle chain, one per level), ``climb/learn`` + ``climb/train-usefulness``
    + ``climb/transfer`` (the LEARN activity's 2-3 runs), ``off-chain``, ``raw-arm``.
    """
    rows: list[dict[str, Any]] = [
        cell_provenance(f"chain/L{level}", record)
        for level, record in sorted(result.oracle_chain.items())
    ]
    if result.learn is not None:
        rows.append(cell_provenance("climb/learn", result.learn.learn))
        rows.append(cell_provenance("climb/train-usefulness", result.learn.train_usefulness))
        if result.learn.transfer is not None:
            rows.append(cell_provenance("climb/transfer", result.learn.transfer))
    if result.off_chain is not None:
        rows.append(cell_provenance("off-chain", result.off_chain))
    if result.raw_arm is not None:
        rows.append(cell_provenance("raw-arm", result.raw_arm.record))
    return rows


#: Budget fields a ladder run varies BY DESIGN, so they cannot signal drift *within* one report:
#: ``run.py::pool_for_depth`` scales the pool with each level's own derived ``depth_limit``
#: (LADDER-FORMAT CFG-7), so a non-uniform schedule moves both. They are still recorded per cell,
#: which is what a cross-report comparison (the `max_pool` 150 vs 30 pair, 19.0x-25.6x apart)
#: reads.
DERIVED_PER_LEVEL = ("depth_limit", "max_pool")

#: The raw arm is a deliberately differently-budgeted baseline -- freed pool, a ``K x laddered``
#: guard, ``solution_limit=1`` (``run.py::RawArm``). Counting it would make every report read as
#: multi-generation, and a warning that always fires is not a warning.
GENERATION_EXEMPT_CELLS = ("raw-arm",)


def _learn_label(rows: list[dict[str, Any]]) -> str:
    """The report's learn configuration, as a label shared by ALL its cells.

    A ladder runs one learn config, but only the ``climb/learn`` cell carries it -- its derived
    SEARCH runs and the whole oracle chain are `learn=None` by construction. So this is a property
    of the REPORT, folded into every cell's generation label rather than compared per cell (which
    would split every report into "the SEARCH cells" and "the LEARN cell" and signal nothing).

    It has to be in the label: a learn-side change moves every ``run_id`` while touching neither
    the commit nor the budget, so without it a governance-objective ARM and the batch of record
    read as the same generation -- which is the exact confusion the arm exists to avoid.
    """
    keys = {
        tuple(sorted((row.get("learn") or {}).items()))
        for row in rows
        if isinstance(row.get("learn"), dict)
    }
    if not keys:
        return "learn=none"
    return " | ".join(sorted(",".join(f"{name}={value}" for name, value in key) for key in keys))


def config_generations(rows: list[dict[str, Any]]) -> list[str]:
    """The distinct ``(pinned budget, learn config)`` generations across a report's cells.

    More than one means this report's cells were run under configs that are **not mutually
    cost-comparable** -- the condition the run-store census found in every ladder but two, and the
    one that predicted which results survived re-certification
    ([experiments/2026-08-03-run-store-census/]).

    Excluded, as legitimate variation: per-level derived fields (:data:`DERIVED_PER_LEVEL`) and the
    raw arm (:data:`GENERATION_EXEMPT_CELLS`).

    **The commit is deliberately NOT part of this key**, though it is recorded per cell. A run's
    identity is ``content_id(config x corpus)`` and this codebase is deterministic by invariant (no
    RNG; frozen specs), so two cells with the same ``run_id`` are the same computation whichever
    commit executed them -- if that failed, the cache would be unsound and a batch would mean
    nothing anyway. Keying on commit would instead flag every report assembled from cache hits
    across any commit, including docs-only ones, and a warning that always fires is not a warning.
    Measured on the first real batch: 4 of 32 members were flagged for a commit difference with
    every budget and learn field identical.

    What this therefore does NOT detect is artifact staleness -- whether a committed report still
    describes the runs the current spec would produce. That is a comparison of recorded ``run_id``s
    against freshly derived ones (a cross-artifact check), not a property of one report's cells.
    """
    learn = _learn_label(rows)
    seen = set()
    for row in rows:
        if row.get("cell") in GENERATION_EXEMPT_CELLS:
            continue
        budget = row.get("budget") or {}
        pinned = tuple(
            f"{key}={budget.get(key)}" for key in BUDGET_KEYS if key not in DERIVED_PER_LEVEL
        )
        seen.add(f"{' '.join(pinned)} [{learn}]")
    return sorted(seen)


def recorded_commits(rows: list[dict[str, Any]]) -> list[str]:
    """The distinct commits that executed this report's cells, newest-agnostic and sorted.

    Provenance, not a verdict: more than one is the ordinary consequence of content-hash caching
    serving cells recorded earlier. Worth showing (a reader can see how much of a report is cache),
    never worth failing on -- see :func:`config_generations` for why.
    """
    return sorted({str(row["commit"]) for row in rows if row.get("commit")})
