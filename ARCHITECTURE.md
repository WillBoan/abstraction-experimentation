# ARCHITECTURE.md — the program-search engine

The design contract for the **full-capability program-search engine** under
`src/arc_lab/solvers/program_search/`. This is the thing we build to; a change that
deviates from it either updates this file first or is a bug.

**Scope.** This document covers the *search engine* — how programs are proposed, filtered,
and ranked. It does **not** yet cover the run/config/corpus model, the activity tiers, or
the `runs/` layout; that lives in [ARCHITECTURE-2026-07-09.md](ARCHITECTURE-2026-07-09.md)
(close-to-canonical, but predates this engine and is not depended on here). Reconciling the
two — and the CLAUDE.md "Sources of truth" pointer — is a tracked follow-up (see *Open
reconciliation* at the end).

**Read against:** [SEARCH-SPACE.md](SEARCH-SPACE.md) (the capability control surface — every
capability below must map to a row there), [ONTOLOGY.md](ONTOLOGY.md) (the primitive floor),
[MACHINERY.md](MACHINERY.md) (mechanisms), [MACHINERY-STRATEGY-2026-07-07.md](MACHINERY-STRATEGY-2026-07-07.md)
(build vs. adopt vs. defer).

---

## 1. The one idea

Program search is **one operation**, applied recursively:

> Enumerate well-typed terms of type `T` in a **scope** Γ (typed bound variables), bottom-up,
> deduplicated by **observational equivalence** over a set of **contexts**, ranked by **cost**,
> guided toward a **target** signature.

This is the typing judgment **`Γ ⊢ ? : T`** turned into an enumerator. *Every* capability is a
specialization of it — closed programs, `build_grid` bodies, lambda synthesis, higher-order
fill — so there is exactly **one engine**, not a zoo of bespoke searches.

| Capability | = enumerate `T` in scope Γ, contexts = … |
| --- | --- |
| Closed program | `T` = task output type, Γ = ∅, contexts = training inputs |
| `build_grid` body | `T` = COLOR, Γ = {`$col`:INT, `$row`:INT}, contexts = output **cells** |
| `map`/`fold` function arg | `T` = element-out, Γ = {`$x`:element-in}, contexts = sampled elements |
| Lambda synthesis | *is* "enumerate a body in an extended scope, then wrap in `Lam`" |
| Higher-order fill | arrow-typed hole → fill from a **function pool** (`PrimRef`s + synthesized lambdas) |

The engine is therefore **recursive**: filling a function hole by lambda synthesis is a
recursive call to the same enumerator with an extended scope. `build_grid` is not special-cased —
it **dissolves** into "a higher-order primitive whose function argument is synthesized."

**Design rule (anti-compromise).** Every capability defaults to its cheapest setting;
expressiveness is opt-in per run. A switch set to *off* (`fill=none`, `monomorphize`) is a
**valid configuration the architecture supports**, never a stub to be re-architected. The engine
is the full recursive judgment-based enumerator from day one; capabilities light up behind their
switches without reshaping anything. The type-system layer that some capabilities need (parametric
containers, arrow-typed holes; §13) is designed and built *with* the engine, not after it — one
architecture, one build, full SEARCH-SPACE.md coverage.

---

## 2. The data model

A configured search is four independent axes:

```
Search = library × engine × constraints × cost
```

- **`library`** — the vocabulary (bag of typed `Primitive`s, given + invented). The Table-A
  control surface of SEARCH-SPACE.md. A slice of the full `Library`.
- **`engine`** — reusable machinery: the recursive enumerator + its capability **policies** +
  budget. A sum type (`BottomUpSearchEngine`, `BeamBottomUpSearchEngine`, …); direction is
  intrinsic to the subclass.
- **`constraints`** — the *filter*: a tuple of `Constraint`, conjoined (AND). `ConsistentWithTraining`
  is the load-bearing one, but it is applied as the **goal test**, not a per-candidate frontier
  prune (see §5).
- **`cost`** — the *rank*: a single `Cost` (compose via a `LexicographicCost`/`WeightedCost`, never
  a bare tuple — cost has no unambiguous combinator).

