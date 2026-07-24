# Ladder drafts

Exploratory `.ladder` files: decompositions sketched for a task, **not** batch members.

A draft is deliberately incomplete — it may propose primitives that do not exist, and it need not have demonstrating tasks. It is therefore kept out of `registry/`, which the batch scans: nothing here is discovered by `arc-lab taskgen`, `run-ladder`, or `lint-ladder` with no argument.

Lint one by path, with `--draft` to take proposed primitives at their declared signatures:

```
uv run arc-lab lint-ladder src/arc_lab/program_search/ladders/drafts/<name>.ladder --draft
```

That runs everything that is signature-level — types, scopes, arity, the rung spine — and returns the unknown primitives as a worklist. It skips everything that needs a corpus, because an assumed primitive has no implementation and so no task can be evaluated.

Promotion is a move into `registry/` once the primitives exist and the tasks are written; the ladder gets its `alN-<slug>` identity and a row in `docs/abstraction_ladders/LADDERS.md` then.
