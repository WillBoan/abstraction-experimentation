# SEARCH-SPACE.md

A map of the **control surface for what programs are _expressible_** — the "what's possible" levers. Sibling to [ONTOLOGY.md](ONTOLOGY.md) (lever 1, the primitive vocabulary / Floor) and [MACHINERY.md](MACHINERY.md) (lever 3, the search / scoring / learning Machinery): those catalog _the things_ (primitives, mechanisms); this one maps _how you toggle which of them are in play for a run_, and why some toggles are the vocabulary itself while others must be an explicit switch. [RESEARCH-2026-07-08.md](RESEARCH-2026-07-08.md) is the frame all three are read against; run-time configuration lives in [ARCHITECTURE.md](ARCHITECTURE.md)'s `Config` (`solvers/dsl/config.py`).

It exists because "control the search space" hides at least two independent gates that get conflated: **curating the bag of primitives** and **flipping a capability the bag can't summon**. The load-bearing fact — the reason this needs its own map — is that _vocabulary curation is necessary but not sufficient_: **invention can re-introduce a capability you thought you removed by emptying the bag** (see Table B, higher-order invention). You can't reason about "turn X off for this run" without seeing both gates.

> **Status: phase-1 conceptual model — not yet reconciled with the code.** This is the map of _what control should look like_, derived from first principles, **before** auditing what's actually wired. Several Table-B switches likely already exist as `Config` axes (`Config.library`, `Config.search.kind`, `Config.cost`, …); others may be absent or baked. **Phase-2 job:** for every row below, mark _implemented? / how? / switch-or-bag-only?_ and reconcile against `solvers/dsl/config.py` + `substrate/`. Confidence is `[H]` working-hypothesis throughout until then.

## How to read / maintain this

- **Two tables, one dividing line.** Table A = capabilities _summoned by the vocabulary_ (control by curating the bag — no switch needed). Table B = capabilities _not fully gated by the bag_ (they need their own config switch). The line between them is the whole point.
- **The Options column is the experiment surface** — the settings you'd actually vary for a run.
- The **rendered companion** — [`search-space-control.html`](search-space-control.html) — carries the same two tables plus the co-dependency **graph** (open in a browser; GitHub shows it as source).
- Deliberately a _map_, not a claim of coverage. Update the Status once phase-2 grounds each row.

## Mental model (the words we're using)

**Three capability layers.**
- **Vocabulary** — the bag of typed primitives (given _and_ invented). Curated per run.
- **Search capability** (forward / wake) — given a hole of type `T`, can the engine _fill_ it? (function-holes, branching, recursion, unification.)
- **Invention capability** (backward / sleep) — given solved programs, what _new_ vocabulary can it manufacture? Feeds back into the bag.

**The law.** _Types summon capabilities._ A primitive is **usable** iff the engine supplies **every** capability its type signature demands; otherwise it sits in the bag as **dead weight**. So capabilities aren't toggled directly — they're summoned by the types you admit.

**Two kinds of "capability."** _New nouns_ (Bool, Object) add leaves to the space, roughly additively. _New constructions_ (higher-order, polymorphism) add ways-to-combine, and multiply the space combinatorially. `if` is neither higher-order nor a noun on its own — it's **control flow** (branching) that _requires_ a Bool sub-vocabulary and short-circuit evaluation.

## Table A — Summoned by the input vocabulary

Control = **curate the bag**. ON iff a primitive whose _type_ demands/provides it is present. No switch needed.

| Capability | Options | Turned on by (a primitive typed…) |
| --- | --- | --- |
| Data nouns in play | Grid · Int/Color · Bool · Object · List[·], Pair[·] | any primitive that produces/consumes that type |
| Boolean sub-vocabulary (predicates) | none · `is_empty` / `equals` / `contains_color` … | a `… → Bool` primitive |
| Branching / control flow | absent · present (`if`) | the `if` primitive — drags in short-circuit eval (build-time) **and** requires the row above |
| Higher-order primitives | none · `map` / `fold` / `filter` / `sort_by` | a primitive with a _function-typed argument_ (also demands the fill-mode switch in B) |
| Arithmetic & comparison | none · `+ − ×` · `= > <` | `Int→Int`, `Int→Int→Bool` primitives |
| Object pathway | neither · on-ramp only (`segment`) · off-ramp only (`render`) · both | `Grid→List[Object]` and `List[Object]→Grid` |
| Type discipline of the bag | ground-only (monomorphic) · schema (polymorphic — type vars) | choosing primitives with vs. without type variables |

