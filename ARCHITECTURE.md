# ARCHITECTURE.md — the program-search engine

The design contract for the **full-capability program-search engine** under `src/arc_lab/solvers/program_search/`. This is the thing we build to; a change that deviates from it updates this file first or is a bug.

**Scope.** This document is the _search engine_ — how programs are proposed, filtered, and ranked (the forward/wake proposer). Two neighbours are **separate specs, written to the same standard**, not covered here: the **`learn/` wake–sleep loop** (invention + MDL governance — §14) and the **run/config/corpus model** ([ARCHITECTURE-2026-07-09.md](ARCHITECTURE-2026-07-09.md), §15). Primitive _semantics_ (what `segment`/`render`/etc. compute) live in [ONTOLOGY.md](ONTOLOGY.md); this spec owns their _types and how search consumes them_.

**Read against:** [SEARCH-SPACE.md](SEARCH-SPACE.md) — every capability here maps to a row there (§10). Also [ONTOLOGY.md](ONTOLOGY.md), [MACHINERY.md](MACHINERY.md), [MACHINERY-STRATEGY-2026-07-07.md](MACHINERY-STRATEGY-2026-07-07.md).

---

## 1. The one idea

Program search is **one operation**, applied recursively:

> Build the pool of well-typed terms in a **scope** Γ, bottom-up, deduplicated by **observational equivalence** over a set of **contexts**, ranked by **cost**, up to a **budget**.

This is the typing judgment **`Γ ⊢ ? : T`** turned into an enumerator. Every capability is a specialization — closed programs, `build_grid` bodies, lambda synthesis, higher-order fill — so there is exactly **one engine**, not a zoo of bespoke searches. The engine is **recursive**: filling a function hole by lambda synthesis is a recursive build in an extended scope.

| Capability | = build the pool in scope Γ, contexts = … |
| --- | --- |
| Closed program | Γ = ∅, contexts = training inputs |
| `build_grid` body | Γ = {`$1`=row:INT, `$0`=col:INT}, contexts = output **cells** |
| `map`/`filter` function arg | Γ = {`$0`=element:…}, contexts = sampled elements |
| `fold` function arg | Γ = {`$1`=acc:…, `$0`=element:…}, contexts = sampled (acc, element) |
| Lambda synthesis | build a body in an extended scope, then wrap in `Lam` |
| Higher-order fill | a function-typed hole drawn from a **function pool** (`PrimRef`s + synthesized `Lam`s) |

**Design rule (anti-compromise, scoped to capabilities).** Every capability defaults to its cheapest setting; expressiveness is opt-in per run. A switch set to _off_ (`fill=none`, `monomorphize`) is a valid configuration the architecture supports — not a stub. No capability in §10 is named-without-a- mechanism; each has a concrete design in §5–§13. (The neighbours in _Scope_ above are separate specs, not deferred capabilities.)

---

## 2. The data model

A configured search is four independent axes:

```
Search = library × engine × constraints × cost
```

- **`library`** — the vocabulary (bag of typed `Primitive`s, given + invented). SEARCH-SPACE.md's Table-A surface; a slice of the full `Library`.
- **`engine`** — reusable machinery: the recursive enumerator, its capability **policies**, and its **budget**. A sum type (`BottomUpSearchEngine`, `BeamBottomUpSearchEngine`, …); direction is intrinsic to the subclass.
- **`constraints`** — the _filter_: a tuple of **extra** `Constraint`s (conjoined, AND), applied at extraction (§5.8). Consistency-with-training is **not** one of them — it is expressed structurally as the `target` signature (`sig == target`), so there is no `ConsistentWithTraining` in the tuple and no double-application. `constraints` is empty by default and carries only inductive-bias filters (e.g. output-shape priors).
- **`cost`** — the _rank_: a single `Cost` (compose via `LexicographicCost`/`WeightedCost`, never a bare tuple).

The content-hashable run identity is `Config` (the bundle), not a separate class; `constraints`/`cost` are passed _into_ the engine as data (values down, never callbacks up), keeping an engine reusable across ablations.

**Blindness seam (agreed, lands with the engine work).** `SearchEngine.run` takes the task's **train examples only** (`run(*, train_examples, library, constraints, cost)`), not the full `Task` — blindness to test examples is structural (a type), not a promise. `Cost.of` takes the same `train_examples`; `task_id` for logging comes from the caller. See [EXECUTION.md](EXECUTION.md).

