# The breadth axis: constants, parameterization, and specialization abstractions (2026-07-24)

Search cost has two axes; the ladder formalism instruments one of them. A dated snapshot of the
2026-07-24 analysis, with the measurements that ground it (EXPERIMENTS.md 2026-07-24, "The breadth
axis"). Consumed by [LADDER-SET-DESIGN-2026-07-24.md](LADDER-SET-DESIGN-2026-07-24.md) and
[LADDER-SET-PLAN-2026-07-24.md](LADDER-SET-PLAN-2026-07-24.md).

## The two axes

- **Depth** — rounds of composition: how many times search applies-to-the-result-of. Instrumented
  everywhere: `d_i`, `depth_limit`, the depth sandwich, the validity window.
- **Breadth** — choices per round: which primitive, which pool entries, **which constants**. What
  the census products multiply over; what `considered` counts; what `max_pool` crowds.

Cost is roughly b^d, and **breadth costs compound with depth**: the same 100 constant choices cost
far more `considered` at round 3 than at round 1, because they multiply through every subsequent
census product. Binding a choice early is cheap; binding it late is expensive.

The project has met the breadth axis repeatedly without naming it: `considered_limit`/`max_pool`
are breadth budgets; the al14 collision guard was breadth censorship; pool starvation is breadth
exhaustion; the "vocabulary tax" of junk mints is this exact mechanism in reverse.

## The constants blur

A literal is functionally a **nullary quasi-primitive whose membership in the search space is
decided by config (`constant_sources`), not by the library**. The library defines the composition
space (depth axis); the config defines the choice space (breadth axis); search cost is their
product. The lint's depth model reads only the library axis — that is the blur. (Run identity is
unaffected: config is machinery-as-data and already hashes into `run_id`.)

## The measurements

One task, `flip_v(map_color(g, 1, 2))`, real engine, `depth_limit=2, max_arity=3, max_pool=400`,
`ProgramSize` cost, two 2x2 train grids (`[[1,0],[3,1]]`, `[[4,1],[1,5]]`), outputs derived.
`mc12(g) := map_color(g, 1, 2)` built with `make_abstraction`. Measured at commit `6432fdc`.

| Cell | Library | Constants | `considered_limit` | Solved | Considered | Ranked solution |
| --- | --- | --- | --- | --- | --- | --- |
| A  | `{map_color, flip_v}` | `finite-enumerate` | 1M | yes (d2) | **4,758** | `map_color(flip_v(input), 1, 2)` |
| B  | `{mc12, flip_v}` | off | 1M | yes (d2) | **7** | `mc12(flip_v(input))` |
| A′ | `{map_color, flip_v}` | `finite-enumerate` | **60** | **no** | 60 | — |
| C  | `{map_color, flip_v, mc12}` | `finite-enumerate` | 1M | yes (d2) | **4,805** | `flip_v(mc12(input))` |

Three findings:

1. **A vs B: 680x considered at identical depth.** What a specialization buys is entirely on the
   breadth axis. The choice does not vanish — it *moves* to a cheap early round (mint time) and is
   cached in the library.
2. **A′: an empirical breadth sandwich.** Under a considered budget between B's cost and A's, the
   skip path is depth-affordable but breadth-intractable — the specialization is *necessary under
   the joint budget* while being structurally skippable on the depth axis. `Budget.considered_limit`
   already expresses this; the probe already checks the joint budget; only the static lint is
   depth-only.
3. **C: minting does NOT reduce search cost — it slightly increases it.** The mint improves the
   *solution* (ranking/MDL: `flip_v(mc12(input))` is now cheapest) but not the *search*. Mechanisms:
   enumeration is exhaustive by rounds, not cost-ordered (`solution_limit` deliberately off); dedup
   is post-generation (`considered` already paid); and the chicken-and-egg — a climb has ONE
   `Config`, and the constants the binding rung's own wake *needs* keep taxing every later rung.
   **The current machinery cannot cash breadth savings mid-climb.**

Consequence drawn immediately: the "specialization prelude" control arm is struck from Phase 1 (it
would measure ~zero, knowably), and Phase-1 cohorts keep `constant_sources` off wherever a
perceiver route exists, so they stay clean depth experiments.

## "Should constants cost depth 1?" — considered and rejected

It would buy symmetry with perceivers (a literal as a nullary derivation) and make specializations
depth-certifiable. It is still a category error: a depth increment is **additive and uniform**,
while the cost it would price is **multiplicative and context-dependent** — it scales with the
constant domain (10 colors vs 121 coords) and with *which round* consumes the choice. "+1 depth"
neither scales with either, and adopting it re-tunes the engine, every budget, every sandwich, and
the locks, for an accounting that is differently wrong. Depth should keep meaning "rounds of
composition"; choices get their own leg (below).

