# Ladder checks — what is verified, and where (2026-07-21; updated 2026-07-22)

A dated snapshot of every check a Ladder passes through, taken after the `.ladder` migration and the demonstration-plan checks landed; updated 2026-07-22 when the evaluation-backed checks (`constant-subterm`, `if-condition-varies`) and the equational `rewrite-shallow` check landed. Point-in-time: the living sources are [LADDER-FORMAT.md](LADDER-FORMAT.md) (the format's normative rules) and the code itself (`ladders/lang/`, `ladders/spec.py::LadderSpec.lint`, `ladders/checks.py`, `analysis/equations.py` + `analysis/rewrite.py`, `ladders/certificate.py`). The planned-checks list this is measured against is [ABSTRACTION-LADDERS-2026-07-16.md](ABSTRACTION-LADDERS-2026-07-16.md) §6.4.

## The pipeline

The quality gates a ladder passes through, each strictly cheaper than the thing it protects:

1. **Author + load** — write the `.ladder` file; every load-time check fires with a line number (`arc-lab lint-ladder` runs this plus lint on a draft, no testbed needed — the loop is edit → lint → edit).
2. **Lint** — the static + evaluation-backed checks below; seconds for the whole batch.
3. **Rung probe** (`arc-lab probe-ladder`, `ladders/probe.py`) — per-rung wake/skip/sleep/forecast against the REAL engine at design time, in process, recording nothing. Seconds per rung on a sound ladder. This is where the task-collision check lives (it needs a search, so it could never live in `lint()`).
4. **Oracle chain + certificate** — the admission gate, run WITHOUT the climb (a rejected ladder never pays for learning).
5. **LEARN climb + reports** — the experiment proper, for admitted ladders only.

## The layering principle

Three layers, drawn on a deliberate line:

| Layer | Question | Failure means |
| --- | --- | --- |
| **Load** (`ladders/lang/`) | Can this file mean anything? | The file does not parse — no ladder can exist in that state |
| **Lint** (`LadderSpec.lint()`) | Is what it means a sound ladder? | A finding; the ladder still loads and runs |
| **Certificate** (`ladders/certificate.py`) | Did it behave that way in fact? | Not admitted to the batch |

The load/lint split is why al4 and al13 still load and run despite failing lint: their rows in [LADDERS.md](LADDERS.md) stay meaningful and the defect is _reported_ rather than making the ladder unloadable. Lint remains **engine-search-free**, but is no longer evaluation-free: the 2026-07-22 checks evaluate stated solutions' subterms on the tasks' own train inputs (`constant-subterm`, `if-condition-varies`) and run bounded equational rewriting over templates (`rewrite-shallow`) — deterministic, capped, and still never a run.

## Layer 1 — Load time

Enforced by `ladders/lang/`; every error carries its line number. Roughly forty distinct messages in six groups.

- **Structure** — filename matches the `ladder` header; kebab-case name; fixed section order (`ladder` → `config` → `floor` → rungs → distractors → `top`); rungs precede distractors; blocks open and close per the brace rule; no unbalanced brackets.
- **Names** — identifiers are valid Python identifiers, not keywords (hard or soft), not reserved words; task ids match their shape and are unique ladder-wide; a rung name cannot shadow a floor primitive or an earlier rung.
- **Floor** — every primitive resolves in `BASE_PRIMITIVES`; its declared signature must match the registry's exactly; no duplicates; at least one primitive.
- **Config** — dotted paths and semantics are exactly `overrides.py`'s; values are Python literals; duplicate and unknown paths rejected; `library` unsettable; `learn` cannot be unset.
- **Expressions** — a closed grammar (positional application, identifiers, int literals — no operators, lambdas, keyword args, negative literals, list literals); scope rules for `input`, params and rungs; full type- and arity-checking with unification; an int literal must land in a `Color` or `Int` position; a rung body must match its declared signature (unused params and wrong return types rejected).
- **Semantics** — every task's solution must evaluate on every declared input; a demonstrating task must actually _call_ its rung; a distractor may not reference any rung.

## Layer 2 — Static lint

**28 checks: 24 error-class, 4 warnings** (`constant-subterm` is error-class with a warn tier — see its row). Most are parametrised per rung or per task, so a real ladder runs many more instances (al13 runs 61).

### Structure

| Check | Asserts |
| --- | --- |
| `levels-contiguous` | rung levels are 1..k |
| `tasks-exist` | every demonstration / top task id is in the train corpus |
| `top-solutions-aligned` | one reference solution per top task id |
| `min-2-demos` | each rung has >= 2 demonstrating tasks |
| `well-typed` | each template builds as an abstraction over `L_{i-1}` |
| `rung-referenced` | the rung above actually calls this one |
| `top-uses-top-rung` | each top solution calls `r_k` |
| `rung-distinct` | no two rungs compute the same function (compared unfolded) |

### The depth sandwich (anchored at the pinned `depth_limit`)

| Check | Asserts |
| --- | --- |
| `jump-affordable` | `d_i <= depth_limit` |
| `proper-composition` | `d_i >= 2` — a rung composes, it does not restate a primitive |
| `double-jump-intractable` | the inlined rung-above exceeds `depth_limit` |
| `top-affordable-with-ladder` | each top solution is affordable over `L_k` |
| `raw-intractable` | `d_raw` exceeds `depth_limit` |
| `top-double-jump-intractable` | the top over `L_{k-1}` exceeds `depth_limit` |
| `rewrite-shallow` | no BEHAVIORALLY-CONFIRMED witness re-expresses the layer above a skipped rung over `L_{i-1}` within `depth_limit` — bounded equational rewriting (`analysis/equations.py` curated laws + derived D4 table; `analysis/rewrite.py` normal forms + typed candidate enumeration). The depth checks above measure the INTENDED template; this one asks what a few known equations reach anyway. Caps (`RewriteLimits`) are silent passes: the check can convict, never acquit |

Plus the computed **validity window** in `depth_limit` units.

### The demonstration plan

Added 2026-07-21. These properties used to hold by construction — `taskgen`'s seed generator built varied grids and `RungTasks.train_args` built the free-parameter sweep — but a `.ladder` file states both as literal data, so nothing enforces them except this block.

| Check | Asserts |
| --- | --- |
| `distinct-train-inputs` | a task's train inputs are not repeated |
| `outputs-vary` | not every train output is the same grid (a constant program would fit) |
| `not-identity` | output != input on at least one train example |
| `heldout-distinct` | no heldout task duplicates a train task's examples |
| `free-param-varies` | a rung's free parameters are demonstrated at more than one value (aggregated over EVERY call site of every demonstration) |
| `constant-subterm` | no composite scalar subterm of a stated solution (unfolded to the floor) is constant across the task's train examples — the literal-collapse law made static: signature dedup keeps the cheapest representative, so a train-constant subterm is strictly beaten by its literal. **Error** when the (type, value) is in the ladder's own configured constant domain (`leaves.py::policy_constants`); **warn** when merely constant (fictional depth) |
| `if-condition-varies` | every `If` condition takes both truth values across the task's train examples, else the conditional collapses to the taken branch (dormant: no ladder uses branching yet) |

### Learnability

| Check | Asserts |
| --- | --- |
| `proposer-compat` | the configured proposer can serve each rung's demonstration kinds |
| `mdl-break-even` | minting a rung lowers the description length of its own demonstrations, under the ladder's own configured metric |

### Advisories (warnings)

| Check | Warns when |
| --- | --- |
| `floor-fully-exercised` | a floor primitive is used by no rung, demonstration, distractor or top solution |
| `min-2-train-examples` | a demonstrating task has < 2 train examples |
| `not-all-telescope` | every rung has fan-in 1 (a pure telescope) |
| `no-lambda-in-templates` | a template contains a `Lam`, making the depth checks advisory (no current ladder does) |

## Layer 3 — Empirical certificate

Read-side, over the oracle-chain runs. Three verdicts per jump:

- `tractable_jumps` — the jump was affordable in fact;
- `no_skip_paths` — **tri-state**: `True` none found, `False` found, `None` inconclusive because a search censored. `None` fails admission exactly as `False` does;
- `demonstration_health` — the fraction of demonstrating tasks whose retained cheapest solution contains the rung template.

Admission requires every jump tractable and every skip verdict literally `True`.

## Layer 4 — Test locks

- every ladder regenerates its committed testbed byte-for-byte (the drift guard that replaced the per-ladder Python modules);
- every ladder builds a spec;
- batch health is pinned to exactly which ladders fail lint and on what (now 11 of 20, with the per-ladder check lists written from an observed batch run, never predictions);
- the variation checks are asserted clean batch-wide; the new checks' batch posture is pinned separately (`if-condition-varies` fires nowhere; `constant-subterm` errors only on al4/al5/al6/al14; `rewrite-shallow` only on al3/al6/al7/al9/al10/al11; al8's warn tier pinned exactly);
- every batch template survives `render` → `elaborate` unchanged.

