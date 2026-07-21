# The `.ladder` file format — spec

Normative spec for `.ladder` files: the declarative source format in which a Ladder ([ABSTRACTION-LADDERS-2026-07-16.md](ABSTRACTION-LADDERS-2026-07-16.md)) is authored.

A `.ladder` file is the **single source of truth for a ladder's identity**: it drives the `LadderSpec`, the testbed (via taskgen), and every derived artifact. It is hand-authored: no tool rewrites it.

This doc governs the implementation — where code and this spec disagree, this spec wins until deliberately amended.

**Status: agreed design, 2026-07-21 — not yet implemented.** The Python registry modules (`src/arc_lab/program_search/ladders/registry/*.py`) remain the operative source until migration completes.

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
- **LEX-6** Reserved words: `ladder`, `floor`, `config`, `rung`, `top`, `task`, `heldout`, `use`, `solution`, `train`, `test`, `input`.

### STR — file structure

- **STR-1** Filename is `<name>.ladder`.
- **STR-2** `<name>` must equal the `ladder <name>` header.
- **STR-3** `<name>` must be kebab-case: `[a-z0-9]+(-[a-z0-9]+)*`.
- **STR-4** Section order is fixed; nothing else, nothing twice, nothing missing:
  - `ladder` header
  - `config`
  - `floor`
  - one or more `rung`
  - `top`

### NAM — naming & scoping

- **NAM-1** Code identifiers (primitive, abstraction, param names) must be valid Python identifiers, not Python keywords, and not reserved words (LEX-6).
- **NAM-2** Task ids match `[a-z0-9][a-z0-9_-]*` and are unique across the whole ladder.
- **NAM-3** A rung's name must be unique among rungs and must not shadow a floor primitive.
- **NAM-4** Template body scope: own params + floor primitives + _strictly earlier_ rungs. No self-reference, no forward reference, no `input`.
- **NAM-5** Solution scope: `input` + floor + rungs up to and including the enclosing rung (for rung tasks) or all rungs (for top tasks).

### FLR — floor

- **FLR-1** Floor primitives are declared one per line: `use <name>: <signature>`.
- **FLR-2** The Floor must have at least 1 primitive.
- **FLR-3** The Floor must not have duplicate primitive names.
- **FLR-4** Declaration order is significant: it is the `Library` primitive order.
- **FLR-5** `<name>` must resolve in `BASE_PRIMITIVES`.
- **FLR-6** The signature is required.
- **FLR-7** The signature must exactly match the registry's signature for that primitive.
- **FLR-8** Signature grammar: `(T1, T2, ...) -> T`, type names resolving against the substrate's type registry.

### CFG — config

- **CFG-1** Each line is `dotted.path: value`. Paths and application semantics are exactly those of `execution/overrides.py`.
- **CFG-2** Values are Python-style literals (ints, floats, strings, booleans, lists, `None`).
- **CFG-3** Overrides apply to a single canonical LEARN-shaped base config — the "ladder default" — which is frozen, documented data.
- **CFG-4** `library` is not a settable path (the floor section owns it). Unsetting `learn` is forbidden.
- **CFG-5** Duplicate paths are errors. Unknown paths are errors (**delegated** to the override machinery).
- **CFG-6** Values naming registered components (proposer, engines) use their serde `kind` strings.

### RNG — rungs

- **RNG-1** Rung levels are derived from file order: the Nth `rung` block is level N.
- **RNG-2** The first statement of a `rung` block is exactly one definition, the only `=` form: `name(p1: T1, ...) -> T = <expr>`.
- **RNG-3** Param names are unique within a definition. Param index = position in the signature; param type = the annotation.
- **RNG-4** Whether a template is otherwise admissible (unused params, empty param lists, depth, etc.) is **delegated** to `make_abstraction` + `lint()`.
- **RNG-5** After the definition: zero or more task blocks. Minimum counts are **delegated** to `lint()` (`min-2-demos`).

