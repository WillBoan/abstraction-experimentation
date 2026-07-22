# Higher-order depth model, and a propagation bug (2026-07-22)

**Question.** Two, arrived at while designing `.ladder` syntax for `Lam`/`Var`/`AppFn` ([LADDER-FORMAT.md](../../docs/abstraction_ladders/LADDER-FORMAT.md)):

1. Can compositional depth be computed at all when a program contains a `Lam` — and can the generation at which search finds it be predicted?
2. If so, what actually breaks for a higher-order ladder?

The immediate motivation: a ladder's whole tractability apparatus (`jump-affordable`, `raw-intractable`, the validity window) is stated in depth against `Budget.depth_limit`. If depth is meaningless once a lambda appears, a higher-order ladder can be *written* but never *certified*, which is a worse place to be than not being able to write it.

**Answer, up front.** Depth is fine. Two quantities that coincide without lambdas come apart with them, and both are computable statically. What breaks is (a) depth as a *cost* proxy, and (b) an unrelated engine bug that makes some higher-order programs unreachable at any depth.

---

## 1. The two laws

Runs: [`artifacts/depth_matrix.py`](artifacts/depth_matrix.py) → [`artifacts/depth_matrix.out`](artifacts/depth_matrix.out). Each case builds a target program, generates a task from it, then sweeps `depth_limit` upward to find the smallest one at which the engine returns that program.

- **Generation found = `compositional_depth(prog)`** — the existing `lam_as_leaf=True` default, which treats a `Lam` as an atom and never enters its body.
- **Minimum `depth_limit` = effective depth = `max over frames of (frame depth + descent)`**.

A **frame** is one enumeration context: the top level is frame 0, and each *function-hole fill* opens a child frame one descent down, because `_synthesize_for_hole` calls `budget.descend()` (`depth_limit - 1`). A curried `Lam(Lam(body))` is **one** fill, not two — the engine descends once and then wraps every binder — so binder count and descent count are different things (every `build_grid` row below has 2 binders and 1 descent).

With no lambdas there are no descents, both laws collapse to the familiar single number, and everything already in the lint stays true.

| # | Program | Depth | Raw | Frames | Eff | Min limit | Gen | Considered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | `input` | 0 | 0 | (0,0) | 0 | 0 | 0 | 4 |
| A1 | `flip_h(input)` | 1 | 1 | (1,0) | 1 | 1 | 1 | 10 |
| A2 | `flip_h(flip_v(input))` | 2 | 2 | (2,0) | 2 | 2 | 2 | 28 |
| A3 | `transpose(flip_h(flip_v(input)))` | 3 | 3 | (3,0) | 3 | 3 | 3 | 46 |
| B0 | `build_grid(height(input), width(input), lam(lam(0)))` | 2 | 3 | (2,0) (0,1) | 2 | 2 | 2 | 236 |
| B1 | `build_grid(width(input), height(input), lam(lam(read(input, $0, $1))))` | 2 | 4 | (2,0) (1,1) | 2 | 2 | 2 | 44 |
| B2 | `build_grid(height(input), width(input), lam(lam(read(input, sub($1,$1), $0))))` | 2 | 5 | (2,0) (2,1) | 3 | **3** | 2 | 572 |
| B3 | `build_grid(height(input), width(input), lam(lam(read(input, sub(height(input),1), $0))))` | 2 | 6 | (2,0) (3,1) | 4 | **4** | 2 | 4,000,000 |
| B5 | `build_grid(width(input), height(input), lam(lam(read(flip_h(input), $0, $1))))` | 2 | 5 | (2,0) (2,1) | 3 | 3 | 2 | 171 |
| B4 | `flip_h(build_grid(width(input), height(input), lam(lam(read(input, $0, $1)))))` | 3 | 5 | (3,0) (1,1) | 3 | **3\*** | **3\*** | 862\* |

\* only with example propagation disabled — see §3. As shipped, B4 is unreachable at any `depth_limit`.

Column definitions: **Depth** = `compositional_depth(p)`; **Raw** = `compositional_depth(p, lam_as_leaf=False)` (plain syntactic tree depth, entering lambda bodies, counting each `Lam` node); **Frames** = `(depth within frame, descent)` per frame; **Eff** = the max of `depth + descent`.

What the sweep covers: non-higher-order depths 0–3 (A0–A3); lambda body depth swept 0→3 against a fixed outer depth of 2 (B0–B3), so both the outer-binds and body-binds regimes appear; a same-effective-depth pair differing only in where the higher-order call sits (B5 root vs B4 wrapped); and curried binders throughout.

### Not measured

Three shapes have derived numbers only, because each needs a task where that exact program is uniquely cheapest and I could not cheaply construct one:

- **descent 2** — `map(lam c. head(map(lam d. d, cells(input))), cells(input))`: frames `(2,0) (3,1) (0,2)`, effective **4**. Note it returns `list[color]`, so it could not be a task solution unwrapped.
- **point-free `PrimRef` fill** — a `PrimRef` is a leaf and opens *no* frame, so effective depth equals compositional depth. No type-valid example exists on the current substrate: `cells` yields `list[color]` and there is no `(color) -> …` primitive to map with. (An earlier draft of this table showed `map(&flip_h, cells(input))`, which is ill-typed — `flip_h` is `(grid) -> grid`. `compositional_depth` does not typecheck, so nothing caught it.)
- **`If`** — a constructor like `Apply` (+1), opening no frame; `if eq(height(input), width(input)) then flip_h(input) else input` is depth 3.