The **bundle** (the content-hashable run identity) is `Config`, not a separate class. The engine
is reusable machinery; `constraints`/`cost` are passed *into* `engine.run(...)` as data — values
down, never callbacks up. This keeps an engine reusable across ablations (vary cost, hold engine
fixed).

### Components

- **`SearchEngine`** (`search_engine.py`) — frozen dataclass; capability policies + budget as
  fields; `run(*, task, library, constraints, cost) -> SearchResult` is the entry point (the
  `scope=∅, contexts=training-inputs` instantiation of the recursive core).
- **`Pool`** (`pool.py`) — mutable engine scratch (never hashed, never a frozen field). Keyed
  `type → signature → (cheapest program, cost)`. Dumb typed store: knows nothing of "output" or
  "consistency". Surface: `add_dedup`, `of_type`, `items_of_type`, `cheapest`, `ranked`, `size`.
- **`SearchResult` / `SearchStats`** (`search_result.py`) — ranked programs + a frozen tally
  (`considered`, `accepted`, `extra`). Stats are a *byproduct* collected at the decision points
  during the run, then frozen — never reconstructed from output (search effort is invisible from
  the result alone).
- **`Signature`** (`signature.py`) — `tuple[Value | Bottom, ...]` over an ordered **context** list —
  **partial**: an element is `⊥` where the program errors on that context. Partial programs stay in
  the pool (they are the branch scaffolding `if` needs; §5). Plus `signature_matches_type` (the
  runtime type check).

---

## 3. The binding model — `scope` vs. `env`, De Bruijn

The substrate ([substrate/program.py](src/arc_lab/solvers/program_search/substrate/program.py))
already provides the right foundation: **two separate binding channels** on `evaluate(grid,
library, env, scope)`.

- **`scope`** — lambda-bound variables. `Var($i)` reads `scope[-1 - index]`; `Lam` pushes one
  value per application (per cell, for `build_grid`). A runtime *stack*.
- **`env`** — abstraction arguments. `Param(#j)` reads `env[index]`, fixed once per abstraction
  *call*.

Mapping to the engine:

- The enumeration **`Scope` (Γ)** is the *static shadow* of the runtime `scope` channel — the list
  of *types* of the variables that will occupy the `scope` stack at eval time. Enumerating open
  terms = emitting `Var`s valid in Γ; the **contexts** supply the runtime `scope` values.
- **`env`/`Param` is a different axis** — abstraction / `parameterize`, realized in `learn/` (§14). Forward
  search leaves `env = ()`. The two channels stay separate so a searched `build_grid` body (uses
  `scope`) can become a learned abstraction (uses `env`) with no aliasing.

**De Bruijn indices** (`Var(index)`, nameless, counting binder-nesting) are the best-practice
choice for an enumerator:

1. **α-equivalence is structural equality** — `λx.x` and `λy.y` are the *same* term; the engine
   cannot waste dedup on renamings.
2. **No variable capture** when composing subterms.
3. **Legal `Var`s at a point = the index range `0..len(Γ)-1`** — trivial to enforce.

**Gotcha:** indices are relative to binder depth. An *open* subterm valid in scope Γ needs a shift
(`↑`, +1 per inserted binder) to be reused one binder deeper. **Policy:** pool-per-scope; share
only *closed* subterms across scopes (no free `Var`s → no shift), enumerate the open part fresh
per scope. ARC binders are shallow (≤2), so this is correct and cheap; `↑` stays available as the
general tool.

---

## 4. The recursive contract

```python
_enumerate(
    goal_type: Type,                 # the type we ultimately want out (derived from the task, NOT hardcoded GRID)
    scope: Scope,                    # Γ; () at top level, extended under binders
    contexts: tuple[Context, ...],   # observational-equivalence sample points
    target: Signature | None,        # desired signature over `contexts` (example propagation); None ⇒ no early-exit
    budget: Budget,                  # shrinks on recursion ⇒ termination guarantee
) -> Pool                            # the full typed pool for (scope, contexts); goal_type programs extracted by caller
```

Supporting types:

- **`Scope`** — an ordered tuple of typed De Bruijn binders. `Scope(())` at top level.
- **`Context`** — `(input_grid, scope_binding)`. Top level: `(ex.input, ())`. A `build_grid` cell:
  `(input, (col, row))`. (`env` binding omitted for forward search; addable later without rework.)