**Components.** `SearchEngine` (`search_engine.py`, frozen dataclass; policies + budget + the `run(...) → SearchResult` entry) · `Pool` (`pool.py`, mutable engine scratch, never hashed; keyed `type → signature → (cheapest program, cost)`) · `SearchResult`/`SearchStats` (`search_result.py`, ranked programs + a frozen byproduct tally) · `Signature` (`signature.py`, §4).

---

## 3. The binding model — `scope` vs. `env`, De Bruijn

The substrate ([substrate/program.py](src/arc_lab/solvers/program_search/substrate/program.py)) has **two separate binding channels** on `evaluate(grid, library, env, scope)`:

- **`scope`** — lambda-bound variables. `Var($i)` reads `scope[-1 - index]`; `Lam` pushes one value per application. A runtime stack.
- **`env`** — abstraction arguments. `Param(#j)` reads `env[index]`, fixed per abstraction _call_.

Mapping to the engine:

- The enumeration **`Scope` (Γ)** is the static shadow of the runtime `scope` channel — the _types_ of the variables that will occupy the stack. Enumerating open terms = emitting `Var`s valid in Γ; the **contexts** supply the runtime `scope` values.
- **`env`/`Param` is a different axis** — abstraction / `parameterize`, realized in `learn/` (§14). Forward search leaves `env = ()`. The channels stay separate so a searched `build_grid` body (uses `scope`) can become a learned abstraction (uses `env`) without aliasing.

**De Bruijn** (`Var(index)`, nameless, counting binder-nesting) is the best-practice choice: α-equivalence is structural equality (no wasted dedup on renamings), no variable capture, and the legal `Var`s at a point are exactly `0..len(Γ)-1`. **Gotcha:** indices are relative to binder depth, so an _open_ subterm is valid only at its depth. **Pool-per-scope protocol:** each pool is identified by its `(scope, contexts, budget)` memo key (§9). A **closed** subterm (no free `Var`) is scope-independent — its signature ignores `scope_binding` — so it may be reused across scopes without rewriting; an **open** subterm (containing a `Var`) is enumerated _fresh_ per scope, never imported (its De Bruijn indices are depth-relative). No cross-scope key rewriting is performed beyond the optional `↑`/shift, which is not used in the default path (ARC binders are shallow, so fresh open-enumeration is cheap).

**Scope ordering (authoritative).** `build_grid`'s function is _curried_ `Lam(Lam(body))`, applied row-then-column, so the body sees **`$1` = row, `$0` = col** ([build.py](src/arc_lab/solvers/program_search/substrate/primitives/build.py)). The runtime scope tuple is therefore **`(row, col)`** (row pushed first/outer, col on top). Every `Context` and `body_sampler` below uses `(row, col)`.

---

## 4. The core contract

`_enumerate` is a **full-pool builder**. It does _not_ take a goal type or a target and does _not_ early-exit — that keeps its result a pure function of its inputs, hence soundly memoizable (§9). Goal-directed extraction (§5.8) is a separate, thin step the caller runs against the returned pool.

```python
_enumerate(
    scope: Scope,                     # Γ; () at top level, extended under binders
    contexts: tuple[Context, ...],    # observational-equivalence sample points
    budget: Budget,                   # depth + arity + pool caps; shrinks on recursion ⇒ terminates
) -> Pool                             # the full typed pool for (scope, contexts) up to budget
```

Supporting types:

