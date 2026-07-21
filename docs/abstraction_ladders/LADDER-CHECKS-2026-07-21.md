# Ladder checks — what is verified, and where (2026-07-21)

A dated snapshot of every check a Ladder passes through, taken after the `.ladder` migration and the demonstration-plan checks landed. Point-in-time: the living sources are [LADDER-FORMAT.md](LADDER-FORMAT.md) (the format's normative rules) and the code itself (`ladders/lang/`, `ladders/spec.py::LadderSpec.lint`, `ladders/certificate.py`). The planned-checks list this is measured against is [ABSTRACTION-LADDERS-2026-07-16.md](ABSTRACTION-LADDERS-2026-07-16.md) §6.4.

## The layering principle

Three layers, drawn on a deliberate line:

| Layer | Question | Failure means |
| --- | --- | --- |
| **Load** (`ladders/lang/`) | Can this file mean anything? | The file does not parse — no ladder can exist in that state |
| **Lint** (`LadderSpec.lint()`) | Is what it means a sound ladder? | A finding; the ladder still loads and runs |
| **Certificate** (`ladders/certificate.py`) | Did it behave that way in fact? | Not admitted to the batch |

The load/lint split is why al4 and al13 still load and run despite failing lint: their rows in [LADDERS.md](LADDERS.md) stay meaningful and the defect is _reported_ rather than making the ladder unloadable. Lint is deliberately **search-free** — every check below is static.

## Layer 1 — Load time

Enforced by `ladders/lang/`; every error carries its line number. Roughly forty distinct messages in six groups.

- **Structure** — filename matches the `ladder` header; kebab-case name; fixed section order (`ladder` → `config` → `floor` → rungs → distractors → `top`); rungs precede distractors; blocks open and close per the brace rule; no unbalanced brackets.
- **Names** — identifiers are valid Python identifiers, not keywords (hard or soft), not reserved words; task ids match their shape and are unique ladder-wide; a rung name cannot shadow a floor primitive or an earlier rung.
- **Floor** — every primitive resolves in `BASE_PRIMITIVES`; its declared signature must match the registry's exactly; no duplicates; at least one primitive.
- **Config** — dotted paths and semantics are exactly `overrides.py`'s; values are Python literals; duplicate and unknown paths rejected; `library` unsettable; `learn` cannot be unset.
- **Expressions** — a closed grammar (positional application, identifiers, int literals — no operators, lambdas, keyword args, negative literals, list literals); scope rules for `input`, params and rungs; full type- and arity-checking with unification; an int literal must land in a `Color` or `Int` position; a rung body must match its declared signature (unused params and wrong return types rejected).
- **Semantics** — every task's solution must evaluate on every declared input; a demonstrating task must actually _call_ its rung; a distractor may not reference any rung.

## Layer 2 — Static lint

**25 checks: 21 errors, 4 warnings.** Most are parametrised per rung or per task, so a real ladder runs many more instances (al13 runs 54).

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

Plus the computed **validity window** in `depth_limit` units.

### The demonstration plan

Added 2026-07-21. These properties used to hold by construction — `taskgen`'s seed generator built varied grids and `RungTasks.train_args` built the free-parameter sweep — but a `.ladder` file states both as literal data, so nothing enforces them except this block.

| Check | Asserts |
| --- | --- |
| `distinct-train-inputs` | a task's train inputs are not repeated |
| `outputs-vary` | not every train output is the same grid (a constant program would fit) |
| `not-identity` | output != input on at least one train example |
| `heldout-distinct` | no heldout task duplicates a train task's examples |
| `free-param-varies` | a rung's free parameters are demonstrated at more than one value |

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
- batch health is pinned to exactly which ladders fail lint and on what;
- the variation checks are asserted clean batch-wide;
- every batch template survives `render` → `elaborate` unchanged.

## The one gap

**Task collision** — "no shallower program coincides with the intended solution on all train examples" (§6.4) — is the only planned check not implemented. It is the one check that cannot be decided statically: it means enumerating the cheap end of the program space over `L_{i-1}` below the rung's depth, which is a real search and would break lint's search-free contract. It needs a home outside `lint()` (a certificate-side check, or an opt-in flag) before it can be built.

Consequence: al14's known defect stays uncaught — its task `-01` retains a solution that reads (0,2) to write (1,1), sound only because those cells happen to share a colour in both train examples.

## What the checks currently find

Batch health at this snapshot — four ladders carry errors, and the warnings name three more with dead vocabulary.

| Ladder | Finding | Reading |
| --- | --- | --- |
| al13-symmetry-repair | `free-param-varies[sym_h#1]`, `[sym_both#1]` | Both rung colour parameters are only ever demonstrated at `0`, so antiunification has nothing to generalise and mints the specialised form. **This statically explains al13's recorded zero rung recovery.** |
| al4-mask-crop | `heldout-distinct[nonbg_mask-heldout-00]` | The heldout task is byte-identical to `nonbg_mask-00` — r1's heldout column has been measuring transfer to a task it trained on. |
| al12-unlearnable | `mdl-break-even[rot90]` | With one demonstration, folding saves nothing against the library cost — an independent static prediction of the climb failure this control exists to exhibit. |
| al10-skippable | `raw-intractable`, `top-double-jump-intractable` | Fails by design: the sandwich is deliberately unenforced. |
| al7, al11 (warn) | `floor-fully-exercised` | `flip_v` is in the floor and used by nothing — likely accidental, and it inflates the vocabulary tax those ladders measure. |
| al4 (warn) | `floor-fully-exercised` | Three of nine mask primitives unused — plausibly deliberate breadth. |

`mdl-break-even` fires on **no** healthy ladder, which is the evidence its formula is not over-firing.

Neither al4's duplicate task nor al13's unvaried colour parameter has been fixed: both are one-line edits to their `.ladder` files, and both would change those ladders' testbeds and recorded verdicts, so both are deliberate acts pending a decision.

## Supporting structure

Two additions to `LadderSpec` were needed to make the demonstration-plan checks possible, and are worth knowing:

- **`Demonstration.solution`** — each demonstrating task's intended program, stated over `L_i`. Previously the loader computed these and discarded them, so lint could only reason about templates.
- **`Distractor`** — off-spine tasks as first-class spec data. Without it, al9's `decoy` (the only thing exercising its `flip_v`) would have been falsely flagged as dead floor vocabulary.

Both flow into the provenance payload and into the generated `spec.md`.
