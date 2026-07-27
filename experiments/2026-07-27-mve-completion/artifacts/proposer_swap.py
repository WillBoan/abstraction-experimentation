"""S15: is the never-failing learner a property of wake-sleep, or of ONE proposer?

Every real-task result to date -- 43/43 rungs recovered, 0 junk mints -- was produced with
`AntiunifyPairs` and nothing else. That makes "the learned-vs-oracle gap is exactly zero" a claim
about one proposer, not about the loop. This swaps the proposer on already-certified ladders and
asks whether recovery survives.

**Why it is cheap:** the oracle chain builds its configs with `learn=None`
(`run.py::run_ladder_chain`), so the learn spec is not part of any chain cell's run identity. Change
the proposer and the ENTIRE chain cache-hits; only the climb re-runs. Verified below by asserting
the certificate is byte-identical across arms -- if a chain cell had re-run, that is where it would
show.

Outcomes and what each means:
- all proposers recover every rung -> the zero gap is a property of the LOOP, much stronger claim
- a proposer fails to recover -> proposer sensitivity, the first honest nonzero gap, and it names
  which proposer capability the ladder actually depends on
"""

from __future__ import annotations

from dataclasses import replace

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report
from arc_lab.program_search.ladders.run import run_ladder
from arc_lab.program_search.learn.antiunify import (
    AntiunifyPairs,
    FrequentSubtree,
    TypeScopedFrequentSubtree,
)
from arc_lab.program_search.substrate.types import GRID

PROPOSERS: list[tuple[str, object]] = [
    ("AntiunifyPairs (baseline)", AntiunifyPairs()),
    ("FrequentSubtree", FrequentSubtree()),
    ("TypeScopedFrequentSubtree[GRID]", TypeScopedFrequentSubtree(result_type=GRID)),
]
try:
    from arc_lab.program_search.learn.stitch_shim import StitchProposer

    PROPOSERS.append(("StitchProposer", StitchProposer()))
except Exception as exc:
    print(f"note: StitchProposer unavailable ({exc}) -- arm skipped\n")

MEMBERS = ("dae9d2b5-split-recolor-lean", "94f9d214-nor-merged", "al1-mirror")

for name in MEMBERS:
    base = make_ladder(name)
    print(f"=== {name}  ({len(base.rungs)} rungs)")
    print(
        f"{'proposer':28} {'admitted':>8} {'recovered':>10} {'junk':>5} {'iters':>6} {'end-to-end':>12}  mints"
    )
    reference_cert: object | None = None
    for label, proposer in PROPOSERS:
        learn_spec = base.reference_config.learn
        assert learn_spec is not None
        engine = replace(learn_spec.learn_engine, proposer=proposer)
        spec = replace(
            base,
            reference_config=base.reference_config.with_(
                learn=replace(learn_spec, learn_engine=engine)
            ),
        )
        try:
            result = run_ladder(spec, raw_arm_k=0)
        except Exception as exc:
            print(f"{label:28} {'-':>8} {'-':>10} {'-':>5} {'-':>6} {'-':>12}  RAISED: {exc}")
            continue
        report = create_ladder_report(result)
        cert = report["certificate"]
        # The chain must be untouched by a learn-side change; if it were not, every cost number
        # below would be comparing different searches.
        if reference_cert is None:
            reference_cert = cert
        else:
            assert cert == reference_cert, f"{label}: chain moved -- costs are not comparable"

        recovery = report["rung_recovery"]
        recovered = sum(1 for r in recovery if r["recovered"])
        matched = {m for r in recovery for m in r["matched_by"]}
        climb = report["climb_trace"]
        minted = [m for it in climb for m in it.get("minted", [])]
        junk = [m for m in minted if m not in matched]
        print(
            f"{label:28} {cert['admitted']!s:>8} {f'{recovered}/{len(recovery)}':>10} "
            f"{len(junk):>5} {len(climb):>6} "
            f"{report['cost']['laddered_end_to_end_considered'] or 0:>12,}  "
            f"{len(minted)} minted" + (f", junk={junk}" if junk else "")
        )
    print(flush=True)
