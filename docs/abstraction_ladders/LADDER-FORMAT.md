# The `.ladder` file format — spec

Normative spec for `.ladder` files: the declarative source format in which a Ladder ([ABSTRACTION-LADDERS-SPEC.md](ABSTRACTION-LADDERS-SPEC.md)) is authored.

A `.ladder` file is the **single source of truth for a ladder's identity**: it drives the `LadderSpec`, the testbed (via taskgen), and every derived artifact. It is hand-authored: no tool rewrites it.

This doc governs the implementation — where code and this spec disagree, this spec wins until deliberately amended.

**Status (2026-07-22): implemented; all 20 ladders migrated; the expression grammar now covers all nine substrate node kinds.** The language lives in `src/arc_lab/program_search/ladders/lang/`, and `ladders/registry/` holds `.ladder` files only. A test locks every ladder's regenerated testbed against its committed one. One known gap sits _below_ the format: `substitute_params` cannot inline a higher-order template whose call site passes a lambda-bound variable (it needs De Bruijn shifting), so that one shape has no `d_raw`.

## 1. Motivation

- **One statement of semantics.** Today each ladder's semantics exist in three places: the registry module's `Program` templates, the taskgen generator's hand-written numpy re-implementation of the same functions, and the committed testbed outputs. Nothing but care keeps them aligned. In the file-driven world, task outputs are computed by _executing the declared solution `Program`_ through the engine's own evaluator — semantics stated once, everything else derived.
- **A write/edit surface.** Nested `Apply(...)` trees are error-prone to author and miserable to review; `mirror_recolor(g: Grid, src: Color, dst: Color) -> Grid = map_color(rot180(g), src, dst)` is neither.
- **A diff surface.** A PR changing a ladder shows a readable structural diff of exactly what changed in the ladder's identity.
- **Source/derived split.** The file holds everything _chosen_; generated artifacts (`spec.md`, testbed, reports) hold everything _derived_. Neither duplicates the other.

## 2. Rules

Rules are numbered per section for referenceability. Where a rule says **delegated**, the format re-enforces nothing — the named existing machinery is the sole authority.

### LEX — file & lexical

- **LEX-1** Encoding: ASCII, LF line endings.
- **LEX-2** `#` starts a comment, anywhere on a line, to end of line; comments are never load-bearing.
- **LEX-3** Blank lines and indentation are insignificant (braces carry structure).
- **LEX-4** One statement per line; a statement continues across lines while brackets are unbalanced.
- **LEX-5** A block opens with `{` at the end of its header line and closes with `}` on its own line.
- **LEX-6** Reserved words: `ladder`, `floor`, `config`, `rung`, `distractor`, `top`, `task`, `heldout`, `use`, `solution`, `train`, `test`, `input`, `true`, `false`.

### STR — file structure

- **STR-1** Filename is `<name>.ladder`.
- **STR-2** `<name>` must equal the `ladder <name>` header.
- **STR-3** `<name>` must be kebab-case: `[a-z0-9]+(-[a-z0-9]+)*`.
- **STR-4** Section order is fixed; nothing else, nothing twice, nothing missing:
  - `ladder <name>` header
  - `config`
  - `floor <library-name>`
  - one or more `rung`
  - zero or more `distractor <label>`
  - `top`

### NAM — naming & scoping

- **NAM-1** Code identifiers (primitive, abstraction, param names) must be valid Python identifiers, not Python keywords, and not reserved words (LEX-6). The one exception is the branching summoner `if`, whose registered name is a keyword: it may be declared as a **floor** primitive (`use if: (Bool, a, a) -> a`) so a conditional ladder can summon it, since it is only ever reached through the `a if c else b` syntax, never spelled as a call. A rung or parameter still may not be named `if`.
- **NAM-2** Task ids match `[a-z0-9][a-z0-9_-]*` and are unique across the whole ladder.
- **NAM-3** A rung's name must be unique among rungs and must not shadow a floor primitive.
- **NAM-4** Template body scope: own params + floor primitives + _strictly earlier_ rungs. No self-reference, no forward reference, no `input`.
- **NAM-5** Solution scope: `input` + floor + rungs up to and including the enclosing rung (for rung tasks) or all rungs (for top tasks).

### FLR — floor

