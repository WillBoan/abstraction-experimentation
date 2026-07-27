"""S6: sweep every registry ladder for the S2 defect class.

The climb searches at the pinned reference ``budget.depth_limit``; the chain runs the derived
per-level schedule. If the pinned value is below the schedule's maximum (the top's jump depth),
the climb is structurally unable to express the top at any budget -- the defect found on
``dae9d2b5-split-asym-lean`` and latent in both ``nor-halves`` members. Statically checkable,
so check it everywhere.
"""

from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder

bad = 0
for name in sorted(ladder_paths()):
    try:
        spec = make_ladder(name)
    except Exception as e:  # noqa: BLE001 -- a survey, not a gate
        print(f"{name:34} LOAD FAILED: {e}")
        continue
    sched = spec.depth_schedule()
    pinned = spec.reference_config.budget.depth_limit
    need = max(sched)
    flag = ""
    if pinned < need:
        flag = "  <-- CLIMB CUT OFF (pinned < top depth)"
        bad += 1
    print(f"{name:34} pinned={pinned}  schedule={list(sched)}  max={need}{flag}")
print(f"\naffected: {bad}")
