"""``create_ladder_report``: the Ladder read side — a pure function of a ``LadderResult``.

Synthesizes the headline metrics from the recorded runs: the certificate, the climb trace (what
minted when), rung recovery (minted abstractions vs the intended rungs, graded behaviorally), the
jump-cost / cost-matrix view over the oracle chain, and the RQ1 amortization (raw vs laddered). It
never executes. Some views the design lists (vocabulary tax, b_eff, break-even horizon) are left
for a follow-up; what's here is what ladder #1 needs to be read end to end.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.behavioral import MAX_PROBE_COMBOS, matches_target
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders.certificate import certify
from arc_lab.program_search.ladders.run import LadderResult
from arc_lab.program_search.substrate.abstraction import make_abstraction


def create_ladder_report(result: LadderResult) -> dict[str, object]:
    """The ladder report: shape, certificate, climb trace, rung recovery, jump costs, amortization."""
    spec, shape = result.spec, result.shape
    cert = certify(result)
    k = len(spec.rungs)
    considered = {level: _per_task_considered(rec) for level, rec in result.oracle_chain.items()}
    solved = {level: _search_solved_ids(rec) for level, rec in result.oracle_chain.items()}

    # Jump costs: rung i solved under L_{i-1}; the top under L_k.
    jump_costs: dict[str, int] = {}
    for i, rung in enumerate(spec.rungs, start=1):
        ids = [demo.task_id for demo in rung.demonstrations]
        jump_costs[rung.name] = sum(considered[i - 1].get(tid, 0) for tid in ids)
    top_ids = list(spec.top.task_ids)
    top_jump_cost = sum(considered[k].get(tid, 0) for tid in top_ids)
    laddered_marginal = sum(jump_costs.values()) + top_jump_cost

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
        "cost": {
            "jump_costs": jump_costs,
            "top_jump_cost": top_jump_cost,
            "laddered_marginal_considered": laddered_marginal,
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


def _per_task_considered(record: RunRecord) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in record.trace_rows():
        tid = row.get("task_id")
        stats = row.get("search_stats")
        if isinstance(tid, str) and isinstance(stats, dict):
            total = stats.get("total")
            if isinstance(total, dict) and isinstance(total.get("considered"), int):
                out[tid] = total["considered"]
    return out


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
