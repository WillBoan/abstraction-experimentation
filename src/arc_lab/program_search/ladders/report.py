"""``create_ladder_report``: the Ladder read side — a pure function of a ``LadderResult``.

Synthesizes the headline metrics from the recorded runs: the certificate, the climb trace (what
minted when), rung recovery (minted abstractions vs the intended rungs, graded behaviorally), the
per-task **cost matrix** over the oracle chain (the design's primary derived object -- considered
count, solve generation, first/cheapest solution index, fitted ``b_eff`` per cell), the RQ1
amortization (raw vs laddered, both accountings), and the comparison views (loop-overhead factor,
marginal rung value, vocabulary tax, enablement). It never executes.
``render_report_markdown`` renders the report dict as the committed ``results.md`` artifact, whose
"Not computed here" section names what is still missing and why (break-even horizon; the sleep
cost conversion weight `w`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arc_lab.program_search.analysis.behavioral import MAX_PROBE_COMBOS, matches_target
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.certificate import certify
from arc_lab.program_search.ladders.run import LadderResult
from arc_lab.program_search.substrate.abstraction import make_abstraction


def create_ladder_report(result: LadderResult) -> dict[str, object]:
    """The ladder report: shape, certificate, climb trace, rung recovery, the per-task cost matrix,
    jump costs, amortization, and the comparison views."""
    spec, shape = result.spec, result.shape
    cert = certify(result)
    k = len(spec.rungs)
    cells = {level: _per_task_cells(rec) for level, rec in result.oracle_chain.items()}
    considered: dict[int, dict[str, int]] = {
        level: {tid: _as_int(cell["considered"]) for tid, cell in by_task.items()}
        for level, by_task in cells.items()
    }
    solved = {level: _search_solved_ids(rec) for level, rec in result.oracle_chain.items()}
    rung_of = {demo.task_id: rung.name for rung in spec.rungs for demo in rung.demonstrations}
    for task_id in spec.top.task_ids:
        rung_of[task_id] = "top"

    # Cost-to-first-solution (exact): the candidate_index at which the first solution was
    # absorbed. The task-sensitive currency -- without early stop, cost-paid-full is the whole
    # budgeted enumeration, so it barely varies by task and understates what a rung buys.
    first_index: dict[int, dict[str, int]] = {
        level: {
            tid: _as_int(cell["first_solution_index"])
            for tid, cell in by_task.items()
            if isinstance(cell.get("first_solution_index"), int)
        }
        for level, by_task in cells.items()
    }

    # Jump costs: rung i solved under L_{i-1}; the top under L_k.
    jump_costs: dict[str, int] = {}
    jump_costs_to_first: dict[str, int | None] = {}
    for i, rung in enumerate(spec.rungs, start=1):
        ids = [demo.task_id for demo in rung.demonstrations]
        jump_costs[rung.name] = sum(considered[i - 1].get(tid, 0) for tid in ids)
        jump_costs_to_first[rung.name] = _sum_to_first(first_index[i - 1], ids)
    top_ids = list(spec.top.task_ids)
    top_jump_cost = sum(considered[k].get(tid, 0) for tid in top_ids)
    top_jump_to_first = _sum_to_first(first_index[k], top_ids)
    laddered_marginal = sum(jump_costs.values()) + top_jump_cost
    to_first_parts = [*jump_costs_to_first.values(), top_jump_to_first]
    laddered_marginal_to_first = (
        sum(part for part in to_first_parts if part is not None)
        if all(part is not None for part in to_first_parts)
        else None
    )

    # Raw: the top under L_0 (the Floor). Censored -- the top is unreachable at the reference budget
    # (d_raw exceeds it), so this is cost-paid-full, a LOWER BOUND on the true raw cost.
    raw_considered = sum(considered[0].get(tid, 0) for tid in top_ids)
    raw_solved = bool(top_ids) and all(tid in solved[0] for tid in top_ids)
    off_solved = bool(top_ids) and all(
        tid in _search_solved_ids(result.off_chain) for tid in top_ids
    )

    # Rung recovery: minted (learned) abstractions vs the intended rungs, graded behaviorally.
    learned = result.learn.learn.learned_library()
    floor_names = {p.name for p in spec.floor().primitives}
    invented = [p for p in learned.primitives if p.name not in floor_names]
    probes = tuple(
        example.input for entry in spec.train_corpus.entries for example in entry.task.train
    )
    recovery: list[dict[str, object]] = []
    for i, rung in enumerate(spec.rungs, start=1):
        target = make_abstraction(rung.name, rung.template, spec.oracle_library(i - 1))
        matched = [p.name for p in invented if matches_target(p, target, probes)]
        recovery.append(
            {
                "rung": rung.name,
                "level": rung.level,
                "recovered": bool(matched),
                "matched_by": matched,
            }
        )

    climb = _climb_trace(result.learn.learn)
    # End-to-end laddered cost: every wake re-searches every task, iteration after iteration.
    end_to_end = 0
    for entry in climb:
        wake_considered = entry.get("wake_considered")
        if isinstance(wake_considered, int):
            end_to_end += wake_considered

    # The cost matrix (design doc 3.5): cost(task, library) over the oracle-chain columns, with
    # each cell's solve detail. The source for every comparison view below.
    cost_matrix = [
        {
            "task_id": task_id,
            "rung": rung_of.get(task_id, "-"),
            "columns": {
                str(level): dict(cells[level].get(task_id, _EMPTY_CELL)) for level in sorted(cells)
            },
        }
        for task_id in sorted(rung_of, key=lambda t: (rung_of[t], t))
    ]

    # Marginal rung value: what rung i bought for the layer above it -- cost(layer above | L_{i-1})
    # / cost(layer above | L_i). The numerator is usually CENSORED (the layer above is unsolved at
    # L_{i-1} by design -- that is the double-jump claim), so the ratio is a lower bound.
    rung_value: list[dict[str, object]] = []
    for i, rung in enumerate(spec.rungs, start=1):
        above_ids = (
            [demo.task_id for demo in spec.rungs[i].demonstrations]
            if i < k
            else list(spec.top.task_ids)
        )
        below = sum(considered[i - 1].get(tid, 0) for tid in above_ids)
        at = sum(considered[i].get(tid, 0) for tid in above_ids)
        censored = not all(tid in solved[i - 1] for tid in above_ids)
        rung_value.append(
            {
                "rung": rung.name,
                "layer_above": "top" if i == k else spec.rungs[i].name,
                "cost_without_rung": below,
                "cost_with_rung": at,
                "ratio": (below / at) if at else None,
                "censored": censored,
            }
        )

    # Vocabulary tax: the SAME tasks re-measured under a bigger library. A rung's demonstrating
    # tasks don't use the rungs above them, so any cost increase from L_{i-1} to L_k is pure tax.
    vocabulary_tax: list[dict[str, object]] = []
    for i, rung in enumerate(spec.rungs, start=1):
        ids = [demo.task_id for demo in rung.demonstrations]
        own = sum(considered[i - 1].get(tid, 0) for tid in ids)
        full = sum(considered[k].get(tid, 0) for tid in ids)
        vocabulary_tax.append(
            {
                "rung": rung.name,
                "at_own_level": own,
                "at_full_library": full,
                "factor": (full / own) if own else None,
            }
        )

    # Enablement: tasks solvable under L_i but not under L_{i-1}, at the pinned budget.
    enablement = {
        str(level): sorted(solved[level] - solved[level - 1])
        for level in sorted(cells)
        if level >= 1
    }

    return {
        "ladder": spec.to_dict(),
        "shape": {
            "height": shape.height,
            "raw_depth_profile": list(shape.raw_depth_profile),
            "max_jump_depth": max((s.jump_depth for s in shape.rungs), default=0),
            "validity_window": list(shape.validity_window),
            "lint_ok": shape.ok,
        },
        "certificate": {
            "admitted": cert.admitted,
            "tractable_jumps": cert.tractable_jumps,
            "no_skip_paths": cert.no_skip_paths,
            "demonstration_health": cert.demonstration_health,
        },
        "climb_trace": climb,
        "rung_recovery": recovery,
        "probe_cap": MAX_PROBE_COMBOS,
        "cost_matrix": cost_matrix,
        "comparisons": {
            "loop_overhead_factor": (end_to_end / laddered_marginal) if laddered_marginal else None,
            "marginal_rung_value": rung_value,
            "vocabulary_tax": vocabulary_tax,
            "enablement": enablement,
        },
        "cost": {
            "jump_costs": jump_costs,
            "jump_costs_to_first": jump_costs_to_first,
            "top_jump_cost": top_jump_cost,
            "top_jump_cost_to_first": top_jump_to_first,
            "laddered_marginal_considered": laddered_marginal,
            "laddered_marginal_to_first": laddered_marginal_to_first,
            "laddered_end_to_end_considered": end_to_end,
            "raw_considered": raw_considered,
            "raw_solved": raw_solved,
            "raw_censored": not raw_solved,
            "off_chain_top_solved": off_solved,
            # A meaningful ratio needs a raw baseline that actually SOLVES; when raw is censored
            # (unsolved at the reference budget) raw_considered is only a lower bound, so the ratio
            # is uninformative and reported as None. The depth compression below is the honest signal
            # then; a calibration/deeper-budget raw run gives the considered-ratio (a follow-up).
            "amortization_ratio_considered": (
                raw_considered / laddered_marginal if raw_solved and laddered_marginal else None
            ),
            "budget_compression_depth": {
                "raw_depth": max(shape.raw_depth_profile, default=0),
                "max_jump_depth": max((s.jump_depth for s in shape.rungs), default=0),
            },
        },
    }


def render_report_markdown(report: Mapping[str, Any]) -> str:
    """Render a ``create_ladder_report`` dict as the committed ``results.md`` artifact: the
    certificate, climb trace, rung recovery, and cost accounting as readable markdown. A pure
    formatter -- every number comes from the report dict."""
    ladder: Mapping[str, Any] = report.get("ladder") or {}
    corpus: Mapping[str, Any] = ladder.get("train_corpus") or {}
    name = str(corpus.get("name") or "ladder").split(":")[0]
    shape: Mapping[str, Any] = report.get("shape") or {}
    cert: Mapping[str, Any] = report.get("certificate") or {}
    cost: Mapping[str, Any] = report.get("cost") or {}

    lines = [
        f"<!-- Generated by render_report_markdown -- regenerate with `arc-lab run-ladder {name} "
        "--artifacts <dir>`; never hand-edit. Full numbers: report.json beside this file. -->",
        "",
        f"# Ladder results: {name}",
        "",
        f"- Certificate (the empirical admission gate): "
        f"**{'ADMITTED' if cert.get('admitted') else 'NOT ADMITTED'}**",
        f"- Static lint (asserted in spec.md): {'OK' if shape.get('lint_ok') else 'FAILED'} -- "
        f"height {shape.get('height')}, validity window {shape.get('validity_window')}, "
        f"raw depth profile {shape.get('raw_depth_profile')}",
    ]
    tractable: Mapping[Any, Any] = cert.get("tractable_jumps") or {}
    no_skip: Mapping[Any, Any] = cert.get("no_skip_paths") or {}
    health: Mapping[Any, Any] = cert.get("demonstration_health") or {}
    cert_rows = [["jump", "tractable", "no skip path", "demonstration health"]]
    for level in sorted(tractable, key=int):
        cert_rows.append(
            [
                str(level),
                _yes_no(tractable.get(level)),
                _yes_no(no_skip.get(level)),
                str(health.get(level)),
            ]
        )
    lines += ["", "## Certificate (per jump)", "", *table(cert_rows)]

    climb_rows = [["iter", "wake solved", "considered (all tasks)", "minted", "converged"]]
    for entry in report.get("climb_trace") or []:
        solved = entry.get("wake_solved") or []
        minted = entry.get("minted") or []
        climb_rows.append(
            [
                str(entry.get("iteration")),
                f"{len(solved)}: " + ", ".join(f"`{t}`" for t in solved) if solved else "0",
                _count(entry.get("wake_considered")),
                ", ".join(f"`{m}`" for m in minted) if minted else "-",
                _yes_no(entry.get("converged")),
            ]
        )
    lines += ["", "## Climb trace", "", *table(climb_rows)]

    recovery_rows = [["rung", "level", "recovered", "matched by"]]
    for row in report.get("rung_recovery") or []:
        matched = row.get("matched_by") or []
        recovery_rows.append(
            [
                f"`{row.get('rung')}`",
                str(row.get("level")),
                _yes_no(row.get("recovered")),
                ", ".join(f"`{m}`" for m in matched) if matched else "-",
            ]
        )
    lines += ["", "## Rung recovery", "", *table(recovery_rows)]

    matrix = report.get("cost_matrix") or []
    if matrix:
        levels = sorted((matrix[0].get("columns") or {}), key=int)
        header = ["task", "rung", *(f"L_{level}" for level in levels)]
        matrix_rows = [header]
        for entry in matrix:
            columns = entry.get("columns") or {}
            cells = []
            for level in levels:
                cell = columns.get(level) or {}
                mark = " *" if cell.get("solved") else ""
                cells.append(f"{_count(cell.get('considered'))}{mark}")
            matrix_rows.append([f"`{entry.get('task_id')}`", str(entry.get("rung")), *cells])
        lines += [
            "",
            "## Cost matrix (considered count per task x library)",
            "",
            *table(matrix_rows),
            "",
            "- `*` = the search solved that task in that column; a bare number is cost-paid-full "
            "on an unsolved task (a censored lower bound on what solving would cost).",
            "- `L_i` = Floor + the intended rungs `r_1..r_i` gifted (the oracle chain), all at the "
            "pinned budget.",
            "- These are **cost-paid-full** figures: with no early stop every search enumerates "
            "the entire budgeted space, so a column varies by task only through signature dedup "
            "-- near-constant columns are expected, not a bug. The task-sensitive currency is "
            "**cost-to-first**, in the next table.",
        ]

        detail_rows = [
            [
                "task",
                "library",
                "solve generation",
                "first solution index",
                "cheapest solution index",
                "considered",
                "b_eff",
            ]
        ]
        for entry in matrix:
            columns = entry.get("columns") or {}
            for level in levels:
                cell = columns.get(level) or {}
                if not cell.get("solved"):
                    continue
                detail_rows.append(
                    [
                        f"`{entry.get('task_id')}`",
                        f"L_{level}",
                        str(cell.get("solve_generation")),
                        _count(cell.get("first_solution_index")),
                        _count(cell.get("cheapest_solution_index")),
                        _count(cell.get("considered")),
                        str(cell.get("b_eff") if cell.get("b_eff") is not None else "-"),
                    ]
                )
        lines += [
            "",
            "## Per-task solutions (solved cells only)",
            "",
            *table(detail_rows),
            "",
            "- `first solution index` / `cheapest solution index`: the `candidate_index` at which "
            "the first / the globally-cheapest solution was absorbed (the solution sink -- exact, "
            "and independent of later pool eviction).",
            "- `solve generation`: the composition round the accepted solution was built at "
            "(round 0 = leaves).",
            "- `b_eff`: fitted per-round growth in composed candidates over pre-saturation rounds "
            "(`-` when the pool saturates too early to fit).",
        ]

    jump_costs: Mapping[Any, Any] = cost.get("jump_costs") or {}
    censored = bool(cost.get("raw_censored"))
    ratio = cost.get("amortization_ratio_considered")
    compression: Mapping[str, Any] = cost.get("budget_compression_depth") or {}
    lines += [
        "",
        "## Cost (considered counts)",
        "",
        f"- Laddered marginal: {_count(cost.get('laddered_marginal_considered'))}",
        *(f"  - jump `{rung_name}`: {_count(value)}" for rung_name, value in jump_costs.items()),
        f"  - top jump: {_count(cost.get('top_jump_cost'))}",
        f"- Laddered end-to-end: {_count(cost.get('laddered_end_to_end_considered'))} "
        "(every wake re-searches every task)",
        f"- Raw (Floor on the top tasks): {_count(cost.get('raw_considered'))}"
        + (" -- CENSORED: unsolved at the reference budget, a lower bound" if censored else ""),
        "- Amortization considered-ratio: "
        + (f"{ratio:.2f}" if isinstance(ratio, float) else "n/a (raw censored)"),
        f"- Depth compression: d_raw {compression.get('raw_depth')} -> "
        f"max jump depth {compression.get('max_jump_depth')}",
        f"- Off-chain (Floor + top rung only) solves the top: "
        f"{_yes_no(cost.get('off_chain_top_solved'))}",
    ]

    comparisons: Mapping[str, Any] = report.get("comparisons") or {}
    overhead = comparisons.get("loop_overhead_factor")
    to_first = cost.get("laddered_marginal_to_first")
    jump_to_first: Mapping[Any, Any] = cost.get("jump_costs_to_first") or {}
    lines += [
        "",
        "## Comparisons",
        "",
        "### Two currencies -- read this first",
        "",
        "- **cost-paid-full**: the whole budgeted enumeration. With no early stop, every search "
        "pays it whether it solves at candidate 100 or not at all -- so it is nearly "
        "task-independent and it cannot show what a rung buys in cost terms.",
        "- **cost-to-first**: the `candidate_index` where the first solution was absorbed -- what "
        "an early-stopping search would have paid. This is the currency the rung-value "
        "comparisons below should be read in.",
        f"- Laddered marginal, cost-paid-full: "
        f"{_count(cost.get('laddered_marginal_considered'))} vs cost-to-first: "
        + (_count(to_first) if isinstance(to_first, int) else "n/a (a jump is censored)"),
        *(
            f"  - jump `{name}`: {_count(value) if isinstance(value, int) else 'censored'}"
            for name, value in jump_to_first.items()
        ),
        "  - top jump: "
        + (
            _count(cost.get("top_jump_cost_to_first"))
            if isinstance(cost.get("top_jump_cost_to_first"), int)
            else "censored"
        ),
        "",
        "### Raw vs laddered (RQ1)",
        "",
        f"- Raw {_count(cost.get('raw_considered'))}"
        + (" (CENSORED -- unsolved, a lower bound)" if censored else "")
        + f" vs laddered marginal {_count(cost.get('laddered_marginal_considered'))}: "
        + (
            f"amortization ratio {ratio:.2f}x"
            if isinstance(ratio, float)
            else "ratio not computable -- see 'Why the ratio is missing' below"
        ),
        f"- Depth compression (always honest, no censoring): d_raw "
        f"{compression.get('raw_depth')} -> max jump depth {compression.get('max_jump_depth')} -- "
        "the ladder converts one deep search into shallow ones",
        "",
        "### Marginal vs end-to-end laddered cost",
        "",
        f"- Marginal (jump costs only, the idealized bound): "
        f"{_count(cost.get('laddered_marginal_considered'))}",
        f"- End-to-end (every wake re-searches every task, incl. full-budget failures): "
        f"{_count(cost.get('laddered_end_to_end_considered'))}",
        "- **Loop-overhead factor**: "
        + (f"{overhead:.2f}x" if isinstance(overhead, float) else "n/a")
        + " -- what today's loop mechanics cost above the ideal (re-search + overshoot + "
        "termination + learned-vs-oracle gap)",
    ]

    value_rows = [
        ["rung", "layer above", "cost without rung", "cost with rung", "ratio", "censored"]
    ]
    for row in comparisons.get("marginal_rung_value") or []:
        value_ratio = row.get("ratio")
        value_rows.append(
            [
                f"`{row.get('rung')}`",
                str(row.get("layer_above")),
                _count(row.get("cost_without_rung")),
                _count(row.get("cost_with_rung")),
                f"{value_ratio:.2f}x" if isinstance(value_ratio, float) else "-",
                _yes_no(row.get("censored")),
            ]
        )
    lines += [
        "",
        "### Marginal rung value (what each rung bought the layer above it)",
        "",
        *table(value_rows),
        "",
        "- Censored rows: the layer above is unsolved without the rung (by design -- that IS the "
        "double-jump claim). 'cost without rung' is then a full-budget FAILURE, so the ratio is "
        "not a speedup: a value near or below 1.0x on a censored row means the rung bought "
        "**reachability**, not cost -- read the Enablement section, not this ratio. The ratio "
        "only becomes a speedup measure when the row is uncensored.",
    ]

    tax_rows = [["rung's tasks", "at own level", "at full library L_k", "factor"]]
    for row in comparisons.get("vocabulary_tax") or []:
        factor = row.get("factor")
        tax_rows.append(
            [
                f"`{row.get('rung')}`",
                _count(row.get("at_own_level")),
                _count(row.get("at_full_library")),
                f"{factor:.2f}x" if isinstance(factor, float) else "-",
            ]
        )
    enablement: Mapping[str, Any] = comparisons.get("enablement") or {}
    lines += [
        "",
        "### Vocabulary tax (same tasks, bigger library)",
        "",
        *table(tax_rows),
        "",
        "- These tasks never use the rungs above them, so the increase is pure tax: a wider "
        "round-0 leaf set and more compositions per round. It is paid INSIDE every later jump.",
        "",
        "### Enablement (newly solvable per gifted rung)",
        "",
    ]
    for level in sorted(enablement, key=int):
        ids = enablement[level] or []
        lines.append(
            f"- `L_{level}` (vs `L_{int(level) - 1}`): "
            + (", ".join(f"`{tid}`" for tid in ids) if ids else "nothing new")
        )

    lines += [
        "",
        "## Not computed here",
        "",
    ]
    if censored:
        lines += [
            "- **Why the ratio is missing (raw is censored).** The pinned budget deliberately puts "
            "the raw top out of reach (`d_raw` > `depth_limit`) -- that is the ladder's whole "
            "claim. So the Floor column on the top tasks records what a FAILED full-budget search "
            "cost, not what solving would cost: a lower bound, not the raw cost. Dividing by it "
            "would understate the ladder's value, so the ratio is reported as n/a. To get a real "
            "number, re-run the top tasks at a budget deep enough to solve them raw (an "
            "above-window calibration cell) -- the depth compression above is the honest headline "
            "until then.",
        ]
    lines += [
        "- **Break-even horizon** (how many future top-level tasks justify the ladder): needs the "
        "heldout transfer run's per-task costs read against the learning overhead -- the runs "
        "exist, the view does not yet.",
        "- **Sleep-cost conversion**: the sleep counters (proposal / antiunify-pair counts) are "
        "recorded per iteration in report.json, but converting them into considered-count "
        "equivalents needs the batch-level calibration weight `w`, which is declared once per "
        "batch and does not exist yet.",
    ]
    return "\n".join(lines)


def _yes_no(value: object) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def _count(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) else "?"


def _climb_trace(learn_record: RunRecord) -> list[dict[str, object]]:
    """Per wake-sleep iteration from the LEARN trace: solved-task set + minted abstractions."""
    by_iter: dict[int, dict[str, object]] = {}
    for row in learn_record.trace_rows():
        iteration = row.get("iteration")
        if not isinstance(iteration, int):
            continue
        entry = by_iter.setdefault(iteration, {"iteration": iteration})
        if row.get("phase") == "wake":
            solved = row.get("solved")
            entry["wake_solved"] = solved if isinstance(solved, list) else []
            entry["wake_considered"] = row.get("considered")
        elif row.get("phase") == "sleep":
            added = row.get("added")
            entry["minted"] = added if isinstance(added, list) else []
            entry["converged"] = row.get("converged")
            entry["proposal_count"] = row.get("proposal_count")
            entry["antiunify_pair_count"] = row.get("antiunify_pair_count")
    return [by_iter[i] for i in sorted(by_iter)]


def _sum_to_first(indices: Mapping[str, int], task_ids: list[str]) -> int | None:
    """Total cost-to-first over a task group -- ``None`` if any task is unsolved (censored), since
    a partial sum would silently understate the group's cost."""
    if not task_ids or any(tid not in indices for tid in task_ids):
        return None
    return sum(indices[tid] for tid in task_ids)