- **`Scope`** — an ordered tuple of typed De Bruijn binders. `Scope(())` at top level.
- **`Context`** — `(input_grid, scope_binding)`, where `scope_binding` is a tuple of `Value`s matching Γ. Top level: `(ex.input, ())`. A `build_grid` cell: `(input, (row, col))`. This one type is used everywhere a program is evaluated — including function-value sampling (§8), so a lambda body that reads `Input()` still has its grid.
- **`Signature`** — `tuple[Key | ⊥, ...]`, one entry per context. **Partial**: `⊥` (a singleton sentinel) marks a context where the program errors. `⊥ == ⊥` (identity) so partial behaviours dedup correctly; `⊥ ≠ k` for any concrete key `k`, so a partial program never matches a concrete target. Entries are **canonical value-keys, not raw runtime objects** — the `Value → Key` map that makes observational equivalence deterministic and hashable: scalars (`int`/`bool`) key as themselves; a `Grid` by its frozen content (already hashable); `list`/`pair` recursively as tuples of element keys; and a **function value by its behavioural fingerprint** — its own sampled signature (§8) for a synthesized `Lam`/`Closure`, or the primitive name for a `PrimRef` — **never** closure identity. This is the single rule behind both top-level dedup and §8's function-value dedup; the target is the key-tuple of the training outputs.
- **`Budget`** — `(max_depth, max_arity, max_pool, max_type_nodes)`. **Decrement rule:** descending into a lambda body consumes **exactly 1** from `max_depth`; peeling the N curried binders of one arrow hole is a _single_ descent (1, not N), since the body sits one level below the application. `max_depth` therefore strictly decreases on every recursion and reaches 0 in finite steps — the sole termination guarantee for lambda synthesis. `max_arity` (variadic bound, §5.2), `max_pool` (frontier cap, §5.7), and `max_type_nodes` (universe bound, §6.2) are caps that need not shrink.

**Top-level driver** (`SearchEngine.run`):

```python
contexts  = tuple((ex.input, ()) for ex in task.train)
pool      = self._enumerate(Scope(()), contexts, self.budget)
target    = tuple(ex.output for ex in task.train)          # a total Signature
goal_type = task.output_type                               # GRID for ARC; not assumed by the engine
solutions = extract(pool, goal_type, target, self.constraints, task, library)   # §5.8
return SearchResult(ranked_programs=solutions, stats=…)
```

`goal_type` and `target` are **extraction** inputs, not enumeration inputs — the resolution of the full-pool-vs-early-exit tension. Optional early termination is _iterative deepening at the driver_: call `_enumerate` with increasing `max_depth`, extracting after each; the §9 cache makes the shared prefix free.

---

## 5. The enumeration algorithm

`_enumerate` runs bottom-up rounds up to `budget.max_depth`. Signatures are partial throughout.

### 5.1 Seed leaves (round 0)

- `Input()`.
- **Bound variables**: one `Var(i)` for each entry of Γ (the open-term leaves).
- **Constants**: minted by the `ConstantSource` policies (§6.3).

### 5.2 Compose (each round)

For every library primitive, generate well-typed applications; the **type flows out of composition** (never recomputed on the finished program), so each pooled entry carries its instantiated type.

- **First-order:** instantiate the primitive's signature with fresh type vars (`instantiate`), `unify` each parameter against a pooled argument's type threading the `Substitution`, and read the instantiated result type via `apply_subst`. (These are the real [types.py](src/arc_lab/solvers/program_search/substrate/types.py) names — §11 uses them, not `fresh`/`substitute`.)
- **Variadic primitives** (`overlay`, `tile`; `Primitive.is_variadic`): enumerate applications at each arity `k = 1 … budget.max_arity`, drawing the `k` variadic arguments from the pool at the required type. Costed and deduped like any candidate; `max_arity` bounds the blow-up.
- **Polymorphism** of any remaining free type var in a result is governed by the `PolymorphismInstantiation` policy (§6.2).
- **Higher-order** (a function-typed parameter): §5.3.
- **Branching** (`If`): §5.4.

### 5.3 Higher-order fill

For a function-typed parameter hole of type `H`, draw from the **function pool** per the `FunctionHoleFill` policy (§6.1):

