<!-- Generated from `checks/plan.py` -- regenerate with `uv run arc-lab lint-checks --out docs/abstraction_ladders/LINT-CHECKS.md`; never hand-edit. -->

# Ladder lint checks

Every static check a `.ladder` file is held to, in the order they run. This file is GENERATED from the checks themselves (each one declares its code, family, stage and severity in its class body), so it cannot drift from what the lint actually does.

- **4 syntax checks** run over the parsed document, before anything resolves. They are pure predicates over what the file says, so the editor reports all of them at once on their exact spans; a strict load raises the first and stops.
- **31 lint checks** run over the resolved ladder: 22 error-class, 9 advisory. Most are parametrised per rung or per task, so a real ladder runs many more instances.
- **10 of those are corpus-backed** -- they read the generated task grids, or evaluate a subterm on them. `lint(corpus_backed=False)` skips exactly these and NAMES them in `LadderShape.skipped_checks`, which is what lets a draft over assumed primitives be linted at all.
- **Severity** is the check's default; two checks decide it per finding (`constant-subterm`, `proposer-compat` -- see their rows).

Prose context -- the layering these sit in, what lint can and cannot catch, and the current batch health -- is in [LADDER-CHECKS-2026-07-21.md](../archive/LADDER-CHECKS-2026-07-21.md).

## Syntax -- the document alone (`DOCUMENT_PLAN`)

Everything a file answers on its own. A rule belongs here only if it needs nothing but the parsed document; the rest of the load-time errors are raised while *constructing* a library, template or config, so they have no completed model to be a predicate over.

| #   | code                  | severity | what it checks                                          |
| --- | --------------------- | -------- | ------------------------------------------------------- |
| S1  | `floor-non-empty`     | error    | The floor declares at least one primitive (spec FLR-3). |
| S2  | `floor-names-unique`  | error    | No floor primitive is declared twice.                   |
| S3  | `config-paths-unique` | error    | No config path is overridden twice.                     |
| S4  | `task-ids-unique`     | error    | No task id is used twice.                               |

## Lint -- the resolved ladder (`CHECK_PLAN`)

### Structure (S) -- is this a ladder at all?

| #   | code                    | stage      | severity | what it checks                                                                    |
| --- | ----------------------- | ---------- | -------- | --------------------------------------------------------------------------------- |
| 1   | `levels-contiguous`     | structural | error    | Rung levels are exactly 1..k, in order.                                           |
| 2   | `top-solutions-aligned` | structural | error    | Every top task id has a reference solution, and vice versa.                       |
| 3   | `min-2-demos`           | structural | error    | Every rung is demonstrated by at least two tasks.                                 |
| 4   | `tasks-exist`           | corpus     | error    | Every demonstration and top task id resolves in the train corpus.                 |
| 5   | `min-2-train-examples`  | corpus     | warn     | Every demonstrating task shows at least two train examples.                       |
| 6   | `rung-referenced`       | structural | error    | Every rung is reachable from the top (some higher rung or top solution calls it). |
| 30  | `rung-distinct`         | structural | error    | No two rungs unfold to the same floor-level template.                             |

### Depth sandwich (D) -- the tractability claims