def _as_int(value: object) -> int:
    """Trace payloads are ``object``-typed; coerce a count, defaulting a missing one to 0."""
    return value if isinstance(value, int) else 0


#: A (task, library) cell with no recorded search (the task wasn't in that run).
_EMPTY_CELL: dict[str, object] = {
    "considered": 0,
    "solved": False,
    "solve_generation": None,
    "first_solution_index": None,
    "cheapest_solution_index": None,
    "b_eff": None,
}


def _per_task_cells(record: RunRecord) -> dict[str, dict[str, object]]:
    """One cost-matrix column: per task, the considered count plus the solution-sink detail
    (solve generation, first / cheapest candidate index) and the fitted ``b_eff``."""
    out: dict[str, dict[str, object]] = {}
    for row in record.trace_rows():
        tid = row.get("task_id")
        stats = row.get("search_stats")
        if not (isinstance(tid, str) and isinstance(stats, dict)):
            continue
        total = stats.get("total")
        solutions = stats.get("solutions")
        solutions = solutions if isinstance(solutions, dict) else {}
        generations = stats.get("generations")
        out[tid] = {
            "considered": total.get("considered", 0) if isinstance(total, dict) else 0,
            "solved": stats.get("solved_at_generation") is not None,
            "solve_generation": stats.get("solved_at_generation"),
            "first_solution_index": solutions.get("first_index"),
            "cheapest_solution_index": solutions.get("cheapest_index"),
            "b_eff": _fit_b_eff(generations if isinstance(generations, list) else []),
        }
    return out