### TSK — tasks

- **TSK-1** Header is `task <id> {` or `heldout task <id> {`. `heldout` routes the task to the heldout corpus; otherwise train.
- **TSK-2** Field order is fixed: one `solution:`, then >= 1 `train <grid>` lines, then >= 1 `test <grid>` lines.
- **TSK-3** A grid literal is a nested list of int literals, rectangular and non-empty; value-range and shape validation is **delegated** to `Grid.from_list`.
- **TSK-4** Distinctness/variation of a task's inputs is **delegated** to `lint()`.
- **TSK-5** Top-block tasks follow the same rules; the non-heldout ones become `TopRung.task_ids` + `reference_solutions` (index-aligned); heldout top tasks exist only in the heldout corpus.

### EXP — expression elaboration (text → `Program`)

- **EXP-1** An expression is positional application of named functions over identifiers and int literals — nothing else: no operators, keyword args, lambdas, attributes, subscripts, or comprehensions.
- **EXP-2** `f(a, b)` → `Apply("f", (a, b))`; `f` must resolve per the scope rules (NAM-4/5).
- **EXP-3** `input` → `Input()`.
- **EXP-4** A param name in a template body → `Param(index, type)` per RNG-3.
- **EXP-5** An int literal → `Const(value, T)`, where `T` is the expected type of that argument position in the enclosing application; if that type is ambiguous (polymorphic), it is a load error.
- **EXP-6** Every application is type/arity-checked — **delegated** to the substrate (`make_abstraction` for templates; type-check + evaluation for solutions).
- **EXP-7** Expressions produce only `Apply | Param | Const | Input` nodes; there is no surface syntax for `Lam`, `If`, `Var`, `AppFn`, `PrimRef`, or grid literals inside expressions.

### DRV — derivation (computed, never written)

- **DRV-1** Rung levels (RNG-1), oracle libraries `L_i`, and library names (`<name>-L0`) are derived.
- **DRV-2** `DemonstrationKind` is derived per task by structural comparison of solution vs the rung's template: solution = template instantiated ⇒ `full_solution`; template a proper subprogram with identical instantiation across the rung's **train** tasks ⇒ `fragment_identical`; else ⇒ `fragment_varying`. Heldout tasks don't vote.
- **DRV-3** Task outputs are derived by executing the declared solution `Program` on each declared input through the engine's own evaluator. Execution failure on any input is a load error.
- **DRV-4** The testbed (task JSONs + manifest, labels = rung names, splits per TSK-1) is generated from the file deterministically: same file ⇒ byte-identical testbed.
- **DRV-5** Everything `lint()`/`render()` computes (depths, double-jumps, fan-in, validity window, `spec.md`) stays derived and is never in the file.

### VAL — validation order

- **VAL-1** Any violation of this spec is a load error.
- **VAL-2** After a successful load, the existing pipeline applies unchanged: `LadderSpec.lint()` (with `proposer-compat` consuming derived kinds), then the empirical certificate.

## 3. Source/derived split (summary)

| In the file (chosen) | Derived (never in the file) |
| --- | --- |
| Ladder name | Rung levels, library names, oracle libraries `L_i` |
| Floor primitive references + asserted signatures | `DemonstrationKind` per task |
| Reference config (as overrides on the frozen base) | Task outputs; testbed JSONs + manifest |
| Rung definitions (signature + template) | Demonstration lists (tasks under their rung); depths, double-jumps, fan-in, validity window |
| Tasks: id, heldout flag, solution, train/test inputs | `spec.md`, reports, certificate verdicts |

## 4. Reference example

Abridged from `al1-mirror` (the real ladder has more tasks per rung and a fuller config block):

```
ladder al1-mirror

config {
    budget.depth_limit: 2
    budget.max_arity: 2
    budget.max_pool: 300
    search_engine.constant_sources: ["finite-enumerate"]
    learn.proposer: "antiunify-pairs"
    learn.iterations: 5
}

floor {
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