- **FLR-1** The section header carries the Floor library's name: `floor <library-name> { ... }`. It is stated, not derived: a control ladder deliberately shares its parent's floor identity (al9/al11 share al7's, al10/al12 share al2's), and that sharing is what makes their columns comparable.
- **FLR-2** Floor primitives are declared one per line: `use <name>: <signature>`.
- **FLR-3** The Floor must have at least 1 primitive.
- **FLR-4** The Floor must not have duplicate primitive names.
- **FLR-5** Declaration order is significant: it is the `Library` primitive order.
- **FLR-6** `<name>` must resolve in `BASE_PRIMITIVES`.
- **FLR-7** The signature is required.
- **FLR-8** The signature must exactly match the registry's signature for that primitive.
- **FLR-9** Signature grammar: `(T1, T2, ...) -> T`, type names resolving against the substrate's type registry. A trailing `...` on the last parameter marks a variadic primitive (`overlay` is `(Color, Grid...) -> Grid`).

### CFG — config

- **CFG-1** Each line is `dotted.path: value`. Paths and application semantics are exactly those of `execution/overrides.py`.
- **CFG-2** Values are Python-style literals (ints, floats, strings, booleans, lists, `None`).
- **CFG-3** Overrides apply to a single canonical LEARN-shaped base config — the "ladder default" — which is frozen, documented data.
- **CFG-4** `library` is not a settable path (the floor section owns it). Unsetting `learn` is forbidden.
- **CFG-5** Duplicate paths are errors. Unknown paths are errors (**delegated** to the override machinery).
- **CFG-6** Values naming registered components (proposer, engines) use their serde `kind` strings.
- **CFG-7** Paths under the reserved `ladder.` namespace set the LADDER's own settings, not its `Config`'s, and are routed past the override machinery. They live in this block because it is where a reader looks for "how is this ladder set up", but a plain SEARCH run has no rungs, so they are not `Config` fields. One path so far:
  - `ladder.depth_schedule: 'derived' | 'pinned'` (default `derived`) — the budget regime. `derived` gives each oracle-chain level the smallest `depth_limit` that puts what that level must find in reach (`L_j` carries rung `j+1`'s `jump_needs`, `L_k` the top's); `pinned` gives every level `budget.depth_limit`, uniformly. A ladder whose rungs differ in depth generally has NO valid uniform budget, which is what `derived` dissolves; it is also cheaper, since cost is exponential in `depth_limit`. Set `pinned` only where the uniform budget is the ladder's content ([`al10-skippable`](../../src/arc_lab/program_search/ladders/registry/al10-skippable.ladder) is the sole case: budget-induced skippability is a phenomenon derived budgets cannot produce). The resolved schedule is reported in each ladder's `spec.md`.

### RNG — rungs

- **RNG-1** Rung levels are derived from file order: the Nth `rung` block is level N.
- **RNG-2** The first statement of a `rung` block is exactly one definition, the only `=` form: `name(p1: T1, ...) -> T = <expr>`.
- **RNG-3** Param names are unique within a definition. Param index = position in the signature; param type = the annotation.
- **RNG-4** Whether a template is otherwise admissible (unused params, empty param lists, depth, etc.) is **delegated** to `make_abstraction` + `lint()`.
- **RNG-5** After the definition: zero or more task blocks. Minimum counts are **delegated** to `lint()` (`min-2-demos`).

### DST — distractors

- **DST-1** A `distractor <label> { ... }` section holds tasks that sit in the corpus but off the ladder's spine — a control's learnable-but-unused competence (al9's `decoy`, al11's `trap`).
- **DST-2** Its tasks follow the TSK rules; `<label>` becomes their corpus label.
- **DST-3** Their solution scope is the Floor alone: a distractor must not reference a rung.
- **DST-4** A distractor demonstrates nothing — no rung, no `DemonstrationKind`, nothing minted for it. It appears in the corpus and, as a `Distractor`, in the `LadderSpec` (so the lint can tell a primitive only a distractor exercises from dead floor vocabulary).

### TSK — tasks

- **TSK-1** Header is `task <id> {` or `heldout task <id> {`. `heldout` routes the task to the heldout corpus; otherwise train.
- **TSK-2** Field order is fixed: one `solution:`, then >= 1 `train <grid>` lines, then >= 1 `test <grid>` lines.
- **TSK-3** A grid literal is a nested list of int literals, rectangular and non-empty; value-range and shape validation is **delegated** to `Grid.from_list`.
- **TSK-4** Distinctness/variation of a task's examples is **delegated** to `lint()` (`distinct-train-inputs`, `outputs-vary`, `not-identity`, `heldout-distinct`) — properties `taskgen`'s seed generator used to guarantee by construction, and which literal grids no longer do.
- **TSK-5** Top-block tasks follow the same rules; the non-heldout ones become `TopRung.task_ids` + `reference_solutions` (index-aligned); heldout top tasks exist only in the heldout corpus.

### EXP — expression elaboration (text → `Program`)

