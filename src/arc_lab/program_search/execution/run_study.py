"""The STUDY activity: search + learn + targets, over two corpora (EXECUTION.md).

``run_study`` executes: (1) SEARCH + LEARN on the train corpus with **L1** -> the grown
**L2**; (2) **L3** = L1 + the target abstractions; (3) the grid ``(L1, L2, L3) x budgets
x (train, eval)`` as plain SEARCH recorded runs — every cell is the same recorded-run
primitive, so cells already computed (e.g. the learn activity's derived runs) are served
from cache by ``run_id``.

``create_study_report`` is the read side: a *pure* function of a completed
:class:`StudyResult` — behavioral check of invented abstractions vs targets, solve-rate
and search-effort comparisons across the grid, and transfer metrics. It never executes.

The behavioral check grades an invented primitive against a target by **behavior**, not
syntax: identical templates match immediately; otherwise both are evaluated over probe
inputs (train-corpus example grids for GRID params; the full 0-9 range for COLOR; small
canonical ranges for INT/BOOL) under every type-compatible argument permutation. Probe
combinations are capped at :data:`MAX_PROBE_COMBOS` (recorded in the report — never a
silent cap). Targets are observables only: nothing on the execution path reads them.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from arc_lab.core.grid import Grid
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive, Value
from arc_lab.program_search.substrate.types import BOOL, COLOR, GRID, INT, Type

from .execute import execute
from .model.run_record import RunRecord
from .model.run_spec import RunSpec
from .model.serde import to_data
from .model.study_spec import StudySpec
from .run_search_learn import LearnActivityResult, run_search_learn

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

#: The library roles of the study grid, in report order.
LIBRARY_ROLES: tuple[str, ...] = ("L1", "L2", "L3")

#: The corpus roles of the study grid (keys are roles, not corpus names — names are provenance).
CORPUS_ROLES: tuple[str, ...] = ("train", "eval")

#: Cap on probe-argument combinations per behavioral comparison. Deterministic (a prefix of
#: the probe product) and reported (`probe_cap`), so a capped check is visible, never silent.
MAX_PROBE_COMBOS = 512

_COLOR_PROBES: tuple[Value, ...] = tuple(range(10))  # the full COLOR domain
_INT_PROBES: tuple[Value, ...] = (0, 1, 2, 3, 4)
_BOOL_PROBES: tuple[Value, ...] = (False, True)


@dataclass(frozen=True, slots=True)
class GridCell:
    """One cell of the study grid: a library role x a budget x a corpus role."""

    library: str  # "L1" | "L2" | "L3"
    budget: Budget
    corpus: str  # "train" | "eval"


@dataclass(frozen=True, slots=True)
class StudyResult:
    """Everything ``run_study`` produced: the learn activity, the libraries, the grid."""

    spec: StudySpec
    learn: LearnActivityResult
    libraries: dict[str, Library]  # keyed by LIBRARY_ROLES
    grid: dict[GridCell, RunRecord]


def run_study(spec: StudySpec, *, runs_root: Path | None = None) -> StudyResult:
    """Execute a study: learn L2, build L3, run the full grid (cache hits are free)."""
    learn = run_search_learn(
        spec.base_config, spec.train_corpus, spec.eval_corpus, runs_root=runs_root
    )

    l1 = spec.base_config.library
    l2 = learn.learn.learned_library()
    l3 = l1.extended(
        name=f"{l1.name}+targets",
        extra=tuple(
            make_abstraction(target.name, target.template, l1)
            for target in spec.target_abstractions
        ),
    )
    libraries = {"L1": l1, "L2": l2, "L3": l3}
    corpora = {"train": spec.train_corpus, "eval": spec.eval_corpus}

    grid: dict[GridCell, RunRecord] = {}
    for role, library in libraries.items():
        for budget in spec.budgets:
            config = spec.base_config.with_(library=library, budget=budget, learn=None)
            for corpus_role, corpus in corpora.items():
                cell = GridCell(library=role, budget=budget, corpus=corpus_role)
                grid[cell] = execute(RunSpec(config=config, corpus=corpus), runs_root=runs_root)
    logger.info("study grid complete: %d cells", len(grid))
    return StudyResult(spec=spec, learn=learn, libraries=libraries, grid=grid)


# -- the report (pure read over the StudyResult; the analyze layer) ---------------


def create_study_report(result: StudyResult) -> dict[str, object]:
    """The study report: behavioral check, solve rates, search effort, transfer. Pure read."""
    spec = result.spec
    invented = _invented(result.libraries["L1"], result.libraries["L2"])
    probes = tuple(example.input for task in spec.train_corpus for example in task.train)

    behavioral: list[dict[str, object]] = []
    for target in spec.target_abstractions:
        target_primitive = result.libraries["L3"].get(target.name)
        matched_by = [
            primitive.name
            for primitive in invented
            if _matches_target(primitive, target_primitive, probes)
        ]
        behavioral.append(
            {"target": target.name, "matched": bool(matched_by), "matched_by": matched_by}
        )

    cells = [
        {
            "library": cell.library,
            "budget": to_data(cell.budget),
            "corpus": cell.corpus,
            "run_id": record.run_id,
            **_cell_metrics(record),
        }
        for cell, record in result.grid.items()
    ]

    return {
        "study": spec.to_dict(),
        "learn": {"run_id": result.learn.learn.run_id, **result.learn.learn.results()},
        "invented": [primitive.name for primitive in invented],
        "behavioral_check": behavioral,
        "probe_cap": MAX_PROBE_COMBOS,
        "grid": cells,
        "effort": _effort_comparison(result),
        "transfer": _transfer_metrics(result),
    }


def _invented(l1: Library, l2: Library) -> tuple[Primitive, ...]:
    """The primitives sleep minted: present in L2, absent from L1."""
    starting = {primitive.name for primitive in l1.primitives}
    return tuple(p for p in l2.primitives if p.name not in starting)


def _cell_metrics(record: RunRecord) -> dict[str, object]:
    results = record.results()
    return {
        "solved": results.get("solved"),
        "task_count": results.get("task_count"),
        "considered_total": results.get("considered_total"),
    }


def _effort_comparison(result: StudyResult) -> list[dict[str, object]]:
    """Per (budget, corpus): each library's ``considered`` and its speedup vs L1.

    Speedup = considered(L1) / considered(Lx): > 1 means the richer library reached its
    solutions through fewer candidates — a distinct, often earlier signal than enablement.
    """
    rows: list[dict[str, object]] = []
    for budget in result.spec.budgets:
        for corpus_role in CORPUS_ROLES:
            considered: dict[str, int | None] = {}
            for role in LIBRARY_ROLES:
                record = result.grid[GridCell(library=role, budget=budget, corpus=corpus_role)]
                value = record.results().get("considered_total")
                considered[role] = value if isinstance(value, int) else None
            baseline = considered["L1"]
            speedup: dict[str, float | None] = {}
            for role in LIBRARY_ROLES:
                if role == "L1":
                    continue
                considered_x = considered[role]
                speedup[role] = (
                    baseline / considered_x
                    if isinstance(baseline, int)
                    and isinstance(considered_x, int)
                    and considered_x > 0
                    else None
                )
            rows.append(
                {
                    "budget": to_data(budget),
                    "corpus": corpus_role,
                    "considered": dict(considered),
                    "speedup_vs_L1": speedup,
                }
            )
    return rows


def _transfer_metrics(result: StudyResult) -> list[dict[str, object]]:
    """Per (library, budget): eval-corpus cells vs train-corpus cells — does it transfer?"""
    rows: list[dict[str, object]] = []
    for role in LIBRARY_ROLES:
        for budget in result.spec.budgets:
            row: dict[str, object] = {"library": role, "budget": to_data(budget)}
            for corpus_role in CORPUS_ROLES:
                record = result.grid[GridCell(library=role, budget=budget, corpus=corpus_role)]
                results = record.results()
                solved, count = results.get("solved"), results.get("task_count")
                row[f"{corpus_role}_solved"] = solved
                row[f"{corpus_role}_task_count"] = count
                row[f"{corpus_role}_rate"] = (
                    solved / count
                    if isinstance(solved, int) and isinstance(count, int) and count > 0
                    else None
                )
            rows.append(row)
    return rows


# -- behavioral equivalence (the checker behind the behavioral check) -------------


def _matches_target(candidate: Primitive, target: Primitive, probe_grids: tuple[Grid, ...]) -> bool:
    """True iff ``candidate`` behaves as ``target`` — syntactic identity, else probing.

    Identical templates match immediately. Otherwise both are applied to probe-argument
    tuples (see module docstring) under every argument permutation that lines the types
    up — a factoring that merely reorders its parameters is still the target. Variadic
    primitives (no fixed arity to probe) match by template identity only. A parameter
    type with no probe source (arrow / parametric container) likewise falls back to
    template identity — extend the probe sources when such targets become expressible.
    """
    if candidate.template is not None and candidate.template == target.template:
        return True
    if candidate.return_type != target.return_type:
        return False
    if candidate.is_variadic or target.is_variadic:
        return False  # template-identity fallback already tried
    if len(candidate.param_types) != len(target.param_types):
        return False
    per_param: list[tuple[Value, ...]] = []
    for param_type in target.param_types:
        values = _probe_values(param_type, probe_grids)
        if values is None or not values:
            return False  # some parameter is not probeable
        per_param.append(values)
    probe_tuples = list(itertools.islice(itertools.product(*per_param), MAX_PROBE_COMBOS))
    for permutation in _type_matched_permutations(candidate.param_types, target.param_types):
        if all(_agree(candidate, target, permutation, args) for args in probe_tuples):
            return True
    return False


def _probe_values(param_type: Type, probe_grids: tuple[Grid, ...]) -> tuple[Value, ...] | None:
    if param_type == GRID:
        return probe_grids
    if param_type == COLOR:
        return _COLOR_PROBES
    if param_type == INT:
        return _INT_PROBES
    if param_type == BOOL:
        return _BOOL_PROBES
    return None


def _type_matched_permutations(
    candidate_params: tuple[Type, ...], target_params: tuple[Type, ...]
) -> Iterator[tuple[int, ...]]:
    """Permutations ``p`` with ``candidate_params[i] == target_params[p[i]]``, identity first."""
    for permutation in itertools.permutations(range(len(target_params))):
        if all(candidate_params[i] == target_params[j] for i, j in enumerate(permutation)):
            yield permutation


def _agree(
    candidate: Primitive,
    target: Primitive,
    permutation: tuple[int, ...],
    args: tuple[Value, ...],
) -> bool:
    """Both impls succeed and produce equal values on ``args`` (candidate's reordered)."""
    try:
        expected = target.impl(*args)
        actual = candidate.impl(*(args[j] for j in permutation))
    except Exception:  # a probe outside either impl's domain is a disagreement
        return False
    result: bool = expected == actual
    return result
