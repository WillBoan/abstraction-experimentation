# SEARCH-SPACE.md

A map of the **control surface for what programs are _expressible_** — the "what's possible" levers. Sibling to [ONTOLOGY.md](ONTOLOGY.md) (lever 1, the primitive vocabulary / Floor) and [MACHINERY.md](MACHINERY.md) (lever 3, the search / scoring / learning Machinery): those catalog _the things_ (primitives, mechanisms); this one maps _how you toggle which of them are in play for a run_, and why some toggles are the vocabulary itself while others must be an explicit switch. [RESEARCH-2026-07-08.md](archive/RESEARCH-2026-07-08.md) is the frame all three are read against; run-time configuration is the frozen `Config` bundle (`program_search/execution/model/config.py`, presets in `execution/presets.py` — see [EXECUTION.md](EXECUTION.md)), and the expressiveness switches themselves are fields on `program_search/search/search_engine.py::BottomUpSearchEngine`.

It exists because "control the search space" hides at least two independent gates that get conflated: **curating the bag of primitives** and **flipping a capability the bag can't summon**. The load-bearing fact — the reason this needs its own map — is that _vocabulary curation is necessary but not sufficient_: **invention can re-introduce a capability you thought you removed by emptying the bag** (see Table B, higher-order invention). You can't reason about "turn X off for this run" without seeing both gates.

