"""Is the TwoPartMDL collapse CALIBRATION or STRUCTURE?

2026-08-03's arm took rung recovery 55/57 -> 1/57 under `TwoPartMDL`, from one decline per
ladder at its lowest rung. The registered caveat was that a total collapse is equally consistent
with `bits_per_primitive = 1.0` being miscalibrated -- never swept.

It is decidable WITHOUT sweeping, because the parameter enters linearly and only through the flat
term. For one candidate abstraction over a library `L` and corpus `C`:

    DL(mint) - DL(none) = b * 1                      # one more primitive at the flat rate
                        + template.size()            # TwoPartMDL's definition term (b-independent)
                        - saving                     # program bits the rewrite removes

so minting wins iff `b < saving - template.size()`. Call that the **break-even b***. Since
`b >= 0`, a candidate whose b* is negative is declined at EVERY setting of the parameter: the
definition term alone already outweighs what the abstraction saves.

This prices every proposal the recorded runs actually saw -- read-side, no search. Proposals are
recomputed from each iteration's wake programs + library exactly as `ladders/recovery.py` does.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.compression import TwoPartMDL
from arc_lab.program_search.ladders.batch import batch_members
from arc_lab.program_search.ladders.recovery import (
    _as_primitive,
    _iteration_views,
    _proposers_of,
)
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import run_ladder
from arc_lab.program_search.learn.engines import rewrite_with

METRIC = TwoPartMDL()


def break_even(spec, record, floor):
    """Every proposal the run's own wake programs support, priced. Returns rows of
    (iteration, name, definition size, program saving, b*)."""
    rows = []
    views, _ = _iteration_views(record, floor)
    proposers = _proposers_of(spec)
    for iteration, library, programs in views:
        if not programs:
            continue
        base_program_bits = sum(METRIC.cost.of(p, (), library) for p in programs)
        seen = set()
        for proposer in proposers:
            for proposal in proposer.propose(list(programs), library):
                template = getattr(proposal, "template", proposal)
                key = str(template)
                if key in seen:
                    continue
                seen.add(key)
                name = f"cand{len(seen)}"
                primitive = _as_primitive(name, template, library)
                if primitive is None:
                    continue
                grown = library.extended(name=f"{library.name}+{name}", extra=(primitive,))
                rewritten = [rewrite_with(p, name, template) for p in programs]
                new_bits = sum(METRIC.cost.of(p, (), grown) for p in rewritten)
                saving = base_program_bits - new_bits
                size = template.size()
                rows.append(
                    {
                        "iteration": iteration,
                        "definition_size": size,
                        "saving": saving,
                        "b_star": saving - size,
                        "template": key[:60],
                    }
                )
    return rows


def main() -> None:
    """Iteration 0 only. Iterations >= 1 are unreachable in the counterfactual: if nothing mints
    at iteration 0 the library never grows and `early_stop` ends the loop, so their libraries are
    ones TwoPartMDL would never have seen. Pooling them overstates what the metric would do."""
    print("Break-even `bits_per_primitive` per member, iteration 0 (read-side; no searches).")
    print("Minting wins iff b < b*, and b >= 0 -- so b* <= 0 means declined at EVERY setting.\n")
    print(f"{'ladder':30s} {'props':>5} {'b*':>6} {'defn':>5} {'save':>5}  {'at b=1.0':16s} class")
    print("-" * 88)
    tally: dict[str, int] = {}
    for name in batch_members():
        spec = make_ladder(name)
        # raw_arm_k=0: read-side pass; buying arms here would cost enumerations AND violate the
        # once-per-cohort RQ1 protocol (batch.RAW_ARM_MEMBERS).
        result = run_ladder(spec, raw_arm_k=0)
        if result.learn is None:
            continue
        rows = [
            r
            for r in break_even(spec, result.learn.learn, spec.reference_config.library)
            if r["iteration"] == 0
        ]
        if not rows:
            print(f"{name:30s} {0:>5} {'-':>6} {'-':>5} {'-':>5}  {'-':16s} no-proposals")
            tally["no-proposals"] = tally.get("no-proposals", 0) + 1
            continue
        best = max(rows, key=lambda r: r["b_star"])
        b = best["b_star"]
        # GreedyMDL accepts on STRICT improvement (`dl < best_dl`, engines.py), so a tie declines.
        if b > 1.0:
            at1, klass = "MINTS", "already-mints"
        elif b > 0.0:
            at1, klass = "declines (tie)" if b == 1.0 else "declines", "CALIBRATION"
        else:
            at1, klass = "declines", "STRUCTURAL"
        tally[klass] = tally.get(klass, 0) + 1
        print(
            f"{name:30s} {len(rows):>5} {b:>6.1f} {best['definition_size']:>5} "
            f"{best['saving']:>5.0f}  {at1:16s} {klass}",
            flush=True,
        )
    print("-" * 88)
    print(f"tally: {tally}")
    print(
        "\nSTRUCTURAL    b* <= 0 -- the definition term alone outweighs the saving; no b rescues it.\n"
        "CALIBRATION   0 < b* <= 1 -- some b below the current 1.0 would mint.\n"
        "already-mints b* > 1 -- minting already wins at b = 1.0 (recovery can still be 0 if what\n"
        "              it mints is not the authored rung -- see 94f9d214-nor-recolor)."
    )


if __name__ == "__main__":
    main()