## The certificate consequence

The sandwich is two-legged in principle:

- **Depth leg** (exists, static): rung affordable at `depth_limit`; skip exceeds it.
- **Breadth leg** (missing from the static lint): rung mintable from demos (the S-B binding law);
  skip exceeds `considered_limit`/`max_pool` even where depth permits. Cell A′ is this leg run
  empirically with stock machinery.

This revises the depth-only claim about depth-1 rungs: they never certify **on the depth axis**;
on the breadth axis they certify whenever the choice they bind is expensive enough — once the
machinery can cash it.

## Approaches to cashing the savings (Phase 2+ candidates)

1. **Remove constants when a specialization mints** — wrong-grained. Leaves are shared (`1` serves
   every other binding); what the mint covers is a *product* (`map_color x 1 x 2`), not a leaf.
   Points at approach 3.
2. **Weight them down** — the standard answer: a probabilistic grammar over the library,
   enumeration in likelihood order, learned reweighting (constants stay reachable but drop below
   any budget's horizon). This is the DreamCoder architecture and leads to neural-guided search.
   Cost: replaces round-based deterministic enumeration with priority search and puts continuous
   learned parameters into run identity. Phase 3 flavored.
3. **Abstraction-normal-form pruning** — generate only terms in normal form w.r.t. the library:
   refuse to build a candidate whose body is a library template instantiated (`map_color(x, 1, 2)`
   is `mc12(x)` spelled long). Subsumption pruning: discrete, deterministic, compatible with
   content-hashed run identity, and the machinery half-exists (`analysis/rewrite.py` normal forms,
   the equations infrastructure). Literature: equality-saturation library learning ("babble").
   **The arc-lab-native option**; genuinely reduces `considered`, not just ranking.

## Taxonomy: what reduces which axis

Learnable artifacts come in (at least) three kinds over the two cost axes:

| Artifact | Axis | Mechanism | Objective it needs |
| --- | --- | --- | --- |
| Chunking abstraction (d_i>=2 rung) | depth | fewer rounds to the target | compression (have: MDL) |
| Binding / fusing abstraction (specialization; deliberate param-fusion per S-B covariance) | breadth | fewer choices per hole | search-cost delta (missing) |
| Type refinement (e.g. the addressing tier: `Coord` vs `pair[int,int]`) | breadth | partitions pools; excludes ill-typed products from the support | pruning value (missing; see the type-invention discussion) |

Config-level breadth *controls* (not learned): `Constraint`s, observational dedup, `max_pool`.
Note the addressing tier was breadth work all along — "perception-derived coordinates stay bundled"
never changed a depth; it shrank per-hole candidate pools.

**Parameterization is the bridge**: choosing Param-vs-frozen-Const is choosing *where each choice
is paid* — at mint time (early, once, specialized) or at every consumer's search round (late,
recurring, general). v1-vs-v3 of cfb2ce5a is bind-early vs bind-late; the S-B demo law is the
control surface. Sub-cohorts differing in parameterization are experiments in choice-binding
placement (LADDER-SET-DESIGN).

## Literature anchors

The unifying frame is **description length**: enumeration cost ~ 2^(bits under the library's
induced prior). Chunking saves structure bits; binding saves parameter bits (~log2|choices| per
bound constant, compounding); type refinement saves bits by shrinking the support. Our
`(depth_limit, considered_limit)` budget is a two-knob approximation of one bit-budget.

- **DreamCoder** (Ellis et al. 2021) — wake-sleep library learning, PCFG-weighted enumeration,
  neural recognition model: the canonical "weighting" endpoint.
- **Stitch** (Bowers et al. 2023; shipped here) — note both score by *corpus compression*, not
  search cost; the gap between those objectives is exactly what cell C exposes (MDL improved,
  search worsened).
- **Fragment grammars** (O'Donnell) / **adaptor grammars** (Johnson) — store-vs-compute as
  inference; the closest literature to the ladder program's actual question.
- **Type-directed synthesis** (Synquid; Myth) — "types as selection constraints," fully developed.
- **Equality saturation / babble** — library learning modulo equations; the normal-form-pruning
  line.

Not found in the literature: certificates of rung *necessity* (the sandwich) and the explicit
two-knob budget treatment — the lab's controlled-experiment angle appears to be the novel part.
