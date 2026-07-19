"""The LADDER activity: the climb (LEARN) + the oracle chain + the off-chain run.

``run_ladder`` executes, as ordinary content-hashed recorded runs (so cells shared with a study or
a plain search are cache hits): (1) the wake-sleep LEARN run on the train corpus with the Floor
(``run_search_learn`` -- also gives the learned-library searches on train + heldout); (2) the
**oracle chain** ``L_0..L_k`` (each gifting one more intended bridging rung) over the full train
corpus at the reference budget -- the cost matrix's columns; (3) the **off-chain** run, Floor + the
top bridging rung only (unfolded to floor form), to ask whether the top needs the whole chain.

``L_0`` is run explicitly here (a cheap Floor search) rather than recovered from the LEARN trace's
iteration-0 wake -- simpler for the certificate, which needs per-task solve results under every
``L_i`` uniformly. ``create_ladder_report`` / ``certify`` are the read side (``report`` /
``certificate``); this module only executes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.execution.run_search_learn import LearnActivityResult, run_search_learn
from arc_lab.program_search.ladders.shape import LadderShape
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.substrate.abstraction import make_abstraction, unfold_program
from arc_lab.program_search.substrate.library import Library


@dataclass(frozen=True, slots=True)
class LadderResult:
    """Everything ``run_ladder`` produced: the shape, the climb, the oracle chain, the off-chain run."""

    spec: LadderSpec
    shape: LadderShape
    learn: LearnActivityResult
    #: level ``i`` (0..k) -> the ``L_i`` oracle SEARCH run over the full train corpus.
    oracle_chain: dict[int, RunRecord]
    off_chain: RunRecord


def run_ladder(spec: LadderSpec, *, runs_root: Path | None = None) -> LadderResult:
    """Execute a ladder: the LEARN climb, the oracle chain ``L_0..L_k``, and the off-chain run."""
    shape = spec.lint()
    learn = run_search_learn(
        spec.reference_config, spec.train_corpus, spec.heldout_corpus, runs_root=runs_root
    )

    oracle_chain: dict[int, RunRecord] = {}
    for level in range(len(spec.rungs) + 1):  # L_0 (Floor) through L_k (all bridging rungs)
        config = spec.reference_config.with_(library=spec.oracle_library(level), learn=None)
        oracle_chain[level] = execute(
            RunSpec(config=config, corpus=spec.train_corpus), runs_root=runs_root
        )

    off_chain = execute(
        RunSpec(
            config=spec.reference_config.with_(library=_off_chain_library(spec), learn=None),
            corpus=spec.train_corpus,
        ),
        runs_root=runs_root,
    )
    return LadderResult(
        spec=spec, shape=shape, learn=learn, oracle_chain=oracle_chain, off_chain=off_chain
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
