# Machinery Build Strategy · 2026-07-07

> **Provisional. A dated snapshot of _how we decide what machinery to build, adopt, or defer_ — as of 2026-07-07.** Companion to [MACHINERY.md](MACHINERY.md) (the _catalog_ of mechanisms) and [RESEARCH-2026-07-07.md](RESEARCH-2026-07-07.md) (the _frame_ — what we believe). Division of labor: MACHINERY = _the map_; RESEARCH = _what we believe_; **this = _how we proceed_.** Prior-art scores/meaning live in RESEARCH; here they appear only as build decisions.
>
> **May graduate to a living `MACHINERY-STRATEGY.md`** if it proves durable — until then, supersede with a new dated snapshot. Tags: **[C]** committed · **[H]** hypothesis · **[O]** open.
>
> **Current frame:** the barbell + build/adopt/defer decisions here remain current under [RESEARCH-2026-07-08.md](RESEARCH-2026-07-08.md) — which added the axis-2 framing and the measurement-first priority but changed no build/adopt/defer _decision_ — so this 07-07 snapshot still stands (no 07-08 strategy snapshot needed yet).

## The question that prompted this

Are we building the machinery too **step-by-step**, and would it be cheaper long-run to build the "maximal" system (maximal generality/expressivity/scale) **up front**? Reframed to its real content: _assuming we must build machinery to do the research, how do we balance **YAGNI vs. rework** so we waste the least effort?_ (Not about score — about time.)

The short answer **[H]:** a **barbell**. Build _one_ thing general and up front — the substrate. Stay demand-driven everywhere above it. Adopt rather than rebuild the two or three pieces mature tools already own. "Build the maximal system" is the wrong frame because most of it is either _unneeded_ or _not-yet-knowable_ — see below.

## Principle 1 — the maps are for planning, not a build queue [C]

[ONTOLOGY](ONTOLOGY.md) and [MACHINERY](MACHINERY.md) are _deliberately over-complete_ (they say so). Most `⚪ cand` rows are **alternatives to each other, not requirements** (MCTS vs. A\* vs. beam; e-graph vs. antiunify invention; whole stretches of L4/L5/L6 vocabulary). ARC is solvable by many routes — you will not need all of them, so building them all is _guaranteed_ waste. Over-completeness is a feature for **planning**, a trap for **building**. → Don't walk the rows top-to-bottom.

## Principle 2 — the A/B/C epistemic filter [H]

"Build it right from the start" is only _coherent_ for pieces whose design is known. Sort every candidate:

- **A — known, just labor.** Most of ONTOLOGY (masks, `segment`, `crop_to_content`, perceivers, object props); bottom-up enumeration; beam; two-part MDL; antiunify; real bit-costing; **lambda-index binding** (a De Bruijn index — DreamCoder/Stitch ship it). Here "build right up front" is a legitimate call.
- **B — known in the literature, hard to integrate/validate here.** Neurally-guided search, recognition models, version-space/e-graph invention, MCTS. Each ~doubles the codebase and **kills determinism** (RESEARCH names determinism as what makes the locks mean anything). Adopt or defer; don't hand-build.
- **C — genuinely open.** Does the bootstrap _climb_? Does compression predict transfer? What curriculum works? Which paradigm (descriptive vs. transformational)? **You cannot build these — only run experiments toward them.** This is the research, and "build it right up front" is a category error here.

→ Front-loading is possible for A, sometimes worth it for a slice of B, _impossible_ for C. The part that matters most cannot be pre-built.

## Principle 3 — the rework rule [H]

Build-ahead beats build-later **only when all three hold**: (1) confident it's **needed**; (2) retrofitting-later is **expensive** (things get built on top); (3) the **design is understood now** (you won't build the wrong version). Applied:

- **Substrate (F0):** all three hold — everything gates on it, retrofit-expensive, and E1–E4 taught us what binding needs. → **build ahead, build general.** The one place rework genuinely dominates.
- **Invention engine (F4 at scale):** (3) fails _if we build it_ (version spaces are subtle) but _passes if we adopt Stitch_. → the tension is **dissolved by adoption**, not resolved by timing.
- **Everything else:** (1) fails (over-complete) _and_ (3) fails (right shape unknown until real tasks hit). → **defer, YAGNI wins.**

The only rework worth _fearing_: (a) substrate rework, and (b) **building the invention engine twice.** Both have cheap insurance (Principle 4 + the keystone).

