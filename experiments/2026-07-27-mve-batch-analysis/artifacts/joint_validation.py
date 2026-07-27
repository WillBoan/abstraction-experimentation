"""Joint 1x2 validation: does (per-level pool + immediate solution_limit) reproduce the CERTIFIED
verdict profile of `dae9d2b5-split-recolor` (pool 150, exhaustive, ADMITTED)?

Validated as a PAIR, not knob-by-knob: with an immediate stop the retained program is the
first-enumerated, and which program that is depends on the pool -- so the two interact exactly where
collapse/alternative detection lives.
"""
import dataclasses, json, time
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import run_ladder

spec = make_ladder("dae9d2b5-split-recolor")
budget = dataclasses.replace(spec.reference_config.budget, solution_limit=1,
                             solution_limit_mode="immediate")
fast = dataclasses.replace(spec, reference_config=spec.reference_config.with_(budget=budget))
t0 = time.time()
res = run_ladder(fast, raw_arm_k=0)
cert = res.certificate
print(f"elapsed {time.time()-t0:.1f}s")
print("admitted        :", cert.admitted)
print("tractable_jumps :", cert.tractable_jumps)
print("no_skip_paths   :", cert.no_skip_paths)
print("demo health     :", cert.demonstration_health)
print("recovered       :", [(r.rung, r.recovered) for r in (res.learn.rung_recovery if res.learn else [])]
      if res.learn else "no climb")
