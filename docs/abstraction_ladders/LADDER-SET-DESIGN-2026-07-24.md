# Ladder-set design: tasks, cohorts, sub-cohorts, spines (2026-07-24)

How the experiment set of ladders is structured, and the vocabulary for talking about it. A dated
snapshot of a design discussion (2026-07-24); the relationship taxonomy it builds on is
[LADDER-RELATIONSHIPS-2026-07-23.md](LADDER-RELATIONSHIPS-2026-07-23.md), the cost-axis analysis it
leans on is [BREADTH-AXIS-2026-07-24.md](BREADTH-AXIS-2026-07-24.md), and the execution plan that
consumes it is [LADDER-SET-PLAN-2026-07-24.md](LADDER-SET-PLAN-2026-07-24.md).

## The hierarchy

```
task            an ARC task (the shared target)
 └─ cohort      shared floor + top          -> raw search cost cancels; costs directly subtractable
     └─ sub-cohort   shared factorization skeleton (compositional path + parameterization)
         └─ ladder   one cut-set of the skeleton, at its own budget
```

- **Within a sub-cohort**, members vary in **cut density only** — the granularity experiment
  (relationship: *sub-ladder / skip*).
- **Across sub-cohorts of one cohort**, the skeleton differs — different intermediates and/or
  different parameterization (relationship: *sibling*). This is the **decomposition-strategy**
  experiment, a different question from granularity, and keeping them in separate sub-cohorts is
  what keeps the two questions unconfounded.
- **Across cohorts of one task**, the floor differs — in depth *and* in kind (a high-level floor /
  a lowered floor / a floor with HOF or conditional capability are all cohorts of the same task).
  Relationship: *ablation*; the raw-cost delta measures what the floor's power was worth.
- **Across tasks**: the remaining diversity (perception-heavy vs layout vs recolor, difficulty).

## Definitions

**The coordinate system.** A cohort's ladders all compute the same top; `diff-ladder` proves their
unfolded-to-floor terms equal (cfb2ce5a v1 ≡ v3: byte-identical). That unfolded term — the AST — is
the **coordinate system** for the whole cohort. It is not a ladder and has no budget; every rung of
every member is a contiguous fragment of it.

**Compositional path / factorization skeleton = cuts + parameterization.** Parameterization (which
subterms of a fragment become `Param`s vs stay frozen `Const`s) is *invisible after unfolding* —
v1 and v3 have identical terms but different intermediate functions — so it must be carried
explicitly at the sub-cohort level. It is also an *economic* choice, not just a structural one:
binding a value at mint time vs deferring it to every consumer's search round is a choice of where
on the breadth axis the cost is paid (see BREADTH-AXIS §parameterization).

**Sub-cohort identity = the coordinate system + the finest-level parameterization.** Members are
cut-sets. Two facts keep this honest:

1. Coarser members' parameterization is **induced, not identical**: merging fragments can freeze
   what the finer level parameterized (the consumer's call site is absorbed). The invariant lives
   at the spine level; each member's effective parameterization is derivable from its cut-set.
2. Newly-frozen params in merged rungs are exactly the S-D specialization-mint risk — the
   `free-params-covary` lint and the probe catch it, but coarser members trip it structurally more
   often. Demo plans must be re-derived per member (S-B: the demo value-patterns ARE the mint's
   specification).

## Spines

**There is no depth-1 decomposition of a nontrivial top.** To chain is to compose: a rung that
builds on a lower rung's value must apply its new operation *to the lower rung's application* —
d_i >= 2 definitionally. The only depth-1 rungs that exist are the two non-chaining forms:

- **aliases** (all children are params) — zero MDL compression; governance refuses them;
- **specializations** (some children frozen constants) — real objects, but they live on the
  *breadth* axis (BREADTH-AXIS doc), not the depth axis.

**The finest chained decomposition is one-new-AST-node-per-rung — an all-d2 chain.** This is what
"trivial spine" correctly refers to. (The earlier notion of a depth-1 trivial spine was a
confusion; the object does not exist.)

**Depth-1 rungs structurally fail the depth sandwich at every budget** (verified): inlining a
depth-1 body into its call site preserves every consumer's depth, so if the consumer is affordable
the skip is too. With constants off the rung is instead unreachable. Either way it fails one leg.
(On the *breadth* axis a specialization can be genuinely necessary — but the current machinery
cannot cash that; see BREADTH-AXIS.)

**The "useful spine" is a pragmatic artifact, not a derived object.** Maximal cut-sets are not
unique (chunking a 5-deep unary chain into >=2-deep fragments can go 2+3 or 3+2; neither refines
the other), so "the finest member" involves a small, localized judgment: which maximal alignment to
anchor on. Everything else stays derived and checkable:

- **membership** — unfold a coarse member's rung and check it equals the composition of consecutive
  spine rungs (`diff-ladder`-style static check, no bodies needed);
- **achievable skips** — the per-consumer double-jump computes which cut-sets survive *before
  anything is authored* ("the count bounds; the depth-sandwich selects");
- **budget windows** — each cut-set induces a validity window (`depth_limit` >= max rung depth,
  < min double-jump). The finest member needs `depth_limit=2`; merging k consecutive nodes needs
  ~k+1. **Granularity and budget co-vary by necessity — the coupling is the content of the
  granularity question** (many small steps at small budgets vs few big steps at big budgets), not a
  confound to control away.

## The spine as generator

Author one spine per sub-cohort + a list of cut-sets; coarser members are derivable (merged rung
templates are compositions of consecutive spine rungs; induced parameterizations follow). What is
NOT mechanical is the **demo plan** per member: outputs are derived (the `.ladder` loader evaluates
declared solutions — DRV-3/4), but choosing input grids and the per-param variation plan is a
**propose-check loop with Claude as the proposer** and a fully-built checker (S-B arity law +
`free-params-covary` + discriminating grids + `probe-ladder`, seconds per iteration). Authoring
effort concentrates there; quantify it on the first generated sub-cohort before building a
generator.

## Choosing tasks

- **Hostability considered, not overindexed**: a fold cohort wants genuine repetition structure; a
  conditional cohort wants a condition that takes both truth values across examples
  (`if-condition-varies`). Tasks are chosen partly for which bundle-type cohorts they can host —
  but the cohort axis carries bundle diversity too, so this is one factor among several.
- **Difficulty ranges, biased easier**: easier tasks mean low-to-medium floors, cheaper
  floor-lowering per cohort, affordable raw arms.
- **With a hard lower bound**: a task can be too easy to host any ladder — if the top is reachable
  from the floor within a reasonable budget, every candidate collapses via skip paths (Family-B,
  al10-style). Screen candidates with a cheap probe of raw-intractability from 1-2 candidate floors
  before committing to authoring; select from survivors.

## Cost accounting (what shapes the set)

Raw cancels within a cohort, so **one raw arm prices every member**: skips and sub-cohorts are the
cheap dimensions. **Every new cohort is a new floor and a new raw arm** — cohorts (and tasks) are
the expensive dimension. Hence the shape: few tasks x 1-2 cohorts each (Phase 1) x 1-2 sub-cohorts
x skip-populated members, landing in the 10-30 range; Phase 2 adds the HOF/conditional cohorts to
tasks whose baselines already ran.
