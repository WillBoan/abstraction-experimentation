# The `.ladder` file format — spec

Normative spec for `.ladder` files: the declarative source format in which a Ladder ([ABSTRACTION-LADDERS-2026-07-16.md](ABSTRACTION-LADDERS-2026-07-16.md)) is authored.

A `.ladder` file is the **single source of truth for a ladder's identity**: it drives the `LadderSpec`, the committed testbed (via taskgen), and every derived artifact.

This doc governs the implementation — where code and this spec disagree during the build, this spec wins until deliberately amended.

**Status: agreed design, 2026-07-21 — not yet implemented.** Format decisions were settled in design discussion; the build (parser/elaborator, loader, taskgen bridge, pretty-printer, migration) has not started. Until migration completes, the Python registry modules (`src/arc_lab/program_search/ladders/registry/*.py`) remain the operative source.

## 1. Motivation

- **One statement of semantics.** Today each ladder's semantics exist in three places: the registry module's `Program` templates, the taskgen generator's hand-written numpy re-implementation of the same functions, and the committed testbed outputs. Nothing but care keeps them aligned. In the file-driven world, task outputs are computed by _executing the declared solution `Program`_ through the engine's own evaluator — semantics stated once, everything else derived.
- **A write/edit surface.** Nested `Apply(...)` trees are error-prone to author and miserable to review; `mirror_recolor(g: Grid, src: Color, dst: Color) -> Grid = map_color(rot180(g), src, dst)` is neither.
- **A diff surface.** A PR changing a ladder shows a readable structural diff of exactly what changed in the ladder's identity.
- **Source/derived split.** The file holds everything _chosen_; generated artifacts (`spec.md`, testbed, reports) hold everything _derived_. Neither duplicates the other.

## 2. Rules

Rules are numbered per section for referenceability. Where a rule says **delegated**, the format deliberately re-enforces nothing — the named existing machinery is the sole authority.

Reading conventions: `:` binds a value to a field; `=` (only in rung definitions) defines an abstraction; `train`/`test` lines are repeated items, not fields. Param names were renamed from the al1 registry module's `from`/`to` (Python keywords — NAM-1); harmless, since `Param`s are positional.

### LEX — file & lexical

- **LEX-1** Encoding: ASCII, LF line endings.
- **LEX-2** `#` starts a comment, anywhere on a line, to end of line. Comments are never load-bearing — the loader ignores them entirely.
- **LEX-3** Blank lines and indentation are insignificant (braces carry structure). Convention: 4-space indent, one statement per line.
- **LEX-4** A statement continues across lines while brackets (`[`, `(` inside expressions) are unbalanced — so large grid literals can be laid out multi-row.
- **LEX-5** A block opens with `{` at the end of its header line and closes with `}` on its own line.
- **LEX-6** Reserved words: `ladder`, `floor`, `config`, `budgets`, `sweep`, `rung`, `top`, `task`, `heldout`, `use`, `solution`, `train`, `test`, `input`.

### STR — file structure

- **STR-1** Filename is `<name>.ladder`.
- **STR-2** `<name>` must equal the `ladder <name>` header.
- **STR-3** `<name>` must be kebab-case: `[a-z0-9]+(-[a-z0-9]+)*`.
- **STR-4** Section order is fixed; nothing else, nothing twice, nothing missing:
  - `ladder` header
  - `floor`
  - `config`
  - one or more `rung`
  - `top`

### NAM — naming & scoping

- **NAM-1** Code identifiers (primitive, abstraction, param names) must be valid Python identifiers, not Python keywords, and not reserved words (LEX-6). This is what makes the `ast`-based parse safe.
- **NAM-2** Task ids match `[a-z0-9][a-z0-9_-]*` and are unique across the whole ladder (the manifest is flat).
- **NAM-3** A rung's name must be unique among rungs and must not shadow a floor primitive.
- **NAM-4** Template body scope: own params + floor primitives + _strictly earlier_ rungs. No self-reference, no forward reference, no `input`.
- **NAM-5** Solution scope: `input` + floor + rungs up to and including the enclosing rung (for rung tasks) or all rungs (for top tasks).

### FLR — floor

- **FLR-1** Floor primitives must be defined on their own lines, with the format: `use <name>: <signature>`
- **FLR-2** The Floor must have at least 1 primitive.
- **FLR-3** The Floor must not have any duplicate primitive names.
- **FLR-4** `<name>` must resolve in `BASE_PRIMITIVES`.
- **FLR-5** The signature is required.
- **FLR-6** The signature must exactly match the registry's signature for that primitive.
- **FLR-7** Signature grammar: `(T1, T2, ...) -> T`, type names resolving against the substrate's type registry.

### CFG — config & budgets

- **CFG-1** Each line is `dotted.path: value`. Paths and application semantics are _exactly_ `execution/overrides.py` — no parallel config language. Values are Python literals (via `ast`), lowered to the same data a config-file `set` dict carries.
- **CFG-2** Overrides apply to a single canonical LEARN-shaped base config defined once in the loader and documented — the "ladder default". The base is part of every ladder's identity: changing it changes every ladder's `run_id`, so it is frozen, documented data (see §6).
- **CFG-3** `library` is not a settable path — the floor section owns it, injected by the loader. Unsetting `learn` is forbidden (a `LadderSpec` must be a LEARN config).
- **CFG-4** Duplicate paths are errors (no silent last-wins). Unknown paths are errors (**delegated** to the override machinery).
- **CFG-5** Values naming registered components (proposer, engines) use their serde `kind` strings.
- **CFG-6** `budgets` block, if present, holds one or more `sweep { ... }` blocks whose paths must all start with `budget.`; each produces (reference budget + those overrides). The reference budget is always implicitly the first sweep cell; duplicate cells are errors. Absent block ⇒ reference only.