- **EXP-1** An expression is a subset of Python expressions: application, identifiers, int and boolean literals, conditionals and lambdas — nothing else (no operators, keyword args, attributes, subscripts, comprehensions, or list literals).
- **EXP-2** `f(a, b)` → `Apply("f", (a, b))` when `f` is a library primitive; `f` must resolve per the scope rules (NAM-4/5).
- **EXP-3** `input` → `Input()`.
- **EXP-4** A rung parameter's name → `Param(index, type)` per RNG-3; a lambda binder's name → `Var(index, type)`, De Bruijn, innermost = 0.
- **EXP-5** An int literal (optionally negated: `-1`) → `Const(value, T)` where `T` is the expected type of that argument position; `T` must be `Color` or `Int`. `true` / `false` → `Const(value, Bool)`, lowercase only. A polymorphic or non-scalar position is a load error.
- **EXP-6** Elaboration type-checks and arity-checks every application, unifying each argument's type against the parameter position it fills. (Not delegable: the substrate types programs but does not verify them.) Still **delegated**: `make_abstraction` (a template is closed, with contiguous and consistently-typed param indices) and evaluation (spec DRV-3).
- **EXP-7** `a if c else b` → `If(cond, then, orelse)` — short-circuit, as in Python.
- **EXP-8** A bare primitive name in a position whose expected type is a **function type** → `PrimRef(name)`. Anywhere else it stays an error.
- **EXP-9** `lambda p1, p2: body` → a curried `Lam` chain, one arrow peeled from the expected type per binder. Binder types are never annotated — the function-typed position supplies them. A binder may not shadow a rung parameter or an enclosing binder.
- **EXP-10** `f(a)` where `f` resolves to a **function value** (a parameter, a binder, a lambda, a `PrimRef`) → `AppFn(f, args)`. A curried function is applied one stage at a time, as `f(a)(b)`.
- **EXP-11** The expression grammar covers all nine substrate node kinds. Grid literals inside expressions remain absent (the substrate's `Const` holds `int | bool` only).

### DRV — derivation (computed, never written)

- **DRV-1** Rung levels (RNG-1) and the oracle libraries `L_i` (including their names) are derived; the Floor library's own name is stated (FLR-1).
- **DRV-2** `DemonstrationKind` is derived per task by structural comparison of solution vs the rung's template: solution = template instantiated ⇒ `full_solution`; template a proper subprogram with identical instantiation across the rung's **train** tasks ⇒ `fragment_identical`; else ⇒ `fragment_varying`. Heldout tasks don't vote.
- **DRV-3** Task outputs are derived by executing the declared solution `Program` on each declared input through the engine's own evaluator. Execution failure on any input is a load error.
- **DRV-4** The testbed (task JSONs + manifest, labels = rung names, splits per TSK-1) is generated from the file deterministically: same file ⇒ byte-identical testbed.
- **DRV-5** Everything `lint()`/`render()` computes (depths, double-jumps, fan-in, validity window, `spec.md`) stays derived and is never in the file.

### VAL — validation order

- **VAL-1** Any violation of this spec is a load error.
- **VAL-2** After a successful load, the existing pipeline applies unchanged: `LadderSpec.lint()` (with `proposer-compat` consuming derived kinds), then the empirical certificate.

## 3. Syntax reference

Every example below is verified against the elaborator.

### Types (FLR-9, RNG-2)

| Written | Is |
| --- | --- |
| `Grid`, `Color`, `Int`, `Bool`, `Mask` | a base type — capitalised |
| `a`, `b` | a type **variable** — lowercase |
| `List[Grid]`, `Pair[Grid, Color]` | a parametric constructor |
| `(Grid) -> Grid` | a function type |
| `(Grid, Int, Int) -> Grid` | an n-ary function type |
| `(Grid) -> (Grid) -> Grid` | a **curried** function type (right-associative) |
| `(Color, Grid...) -> Grid` | variadic in its last parameter (`overlay`) |

Capitalisation is load-bearing: it is what distinguishes a nullary constructor from a type variable without a lookup table that could drift from the substrate.

### Expressions (EXP-1..11)

Each row is a Python form, resolved by **the type of the position it sits in**.

| Construct | Written | Elaborates to |
| --- | --- | --- |
| Task input | `flip_h(input)` | `Input` |
| Rung parameter | `flip_h(g)` | `Param(0, Grid)` |
| Application | `map_color(flip_h(g), src, dst)` | `Apply` |
| Variadic application | `overlay(c, g, flip_h(g))` | `Apply` (extra args to the variadic tail) |
| Colour / int literal | `map_color(g, 1, 2)`, `translate(g, 1, 0)` | `Const(1, Color)` / `Const(1, Int)` |
| Negative literal | `translate(g, -1, 0)` | `Const(-1, Int)` |
| Boolean literal | `flip_h(g) if true else g` | `Const(True, Bool)` — lowercase only |
| Conditional | `flip_h(g) if eq(most_common_color(g), 0) else g` | `If` (short-circuit) |
| Primitive as a value | `map(flip_h, gs)` | `PrimRef("flip_h")` |
| Lambda, one binder | `map(lambda x: flip_h(x), gs)` | `Lam` + `Var(0)` |
| Lambda, curried | `build_grid(height(g), width(g), lambda r, c: read(g, c, r))` | `Lam(Lam(...))`; `c` is `Var(0)`, `r` is `Var(1)` |
| Applying a value | `f(g)` where `f: (Grid) -> Grid` | `AppFn` |
| Applying a curried value | `f(g)(g)` where `f: (Grid) -> (Grid) -> Grid` | nested `AppFn` |

Notes that catch people out:

- **Binder types are never annotated.** Python lambdas cannot carry annotations, and they do not need to: the function-typed position supplies each binder's type, one arrow peeled per binder. That serves both `map`'s `(a) -> b` and `build_grid`'s curried `(int) -> (int) -> color`.
- **A binder's type is resolved by the body.** In `map(lambda x: flip_h(x), gs)` the hole is `(a) -> b`, so `x` is only pinned to `Grid` by what the body does with it. The stored program carries the resolved type.
- **De Bruijn order.** The innermost binder is `Var(0)`. In `lambda r, c:`, `c` is innermost.
- **A curried function is applied one stage at a time** — `f(a)(b)`, not `f(a, b)`.
- **Scope.** A rung template sees its own parameters, floor primitives and strictly earlier rungs — never `input` (NAM-4). A task solution sees `input`, the floor, and the rungs up to its own (NAM-5). A lambda binder may not shadow either.

## 4. Source/derived split (summary)

| In the file (chosen) | Derived (never in the file) |
| --- | --- |
| Ladder name; Floor library name | Rung levels; oracle libraries `L_i` and their names |
| Floor primitive references + asserted signatures | `DemonstrationKind` per task |
| Reference config (as overrides on the frozen base) | Task outputs; testbed JSONs + manifest |
| Rung definitions (signature + template) | Demonstration lists (tasks under their rung); depths, double-jumps, fan-in, validity window |
| Tasks: id, heldout flag, solution, train/test inputs | `spec.md`, reports, certificate verdicts |

## 5. Reference example

Abridged from `al1-mirror` (the real ladder has more tasks per rung and a fuller config block):

```
ladder al1-mirror

config {
    budget.depth_limit: 2
    budget.max_arity: 2
    budget.max_pool: 300
    search_engine.constant_sources: ["finite-enumerate"]
    learn.learn_engine.proposer: "AntiunifyPairs"
    learn.iterations: 5
}

floor al1-L0 {
    use flip_h:    (Grid) -> Grid
    use flip_v:    (Grid) -> Grid
    use map_color: (Grid, Color, Color) -> Grid
}

rung {
    rot180(g: Grid) -> Grid = flip_h(flip_v(g))

    task rot180-00 {
        solution: rot180(input)
        train [[1, 2, 3], [4, 5, 1]]
        train [[3, 1, 6], [1, 4, 7]]
        test  [[8, 7, 1], [2, 1, 3]]
    }
    heldout task rot180-heldout {
        solution: rot180(input)
        train [[5, 6, 7], [8, 9, 5]]
        train [[7, 5, 0], [5, 8, 1]]
        test  [[2, 1, 5], [6, 5, 7]]
    }
}

rung {
    mirror_recolor(g: Grid, src: Color, dst: Color) -> Grid = map_color(rot180(g), src, dst)

    task mirror-recolor-1-2 {
        solution: mirror_recolor(input, 1, 2)
        train [[1, 2, 3], [4, 5, 1]]
        train [[3, 1, 6], [1, 4, 7]]
        test  [[8, 7, 1], [2, 1, 3]]
    }
}

top {
    task top-00 {
        solution: map_color(mirror_recolor(input, 1, 2), 3, 4)
        train [[1, 2, 3], [4, 5, 1]]
        train [[3, 1, 6], [1, 4, 7]]
        test  [[8, 7, 1], [2, 1, 3]]
    }
}
```

Reading conventions: `:` binds a value to a field; `=` (only in rung definitions) defines an abstraction; `train`/`test` lines are repeated items, not fields.
