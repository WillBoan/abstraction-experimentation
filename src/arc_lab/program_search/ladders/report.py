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
from arc_lab.program_search.ladders.certificate import search_censored_ids
from arc_lab.program_search.ladders.run import LadderResult
from arc_lab.program_search.substrate.abstraction import make_abstraction


def create_ladder_report(result: LadderResult) -> dict[str, object]:
    """The ladder report: shape, certificate, climb trace, rung recovery, the per-task cost matrix,
    jump costs, amortization, and the comparison views.

    For a rejected ladder that did not climb (``result.climbed`` is ``False``), the climb-derived
    sections read as absent -- ``climb_executed: False``, empty trace/recovery, ``None`` end-to-end
    figures -- while everything the chain measures (certificate, cost matrix, jump costs, raw arm)
    is reported in full."""
    spec, shape = result.spec, result.shape
    cert = result.certificate
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

    # Raw: the top under L_0 (the Floor). Unsolved by construction (d_raw exceeds the pinned
    # depth_limit), so the measured number is a full-budget FAILURE -- not a raw cost. The usable
    # figure is the extrapolated estimate below: running raw is intractable for any ladder worth
    # building, so it is estimated, never measured (design doc 5.3).
    raw_considered = sum(considered[0].get(tid, 0) for tid in top_ids)
    raw_solved = bool(top_ids) and all(tid in solved[0] for tid in top_ids)
    raw_estimate = (
        _estimate_raw_cost(
            _task_generations(result.oracle_chain[0], top_ids[0]),
            max(shape.raw_depth_profile, default=0),
            spec.reference_config.budget.depth_limit,
        )
        if top_ids and not raw_solved
        else {"available": False, "reason": "raw solved outright -- measured, not estimated"}
    )
    # Off-chain is a climb-stage run: ``None`` (not measured) when the climb was skipped.
    off_solved: bool | None = (
        bool(top_ids) and all(tid in _search_solved_ids(result.off_chain) for tid in top_ids)
        if result.off_chain is not None
        else None
    )

    # Rung recovery: minted (learned) abstractions vs the intended rungs, graded behaviorally.
    # Skipped wholesale (empty trace, no recovery rows, no end-to-end figure) when the certificate
    # rejected and the climb never ran -- absent, not zero.
    recovery: list[dict[str, object]] = []
    climb: list[dict[str, object]] = []
    end_to_end: int | None = None
    if result.learn is not None:
        learned = result.learn.learn.learned_library()
        floor_names = {p.name for p in spec.floor().primitives}
        invented = [p for p in learned.primitives if p.name not in floor_names]
        probes = tuple(
            example.input for entry in spec.train_corpus.entries for example in entry.task.train
        )
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

    # The raw arm (AL-PLAN-2026-07-23 decision 1): the deliberately-purchased raw baseline, and
    # RQ1's ONLY authority -- a MEASURED ratio when the arm solved every top task, a PROVEN lower
    # bound when it censored. Sound only if no funnel saturated: a pool-starved search idles, and
    # its spend stops being evidence about the true raw cost.
    raw_arm_view: dict[str, object] | None = None
    if result.raw_arm is not None:
        arm = result.raw_arm
        arm_cells = _per_task_cells(arm.record)
        arm_spend = sum(
            _as_int(cell["considered"]) for tid, cell in arm_cells.items() if tid in set(top_ids)
        )
        arm_solved = _search_solved_ids(arm.record)
        all_solved = bool(top_ids) and all(tid in arm_solved for tid in top_ids)
        saturated_at: dict[str, int] = {}
        for tid in top_ids:
            for index, generation in enumerate(_task_generations(arm.record, tid)):
                if (
                    index > 0
                    and isinstance(generation, dict)
                    and generation.get("composed") == 0
                    and not generation.get("incomplete")
                ):
                    saturated_at[tid] = index
                    break
        sound = not saturated_at
        arm_ratio = arm_spend / arm.laddered_marginal if arm.laddered_marginal else None
        raw_arm_view = {
            "k": arm.k,
            "guard_per_task": arm.guard_per_task,
            "laddered_marginal": arm.laddered_marginal,
            "conditions": {
                "depth_limit": arm.depth_limit,
                "max_pool": arm.max_pool,
                "solution_limit": 1,
            },
            "spend_considered": arm_spend,
            "solved": all_solved,
            "saturated_at": saturated_at or None,
            "sound": sound,
            "amortization_ratio": arm_ratio,
            # measured: the arm solved -- the numerator is cost-to-first, so the measured ratio
            # conservatively UNDERSTATES the ladder's win. lower-bound: the arm censored without
            # solving, so raw cost provably exceeds the spend (ratio >= ~k). A saturated bound is
            # reported but withdrawn: raise max_pool and re-run to restore soundness.
            "amortization_ratio_kind": (
                "measured"
                if all_solved
                else ("lower-bound" if sound else "lower-bound (UNSOUND: pool-saturated)")
            ),
        }

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
        # The rung's OWN tasks, in cost-to-first: what the rung bought the search that has to find
        # it. Both sides are solved by construction (the jump is tractable at L_{i-1}), so unlike
        # the layer-above ratio this one is uncensored -- the honest speedup measure.
        own_ids = [demo.task_id for demo in rung.demonstrations]
        own_without = _sum_to_first(first_index[i - 1], own_ids)
        own_with = _sum_to_first(first_index[i], own_ids)
        rung_value.append(
            {
                "rung": rung.name,
                "layer_above": "top" if i == k else spec.rungs[i].name,
                "cost_without_rung": below,
                "cost_with_rung": at,
                "ratio": (below / at) if at else None,
                "censored": censored,
                "own_tasks_to_first_without": own_without,
                "own_tasks_to_first_with": own_with,
                "own_tasks_speedup": (
                    (own_without / own_with)
                    if isinstance(own_without, int) and isinstance(own_with, int) and own_with
                    else None
                ),
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
        "climb_executed": result.climbed,
        # The wake-schedule arm label (design doc 3.7): any non-"full" value means the climb's
        # end-to-end cost, loop-overhead factor, and what sleep saw were measured under
        # assistance and are NOT comparable against full-wake cells.
        "wake_schedule": (
            spec.reference_config.learn.wake_schedule
            if spec.reference_config.learn is not None
            else None
        ),
        "climb_trace": climb,
        "rung_recovery": recovery,
        "probe_cap": MAX_PROBE_COMBOS,
        "cost_matrix": cost_matrix,
        "comparisons": {
            "loop_overhead_factor": (
                (end_to_end / laddered_marginal)
                if end_to_end is not None and laddered_marginal
                else None
            ),
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
            # Statistical sense: the number is a lower bound, not a raw cost. True whenever raw is
            # unsolved, whatever ended the search.
            "raw_censored": not raw_solved,
            # Distinct and narrower: a `Budget.considered_limit` cut the raw search short, so it is
            # a lower bound on the FLOOR SEARCH ITSELF, not just on the cost of solving. Kept apart
            # from `raw_censored` because only this one means "we chose to stop paying".
            "raw_limit_censored": bool(top_ids)
            and any(tid in search_censored_ids(result.oracle_chain[0]) for tid in top_ids),
            "raw_arm": raw_arm_view,
            # ADVISORY ONLY (AL-PLAN-2026-07-23 decision 1): the extrapolated estimate is retired
            # from results -- its bracket held in 2/10 validation cells. `raw_arm` above is RQ1's
            # authority; these two fields survive as diagnostics carrying their measured caveats.
            "raw_estimate": raw_estimate,
            "amortization_ratio_estimated": (
                {
                    "low": _as_int(raw_estimate["estimate_low"]) / laddered_marginal,
                    "high": _as_int(raw_estimate["estimate_high"]) / laddered_marginal,
                }
                if raw_estimate.get("available") and laddered_marginal
                else None
            ),
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
                _skip_path_verdict(no_skip.get(level)),
                str(health.get(level)),
            ]
        )
    lines += ["", "## Certificate (per jump)", "", *table(cert_rows)]
    if any(no_skip.get(level) is None for level in tractable):
        lines += [
            "",
            "> An INCONCLUSIVE skip-path verdict means that jump's probe search was **censored** "
            "(`Budget.considered_limit`), so it went unsolved without being searched to "
            "completion -- absence of a skip path was never established. Such a ladder is not "
            "admitted: re-run the oracle chain with a higher (or no) `considered_limit` to settle it.",
        ]

    if report.get("climb_executed") is False:
        lines += [
            "",
            "## Climb: SKIPPED",
            "",
            "> The certificate rejected this ladder, so the climb stage (LEARN + off-chain) never "
            "ran and no learning was paid for. The sections below reflect the oracle chain only; "
            "climb trace and rung recovery are absent, not zero. To force a climb anyway (control "
            "arms only): `arc-lab run-ladder <name> --climb-rejected`.",
        ]

    schedule = report.get("wake_schedule")
    if isinstance(schedule, str) and schedule != "full":
        lines += [
            "",
            f"> **ARM LABEL: wake schedule `{schedule}`** -- the climb's end-to-end cost, "
            "loop-overhead factor, and what sleep saw were measured under assistance "
            "(design doc 3.7). Do not compare them against full-wake cells; recovery claims "
            "need an honest `full` cell too.",
        ]

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
                mark = " *" if cell.get("solved") else " !" if cell.get("censored") else ""
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
            "- `!` = that search was cut short by a `Budget.considered_limit`, so its number is the "
            "limit itself, not a measurement -- and its `unsolved` says nothing about whether a "
            "solution exists within the budget.",
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
        f"- Raw (Floor on the top tasks, reference budget): {_count(cost.get('raw_considered'))}"
        + (
            " -- a full-budget FAILURE at the reference budget, not a raw cost (the top is "
            "unreachable raw by design); the raw ARM below is the RQ1 authority"
            if censored
            else ""
        ),
        "- Amortization considered-ratio (reference-budget raw): "
        + (f"{ratio:.2f}" if isinstance(ratio, float) else "n/a -- see the raw arm under RQ1"),
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
        *_raw_arm_lines(cost),
        *_raw_estimate_lines(cost),
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
        [
            "rung",
            "own tasks, cost-to-first without",
            "with",
            "**speedup**",
            "layer above (paid-full)",
            "censored",
        ]
    ]
    for row in comparisons.get("marginal_rung_value") or []:
        speedup = row.get("own_tasks_speedup")
        value_ratio = row.get("ratio")
        value_rows.append(
            [
                f"`{row.get('rung')}`",
                _count(row.get("own_tasks_to_first_without")),
                _count(row.get("own_tasks_to_first_with")),
                f"**{speedup:.2f}x**" if isinstance(speedup, float) else "-",
                (
                    f"{value_ratio:.2f}x vs `{row.get('layer_above')}`"
                    if isinstance(value_ratio, float)
                    else "-"
                ),
                _yes_no(row.get("censored")),
            ]
        )
    lines += [
        "",
        "### Marginal rung value",
        "",
        *table(value_rows),
        "",
        "- **The speedup column is the honest measure**: the rung's own demonstrating tasks, in "
        "cost-to-first, with vs without the rung gifted. Both sides are solved by construction, "
        "so it is uncensored.",
        "- The layer-above column is cost-paid-full on a CENSORED comparison (the layer above is "
        "unsolved without the rung -- that IS the double-jump claim), so it is not a speedup: a "
        "value near or below 1.0x there means the rung bought **reachability**, not cost. Read "
        "Enablement for that, never this number.",
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
        "### Rung necessity: learning path vs search path",
        "",
        f"- Off-chain (Floor + the top bridging rung only, no intermediate rungs) solves the top: "
        f"**{_yes_no(cost.get('off_chain_top_solved'))}**.",
        "- When this is `yes`, the intermediate rungs are NOT needed to express or find the top "
        "solution -- yet the top rung itself is unlearnable without them (its demonstrating tasks "
        "are unsolved at the lower library, so sleep never sees the material to mint it). The "
        "rungs are stepping stones for the **learning path**, not dependencies of the **search "
        "path**. That is the ladder thesis, measured rather than assumed.",
        "",
        "## Not computed here",
        "",
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


def _raw_arm_lines(cost: Mapping[str, Any]) -> list[str]:
    """RQ1's authority (AL-PLAN-2026-07-23 decision 1): measured when the arm solved, a proven
    lower bound when it censored -- never an extrapolation."""
    arm: Mapping[str, Any] = cost.get("raw_arm") or {}
    if not arm:
        return [
            "- Raw arm: NOT RUN (the climb stage was skipped, or the ladder has nothing to size "
            "the spend against). RQ1 has no answer for this ladder."
        ]
    ratio = arm.get("amortization_ratio")
    kind = arm.get("amortization_ratio_kind")
    conditions: Mapping[str, Any] = arm.get("conditions") or {}
    lines = [
        f"- **Amortization ratio ({kind}): "
        + (f"{ratio:.1f}x" if isinstance(ratio, float) else "n/a")
        + f"** -- raw arm spend {_count(arm.get('spend_considered'))} against laddered marginal "
        f"{_count(arm.get('laddered_marginal'))}, guard {arm.get('k')}x laddered "
        f"({_count(arm.get('guard_per_task'))} per top task) at depth_limit "
        f"{conditions.get('depth_limit')}, max_pool {_count(conditions.get('max_pool'))}, "
        "solution_limit 1.",
    ]
    if arm.get("solved"):
        lines.append(
            "  - The arm SOLVED every top task, so the ratio is measured; its numerator is "
            "cost-to-first, so it conservatively understates the ladder's win."
        )
    elif arm.get("sound"):
        lines.append(
            "  - The arm censored without solving: raw cost provably exceeds the spend, so the "
            "ratio is a LOWER BOUND. Raise --raw-arm-k for a stronger claim."
        )
    else:
        lines.append(
            f"  - WITHDRAWN: the arm's search saturated (rounds composing zero at "
            f"{arm.get('saturated_at')}), so its spend is pool starvation, not evidence about raw "
            "cost. Raise the arm's max_pool and re-run."
        )
    return lines


def _raw_estimate_lines(cost: Mapping[str, Any]) -> list[str]:
    """ADVISORY ONLY: the extrapolated estimate, retired from results (AL-PLAN-2026-07-23
    decision 1 -- its bracket held in 2/10 validation cells). Rendered as a diagnostic beneath the
    raw arm, never as an RQ1 answer."""
    estimate: Mapping[str, Any] = cost.get("raw_estimate") or {}
    if not estimate.get("available"):
        return [
            f"- Raw cost estimate (advisory): unavailable -- "
            f"{estimate.get('reason', 'no fit possible')}",
        ]
    low, high = estimate.get("estimate_low"), estimate.get("estimate_high")
    lines = [
        f"- Raw cost estimate (ADVISORY -- not an RQ1 input): {_count(low)} - {_count(high)} "
        "considered, extrapolated from observed composed counts "
        f"{estimate.get('observed_composed')} through depth "
        f"{estimate.get('observed_through_depth')} ({estimate.get('rounds_extrapolated')} rounds "
        f"projected to `d_raw`={estimate.get('d_raw')}). Validated 2026-07-23: the bracket "
        "contained the measured truth in 2 of 10 cells, erring both directions -- treat as an "
        "order-of-magnitude sketch of unknown sign, never a result.",
    ]
    for caveat in estimate.get("caveats") or []:
        lines.append(f"  - caveat: {caveat}")
    return lines


def _yes_no(value: object) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def _skip_path_verdict(value: object) -> str:
    """The tri-state ``no_skip_paths`` verdict. ``None`` renders as INCONCLUSIVE, not as a bare
    dash: it means a search was censored, so we do not know whether a skip path exists -- a
    materially different claim from "no" that must never be skimmed as a pass."""
    if value is None:
        return "INCONCLUSIVE (censored)"
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
            # Cut short by a `considered_limit`: `considered` is the limit, not a measurement, and
            # `solved=False` here means "never established", not "no solution".
            "censored": bool(stats.get("censored")),
        }
    return out