### RNG — rungs

- **RNG-1** Rung levels are not explicit, but derived.
- **RNG-2** The first statement of a `rung` block is exactly one definition, the only `=` form: `name(p1: T1, ...) -> T = <expr>`.
- **RNG-3** Param names are unique within a definition. Param index = position in the signature; param type = the annotation.
- **RNG-4** Whether a template is otherwise admissible (unused params, empty param lists, depth, etc.) is **delegated** to `make_abstraction` + `lint()` — the format adds no rules of its own here.
- **RNG-5** After the definition: zero or more task blocks. Minimum-count enforcement (>= 2 train demos) stays in `lint()` (`min-2-demos`), not the parser.

### TSK — tasks

- **TSK-1** Header is `task <id> {` or `heldout task <id> {`. `heldout` routes the task to the heldout corpus (manifest `split: heldout`); otherwise train.
- **TSK-2** Field order is fixed: one `solution:`, then >= 1 `train <grid>` lines, then >= 1 `test <grid>` lines. (Canonical order keeps diffs stable.)
- **TSK-3** A grid literal is a nested list of int literals, rectangular and non-empty; value-range and shape validation is **delegated** to `Grid.from_list`.
- **TSK-4** Distinctness/variation of a task's inputs is **delegated** to lint (within-task variation, collision checks) — the parser doesn't legislate it.
- **TSK-5** Top-block tasks follow the same rules; the non-heldout ones become `TopRung.task_ids` + `reference_solutions` (index-aligned by construction); heldout top tasks exist only in the heldout corpus.

### EXP — expression elaboration (text → `Program`)

- **EXP-1** The expression grammar is the Python-`ast`-parseable subset: positional function application and int literals only. No operators, keyword args, lambdas, attributes, subscripts, comprehensions — `ast` may parse them; the elaborator rejects them.
- **EXP-2** `f(a, b)` → `Apply("f", (a, b))`; `f` must resolve per the scope rules (NAM-4/5). No higher-order forms — the target fragment is `Apply | Param | Const | Input` only.
- **EXP-3** `input` → `Input()`.
- **EXP-4** A param name in a template body → `Param(index, type)` per RNG-3.
- **EXP-5** An int literal → `Const(value, T)` where `T` is the expected type of that argument position in the enclosing application. If the position's type is ambiguous (polymorphic), that is a load error in v1.
- **EXP-6** Every application is type/arity-checked through the existing substrate machinery (`make_abstraction` for templates; type-check + evaluation for solutions) — the format has no type checker of its own.
- **EXP-7** The unsupported node kinds (`Lam`, `If`, `Var`, `AppFn`, `PrimRef`) and grid literals inside expressions are a **registered deliberate limit** (ARCHITECTURE.md §11.6 entry), with the codec round-trip test scoped to the supported fragment.

### DRV — derivation (computed, never written)

- **DRV-1** Rung levels (RNG-1), oracle libraries `L_i`, and library names (`<name>-L0`) are derived.
- **DRV-2** `DemonstrationKind` is derived per task by structural comparison of solution vs the rung's template: solution = template instantiated ⇒ `full_solution`; template a proper subprogram with identical instantiation across the rung's **train** tasks ⇒ `fragment_identical`; else ⇒ `fragment_varying`. Heldout tasks don't vote. No `kind:` field exists.
- **DRV-3** Task outputs are derived by executing the declared solution `Program` on each declared input through the engine's own evaluator — the single statement of semantics. Execution failure on any input is a load error.
- **DRV-4** The committed testbed (task JSONs + manifest, labels = rung names, splits per TSK-1) is generated from the file, deterministically: same file ⇒ byte-identical testbed.
- **DRV-5** Everything `lint()`/`render()` computes (depths, double-jumps, fan-in, validity window, `spec.md`) stays derived and is never in the file.

### VAL — validation order

- **VAL-1** Load-time errors (parser/elaborator): structure violations (STR), unresolvable or shadowed names (NAM, FLR-2), signature mismatches (FLR-3), scope violations, type/arity errors, ambiguous literals, duplicate ids/paths, malformed grids, solution execution failures.
- **VAL-2** Everything after a successful load is the _existing_ pipeline, unchanged: `LadderSpec.lint()` (all current checks, with `proposer-compat` consuming derived kinds), then the empirical certificate. The format adds no third verdict layer.

### LC — lifecycle & process

- **LC-1** The `.ladder` file is the single source of truth for ladder identity.
- **LC-2** A `.ladder` file should generally not be machine-written.

## 4. Source/derived split (summary)

| In the file (chosen) | Derived (never in the file) |
| --- | --- |
| Ladder name | Rung levels, library names, oracle libraries `L_i` |
| Floor primitive references + asserted signatures | `DemonstrationKind` per task |
| Reference config (as overrides on the frozen base) | Task outputs; testbed JSONs + manifest |
| Budget sweep cells | Demonstration lists (tasks under their rung) |
| Rung definitions (signature + template) | Depths, double-jumps, fan-in, validity window |
| Tasks: id, heldout flag, solution, train/test inputs | `spec.md`, reports, certificate verdicts |
