"""The LADDER activity, staged: oracle chain -> certificate -> (if admitted) the climb.

``run_ladder`` executes, as ordinary content-hashed recorded runs (so cells shared with a study or
a plain search are cache hits):

1. **The oracle chain** ``L_0..L_k`` (each gifting one more intended bridging rung) over the full
   train corpus at the reference budget -- the cost matrix's columns, and everything the
   certificate reads. Runs first, unconditionally (:func:`run_ladder_chain`).
2. **The certificate** (``certificate.certify``) -- the admission gate, read over stage 1.
3. **The climb stage**, only for admitted ladders (or under ``climb_rejected=True``, for control
   arms whose point IS the climb under a rejected structure): the wake-sleep LEARN run on the
   train corpus with the Floor (``run_search_learn`` -- also gives the learned-library searches on
   train + heldout), plus the **off-chain** run (Floor + the top bridging rung only, unfolded to
   floor form) -- a read-side comparison label (al19/al20), never an admission input, hence not in
   stage 1.

A rejected ladder therefore never pays for learning (AL-PLAN-2026-07-23 Phase 1 item 1); what it
still gets -- shape, certificate, cost matrix, jump costs, the raw arm -- is exactly the chain.

``L_0`` is run explicitly here (a cheap Floor search) rather than recovered from the LEARN trace's
iteration-0 wake -- simpler for the certificate, which needs per-task solve results under every
``L_i`` uniformly. ``create_ladder_report`` / ``certify`` are the read side (``report`` /
``certificate``); this module only executes and gates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil
from pathlib import Path

from arc_lab.core.dataset import Corpus
from arc_lab.program_search.analysis.depth import min_depth_limit
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.run_search_learn import LearnActivityResult, run_search_learn
from arc_lab.program_search.ladders.certificate import LadderCertificate, certify
from arc_lab.program_search.ladders.shape import LadderShape
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.substrate.abstraction import make_abstraction, unfold_program
from arc_lab.program_search.substrate.library import Library

#: The raw arm's `max_pool`. The bound is only sound if the arm does not SATURATE (a pool-starved
#: search idles, and its spend stops being evidence about the true raw cost -- 2026-07-22 frontier
#: sweep), so the pool is freed to the setting the estimator-validation sweep ran clean at. The
#: report checks the arm's funnels and withdraws soundness if any complete round composed zero.
RAW_ARM_POOL = 200_000

#: How much the retained pool must grow per extra round of composition, on top of the ladder's
#: configured ``max_pool``. A depth-``d`` search can only compose at round ``d`` what it RETAINED at
#: round ``d-1``, so a pool sized for a shallow level starves a deeper one -- and the failure is
#: silent: the search exhausts, reports ``unsolved``, and nothing says the target was reachable in
#: principle.
#:
#: **Measured 2026-07-27**, on ``94f9d214-nor-recolor``'s depth-3 top over ``L_4`` (and reproduced on
#: ``dae9d2b5-split-halves-lean``): pool 30 -> unsolved (23,754 exhaustive) · pool 60 -> unsolved
#: (702,470 exhaustive) · pool 150 -> SOLVED. The ladders that broke all had a ``3`` in their depth
#: schedule; the two that did not, did not. So the step is fitted to exactly two points (depth 2 at
#: 1x, depth 3 at 5x) and extrapolated geometrically -- a heuristic, not a law. It is safe in the
#: direction that matters (too large costs time, too small loses reachability), and ``top_reachable``
#: on the certificate is the backstop that makes a future miss loud instead of silent.
POOL_GROWTH_PER_ROUND = 5

#: The depth the ladder's configured ``max_pool`` is taken to be sized for.
POOL_BASE_DEPTH = 2


def pool_for_depth(configured: int, depth: int) -> int:
    """The retained-pool cap a level running at ``depth`` needs, given the ladder's setting."""
    return int(configured * POOL_GROWTH_PER_ROUND ** max(0, depth - POOL_BASE_DEPTH))


@dataclass(frozen=True, slots=True)
class LadderChainResult:
    """Stage 1: the lint shape + the oracle-chain runs -- everything the certificate reads."""

    spec: LadderSpec
    shape: LadderShape
    #: level ``i`` (0..k) -> the ``L_i`` oracle SEARCH run over the full train corpus.
    oracle_chain: dict[int, RunRecord]