def _fit_b_eff(generations: list[Any]) -> float | None:
    """Effective branching factor: the geometric mean of the per-round growth in ``composed``,
    over PRE-SATURATION rounds only (a round whose input pool was truncated by ``max_pool`` has
    an artificially capped composed count, so it would understate growth). ``None`` when fewer
    than two such rounds exist -- the fit needs at least one ratio."""
    composed: list[int] = []
    for index, generation in enumerate(generations):
        if not isinstance(generation, dict):
            continue
        if index > 0:  # this round's input pool is the previous round's truncated output
            previous = generations[index - 1]
            if not isinstance(previous, dict):
                break
            if previous.get("pool_size_end") != previous.get("pool_size_before_truncation"):
                break  # saturation reached: later rounds no longer measure free growth
        count = generation.get("composed")
        if not isinstance(count, int) or count <= 0:
            break
        composed.append(count)
    if len(composed) < 2:
        return None
    growth: float = composed[-1] / composed[0]
    fitted: float = growth ** (1.0 / (len(composed) - 1))
    return round(fitted, 2)


def _search_solved_ids(record: RunRecord) -> set[str]:
    solved: set[str] = set()
    for row in record.trace_rows():
        tid = row.get("task_id")
        stats = row.get("search_stats")
        if (
            isinstance(tid, str)
            and isinstance(stats, dict)
            and stats.get("solved_at_generation") is not None
        ):
            solved.add(tid)
    return solved