- **`Signature`** — `tuple[Value | ⊥, ...]`, one entry per context (the program's behavior), `⊥`
  where it errors on that context. **Partial** signatures are first-class — they are what makes
  domain-splitting `if` work (§5); a *solution* is a `goal_type` program whose signature is **total
  and equals `target`**.
- **`Budget`** — the decreasing resource (depth remaining + pool cap). Must strictly shrink on
  each recursive call, or lambda-synthesis recursion is not guaranteed to terminate.

**Top-level instantiation** (`SearchEngine.run`):

```python
goal_type = task.output_type                       # GRID for ARC; the engine does not assume it
contexts  = tuple((ex.input, ()) for ex in task.train)
target    = tuple(ex.output for ex in task.train)  # example propagation starts here
pool      = self._enumerate(goal_type, Scope(()), contexts, target, self.budget)
solutions = [p for sig, p, _ in pool.items_of_type(goal_type)
             if sig == target and all(c.holds(p, task, library) for c in extra_constraints)]
return SearchResult(ranked_programs=sorted_by_cost(solutions), stats=…)
```

The goal test (`sig == target`, using cached signatures) is the *same operation* that runs inside
`_enumerate` as early-exit — not a separate top-level-only step. `extra_constraints` are the
non-consistency filters (consistency *is* `sig == target`).

---

## 5. The enumeration algorithm (`_enumerate`)

Bottom-up rounds until `budget` is exhausted or `target` is hit at `goal_type`:

1. **Seed leaves** (round 0):
   - `Input()` (typed by the input grid).
   - **Bound variables**: one `Var(i)` for each entry of Γ (open-term leaves).
   - **Constants**: minted by the `ConstantSource` policies (§7).
2. **Compose** (each round): for every non-variadic primitive, `candidate_applications` unifies its
   (polymorphic) signature against pooled arguments and yields `(program, instantiated_result_type)`.
   The **type flows out of composition** — never recomputed on the finished program.
3. **Higher-order fill**: for a function-typed argument hole, draw from the **function pool** per the
   `FunctionHoleFill` policy:
   - `point-free` → `PrimRef`s from the library.
   - `lambda-synthesis` → recursively `_enumerate(body_type, scope + params, body_contexts, body_target, budget−)`,
     wrap results in `Lam`. `body_contexts`/`body_target` come from the enclosing HO primitive (§8).
   - **Typed guidance via arrow holes** — function holes carry precise `ArrowType`s (§13.2), so each
     function-pool candidate's arrow type is unified against the hole as a pruning signal, and the
     expected body signature (e.g. `(INT,INT)→COLOR` for `build_grid`) is read off the hole. `FN`
     remains only for genuinely opaque function values.
4. **Evaluate → partial signature**: `_signature(program, contexts, library)` maps `evaluate` over
   contexts (binding `scope`), placing `⊥` at any context that errors. It returns `None` **only** if
   the program errors on *every* context (fully undefined) — a program that errors on *some* contexts
   keeps a partial signature and stays in the pool.
5. **Prune (intrinsic-local only)**: `_prunes` drops the fully-undefined (`None`) and **type
   mismatches** (`not signature_matches_type(defined-part, vtype)`). It does **not** drop *partial*
   programs — they are the branch scaffolding for `if` — and it does **not** apply
   `ConsistentWithTraining`: pruning intermediates by consistency would discard the scaffolding and
   collapse search to depth 1.
   - **Branching / partial signatures.** `if(cond, t, e)` composes two *partial* branches into a
     signature that is defined wherever the selected branch is defined; the result is a *solution*
     iff it is **total and equals `target`**. This is what lets a branch that errors outside its
     selected domain (an out-of-bounds `read`) still be used — the domain-splitting power of `if`,
     which eager whole-signature pruning would destroy. Obs-equiv dedup (step 6) keys on the partial
     signature, `⊥` included.
6. **Dedup**: `pool.add_dedup(vtype, sig, program, cost.evaluate(program))` — one cheapest
   representative per `(type, signature)`. Cost is evaluated **once**, here, and cached; frontier
   and ranking read the cached number.
7. **Frontier select** (`_select_frontier`, the overridable policy): `BottomUp` keeps the cheapest
   `max_pool`; `Beam` keeps the cheapest `beam_width`. Type-aware refinements (don't starve
   low-cardinality value types) live here.
8. **Early exit**: if a `goal_type` program's signature equals `target`, stop.

Consistency is the **goal**, not a frontier filter. Cost is a per-program score consumed set-wise
(dedup tie-break, frontier truncation, final rank); it is evaluated once and cached.

---

## 6. Capability policies

The SEARCH-SPACE.md Table-B switches, as injected strategy objects on the engine, **dormant until
summoned**, defaulting cheap:

- **`FunctionHoleFill`** — `none | point-free | lambda-synthesis`. Governs step 3.
- **`PolymorphismInstantiation`** — `monomorphize | bounded | unrestricted`. Governs how far `unify`
  grounds type variables in step 2.
- **`ConstantSource`s** — a tuple (sources *union* cleanly): `finite-enumerate | harvest-from-instance |
  functionally-derive | parameterize`. Governs constant leaves in step 1.

A policy consulted where it applies, ignored where it doesn't (an `Analytic` engine has no function
holes; a monomorphic bag makes `PolymorphismInstantiation` a no-op). This is what lets the closed-term
case run at full speed with everything off.