> **Status: reconciled against the code, 2026-07-13.** Every row below has been audited and carries its implementation status. The wake-side switches (Table B, rows 4–7) live as fields on `program_search/search/search_engine.py::BottomUpSearchEngine`, set per run through `Config`/presets/`--set`; the sleep-side ones (rows 1–3) live in `program_search/learn/`. Two capabilities remain open — the **Object pathway** (Table A) and **recursive invention** (Table B). Resolutions from the audit are in [Grounding notes](#grounding-notes-2026-07-13).

## How to read / maintain this

- **Two tables, one dividing line.** Table A = capabilities _summoned by the vocabulary_ (control by curating the bag — no switch needed). Table B = capabilities _not fully gated by the bag_ (they need their own config switch). The line between them is the whole point.
- **The Options column is the experiment surface** — the settings you'd actually vary for a run.
- The **rendered companion** — [`docs/archive/search-space-control.html`](archive/search-space-control.html) — carries the same two tables plus the co-dependency **graph** (open in a browser; GitHub shows it as source).
- Deliberately a _map_, not a claim of coverage. The Status columns record the 2026-07-13 code audit; re-ground them when the control surface moves.

## Mental model (the words we're using)

**Three capability layers.**

- **Vocabulary** — the bag of typed primitives (given _and_ invented). Curated per run.
- **Search capability** (forward / wake) — given a hole of type `T`, can the engine _fill_ it? (function-holes, branching, recursion, unification.)
- **Invention capability** (backward / sleep) — given solved programs, what _new_ vocabulary can it manufacture? Feeds back into the bag.

**The law.** _Types summon capabilities._ A primitive is **usable** iff the engine supplies **every** capability its type signature demands; otherwise it sits in the bag as **dead weight**. So capabilities aren't toggled directly — they're summoned by the types you admit.

**Two kinds of "capability."** _New nouns_ (Bool, Object) add leaves to the space, roughly additively. _New constructions_ (higher-order, polymorphism) add ways-to-combine, and multiply the space combinatorially. `if` is neither higher-order nor a noun on its own — it's **control flow** (branching) that _requires_ a Bool sub-vocabulary and short-circuit evaluation.

## Table A — Summoned by the input vocabulary

Control = **curate the bag**. ON iff a primitive whose _type_ demands/provides it is present. No switch needed.

| Capability | Options | Turned on by (a primitive typed…) | Status (2026-07-13) |
| --- | --- | --- | --- |
| Data nouns in play | Grid · Int/Color · Bool · Mask · Object · List[·], Pair[·] | any primitive that produces/consumes that type | ✅ all but Object — `substrate/types.py` (`_BASE_TYPES` = Grid/Color/Int/Bool/Fn/Mask; `list`/`pair` constructors). **Object: not implemented** — the one Table-A gap |
| Boolean sub-vocabulary (predicates) | none · `eq` / `lt` / `gt` / `and` / `or` / `not` … | a `… → Bool` primitive | ✅ `primitives/control.py` |
| Branching / control flow | absent · present (`if`) | the `if` primitive — drags in short-circuit eval (build-time) **and** requires the row above | ✅ `control.py` — a capability token typed `(Bool, a, a) → a`; its presence in the bag summons short-circuit `If` AST nodes (never applied eagerly; ARCHITECTURE.md §5.4) |
| Higher-order primitives | none · `map` / `fold` / `filter` / `sort_by` | a primitive with a _function-typed argument_ (also demands the fill-mode switch in B) | ✅ `primitives/higher_order.py` — all four, with real body samplers |
| Arithmetic & comparison | none · `+ − ×` · `= > <` | `Int→Int`, `Int→Int→Bool` primitives | ✅ `arithmetic.py` (add/sub/mul/floordiv/mod/min/max/abs), comparisons in `control.py` |
| Object pathway | neither · on-ramp only (`segment`) · off-ramp only (`render`) · both | `Grid→List[Object]` and `List[Object]→Grid` | ❌ **not implemented** — no `Object` type, no `segment`/`render` (`Mask` covers cell selection, not objecthood) |
| Type discipline of the bag | ground-only (monomorphic) · schema (polymorphic — type vars) | choosing primitives with vs. without type variables | ✅ `types.py` — `TypeVar` + `unify`/instantiate; both disciplines in live libraries |

## Table B — Not fully gated by vocabulary → give it a switch

Curating the bag can't cleanly toggle these — invention re-summons them through the back door, or they answer _how_, not _what_. Home: sleep-side rows in `program_search/learn/`; wake-side rows are fields on `search/search_engine.py::BottomUpSearchEngine` (surfaced per run via `Config`/presets/`--set`).

| Capability | Options | Why it needs its own switch | Status (2026-07-13) |
| --- | --- | --- | --- |
| Higher-order **invention** | off · on (function-typed `Param`s + operator-position abstraction) | can mint `twice` from a _first-order_ bag — the back-door gate; removing HO primitives does **not** stop it | ✅ `learn/antiunify.py` — `AntiunifyPairs` (with `bound_var_safe`) + `FrequentSubtree` proposers |
| Recursive **invention** | off · on | can mint recursion the bag never held; termination-safety risk | ❌ **not implemented** — no recursion-minting proposer; still open |
| Invention governance (MDL bar) | strict … permissive (threshold) | a policy with no vocabulary proxy | ✅ `GreedyMDL` selector (`learn/selection.py`) over `CompressionMetric`/`TwoPartMDL` (`analysis/compression.py`) |
| Function-hole fill mode | none (unfillable) · point-free only · full lambda synthesis | even with HO primitives present, _how_ a function-hole is filled is a separate choice (dormant until a hole exists) | ✅ `function_hole_fill_mode: "none" \| "point-free" \| "lambda-synthesis"` — all three implemented and tested; ⚠ `lambda-synthesis`'s target propagation is unsound under a same-type wrapper, so a HO call is reliably reachable only at the root of a solution (ARCHITECTURE.md §7 correction, 2026-07-22) |
| Polymorphism instantiation | monomorphize · bounded (task-reachable) · unrestricted | "how far to instantiate type variables" is orthogonal to which primitives exist | ✅ `polymorphism_instantiation` — all three (`search/polymorphism.py`) |
| Constant policy | finite-enumerate · harvest-from-instance · parameterize (lift to `Param`) | orthogonal to which primitives are present | ✅ `constant_sources` tuple (`search/leaves.py`); `parameterize` is an engine no-op realized in `learn/`. The phase-1 `functionally-derive` option was deliberately dropped as a leaf source — derived constants are already reachable as compositions (`width(Input())`) |
| Unpinned-type-var resolution | reject · eager grounding over the type universe · lazy synthesis | how a hole whose type is _still a variable_ gets resolved — orthogonal to instantiation of composed values (a switch the phase-1 map didn't predict) | 🟡 `unpinned_type_var_mode: "reject" \| "eager_grounding_over_universe" \| "lazy_synthesis"` — first two implemented; `lazy_synthesis` unbuilt (raises) |

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

Read it: `Bool` has no direct route to a grid — `if` _is_ its off-ramp; drop `if` and predicates become an island, drop predicates and `if`'s condition is unfillable. `Int` gets home only via a **two-hop** off-ramp (`compare`→`Bool`, then `if`→`Grid`); drop either hop and `Int` is an island. Rendered version with colour/ramps: [`docs/archive/search-space-control.html`](archive/search-space-control.html).

## The through-line

Types summon capabilities (Table A); some capabilities slip past vocabulary and need their own switch (Table B); and the vocabulary only pays off when its types form a connected on-ramp/off-ramp path from input to output (the graph). **Curating the bag is necessary but never sufficient.**

## Grounding notes (2026-07-13)

The phase-2 checklist is drained; per-row verdicts are in the Status columns above. Resolutions worth keeping:

- **Substrate can represent HO invention.** `Param` _can_ carry a function type, and the substrate has first-class function values (`PrimRef`, `AppFn`, `Lam` — `substrate/program.py`), so the operator position is an abstractable subterm, not a fixed symbol.
- **`functionally-derive` dissolved, not dropped.** It isn't a `ConstantSource` leaf because derived constants are already reachable as ordinary compositions (`width(Input())`) — a source would double-count them.
- **One switch the phase-1 map missed:** `unpinned_type_var_mode` (last Table-B row) — the map conflated it with polymorphism instantiation, but instantiating composed _values_ and resolving a still-variable _hole type_ are independent knobs.
- **Still open:** the Object pathway (Table A) and recursive invention (Table B); `unpinned_type_var_mode="lazy_synthesis"` is declared but unbuilt. (The reciprocal pointers — [ONTOLOGY.md](ONTOLOGY.md) / [MACHINERY.md](MACHINERY.md) headers and CLAUDE.md's "Lever maps" line — are in place.)