@dataclass(frozen=True, slots=True)
class RawArm:
    """The deliberately-purchased raw baseline (AL-PLAN-2026-07-23 decision 1).

    The top tasks searched under the Floor at a budget that puts raw in reach (``depth_limit`` from
    ``min_depth_limit`` of the unfolded top solutions; pool freed to :data:`RAW_ARM_POOL`), guarded
    at ``K x the measured laddered cost`` split per task. Two outcomes, by construction:

    - **it solves** -- RQ1 is a *measured* ratio (and <= K). ``solution_limit=1 immediate`` makes
      the spend cost-to-first, so the measured ratio conservatively understates the ladder's win
      (raw-to-first over laddered-paid-full).
    - **it censors** -- RQ1 is a *proven lower bound*: raw cost exceeds the spend, so
      ratio >= spend / laddered ~= K. Sound only if no funnel saturated -- the report checks.
    """

    record: RunRecord
    k: int
    #: The per-task ``considered_limit`` the arm ran under: ``ceil(k x laddered / |top tasks|)``.
    guard_per_task: int
    #: The denominator the guard was sized from: the chain-measured marginal laddered cost.
    laddered_marginal: int
    depth_limit: int
    max_pool: int


@dataclass(frozen=True, slots=True)
class LadderResult:
    """Everything ``run_ladder`` produced. ``learn`` / ``off_chain`` / ``raw_arm`` are ``None``
    exactly when the certificate rejected and the climb stage was skipped (the default for a
    rejected ladder -- RQ1 is not a question about a ladder that is not a ladder)."""

    spec: LadderSpec
    shape: LadderShape
    certificate: LadderCertificate
    #: level ``i`` (0..k) -> the ``L_i`` oracle SEARCH run over the full train corpus.
    oracle_chain: dict[int, RunRecord]
    learn: LearnActivityResult | None
    off_chain: RunRecord | None
    raw_arm: RawArm | None

    @property
    def climbed(self) -> bool:
        return self.learn is not None


def run_ladder_chain(spec: LadderSpec, *, runs_root: Path | None = None) -> LadderChainResult:
    """Stage 1: lint + the oracle chain ``L_0..L_k`` -- the certificate's entire evidence base.

    Each level runs at ITS OWN ``depth_limit`` (``LadderShape.depth_schedule``): ``L_j`` serves rung
    ``j+1``, so it carries that rung's ``jump_needs``, and ``L_k`` the top's. Read off the lint
    shape rather than recomputed -- the unfolds are already paid for there.
    """
    shape = spec.lint()
    oracle_chain: dict[int, RunRecord] = {}
    configured_pool = spec.reference_config.budget.max_pool
    for level in range(len(spec.rungs) + 1):  # L_0 (Floor) through L_k (all bridging rungs)
        depth = shape.depth_schedule[level]
        # The pool travels WITH the depth schedule, for the same reason the schedule exists: a level
        # is budgeted for what IT must find. A single pool sized for the shallow levels silently
        # starves the deep one (see `pool_for_depth`); sized for the deep one it overpays everywhere
        # else, and -- because run identity is Config x Corpus -- moves every level's `run_id`.
        # Per-level keeps the unchanged levels cache-valid.
        budget = replace(
            spec.reference_config.budget,
            depth_limit=depth,
            max_pool=pool_for_depth(configured_pool, depth),
        )
        config = spec.reference_config.with_(
            library=spec.oracle_library(level), budget=budget, learn=None
        )
        oracle_chain[level] = execute(
            RunSpec(config=config, corpus=spec.train_corpus), runs_root=runs_root
        )
    return LadderChainResult(spec=spec, shape=shape, oracle_chain=oracle_chain)


def run_ladder(
    spec: LadderSpec,
    *,
    runs_root: Path | None = None,
    climb_rejected: bool = False,
    raw_arm_k: int = 10,
) -> LadderResult:
    """Execute a ladder, staged: chain, certificate, and -- only if admitted -- the climb + raw arm.

    ``climb_rejected=True`` runs the climb stage regardless of the verdict; for control arms whose
    measurement IS the climb under a rejected structure (al8's head-to-head cost read), never for
    ordinary ladders. ``raw_arm_k`` is decision 1's claim strength: the raw arm's total guard is
    ``raw_arm_k x the chain-measured marginal laddered cost``, so a censoring arm proves an
    amortization ratio of at least ``raw_arm_k``.
    """
    chain = run_ladder_chain(spec, runs_root=runs_root)
    certificate = certify(chain)

    learn: LearnActivityResult | None = None
    off_chain: RunRecord | None = None
    raw_arm: RawArm | None = None
    if certificate.admitted or climb_rejected:
        # The climb searches at the ladder's pinned `depth_limit`, so it needs the pool that depth
        # requires -- the same reason the chain scales per level. Without this a ladder whose top is
        # a round deeper than its rungs certifies on a chain that reached the top and then fails to
        # LEARN it, which is the same silent starvation one stage later.
        climb_config = spec.reference_config.with_(
            budget=replace(
                spec.reference_config.budget,
                max_pool=pool_for_depth(
                    spec.reference_config.budget.max_pool,
                    spec.reference_config.budget.depth_limit,
                ),
            )
        )
        learn = run_search_learn(
            climb_config, spec.train_corpus, spec.heldout_corpus, runs_root=runs_root
        )
        off_chain = execute(
            RunSpec(
                config=spec.reference_config.with_(library=_off_chain_library(spec), learn=None),
                corpus=spec.train_corpus,
            ),
            runs_root=runs_root,
        )
        raw_arm = run_raw_arm(
            spec,
            _laddered_marginal(spec, chain.oracle_chain),
            k=raw_arm_k,
            runs_root=runs_root,
        )
    return LadderResult(
        spec=spec,
        shape=chain.shape,
        certificate=certificate,
        oracle_chain=chain.oracle_chain,
        learn=learn,
        off_chain=off_chain,
        raw_arm=raw_arm,
    )