---

## 7. Higher-order primitives & body sampling

To dedup a function body you must know **what arguments it runs on**. There is a complete baseline for
this and an accelerator on top of it (§8, §13.4) — every higher-order primitive is handled by at least
the baseline, so none is a special case or a hard case:

- **Baseline (always):** a function of type `(P…)→R` is sampled on argument tuples drawn from the
  pool's own values at types `P…`. Complete for every HO primitive, including `fold`.
- **Propagation (optional accelerator):** a HO primitive may supply a `body_sampler` (§13.3) that
  derives precise `(contexts, target)` from the task — `build_grid` (dims → cells → output colors),
  `map` (list elements → output elements). Where available it prunes hard; where not (`fold`, whose
  accumulator is latent) the baseline carries it.

## 8. Function values

Function-typed programs (`PrimRef`, synthesized `Lam`) are first-class pool entries, deduped by a
**behavioral signature over sampled arguments**:

- **`point-free` fill** — `PrimRef`s from the library, arrow-unified against the hole (§13.2).
- **`lambda-synthesis` fill** — recursively `_enumerate` a `Lam` body: with a propagated `target`
  when the enclosing primitive supplies one (§7), otherwise against baseline pool-drawn samples (§13.4).

Both paths are correct; propagation only changes *how many* candidates the pool holds, never *whether*
the right function is reachable.

## 9. Memoization

Recursive sub-searches recur; cache pools by **`(scope, contexts, target)`** — not `scope` alone,
since different sample/target sets are different sub-problems.

---

## 10. SEARCH-SPACE.md capability → home (full coverage)

Every capability is designed, and every one lives in a definite **layer** of the build — `library`
(the bag), `engine` (§4–§9), `type-system` (§13), or `learn/` (the wake–sleep loop). "Layer" is
*where it is built*, not *whether* it is — all four layers are ours to build.

| Capability | SEARCH-SPACE | Layer | Design |
| --- | --- | --- | --- |
| Data nouns: Grid · Int · Color · Bool | A | library | `TypeCon` base types |
| Data nouns: List[·] · Pair[·] | A | type-system | parametric `TypeCon` (§13.1) |
| Boolean predicates · Arithmetic · Comparison | A | library | primitives + generic compose |
| Branching (`if`), total **and** partial/domain-split | A | engine | partial signatures (§5) |
| Higher-order **primitives** (`map`/`fold`/`filter`/…) | A | type-system + library | parametric types (§13.1) + arrow params (§13.2) |
| Object noun + on/off-ramp (`segment`/`render`) | A | type-system + library | `Object` `TypeCon` + ramp primitives (§13.5) |
| Type discipline (mono/poly bag) | A | library | which primitives admitted |
| Higher-order **fill mode** | B | engine | `FunctionHoleFill` (§6); arrow-guided via §13.2 |
| Lambda synthesis | B | engine | recursive `_enumerate` (§5.3) + `body_sampler` (§13.3) |
| Polymorphism **instantiation** switch | B | engine | `PolymorphismInstantiation` policy (§6) |
| Constant policy (finite / harvest / derive) | B | engine | `ConstantSource`s (§6) |
| Constant policy (`parameterize`) | B | learn/ | lifts a constant to a `Param` — realized in the wake–sleep loop (§14) |
| Higher-order / recursive **invention**, MDL governance | B | learn/ | the wake–sleep loop over the engine |