## Principle 4 — adopt, don't rebuild [H]

The uncomfortable pattern: the machinery we've _built_ is mostly ours to own; the biggest `unbuilt` rows are what mature tools already nailed. (Scores/meaning: RESEARCH §Where we sit.)

| Need (MACHINERY row) | Mature tool | Call |
| --- | --- | --- |
| F4 "DreamCoder-grade invention" | **Stitch** (`stitch_core`); **babble** | **Adopt at scale** — don't hand-build version spaces. Not _yet_: antiunify is correct for today's microworlds; adopt when the corpus outgrows it. |
| F3 equivalence at scale | **egg / egglog** | Adopt _if_ structural/soft match is needed; obs-equivalence is fine for now. |
| F1 enumeration | (none turnkey) | **Keep** — ours is idiomatic. |
| F1 neural guidance | PyTorch + bespoke | **Defer hard** — the determinism-killer, and specialists' own ARC results (~4.5–5.8%) say it hasn't paid off. |
| ONTOLOGY L2–L4 vocabulary | **Hodel `arc-dsl`** (~160 prims) | **Reference, not dependency** — crib correct implementations; don't import (the loop should _invent_ L2, not be handed it). |
| Ferré's ARC-MDL / MADIL | OCaml, **GPLv3** | **Learn-from, don't-copy** — language + copyleft wall. Take the _design_ (descriptive parse/generate model, full `L(M)+L(E|M)` accounting, MDL-guided refinement), not the source. |
| F0 substrate · F5 instrumentation | — | **Own it.** The substrate is the research object; F5 (the anti-teleological science layer) is the real differentiator. No library gives you `check_abstractions`. |

## The keystone move [H]

Build the F0 lambda-index as a **De Bruijn-indexed bound variable** — because that _simultaneously_ (1) unlocks the low-floor thesis (size-general geometry from cells; pixels→D4) and (2) **is Stitch's program representation** (`$i` De Bruijn vars, `#j` abstraction vars, `(lam …)`). Our AST is already `Input | Param | Const | Apply`; `Param`'s positional holes ≈ Stitch's abstraction vars, the missing lambda-index ≈ Stitch's `$i`. Design it Stitch-compatibly and future Stitch adoption is near-drop-in instead of a rewrite. **This is the single highest-leverage build** — the rework-avoidance is "shape the one piece you must build now so the biggest future adoption is cheap."

## Principle 5 — maps predict, tasks adjudicate [H]

We are **map-rich and real-workload-poor.** The 2026-07-07 machinery bundle was a _null result_ (four mechanisms shipped, zero measurable change) because the workload that would exercise them doesn't exist yet — latent machinery. Building _more_ of it up front makes that worse. The way to learn which catalogued pieces you actually need is not to reason about the maps — it's to **run the loop against real ARC tasks and see what it can't do.** The maps predict; the tasks write the build queue.

## Recommended approach (the barbell) [H]

1. **Substrate, general, now.** The De Bruijn / Stitch-compatible lambda-index; activate reserved `Mask`/`Object` types as first-class. Rework here dominates YAGNI.
2. **Demand-driven above it.** Batch only the high-confidence cheap tier (L2 perceivers, L3 masks). Leave objects/relations/schemas + exotic search unbuilt until a _task_ demands them.
3. **Adopt at scale, don't rebuild.** Stitch for invention, egg/babble for equivalence, Hodel as vocabulary reference; own substrate + instrumentation.
4. **Shift the workload to real tasks** so reality adjudicates the maps. The highest-value near-term move is probably not machinery at all — it's the keystone + pointing the loop at a real curriculum slice.

## Costs of _this_ approach, named honestly [O]

Incremental has failure modes too: the **microworld treadmill** (polishing the loop forever on known-answer testbeds); **latent machinery** (building ahead of the workload); **maps-as-procrastination** (two over-complete catalogs is itself a mild smell — value is in _draining_ them); and **determinism may not survive the scale** where bootstrap-climbing appears, forcing a bigger jump eventually. None are cured by "build the maximal system" — they're cured by getting the substrate right _once_ and confronting real tasks _sooner_.

**Net [H]:** the biggest long-run time-saver is not building more of the maximal system — it's _refusing to build the pieces mature tools own_, and spending the saved effort on the substrate + instrumentation only we can build.