## Layer 2b — The rung probe (design-time, real engine)

`ladders/probe.py`, driven by `arc-lab probe-ladder [--level N] [--considered-limit N]`. Four questions per rung `r_i`, all under `L_{i-1}` at the pinned budget, none of them recorded:

| Probe | Asks | Verdicts |
| --- | --- | --- |
| **wake** | do `r_i`'s demonstrations solve from `L_{i-1}`, and is what search RETAINS the intended program? | `as-intended` · `collapsed` (same function, shallower spelling) · `collision` (different function, fits the train support only) · `alternative` · `unsolved` · `censored` |
| **skip** | does anything one level up already solve from `L_{i-1}`? | `no-skip` · `skip-path` · `inconclusive` (censored) |
| **sleep** | fed what wake ACTUALLY retained, does governance mint the intended abstraction, at the intended arity? | recovered/missed + minted arity vs intended |
| **forecast** | what does this cell cost? | `estimate_cost`'s static ceiling (loose by construction — the calibrated forecaster is AL-PLAN Phase 0 item 3) |

**This closes the task-collision gap** (§6.4's "no shallower program coincides with the intended solution on all train examples"): the wake probe compares the retained program against the intended one on grids beyond the task's own train support, so a program that merely *fits* is separated from one that is *right*.

Its discriminating power needed one non-obvious ingredient. Comparing on the ladder's own grids is not enough — **al14's seed construction makes `read(g, 0, 2) == read(g, 2, 1)` in all 16 of its grids**, so its known `-01` collision agrees with the intended program everywhere in the corpus, heldout included (same generator). The probe therefore also compares on deterministic **position-separating grids** at each shape the ladder uses (three colour layouts per shape, no RNG). With them, al14's `-00` reads `collapsed` and `-01` reads `collision` — the two failures the 2026-07-21 notebook found by hand, now told apart automatically.

**The probe convicts; only the certificate acquits.** A clean probe does not guarantee admission (the climb pays each jump under a library inflated by earlier mints, and cross-rung interactions are invisible rung-locally), but a dirty probe is proof the ladder will not certify. Remaining bounds, all deliberate: probe grids are at corpus shapes only; a censored probe is inconclusive, not a pass; sleep is graded per-rung, not against whole-corpus governance.

**Read the three components separately** (`wake_ok` / `skip_ok` / `mint_ok`, not just `ok`): wake+skip are *structure*, mint is *learnability*, and the certificate deliberately separates them — al12-unlearnable is structurally sound (it certifies) while its single demonstration leaves `AntiunifyPairs` nothing to pair. The probe says exactly that, in 0.2s: clean wake, clean skip, `sleep: the intended abstraction was NOT minted`.

## What the checks currently find

Batch health at this snapshot (2026-07-22) — **eleven ladders carry errors** (up from four): the new checks statically confirm most of what the 2026-07-20 certificate could only establish empirically, witnesses printed. The clean set is exactly the register's usable arms: al1, al2, al8 (warn tier only), al15–al20.

| Ladder | Finding | Reading |
| --- | --- | --- |
| al13-symmetry-repair | `free-param-varies[sym_h#1]`, `[sym_both#1]` | Both rung colour parameters are only ever demonstrated at `0`, so antiunification has nothing to generalise and mints the specialised form. **This statically explains al13's recorded zero rung recovery.** |
| al4-mask-crop | `heldout-distinct[nonbg_mask-heldout-00]` | The heldout task is byte-identical to `nonbg_mask-00` — r1's heldout column has been measuring transfer to a task it trained on. |
| al14-cell-row-grid | `constant-subterm` on all 7 stated tasks | The literal collapse, static: `sub(1, 1)`/`sub(2, 1)`/`sub(3, 1)` are train-constant enumerable INTs (the 2026-07-21 probe diagnosis needed a day of custom scripts; lint now says it in 0.3s), plus train-constant `read(...)` colours adjacent to the known `-01` collision. |
| al4 / al5 / al6 | `constant-subterm` on the flagged demos + top | The perceiver calls (`most_common_color(input)` etc.) are train-constant on those tasks, so search substitutes the enumerated literal — **statically explaining al5's recorded zero rung recovery and the Family-B skip paths**. |
| al8-lean-perceiver (warn) | `constant-subterm` warn tier on all 4 stated tasks | Same perceiver constancy, but al8 mints no constants — the severity split is the law's "does the beating literal exist in this ladder's own search?" clause, working. |
| al3 / al7 / al9 / al11 | `rewrite-shallow[band]` / `[wide4]`,`[tall4]`,`[wide8]` | The self-similar-doubling collapse, static, witnesses printed: `tower == quad(quad g)`; `tall4 == stack2(stack2 g)`, `wide8 == stack2(wide4 g)`, top via `stack2(tall4 g)` — identical on the al9/al11 controls (inherited spine). |
| al6-mirror-tall | `rewrite-shallow[rot180]` | `norm_mirror = map_color(flip_h(rot180(g)), ...)` hides a `flip_h∘flip_h` cancellation: r1 contributes nothing, witness `map_color(flip_v(#0), most_common_color(#0), #1)` — al1's original-top D4 collapse pattern, caught before any run this time. |
| al12-unlearnable | `mdl-break-even[rot90]` | With one demonstration, folding saves nothing against the library cost — an independent static prediction of the climb failure this control exists to exhibit. |
| al10-skippable | `raw-intractable`, `top-double-jump-intractable`, `rewrite-shallow[rot90]` | Fails by design — and the rewrite check now prints the witness its design promises exists: `flip_h(transpose(flip_h(transpose(input))))` at depth 4. |
| al7, al11 (warn) | `floor-fully-exercised` | `flip_v` is in the floor and used by nothing — likely accidental, and it inflates the vocabulary tax those ladders measure. |
| al4 (warn) | `floor-fully-exercised` | Three of nine mask primitives unused — plausibly deliberate breadth. |

`mdl-break-even`, `constant-subterm` and `rewrite-shallow` all fire on **no** healthy ladder (al1/al2/al15–al20 stay clean, and al1/al15–al20 do enumerate constants) — the evidence none of them over-fires.

None of the flagged defects has been fixed: each is an edit to its `.ladder` file that would change the testbed and recorded verdicts, so each is a deliberate act pending a decision. The whole-batch lint runs in ~8s (`arc-lab lint-ladder`); `unfold_program` is memoized by node identity so deep tops (al14's is millions of node occurrences) cost milliseconds, not tens of seconds.

## Supporting structure

Additions that made these checks possible, worth knowing:

- **`Demonstration.solution`** — each demonstrating task's intended program, stated over `L_i`. Previously the loader computed these and discarded them, so lint could only reason about templates.
- **`Distractor`** — off-spine tasks as first-class spec data. Without it, al9's `decoy` (the only thing exercising its `flip_v`) would have been falsely flagged as dead floor vocabulary.
- **`ladders/checks.py`** (2026-07-22) — the evaluation-backed checks, apart from `spec.py` (plain data in, no import cycle), with an id-memoized bottom-up subterm evaluator.
- **`analysis/equations.py` + `analysis/rewrite.py`** (2026-07-22) — the curated equational theory (flip involutions, flip-over-concat distribution, concat interchange; D4 composition table DERIVED at import from the primitives' own impls, so it cannot drift) and the bounded normalize-and-enumerate engine. Every curated law is behaviorally verified by a test using identity binding (positional — an argument-permutation-tolerant check would accept a swapped-argument law).
- **`search/leaves.py::policy_constants`** — the public view of the configured constant domain; `seed_leaves` delegates to it, so lint and engine can never drift.
- **`unfold_program` memoization by node identity** — a deep top's floor form keeps a near-minimal DISTINCT-node count, making every downstream distinct-id traversal cheap. (The memo holds a reference to each keyed node: `id()` is only unique among live objects, and the aliasing bug the naive version produces is real — it was caught here by the batch firings changing.)

`Demonstration.solution` and `Distractor` flow into the provenance payload and the generated `spec.md`.