**Reading this:** nothing is blocked and nothing is deferred. Some capabilities are built in the
`engine` layer (partial-branch `if`, lambda synthesis, the policy switches), some in the `type-system`
layer (containers, arrow holes, the Object pathway), some in `library` (the primitives), and the
*invention* rows in `learn/`. All four layers are part of what we build; the column says which file
the code lands in, not whether the capability exists.

---

## 11. Best-practice lineage

A **type-and-scope-directed, observational-equivalence bottom-up enumerator with example
propagation into binders** — the synthesis of:

- **EUSolver** — observational-equivalence reduction (the core pruning).
- **λ² / Myth** — type-directed enumeration + example propagation through binders.
- **DreamCoder / Crossbeam** — first-class function values, learned library, sampling-based dedup.

Ten practices, all reflected above: De Bruijn (§3); the `Γ ⊢ ? : T` judgment (§4); obs-equiv
reduction (§5.6); example propagation into binders (§4 `target`, §7); two binding channels (§3);
polymorphism via fresh-instantiation + unification (§5.2, §6); function values by sampling (§8);
memoization by `(Γ, contexts, target)` (§9); cost-bounded frontier / iterative deepening (§5.7);
capabilities as cheap-default injected policies (§6).

## 12. Build vs. adopt

We **build** the enumerator and **adopt the algorithms** (§11 is adoption of ideas). We do *not*
adopt an external engine's *implementation* as the search backend, because:

1. The research **is** abstraction *formation* over this substrate — an external enumerator is a
   black box you cannot invent abstractions inside.
2. Term-representation impedance: the typed `Program` (De Bruijn, two binding channels, `Param`/`env`)
   has no lossless bijection to an external term language that models neither.
3. Determinism: the regression locks require RNG-free reproducible search; many engines / SMT
   backends are not.
4. Instrumentation: the speedup metric reads `considered` (search effort); a black box hides it.
5. Dependencies: external toolchains vs. the clean `uv`/Python stack.

This is **not binary** — per-component adoption stays open (e.g. an SMT solver as a future
constraint/verification backend, a unification library). See MACHINERY-STRATEGY for the per-component
build/adopt/defer calls.

---

## 13. Type-system & substrate design

The engine rests on a type system and substrate rich enough for **every** capability. These are
designed and built alongside the engine — one architecture, one build.

### 13.1 Parametric types

Generalize `Type` to `TypeVar | TypeCon | ArrowType`, where **`TypeCon(name, args)`** is an n-ary type
constructor. Base types are the nullary case (`GRID = TypeCon("grid", ())`); containers are parametric
(`List[a] = TypeCon("list", (a,))`, `Pair[a,b] = TypeCon("pair", (a, b))`). `BaseType` folds into
`TypeCon` with `args=()`; the existing `GRID`/`INT`/`COLOR`/`BOOL` constants keep their spellings.

- **`unify`**: `TypeCon(n, xs)` with `TypeCon(m, ys)` succeeds iff `n == m ∧ len(xs) == len(ys)`, then
  unifies `xs`/`ys` pointwise threading the substitution. `TypeVar` binds with occurs-check (recursing
  into `args`). `ArrowType` as today. Mixed constructors fail.
- **`fresh` / `substitute` / occurs-check** recurse into `TypeCon.args` — exactly as they already do
  for `ArrowType.params`.
- **Runtime `Value`** gains `tuple` for lists (element values) and pairs (2-tuples) — **hashable**, so
  they remain valid `Pool` signature keys.
- **`signature_matches_type`** handles `TypeCon`: `list` ⇒ a `tuple` whose every element matches the
  element type; `pair` ⇒ a 2-tuple matching pointwise; recursive.