- `point-free` → `PrimRef`s whose (pool-known) arrow type `unify`s with `H`. Arity/currying mismatches simply fail to unify and are excluded — e.g. an uncurried `(INT,INT)→COLOR` primitive does _not_ unify with `build_grid`'s curried hole `INT→(INT→COLOR)`, which is also what the runtime requires (`build_grid` rejects a non-`Closure`, §11.2). So the type is the single gate; no runtime surprise.
- `lambda-synthesis` → peel `H` one binder at a time: for `H = ArrowType((p,), R)`, extend the scope by `p` and fill `R`; if `R` is itself an arrow this recurses, producing **nested `Lam(Lam(…))`** for a curried hole (build_grid's two coordinates → `Lam(Lam(body:COLOR))`). At the innermost non-arrow `R₀`, `_enumerate(Γ + peeled-binders, body_contexts, budget with max_depth−1)` — one decrement for the whole curried peel, per §4 — and extract bodies of type `R₀`. The synthesized `Lam`'s arrow type is known to the enumerator at construction (from the peeled binders and `R₀`) and stored as its pool type — **no reliance on `Lam.result_type`** (§11.2). `body_contexts` come from the enclosing primitive's `body_sampler` (§7); with propagation they carry a `body_target` used to extract just the matching body, otherwise the baseline returns all typed bodies (§8).

### 5.4 Branching (short-circuit `If`)

Branching stays **summoned by the vocabulary** (SEARCH-SPACE.md Table A): the enumerator emits `If` **iff the library carries the `if` branching entry** — a capability token typed `(BOOL, a, a) → a` whose presence enables branching and whose type carries its shape. Drop it from the bag and branching turns off, exactly as Table A requires (independently of the predicate row). What the entry does _not_ do is evaluate eagerly: composition emits a **dedicated short-circuit AST node** `If(cond, then, else)` (§11.3), _not_ an eager `Apply` — required for correctness, since an eager `if` would evaluate the unselected branch and a branch that errors outside its selected domain would poison both enumeration _and the final solution on test inputs_. So the `if` bag entry is the _summoner_; the `If` node is the _mechanism_.

The enumerator composes `If` (when enabled) from a pooled `BOOL` program and two pooled same-typed programs. Its signature at context `i` is `⊥` if `cond[i]` is `⊥`, else `then[i]` if `cond[i]` else `else[i]` — computed by **combining the cached branch signatures** (no re-evaluation), which is inherently short-circuit: only the selected branch's cached value is read. This is what makes **domain-splitting `if`** work: a branch that is `⊥` outside its selected region still contributes.

### 5.5 Evaluate → partial signature

`_signature(program, contexts, library)` maps `evaluate` over contexts (binding `scope`), placing `⊥` at any context that raises. It returns `None` **only** if the program errors on _every_ context (fully undefined). A program erring on _some_ contexts keeps a partial signature and stays pooled. (For `If`, the signature is combined per §5.4 rather than re-evaluated.)

### 5.6 Prune (intrinsic-local only)

`_prunes` drops the fully-undefined (`None`) and **type mismatches** (`not signature_matches_type(defined-part, vtype)`). It does **not** drop partial programs (they are branch scaffolding), and it does **not** apply consistency-with-training (there is no such `Constraint` — deleted; consistency is the goal test, §5.8); pruning intermediates by it would collapse search to depth 1.

### 5.7 Dedup + frontier

`pool.add_dedup(vtype, sig, program, cost.evaluate(program))` keeps one cheapest representative per `(type, signature)`. **Cost is evaluated once, here, and cached**; dedup tie-break, frontier, and rank all read the cached number. After each round, `_select_frontier` truncates: `BottomUp` keeps the cheapest `budget.max_pool`; `Beam` keeps `beam_width`. `_select_frontier` may be type-aware (protect low-cardinality value types from truncation) — an engine policy, built with the engine.

### 5.8 Extraction (the goal test)

Against the returned pool, keeping the **cached cost** threaded through (never re-evaluated). A polymorphic pooled entry (present only under `unrestricted`, §6.2) is first `instantiate`d and `unify`d against `goal_type`; entries that don't unify are skipped. Then `extract(pool, goal_type, target, constraints, …)` = `[e.program for e in sorted((e for e in pool.items_of_type(goal_type)   if unifies(e, goal_type) and e.sig == target and all(c.holds(e.program, …) for c in constraints)),   key=lambda e: (e.cost, e.program.size(), e.program.to_dict()))]`. Sorting by an explicit `key` — cost, then `size`, then the substrate's canonical `to_dict` serialization (a total, deterministic order) — never compares `Program`s directly, so cost ties can't raise and the result is implementation-independent. The cost comes straight from `items_of_type` (a `Pool` method, §2 Components) and was cached once in §5.7 — no re-evaluation. Because `target` is a total signature and `⊥ ≠ v`, `sig == target` implicitly requires the program to be total on the training contexts — no separate totality check. Consistency-with-training _is_ `sig == target` and is **not** an entry in `constraints` (§2); `constraints` holds only the _extra_ filters applied to the survivors.

---

## 6. Capability policies (fully designed)

The SEARCH-SPACE.md Table-B switches, as injected strategies on the engine, dormant-until-summoned, defaulting cheap.

### 6.1 `FunctionHoleFill` — `none | point-free | lambda-synthesis`

Governs §5.3. `none`: function holes unfilled (no HO composition). `point-free`: `PrimRef`s only. `lambda-synthesis`: `PrimRef`s + recursively-synthesized `Lam`s.

### 6.2 `PolymorphismInstantiation` — `monomorphize | bounded | unrestricted`

After §5.2 unifies a primitive's fresh signature against concrete pooled arguments, some result type may still contain a free type var. The policy governs that residue:

- `monomorphize`: **reject** any candidate whose result type still has a free var (concrete-only pool).
- `bounded`: instantiate each free var over the **task-reachable monotype universe** `U`, built deterministically: **seed** `U₀` with the monotypes among library primitive return/param types; **close** — repeatedly form `TypeCon(name, args)` for each constructor `name` present in the library (`list`, `pair`, `arrow`, …) with `args` drawn from `U` (so nesting like `list[list[int]]` is included); **bound** by type-node count `≤ budget.max_type_nodes`; **order** the result by `(node_count, name, args)` and de-duplicate, so enumeration is deterministic. Instantiate each free var over `U` in that order.
- `unrestricted`: keep the free var in the pooled result type (a polymorphic entry). **Pool keying:** the type key is the polytype **canonicalized** — type vars renamed in first-occurrence order (`t0`, `t1`, …) so α-equivalent polytypes (`a→a` and `b→b`) share one key; the signature key is unchanged. On consumption the entry is `instantiate`d with fresh vars and `unify`d against the demanded type, as in §5.2. (The engine's default is `monomorphize`, which never creates such entries.)

### 6.3 `ConstantSource`s — a tuple (sources union; a constant reached by several is deduped by its

signature in §5.7, so no precedence rule is needed)

- `finite-enumerate`: emit a fixed, typed, bounded set — `INT`: `0 … max grid dimension`; `COLOR`: `0 … 9`; `BOOL`: `{False, True}`.
- `harvest-from-instance`: emit the constants _present in the task_ — colors occurring in train inputs/outputs, and their dimensions.
- `functionally-derive`: emit constants computed from the instance by designated perceiver primitives applied to `Input()` (e.g. `width`/`height`, most-common-color) — i.e. non-literal constants that are functions of the input.
- `parameterize`: **realized in `learn/`, not the engine** (§14). Replacing a constant with a `Param` only has meaning when an abstraction binds its `env`, which happens in sleep. The enum carries the value so engine and loop share one vocabulary; the engine's leaf generation treats it as a no-op.

---

## 7. Higher-order primitives & body sampling

**All** higher-order primitives are handled by the _one_ function-pool mechanism (§5.3, §8) — there is no bespoke per-primitive search. What a primitive optionally adds is a **`body_sampler`** (§11.4): `body_sampler(task, sibling_arg_values) → (body_contexts, body_target | None)`, giving the recursive body search its contexts and (when derivable) its propagation target:

- `build_grid`: read output dims from the training pairs → per-`(input, (row, col))` contexts; `body_target` = the output cell colors. Full propagation.
- `map`: evaluate the list argument on the training inputs → per-`(input, (element,))` contexts; `body_target` = the aligned output elements. Full propagation.
- `filter`: per-`(input, (element,))` contexts; `body_target` = the `BOOL` keep-mask derivable from which elements survive to the output. Propagation when the surviving set is unambiguous, else baseline.
- `sort_by`, `fold`: contexts as above; **`body_target = None`** (the sort key / the accumulator are latent), so the **baseline** (§8) carries them — correct and complete, without the accelerator.

`body_target = None` is never a capability gap — see §8.

---

## 8. Function values: complete baseline + propagation optimization

Function-typed programs (`PrimRef`, synthesized `Lam`) are first-class pool entries, deduped by a behavioral signature over **`Context`s** (§4) — each pairs a training input grid with a sampled `scope_binding`, so input-dependent bodies are handled. Two paths, **both correct**:

- **Baseline (always available).** A function of type `(P…) → R` is sampled on `Context`s built from each training input paired with argument tuples at types `P…`, and the enclosing HO application is assembled and checked by the normal goal test (§5.8). This finds any within-budget function **up to sample adequacy**: obs-equiv dedup over a _bounded_ sample is complete only if the sample separates behaviourally-distinct bodies (the standard Crossbeam/DreamCoder caveat, §12). The sample-adequacy obligation, made explicit: the argument sample for type `Pᵢ` must contain values witnessing every behavioural distinction the correct body depends on. Sources of samples, in priority: (a) the pool's own values at `Pᵢ`; (b) for a **latent** argument type not otherwise in the pool — e.g. `fold`'s accumulator — seed it from the primitive's `body_sampler` (the seed accumulator + a bounded forward unroll on training), since the pool is not guaranteed to hold it. Where adequacy cannot be guaranteed, the search is sound but may miss (never returns a wrong program — the assembled program is always verified by the goal test); this is stated, not hidden.
- **Propagation (when `body_sampler` yields a target).** The body is extracted directly for the propagated `body_target` — far fewer candidates.

Propagation only changes _how many_ candidates the pool holds, never _whether_ the right function is reachable.

---

## 9. Memoization

Recursive sub-searches recur, so memoize. Because `_enumerate` (§4) is a pure function of its inputs, the sound key is exactly **`(scope, contexts, budget)`** — `contexts` (hashable: grids are frozen, `scope_binding`s are `Value` tuples) fixes how signatures are computed; `budget` fixes depth/arity/pool. `goal_type` and `target` are _not_ in the key — they belong to extraction (§5.8), which the cache never touches.

---

## 10. SEARCH-SPACE.md capability → layer (full coverage)

Every capability is designed, in a definite **layer** of the build: `library` (the bag), `engine` (§4–§9), `type-system`/substrate (§11), or `learn/` (the companion wake–sleep spec, §14). "Layer" is _where it is built_, not _whether_ — all are ours to build; the `learn/` rows are a sibling spec, not this one, and are marked as such rather than claimed here.

| Capability | SEARCH-SPACE | Layer | Design |
| --- | --- | --- | --- |
| Data nouns: Grid · Int · Color · Bool | A | library | `TypeCon` base types |
| Data nouns: List[·] · Pair[·] | A | type-system | parametric `TypeCon` (§11.1) |
| Boolean predicates · Arithmetic · Comparison | A | library | primitives + §5.2 |
| Branching (`if`), total **and** domain-split | A | engine + substrate | short-circuit `If` (§5.4, §11.3) + partial signatures (§4, §5.5) |
| Higher-order **primitives** (`map`/`filter`/`sort_by`/`fold`) | A | type-system + library | parametric types (§11.1) + arrow params (§11.2); consumed uniformly (§7, §8) |
| Variadic primitives (`overlay`/`tile`) | A | engine | bounded-arity composition (§5.2) |
| Object noun + on/off-ramp | A | type-system + library + ONTOLOGY | `Object` `TypeCon` + arrow-typed `segment`/`render` (§11.5); semantics in ONTOLOGY.md |
| Type discipline (mono/poly bag) | A | library | which primitives admitted |
| Higher-order **fill mode** | B | engine | `FunctionHoleFill` (§6.1), arrow-guided (§11.2) |
| Lambda synthesis | B | engine | recursive `_enumerate` (§5.3) + `body_sampler` (§7, §11.4) |
| Polymorphism **instantiation** switch | B | engine | `PolymorphismInstantiation`, 3 procedures (§6.2) |
| Constant policy (finite / harvest / derive) | B | engine | `ConstantSource` algorithms (§6.3) |
| Constant policy (`parameterize`) | B | learn/ | shared enum value; realized in the loop (§6.3, §14) |
| Higher-order / recursive **invention**, MDL governance | B | learn/ | companion spec (§14) — _not claimed by this document_ |

**Reading this:** every Table-A row and every engine-side Table-B row has a concrete mechanism in §4–§9 and §11. The `learn/` rows are a sibling spec at the same standard (§14), explicitly not covered here — the one honest scoping line, not a deferral of a capability this document owns.

---

## 11. Type-system & substrate design

Built _with_ the engine. Uses the real [types.py](src/arc_lab/solvers/program_search/substrate/types.py) API: `unify`, `apply_subst`, `instantiate` (there is no `fresh`/`substitute` at module scope).

**Tag legend.** Each subsection below is either **already in the substrate** (verified present in code) or **[proposed — substrate change]**, which means _the design is complete in that subsection and only the code edit is pending_ — **not** that the capability is under-designed. Representation + algorithm + consumption are given here; field-level naming and serialization are the implementing code's job (the `Program` ABC already mandates `to_dict`/`from_dict`/`evaluate`/`result_type` on every node, so "a node implementing all `Program` operations" commits to those by contract), verified by the code-review pass, not restated here.

### 11.1 Parametric types — **already in the substrate**

This layer exists in [types.py](src/arc_lab/solvers/program_search/substrate/types.py) today; the spec _describes_ it, it is not a proposed change. `Type = TypeCon | ArrowType | TypeVar`; **`TypeCon(name, args)`** is the n-ary constructor with base types as the nullary case (`GRID = TypeCon("grid")`), and `list_type(e) = TypeCon("list", (e,))` / `pair_type(a,b) = TypeCon("pair", (a,b))` are provided. `unify` (names + arities match, then args pointwise), `apply_subst`, and `instantiate` all recurse through `TypeCon.args`; `TypeVar` binds with occurs-check. So `map : ((a→b), List[a]) → List[b]`, `fold`, `filter`, `sort_by` are typeable now.

Two pieces the search layer must confirm/add on top (verify against current code, don't assume):

- Runtime `Value` carries `tuple` for lists (element values) and pairs (2-tuples) — **hashable**, so they remain valid `Pool` signature keys.
- `signature_matches_type` handles `TypeCon("list", …)`/`("pair", …)` recursively (a `list` ⇒ a `tuple` whose elements match the element type; a `pair` ⇒ a pointwise-matching 2-tuple).

### 11.2 Arrow-typed higher-order holes, and how `Lam` is typed — **already in the substrate**

Higher-order primitives type their function argument as a precise `ArrowType`, not opaque `FN`. Because `build_grid`'s function is curried `Lam(Lam(body))` applied row-then-col, its type is `INT → (INT → COLOR)` = `ArrowType((INT,), ArrowType((INT,), COLOR))`, so `build_grid : (INT, INT, ArrowType((INT,), ArrowType((INT,), COLOR))) → GRID` — as typed in [build.py](src/arc_lab/solvers/program_search/substrate/primitives/build.py). Arrow unification is thereby a pruning signal, not just a correctness check.

The engine never calls `Lam.result_type`. Types flow from composition (§5.2) and are stored as pool keys; a synthesized `Lam`'s arrow type is computed by the enumerator at construction from its peeled binders and body type (§5.3). For _self-describing_ programs outside the engine (serialization, viz, `learn/`), the **`Lam` node carries its binder's param type** (`Lam(param_type, body)` — `Lam` is unary, one param type per node; a curried arrow is a nested chain of them, [program.py](src/arc_lab/solvers/program_search/substrate/program.py)), so `result_type` is a well-defined precise arrow — including for the _unused-binder_ case (a bound var absent from the body, whose param type is otherwise unrecoverable). `FN` remains only for genuinely opaque function values.

**Curried vs uncurried, committed once:** all function holes and function values are **curried**. `build_grid : (INT, INT, INT→(INT→COLOR)) → GRID`; its value is `Lam(Lam(body))`, matching the substrate's curried `fn(i)(j)` application and its `Closure`-only runtime check. Point-free fill of a curried hole therefore admits only curried function values (uncurried primitives fail to unify, above); if an uncurried primitive is genuinely wanted at a curried hole, it must be η-expanded into a curried `Lam` by synthesis, not supplied directly.

### 11.3 Short-circuit `If` node — **already in the substrate**

A dedicated AST node `If(cond, then, orelse)` implementing all `Program` operations, whose `evaluate` computes `cond` and then **only the selected branch** (so a program containing `If` is correct on test inputs, not just during search — §5.4). `result_type` = the (unified) branch type; `children` = `(cond, then, orelse)`; round-trips via `to_dict`/`from_dict` ([program.py](src/arc_lab/solvers/program_search/substrate/program.py)). The library keeps an `if` **capability entry** `(BOOL, a, a) → a` as the Table-A summoner (§5.4); the enumerator translates it to `If` nodes rather than eager `Apply`. The old eager `IF` impl in [control.py](src/arc_lab/solvers/program_search/substrate/primitives/control.py) is retired: the entry remains as the token, and its impl raises if anything ever tries to apply it eagerly.

### 11.4 `body_sampler` on `Primitive` — **already in the substrate**

`Primitive` carries an optional `body_sampler(task, sibling_arg_values) → (body_contexts, body_target | None)` (§7) — see [library.py](src/arc_lab/solvers/program_search/substrate/library.py); the substrate stays search-agnostic by returning _raw_ `(grid, scope_binding)` samples the search layer wraps into its `Context`s. Its presence makes higher-order-primitive extensibility real; its absence is the baseline (§8), not a gap. `sibling_arg_values` is in the contract for primitives whose contexts depend on their other arguments (`map`/`filter` sample the evaluated list argument); the engine passes `()` until such a primitive lands.

### 11.5 Object pathway · **[proposed — substrate + ONTOLOGY]**

`Object` is `TypeCon("object", ())` with a frozen, hashable `Object` value (cells + bbox + color). `segment : GRID → List[Object]`, `render : List[Object] → GRID`, and transforms (`recolor`/`translate`/… `: Object → Object`) — arrow/`TypeCon`-typed so they sit on a typed on-ramp/off-ramp path. Their **semantics** (segmentation algorithm, render merge policy, object invariants) are specified in [ONTOLOGY.md](ONTOLOGY.md) — the primitive-floor source of truth — which this section requires be completed there; the engine consumes them through their types.

---

## 12. Best-practice lineage

A **type-and-scope-directed, observational-equivalence bottom-up enumerator with example propagation into binders** — EUSolver (obs-equiv reduction), λ²/Myth (type-directed + example propagation), DreamCoder/Crossbeam (function values, sampling, learned library). All reflected above: De Bruijn (§3); `Γ ⊢ ? : T` (§4); obs-equiv (§5.7); propagation (§7, §8); two binding channels (§3); polymorphism via `instantiate`+`unify` (§5.2, §6.2); function values by sampling (§8); memoization by `(scope, contexts, budget)` (§9); cost-bounded frontier (§5.7); cheap-default policies (§6).

## 13. Build vs. adopt

Build the enumerator; adopt the _algorithms_ (§12). Do not adopt an external engine's _implementation_ as the backend: the research is abstraction _formation over this substrate_ (an external enumerator is a black box you cannot invent inside); the typed `Program` (De Bruijn, two channels, `Param`/`env`) has no lossless bijection to external term languages; the locks require RNG-free determinism; the speedup metric needs `considered`. Not binary — per-component adoption (e.g. an SMT backend for a future constraint, a unification lib) stays open per MACHINERY-STRATEGY.

---

## 14. Layer boundary: the `learn/` companion spec

Two SEARCH-SPACE.md Table-B rows are **realized in the wake–sleep loop**, and get their own spec at this standard (not designed here, and §10 marks them so):

- **Higher-order / recursive invention & MDL governance** — the loop mints new library primitives (including recursive ones, with a termination-safety policy) and governs them by compression. The engine only _consumes_ whatever the library holds; _using_ a recursive combinator like `fold` is ordinary `library` + engine (§7, §8), _inventing_ recursion is the loop.
- **`parameterize`** — lifting a constant to a `Param` is proposing an abstraction (a `Param` has no value until sleep binds its `env`), so it lives in the loop; the `ConstantSource` enum shares the vocabulary (§6.3).

**Deliverable:** a `learn/` architecture spec covering invention representation, the proposal algorithm, recursion admission + termination safety, MDL scoring + acceptance threshold, and how invented primitives re-enter the library under per-run switches. It is required, not optional.

## 15. Open reconciliation

- The run/config/corpus model lives in [ARCHITECTURE-2026-07-09.md](ARCHITECTURE-2026-07-09.md); decide whether this file absorbs it or they are cross-referenced siblings, then fix CLAUDE.md's "Sources of truth" pointer. This is a genuine documentation-integration task (not a capability): the anti-compromise rule in §1 is scoped to _capabilities_, and does not claim this integration is done.
- `Config` as the bundle (§2) must reconcile with the existing `Config`/`RunSpec` and the known "dead constraint/cost injection" debt — this engine is what makes that injection live.