def run_raw_arm(
    spec: LadderSpec, laddered_marginal: int, *, k: int = 10, runs_root: Path | None = None
) -> RawArm | None:
    """Purchase the raw baseline: the top tasks under the Floor, guarded at ``k x laddered``.

    ``None`` when the ladder has no top tasks or the measured laddered cost is zero -- there is
    nothing to size the spend against, and an unguarded raw run is exactly what decision 1 forbids.
    """
    top_ids = set(spec.top.task_ids)
    by_id = {entry.task.task_id: entry.task for entry in spec.train_corpus.entries}
    tasks = [by_id[tid] for tid in spec.top.task_ids if tid in by_id]
    if not tasks or laddered_marginal <= 0 or k < 1:
        return None

    full_lib = spec.oracle_library(len(spec.rungs))
    depth = max(
        min_depth_limit(unfold_program(sol, full_lib)) for sol in spec.top.reference_solutions
    )
    guard = ceil(k * laddered_marginal / len(tasks))
    budget = replace(
        spec.reference_config.budget,
        depth_limit=depth,
        max_pool=RAW_ARM_POOL,
        considered_limit=guard,
        considered_limit_mode="immediate",
        solution_limit=1,
        solution_limit_mode="immediate",
    )
    config = spec.reference_config.with_(library=spec.floor(), budget=budget, learn=None)
    corpus = Corpus.of(
        f"{spec.train_corpus.name}:raw-arm",
        [by_id[tid] for tid in sorted(top_ids) if tid in by_id],
    )
    record = execute(RunSpec(config=config, corpus=corpus), runs_root=runs_root)
    return RawArm(
        record=record,
        k=k,
        guard_per_task=guard,
        laddered_marginal=laddered_marginal,
        depth_limit=depth,
        max_pool=RAW_ARM_POOL,
    )


def _laddered_marginal(spec: LadderSpec, oracle_chain: dict[int, RunRecord]) -> int:
    """The chain-measured marginal laddered cost: rung ``i``'s demonstrations under ``L_{i-1}``,
    plus the top under ``L_k`` -- the raw arm's denominator, and the guard's sizing base. The same
    sum the report's ``laddered_marginal_considered`` makes; recomputed here because the report is
    read-side and the arm must be sized before it exists."""
    total = 0
    k = len(spec.rungs)
    for i, rung in enumerate(spec.rungs, start=1):
        considered = _considered_by_task(oracle_chain[i - 1])
        total += sum(considered.get(demo.task_id, 0) for demo in rung.demonstrations)
    considered = _considered_by_task(oracle_chain[k])
    total += sum(considered.get(tid, 0) for tid in spec.top.task_ids)
    return total


def _considered_by_task(record: RunRecord) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in record.trace_rows():
        tid = row.get("task_id")
        stats = row.get("search_stats")
        if isinstance(tid, str) and isinstance(stats, dict):
            total = stats.get("total")  # the funnel's outcome block owns `considered` in the trace
            if isinstance(total, dict) and isinstance(total.get("considered"), int):
                out[tid] = total["considered"]
    return out


def _off_chain_library(spec: LadderSpec) -> Library:
    """Floor + the top bridging rung only, the rung expressed over the floor (``unfold_program``).

    ``rungs[-1]`` is a LEVEL read, matching what the arm asks: "what does the ladder's TOPMOST
    abstraction buy on its own, without the scaffolding under it?". On a DAG with independent
    branches that deliberately omits the sibling branches -- the arm is a read-side comparison
    label (al19/al20), never an admission input, so it under-credits rather than mis-certifies.
    """
    floor = spec.floor()
    top_rung = spec.rungs[-1]
    over_floor = unfold_program(top_rung.template, spec.oracle_library(len(spec.rungs)))
    return floor.extended(
        name=f"{floor.name}+{top_rung.name}",
        extra=(make_abstraction(top_rung.name, over_floor, floor),),
    )