## 2. Depth is not a cost proxy

The finding that actually matters for ladders. **B1 and B3 have identical compositional depth (2) and identical generation (2), and cost 44 versus 4,000,000+ considered** — five orders of magnitude, invisible to depth, all of it sub-search work.

The Ladder amortization argument is "cost grows steeply with depth, so R shallow terms beat one deep term". On a higher-order floor the growth is dominated by work no depth number sees, so `d_raw` stops standing in for cost. A higher-order ladder could get a real validity window today (swap `compositional_depth` for effective depth in the sandwich checks — the `no-lambda-in-templates` advisory could become an actual check), but **not** a trustworthy amortization ratio. That is a measurement problem, not a syntax one, and it is the thing to design before building higher-order rungs.

## 3. The propagation bug

Repro: [`artifacts/propagation_repro.py`](artifacts/propagation_repro.py) → [`artifacts/propagation_repro.out`](artifacts/propagation_repro.out).

B4 — `flip_h(build_grid(…))`, effective depth 3 — is **not found at `depth_limit` 3, 4 or 5**, at a 4,000,000 guard. B5 has the same effective depth, the same floor and the same 2-binder lambda, and solves at limit 3 after 171 candidates. The only difference is that B4 wraps the higher-order call while B5 has it at the root. So this is not a depth effect.

Isolated by keeping `build_grid`'s `body_sampler` contexts and returning `body_target=None` (the documented "complete baseline", ARCHITECTURE.md §8):

```
propagation ON  (as shipped) depth_limit=3/4/5: solved=False  considered=118 (identical at every limit)
propagation OFF (baseline)   depth_limit=3:     solved=True   gen=3  considered=862
```

Note `considered` is *identical* at limits 3, 4 and 5 with propagation on: the `build_grid` subterm is never produced at all, so there is nothing for the extra depth to compose over.

### Mechanism

`enclosing_target` at the top level is the **task's** outputs (§7). A `build_grid` being composed at the top level cannot know it will later be wrapped — bottom-up search has no notion of a required signature for an interior position. So it receives the task output as its target, derives a `body_target` from it, and the correct body is discarded by `entry.sig != body_target`. The required signature for that position is `flip_h⁻¹(task output)`, which nothing computes.

### Why this is a bug, not a designed trade-off

§8 is titled "**complete baseline + propagation optimization**": propagation is framed as an optimization over a complete baseline, i.e. a *sound* restriction that only skips bodies that provably cannot work. A sound restriction loses nothing, so the contract does not license this.

More pointedly, §7 explicitly anticipates the wrapped case and claims propagation stops there:

> propagation stops the moment a hole's result is consumed by an ordinary (non-hole) parameter of another primitive rather than compared directly against the top-level target — e.g. `map`'s `List[b]` result feeding `render`'s `List[Object] → GRID` argument never sees a target, **because `List[b]` cannot unify with `GRID`**

The intent is right; the guard is a **type** check standing in for a **semantic** precondition. It stops propagation only when the wrapper changes the type. `flip_h` is `GRID → GRID`, so the types unify, the guard passes, and a wrong target flows down. The same holds for most of the D4 group, `map_color`, and every other same-type grid transform.

**Blast radius.** Any task whose solution wraps `build_grid`, `map`, `filter`, `fold` or `sort_by` in a same-type transform, on any floor with `function_hole_fill_mode="lambda-synthesis"`. Currently latent: no committed ladder uses a higher-order floor.

### Options (none free; not decided)

1. **Always use the baseline** — correct, but propagation is what makes higher-order search tractable (§8: "far fewer candidates").
2. **Union propagated + baseline** — identical to (1); the propagated set is a subset.
3. **Accept it as an explicit inductive bias** and document it: higher-order primitives are findable only at the root of a solution. This is the *de facto* behavior today; §7's reasoning suggests it was not intended.
4. **Implement inverse-semantics propagation** — invert the wrapper for the true target. §7 already names this as unbuilt, and `BottomUpSearchEngine.inverse_semantics_propagation: bool = False` exists to mark the gap. It was created for the *type-mismatch* case; this finding shows the same machinery is needed for the same-type case, which the current gate does not even route to it.

## Decisions and open questions

- **Decided:** the higher-order depth model is not a blocker for `.ladder` syntax. Effective depth is a well-defined, cheap, static reachability predictor and reproduces every measured row.
- **Open:** which of the four propagation options to take. No engine behavior was changed here.
- **Open:** whether to implement `effective_depth` in `analysis/depth.py` and use it in the sandwich checks. It is currently only in this notebook's artifact.
- **Open:** the cost model for higher-order ladders (§2). Until `d_raw` predicts cost on a higher-order floor, such a ladder can be certified for reachability but not read for amortization.