def _task_generations(record: RunRecord, task_id: str) -> list[Any]:
    """One task's per-round funnel from a recorded SEARCH run."""
    for row in record.trace_rows():
        if row.get("task_id") != task_id:
            continue
        stats = row.get("search_stats")
        if isinstance(stats, dict) and isinstance(stats.get("generations"), list):
            return list(stats["generations"])
    return []


def _estimate_raw_cost(generations: list[Any], d_raw: int, depth_limit: int) -> dict[str, object]:
    """**Extrapolated raw baseline** (design doc 5.3) -- the honest alternative to actually running
    the raw search, which is intractable by construction for any ladder worth building.

    The raw search is stopped at ``depth_limit`` but its solution lives at ``d_raw``. We have the
    per-round ``composed`` counts it *did* complete, so we fit their growth and project the missing
    ``d_raw - depth_limit`` rounds. Two fits bracket the answer, because the growth ratio is not
    constant:

    - **low** uses the geometric-mean ratio across observed rounds. Round 0 -> 1 is atypically
      cheap (the round-0 pool holds one grid), which drags the mean down, so this under-projects.
    - **high** uses the last observed ratio, which is the most representative of a full pool --
      but growth *decays* as the dedup rate climbs toward function-space saturation, so this
      over-projects.

    .. warning::
       **"The truth sits between" is FALSE, measured.** This docstring used to claim the bracket
       contains the answer. Validated 2026-07-23 against measured raw cost across four floors and
       ten (observed-depth, ``d_raw``) pairs (``experiments/2026-07-23-estimator-validation/``):
       **the bracket contained the truth in 2 of 10 cells**, and the errors run both ways --

       - on floors whose growth *accelerates* (binary primitives take products of a growing pool),
         BOTH fits under-project, badly: the geometric floor at a 2-round gap read 3,616-11,821
         against a measured **973,013** (82x-269x under);
       - on a floor whose reachable space is a finite group, both fits over-project (up to 3.71x),
         because there is exponential growth to fit only until the space is exhausted;
       - error compounds with the number of rounds extrapolated, and is floor-dependent even at a
         one-round gap (0.015x to 1.4x observed).

       So an RQ1 ratio computed from this carries a multiplicative uncertainty of roughly three
       orders of magnitude. Report it as an order-of-magnitude bracket of unknown sign, never as a
       measurement. ``execution/forecast_cost`` is tighter overall on the same cells (median 1.00x,
       range 0.04x-1.24x vs this fit's 0.004x-3.71x) but is itself 25x under on two of them, so it
       is not a drop-in replacement either -- see the notebook before relying on either number.

    Both assume a pool large enough not to bind: the estimate is of the raw search's true cost,
    NOT of what a ``max_pool``-capped run would spend (such a run is cheaper and simply fails to
    find the solution -- see the caveats).

    Rounds flagged ``incomplete`` are DROPPED before fitting. Such a round was cut short mid-way by
    an ``immediate`` stop limit, so its ``composed`` is an arbitrary fraction of the round's real
    size -- and since it is always the last round, both fits read it as collapse rather than growth.
    The result is not a loud failure: the bracket stays ordered and the output looks well-formed, it
    is simply wrong by orders of magnitude (measured in the tests: 1.1e3 where the truth is 1.1e5).
    A censored run is exactly the input this estimator exists to consume, so the filter is not
    optional.
    """
    composed = [
        generation["composed"]
        for generation in generations
        if isinstance(generation, dict)
        and isinstance(generation.get("composed"), int)
        and not generation.get("incomplete")
    ]
    rounds_missing = d_raw - depth_limit
    if len(composed) < 2 or rounds_missing <= 0:
        return {"available": False, "reason": "needs >= 2 observed rounds and d_raw > depth_limit"}

    observed_total = sum(composed)
    ratio_geometric: float = (composed[-1] / composed[0]) ** (1.0 / (len(composed) - 1))
    ratio_last: float = composed[-1] / composed[-2]

    def project(ratio: float) -> int:
        total, last = observed_total, composed[-1]
        for _ in range(rounds_missing):
            last *= ratio
            total += last
        return int(total)

    low, high = project(ratio_geometric), project(ratio_last)
    return {
        "available": True,
        "method": "geometric extrapolation of per-round composed growth (design doc 5.3)",
        "d_raw": d_raw,
        "observed_through_depth": depth_limit,
        "rounds_extrapolated": rounds_missing,
        "observed_composed": composed,
        "observed_considered": observed_total,
        "growth_ratio_geometric": round(ratio_geometric, 2),
        "growth_ratio_last": round(ratio_last, 2),
        "estimate_low": min(low, high),
        "estimate_high": max(low, high),
        "validated": "2026-07-23: bracket contained the measured truth in 2 of 10 cells",
        "caveats": [
            "THE BRACKET IS NOT A CONTAINMENT CLAIM -- measured 2026-07-23, it held in 2/10 cells",
            "accelerating-growth floors: BOTH fits under-project (82x-269x under at a 2-round gap)",
            "finite-space floors: both fits over-project (up to 3.71x) once the space is exhausted",
            "error compounds per extrapolated round and is floor-dependent even at a 1-round gap",
            "assumes a pool large enough not to bind; a max_pool-capped run is cheaper but fails",
            "an RQ1 ratio built on this carries ~3 orders of magnitude of uncertainty, unknown sign",
        ],
    }


def _fit_b_eff(generations: list[Any]) -> float | None:
    """Effective branching factor: the geometric mean of the per-round growth in ``composed``,
    over PRE-SATURATION rounds only (a round whose input pool was truncated by ``max_pool`` has
    an artificially capped composed count, so it would understate growth). ``None`` when fewer
    than two such rounds exist -- the fit needs at least one ratio.

    A round flagged ``incomplete`` stops the fit for the same reason and needs its own check: an
    ``immediate`` stop limit cut it short mid-absorption, so its ``composed`` is a fraction of the
    round's real size. The saturation test above cannot catch it -- ``_repair_aborted_generation``
    records ``pool_size_end == pool_size_before_truncation`` (honest: that round never reached its
    truncation), so an aborted round looks unsaturated and would otherwise drag the fit down."""
    composed: list[int] = []
    for index, generation in enumerate(generations):
        if not isinstance(generation, dict):
            continue
        if generation.get("incomplete"):
            break
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