## Table B — Not fully gated by vocabulary → give it a switch

Curating the bag can't cleanly toggle these — invention re-summons them through the back door, or they answer _how_, not _what_. Likely home: `Config` in `solvers/dsl/config.py`.

| Capability | Options | Why it needs its own switch |
| --- | --- | --- |
| Higher-order **invention** | off · on (function-typed `Param`s + operator-position abstraction) | can mint `twice` from a _first-order_ bag — the back-door gate; removing HO primitives does **not** stop it |
| Recursive **invention** | off · on | can mint recursion the bag never held; termination-safety risk |
| Invention governance (MDL bar) | strict … permissive (threshold) | a policy with no vocabulary proxy |
| Function-hole fill mode | none (unfillable) · point-free only · full lambda synthesis | even with HO primitives present, _how_ a function-hole is filled is a separate choice (dormant until a hole exists) |
| Polymorphism instantiation | monomorphize · bounded (task-reachable) · unrestricted | "how far to instantiate type variables" is orthogonal to which primitives exist |
| Constant policy | finite-enumerate · harvest-from-instance · functionally-derive · parameterize (lift to `Param`) | orthogonal to which primitives are present |

**Two rows that decompose on purpose:**
- **Polymorphism spans both tables.** Its _vocabulary_ aspect (mono vs. poly primitives) is a bag choice → A. Its _instantiation_ aspect (how far to solve type vars) is a knob → B. Same word, two independent levers.
- **"Higher-order support" is not one row** — it's four: _HO primitives_ (A) + _type discipline_ (A) + _HO invention_ (B) + _fill mode_ (B). That's why you can't turn higher-order on/off in one place — and why emptying the bag of HO primitives doesn't disable higher-order _invention_.

## Co-dependency clusters (the connectivity law)

One rule generates every cluster: **a type is useful only if the bag holds both a _producer_ (`…→T`, an on-ramp) and a _consumer_ (`T→…`, an off-ramp) that place it on a typed path from the input Grid back to the output Grid.** A type with no path home is an **island** — search can build it but never use it (dead weight). "Co-dependency" = the requirement that the vocabulary's type graph is _connected_ from input to output through every type it introduces.

```
              on-ramp (…→T)              off-ramp (T→…)
  Grid ─────────────────────▶ [ T ] ─────────────────────▶ Grid

  DIRECT   Grid ─rotate/flip/crop──────────────────────────▶ Grid          ✓ no detour
  OBJECTS  Grid ─segment▶ List[Object] ↻(recolor/move) ─render▶ Grid        ✓ on- & off-ramp
  BOOL+IF  Grid ─predicate▶ Bool ─cond▶ [if] ──────────────▶ Grid          ✓ `if` IS Bool's off-ramp
  NUMBERS  Grid ─count▶ Int ─compare▶ Bool ─▶ [if] ────────▶ Grid          ✓ two-hop off-ramp
  ISLAND   Grid ─histogram▶ Histogram  ─╳  (no consumer back)               ✗ dead weight
```

Read it: `Bool` has no direct route to a grid — `if` _is_ its off-ramp; drop `if` and predicates become an island, drop predicates and `if`'s condition is unfillable. `Int` gets home only via a **two-hop** off-ramp (`compare`→`Bool`, then `if`→`Grid`); drop either hop and `Int` is an island. Rendered version with colour/ramps: [`search-space-control.html`](search-space-control.html).

## The through-line

Types summon capabilities (Table A); some capabilities slip past vocabulary and need their own switch (Table B); and the vocabulary only pays off when its types form a connected on-ramp/off-ramp path from input to output (the graph). **Curating the bag is necessary but never sufficient.**

## Phase-2 checklist (drain when grounding against code)

- [ ] For every Table A/B row: _implemented? / how? / switch-or-bag-only?_
- [ ] Reconcile Table B against `Config` (`solvers/dsl/config.py`) — which switches exist, which are baked, which are absent.
- [ ] Substrate check: can `Param` carry a **function type**? Is the operator position of `Apply` an _abstractable subterm_ (→ HO invention possible) or a fixed symbol (→ not)?
- [ ] Search check: function-hole fill mode actually implemented — none / point-free / lambda synthesis?
- [ ] Once grounded: add reciprocal pointers in [ONTOLOGY.md](ONTOLOGY.md) / [MACHINERY.md](MACHINERY.md), and a line under CLAUDE.md "Sources of truth."