This makes `map : ((a→b), List[a]) → List[b]`, `fold`, `filter`, `sort_by` typeable — the row the type
system's own docstring already promises.

### 13.2 Arrow-typed higher-order holes

Higher-order primitives type their function argument as a precise `ArrowType`, not opaque `FN`:
`build_grid : (INT, INT, ArrowType((INT, INT), COLOR)) → GRID`. `Lam.result_type` reports a precise
`ArrowType` (param types from its binders, result from its body type). Higher-order fill (§5.3) then
unifies each function-pool candidate's arrow type against the hole's — **the type is the pruning
signal.** `FN` remains only for genuinely heterogeneous/opaque function values.

### 13.3 Function-argument sampling on `Primitive`

`Primitive` gains an optional **`body_sampler(task, sibling_arg_values) → (body_contexts, body_target | None)`**.
When lambda synthesis fills a primitive's function hole, `_enumerate` calls it to obtain the recursive
body search's contexts (and, when derivable, its target — the *propagation* accelerator of §8):

- `build_grid`: read output dims from the training pairs → per-`(input, (col,row))` contexts;
  `body_target =` the output cell colors. Full propagation.
- `map`: evaluate the list argument on the training inputs → per-`(input, element)` contexts;
  `body_target =` the aligned output elements. Full propagation.

`body_target = None` is not a gap — see 13.4.

### 13.4 Function values: complete baseline + propagation optimization

Two paths, **both correct**:

- **Baseline (always available).** A function value of type `(P…) → R` is deduped by its behavioral
  signature over sampled argument tuples drawn from the **pool's own values** at types `P…` (a bounded
  canonical sample). The enclosing HO application is assembled and checked by the normal goal test.
  This is *complete* — it finds any within-depth function.
- **Propagation (when `body_sampler` yields a target).** The body is searched directly for the
  propagated target signature — far fewer candidates.

`fold` (accumulator latent ⇒ no target) uses the **baseline** and is thereby **fully handled**:
correct and complete via the function pool, merely without the propagation accelerator. Propagation is
an optimization layered on a complete baseline — never a correctness crutch, never a capability gate.

### 13.5 Object pathway

`Object` is `TypeCon("object", ())` with a frozen, hashable `Object` value (cells + bbox + color).
`segment : GRID → List[Object]`, `render : List[Object] → GRID`, and object transforms
(`recolor`/`translate`/… `: Object → Object`). With 13.1 this puts `Object` on a typed on-ramp/off-ramp
path from input Grid to output Grid — the connectivity SEARCH-SPACE.md requires.

## 14. Layer boundaries (what lives in `learn/`, not the engine)

Two capabilities are *realized in the wake–sleep loop* rather than the forward search — a placement
decision, not a deferral; `learn/` is built too.

- **`parameterize` constant source** — replacing a concrete constant with a `Param` (`#j`) is
  *proposing an abstraction*: a `Param` has no value until an abstraction binds its `env`, which only
  happens when sleep forms and calls the abstraction. So `parameterize` is implemented where it has
  meaning — the `learn/` loop — and the `ConstantSource` enum carries the value so the engine and loop
  share one vocabulary.
- **Higher-order / recursive invention & MDL governance** — the loop mints new library primitives
  (including recursive ones) and governs them by compression. The engine *consumes* whatever the
  library holds; it does not invent. *Using* a recursive combinator like `fold` is ordinary
  `library` + engine (§7, §13.4); *inventing* recursion is `learn/`.

The `_select_frontier` policy (§5.7) — including type-aware frontiers that protect low-cardinality
value types from truncation — is engine design, built with the engine.

## 15. Open reconciliation

- CLAUDE.md "Sources of truth" points to `ARCHITECTURE.md` for the run/config/corpus model; that
  content now lives in [ARCHITECTURE-2026-07-09.md](ARCHITECTURE-2026-07-09.md). Decide whether this
  file absorbs the run/config model or the two are cross-referenced siblings, then fix the pointer.
- `Config` as the search bundle (§2) must be reconciled with the existing `Config`/`RunSpec` and the
  known "dead constraint/cost injection" debt — this engine is what makes that injection live.
