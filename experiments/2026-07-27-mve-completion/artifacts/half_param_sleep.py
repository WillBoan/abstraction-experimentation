"""S16b: WHY does sleep specialise? Separate proposer reach from governance preference.

`dae9d2b5-half-param`'s probe convicts rung 1: wake is as-intended on all four demos, no skip path
exists, and then `sleep: MISSED; minted ['abs0','abs1'] at arity 1 (intended 2)` -- two specialised
abstractions instead of the one parameterized `half`.

Two very different causes produce that symptom, and the distinction is the whole finding:
  (a) GOVERNANCE -- `AntiunifyPairs` offered the arity-2 generalisation and `GreedyMDL` preferred
      the specialised pair. A finding about the SELECTOR / cost model.
  (b) PROPOSER REACH -- the generalisation was never offered at all. A finding about the PROPOSER,
      i.e. the same species as S15's root-exclusion mechanism.

So: pull the four RETAINED programs off the probe, call the proposer directly and inspect every
candidate it offers, then run the full engine and see what governance keeps.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.behavioral import matches_target
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.ladders.probe import probe_rung
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.substrate.abstraction import make_abstraction

spec = make_ladder("dae9d2b5-half-param")
rung = spec.rungs[0]
library = spec.oracle_library(0)
probe = probe_rung(spec, 1)

by_id = {e.task.task_id: e for e in spec.train_corpus.entries}
retained = [(p.task_id, p.found) for p in probe.wake if p.found is not None]
print("RETAINED PROGRAMS (what sleep is fed):")
for task_id, program in retained:
    print(f"  {task_id:12} {program}")

programs = [program for _, program in retained]
target = make_abstraction(rung.name, rung.template, library)
probe_grids = tuple(
    example.input for entry in spec.train_corpus.entries for example in entry.task.train
)
print(f"\nTARGET: {rung.name} arity {target.arity}")

learn = spec.reference_config.learn
assert learn is not None
proposer = learn.learn_engine.proposer
candidates = proposer.propose(list(programs), library)
print(f"\nPROPOSER ({type(proposer).__name__}) offered {len(candidates)} candidate(s):")
generalised_offered = False
for cand in candidates:
    abstraction = make_abstraction("cand", cand, library)
    hit = matches_target(abstraction, target, probe_grids)
    generalised_offered = generalised_offered or hit
    print(f"  arity {abstraction.arity}  matches-target={hit}  {cand}")

solved = tuple(
    SolvedTask(annotated=by_id[task_id], program=program) for task_id, program in retained
)
outcome = learn.learn_engine.run(library, solved)
print(
    f"\nGOVERNANCE ({type(learn.learn_engine).__name__} / "
    f"{type(learn.learn_engine.selector).__name__}) kept {len(outcome.added)}:"
)
for added in outcome.added:
    print(
        f"  {added.name} arity {added.arity}  matches-target="
        f"{matches_target(added, target, probe_grids)}"
    )

print(
    "\nVERDICT: "
    + (
        "GOVERNANCE -- the arity-2 generalisation WAS offered and the selector discarded it."
        if generalised_offered
        else "PROPOSER REACH -- the arity-2 generalisation was never offered."
    )
)