| #   | code                          | stage      | severity | what it checks                                                                     |
| --- | ----------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------- |
| 7   | `jump-affordable`             | structural | error    | Every rung's demonstrations are in reach over L_{i-1} at that level's depth_limit. |
| 8   | `proper-composition`          | structural | error    | Every rung composes over the layer below rather than restating a bare primitive.   |
| 9   | `double-jump-intractable`     | structural | warn     | Skipping a rung leaves every higher rung out of reach at the pinned depth_limit.   |
| 10  | `top-affordable-with-ladder`  | structural | error    | Every top reference solution is in reach over L_k at the pinned depth_limit.       |
| 11  | `climb-budget-covers-top`     | structural | warn     | The pinned depth_limit (the climb's search budget) covers the derived schedule.    |
| 12  | `top-uses-top-rung`           | structural | error    | Every top reference solution calls the top bridging rung.                          |
| 13  | `raw-intractable`             | structural | error    | No top solution is reachable from the bare floor at that level's depth_limit.      |
| 14  | `top-double-jump-intractable` | structural | warn     | No top solution is reachable over L_{k-1} (with the top rung skipped).             |
| 15  | `rewrite-shallow`             | corpus     | error    | No known equation re-expresses the layer above a skipped rung shallowly.           |

### Learnability (L) -- can this machinery mint it?

| #   | code              | stage      | severity | what it checks                                                                     |
| --- | ----------------- | ---------- | -------- | ---------------------------------------------------------------------------------- |
| 16  | `proposer-compat` | structural | error    | The configured proposer can serve every demonstration kind the rungs are shown at. |
| 31  | `mdl-break-even`  | corpus     | error    | Minting each rung pays for itself in bits on its own demonstrations.               |

### Demonstration plan (P) -- what the tasks show

| #   | code                    | stage      | severity | what it checks                                                                  |
| --- | ----------------------- | ---------- | -------- | ------------------------------------------------------------------------------- |
| 17  | `distinct-train-inputs` | corpus     | error    | No task repeats a train input.                                                  |
| 18  | `outputs-vary`          | corpus     | error    | No task has a single repeated train output (a constant program would fit it).   |
| 19  | `not-identity`          | corpus     | error    | No task is solved by the identity on every train example.                       |
| 20  | `heldout-distinct`      | corpus     | error    | No heldout task duplicates a train task's examples.                             |
| 21  | `free-param-varies`     | structural | error    | Every free rung parameter is demonstrated at more than one value.               |
| 22  | `free-params-covary`    | structural | error    | No two free rung parameters hold the same value at every call site.             |
| 23  | `constant-subterm`      | corpus     | error    | No stated solution contains a train-constant composite scalar subterm.          |
| 24  | `if-condition-varies`   | corpus     | error    | Every conditional's condition takes both truth values across a task's examples. |

### Advisories (A) -- observations, not defects

| #   | code                     | stage      | severity | what it checks                                                                       |
| --- | ------------------------ | ---------- | -------- | ------------------------------------------------------------------------------------ |
| 25  | `not-all-telescope`      | structural | warn     | At least one rung recombines rather than piping a single lower-rung call.            |
| 26  | `no-lambda-in-templates` | structural | warn     | No rung template contains a lambda (whose reachability depth cannot certify).        |
| 27  | `floor-fully-exercised`  | structural | warn     | Every floor primitive is used by some rung, demonstration, distractor or top.        |
| 28  | `primitive-necessity`    | structural | warn     | Floor primitives carried below the level that needs them, where the carry is costly. |

### Vocabulary (V) -- config coherence

| #   | code                 | stage      | severity | what it checks                                                           |
| --- | -------------------- | ---------- | -------- | ------------------------------------------------------------------------ |
| 29  | `hof-holes-fillable` | structural | warn     | Every higher-order floor primitive has fillable holes under this config. |

## Run order

Both plans are explicit ordered tuples -- not import order, not subclass discovery -- so the numbers above are the order findings come back in, and `skipped_checks` is the lint order filtered to the corpus-backed entries:

S1. `floor-non-empty`
S2. `floor-names-unique`
S3. `config-paths-unique`
S4. `task-ids-unique`

1. `levels-contiguous`
2. `top-solutions-aligned`
3. `min-2-demos`
4. `tasks-exist`
5. `min-2-train-examples`
6. `rung-referenced`
7. `jump-affordable`
8. `proper-composition`
9. `double-jump-intractable`
10. `top-affordable-with-ladder`
11. `climb-budget-covers-top`
12. `top-uses-top-rung`
13. `raw-intractable`
14. `top-double-jump-intractable`
15. `rewrite-shallow`
16. `proposer-compat`
17. `distinct-train-inputs`
18. `outputs-vary`
19. `not-identity`
20. `heldout-distinct`
21. `free-param-varies`
22. `free-params-covary`
23. `constant-subterm`
24. `if-condition-varies`
25. `not-all-telescope`
26. `no-lambda-in-templates`
27. `floor-fully-exercised`
28. `primitive-necessity`
29. `hof-holes-fillable`
30. `rung-distinct`
31. `mdl-break-even`
