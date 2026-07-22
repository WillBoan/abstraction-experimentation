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

from dataclasses import dataclass
from pathlib import Path

from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.run_search_learn import LearnActivityResult, run_search_learn
from arc_lab.program_search.ladders.certificate import LadderCertificate, certify
from arc_lab.program_search.ladders.shape import LadderShape
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.substrate.abstraction import make_abstraction, unfold_program
from arc_lab.program_search.substrate.library import Library


@dataclass(frozen=True, slots=True)
class LadderChainResult:
    """Stage 1: the lint shape + the oracle-chain runs -- everything the certificate reads."""

    spec: LadderSpec
    shape: LadderShape
    #: level ``i`` (0..k) -> the ``L_i`` oracle SEARCH run over the full train corpus.
    oracle_chain: dict[int, RunRecord]


@dataclass(frozen=True, slots=True)
class LadderResult:
    """Everything ``run_ladder`` produced. ``learn`` / ``off_chain`` are ``None`` exactly when the
    certificate rejected and the climb stage was skipped (the default for a rejected ladder)."""

    spec: LadderSpec
    shape: LadderShape
    certificate: LadderCertificate
    #: level ``i`` (0..k) -> the ``L_i`` oracle SEARCH run over the full train corpus.
    oracle_chain: dict[int, RunRecord]
    learn: LearnActivityResult | None
    off_chain: RunRecord | None

    @property
    def climbed(self) -> bool:
        return self.learn is not None


def run_ladder_chain(spec: LadderSpec, *, runs_root: Path | None = None) -> LadderChainResult:
    """Stage 1: lint + the oracle chain ``L_0..L_k`` -- the certificate's entire evidence base."""
    shape = spec.lint()
    oracle_chain: dict[int, RunRecord] = {}
    for level in range(len(spec.rungs) + 1):  # L_0 (Floor) through L_k (all bridging rungs)
        config = spec.reference_config.with_(library=spec.oracle_library(level), learn=None)
        oracle_chain[level] = execute(
            RunSpec(config=config, corpus=spec.train_corpus), runs_root=runs_root
        )
    return LadderChainResult(spec=spec, shape=shape, oracle_chain=oracle_chain)


def run_ladder(
    spec: LadderSpec, *, runs_root: Path | None = None, climb_rejected: bool = False
) -> LadderResult:
    """Execute a ladder, staged: chain, certificate, and -- only if admitted -- the climb.

    ``climb_rejected=True`` runs the climb stage regardless of the verdict; for control arms whose
    measurement IS the climb under a rejected structure (al8's head-to-head cost read), never for
    ordinary ladders.
    """
    chain = run_ladder_chain(spec, runs_root=runs_root)
    certificate = certify(chain)

    learn: LearnActivityResult | None = None
    off_chain: RunRecord | None = None
    if certificate.admitted or climb_rejected:
        learn = run_search_learn(
            spec.reference_config, spec.train_corpus, spec.heldout_corpus, runs_root=runs_root
        )
        off_chain = execute(
            RunSpec(
                config=spec.reference_config.with_(library=_off_chain_library(spec), learn=None),
                corpus=spec.train_corpus,
            ),
            runs_root=runs_root,
        )
    return LadderResult(
        spec=spec,
        shape=chain.shape,
        certificate=certificate,
        oracle_chain=chain.oracle_chain,
        learn=learn,
        off_chain=off_chain,
    )


def _off_chain_library(spec: LadderSpec) -> Library:
    """Floor + the top bridging rung only, the rung expressed over the floor (``unfold_program``)."""
    floor = spec.floor()
    top_rung = spec.rungs[-1]
    over_floor = unfold_program(top_rung.template, spec.oracle_library(len(spec.rungs)))
    return floor.extended(
        name=f"{floor.name}+{top_rung.name}",
        extra=(make_abstraction(top_rung.name, over_floor, floor),),
    )
