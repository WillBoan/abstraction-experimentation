# Why `half-param` misses its rung: the metric, not the greed (2026-07-27)

A follow-on audit of S16/S17 in [2026-07-27-mve-completion](../2026-07-27-mve-completion/notebook.md),
which found `dae9d2b5-half-param`'s rung 1 missed by governance and characterised the boundary as
"exactly V=2". Both conclusions needed a check they had not had, and both move.

Pure selector/metric arithmetic — no search, no ladder run, no testbed. Milliseconds.

## What S16/S17 established, and the two gaps

S16 separated proposer reach from governance correctly and decisively: `AntiunifyPairs` **does**
offer the arity-2 `nth(split_h(#0), #1)`, and `GreedyMDL` keeps two arity-1 specialisations. That
part reproduces exactly and is not in question. Its mechanical explanation was that a parameterized
abstraction saves less per call site, so specialisation wins at small V and "should invert once the
parameter takes enough distinct values". S17 swept V x M and concluded:

> "greedy-MDL over program size never prunes a specialisation its own generalisation subsumes —
> below V=3 that shows up as specialising instead of generalising, above it as doing both."

Two things neither did:

1. **Neither varied the METRIC.** `GreedyMDLLearnEngine`'s default is the flat `CompressionMetric`
   — 1.0 bit per primitive, definition size **ignored** — whose own docstring says it "lets the
   loop hoard marginal specialisations (observed in E3)" and names `TwoPartMDL` as the anti-bloat
   variant. Verified: `dae9d2b5-half-param` ran the flat one.
2. **Neither priced the END STATES.** They observed what greedy produced and read it as what MDL
   prefers. Greedy is explicitly myopic (`selection.py::GreedyMDL`'s own TODO names beam/joint
   selection as missing), so those are different claims.

## Log

### G1 — the real case under both metrics ([`metric_and_myopia.py`](artifacts/metric_and_myopia.py) · [`.out`](artifacts/metric_and_myopia.out))

**My hypothesis — "TwoPartMDL will recover `half`" — is REFUTED.** It mints *nothing at all*
(0 abstractions, DL 20.0 vs the flat metric's 2 mints at DL 14.0). The generalisation is not
rescued by charging definitions.

Also confirmed, since S16 asserted it: the two mints are structurally `nth(split_h(#0), 0)` and
`nth(split_h(#0), 1)` — i.e. exactly the sibling ladder's `west` and `east`. The "bind-late member
collapses into the bind-early one" claim holds.

### G2 — the greedy trajectory: the rewrite destroys the candidate

Round by round under the default metric:

| round | corpus | arity-2 generalisation | selector takes |
| --- | --- | --- | --- |
| 0 | 4x `nth(split_h(input), k)` | **ON OFFER** | `nth(split_h(#0), 0)` |
| 1 | 2x `abs0(input)`, 2x `nth(split_h(input),1)` | **GONE** | `nth(split_h(#0), 1)` |
| 2 | 2x `abs0(input)`, 2x `abs1(input)` | — | nothing improves DL; loop ends |

The generalisation is available once and never again: minting `abs0` rewrites half the corpus, and
the antiunification pair it was derived from no longer exists. So it is structurally unreconsiderable
after round 0 — latent myopia, whether or not it bites.

### G3/G5 — what MDL PREFERS vs what greedy DOES ([`optimum_vs_greedy.py`](artifacts/optimum_vs_greedy.py) · [`.out`](artifacts/optimum_vs_greedy.out))

Priced all four reachable end states (`none` / `specialise` / `generalise` / `both`) directly under
each metric, across V x M, and compared the DL-minimum with greedy's output. This is the
experiment that separates the two candidate causes.

**Under the flat `CompressionMetric` (the default, the one the batch runs):**

- The optimum is **`specialise` at every V and every M tested** (V up to 8, M up to 6).
  Generalisation is *never* DL-optimal.
- Greedy **agrees at V=2** — it reaches the true optimum, no myopia.
- Greedy **diverges at V>=3**, producing `both` where the optimum is `specialise`.

**Under `TwoPartMDL`:**

| regime | optimum | greedy |
| --- | --- | --- |
| V=2, M=2 (**the real `half-param` case**) | **none** | none — agrees |
| V=2, M>=3 | specialise | specialise — agrees |
| V>=3, M<=3 | **generalise** | generalise — agrees |
| V>=3, M>=4 | specialise | generalise / both — diverges |

## Findings

1. **The real case is handled CORRECTLY, under a proper two-part code.** At V=2, M=2 the DL-optimal
   action is to mint **nothing**: `none` 26.0 < `generalise` 27.0 < `specialise` 28.0. With four
   programs, no abstraction pays for its own definition. So `half-param`'s missed rung is not a
   governance pathology — it is a correct verdict that the evidence is too thin, which the flat
   metric hides by not charging definitions.

2. **`half` is never MDL-optimal at V=2, under either metric.** A binary parameter cannot justify a
   parameterized abstraction: two specialisations each recur enough to pay their way, and the
   generalisation still has to write the argument. The ladder's registered prediction was wrong on
   the economics, not because the selector is broken. **This is a design finding for the ladder
   method**: bind-late is the wrong decomposition for a 2-way split, and the certificate's
   `recovered` predicate is measuring intent against a learner whose job is compression.

3. **S16's stated mechanism does not hold under the metric in use.** It predicted the bias "should
   invert once the parameter takes enough distinct values". Under the flat metric it **never**
   inverts at any V tested — because a flat 1-bit-per-entry charge makes V cheap entries beat one
   entry with weaker per-site savings, indefinitely. The inversion S16 reasoned to requires a
   metric that charges definition size.

4. **S17's "boundary is exactly V=2" is a greedy artefact, not a boundary in MDL's preference.**
   Under the flat metric MDL's preference is uniformly `specialise`; what changes at V=3 is that
   *greedy stops reaching it*. So the two "pathologies either side of V=2" are one metric defect
   (never prefers generalisation) plus one search defect (adds past the optimum), not a boundary.

5. **Under `TwoPartMDL` the economics become interpretable, and non-monotone in both variables**:
   generalisation wins for **many distinct values used few times each**; specialisation wins once
   each value recurs enough (M>=4) to amortise its own definition. That is the sensible answer, and
   it is a genuinely two-dimensional boundary — neither S16's "V grows" nor S17's "V=2 line".

6. **Greedy myopia is real but is NOT what caused the real failure.** It is attributable and
   bounded: it never bites at V=2, and it appears where the corpus rewrite has destroyed a
   candidate (G2). The repo already names the fix (beam/joint selection, MACHINERY.md F4).

## Corrections to record

- S16's "both halves of the system push away from abstractions that generalise" — S17 already
  softened this; it should be narrower still. Search bias (the vocabulary tax) stands. The
  governance half is a **property of the default metric**, and reverses under the shipped
  alternative at V>=3.
- S17's headline sentence attributes to greedy-MDL what belongs to the flat metric. Both notebooks
  should point here.

## Decisions this raises (NOT taken here)

- **Should `ladder_default_config` use `TwoPartMDL`?** It is the anti-bloat variant, it makes
  governance behave sensibly at V>=3, and it correctly declines to mint on thin evidence. But the
  metric is part of `Config`, so switching moves the `run_id` of **every LEARN run in the repo** —
  every climb, every committed report. That is a deliberate, expensive call and it is the user's.
- **Is `rung_recovery` the right predicate?** It scores intent-matching. Finding 1 shows a case
  where the learner is right and the ladder is wrong; the certificate has no way to say so.

## Open / unverified

- All of G5 uses `map_color(input, c, 6)` as the V-varying shape — the same proxy S17 used. Node
  counts match the real `nth(split_h(#0), #1)` case (4-node term, 4-node template), and G1/G3
  price the real programs directly at V=2, but the V>=3 rows are proxy-only. No real ladder in the
  batch has V>=3.
- `bits_per_primitive = 1.0` is a free parameter of both metrics and was not swept; the V=2
  `none`-vs-`generalise` gap is 1.0 bit, so that corner is sensitive to it.

## Artifacts

| script | what it showed |
| --- | --- |
| [`metric_and_myopia.py`](artifacts/metric_and_myopia.py) · [`.out`](artifacts/metric_and_myopia.out) | G1-G4 — TwoPartMDL mints nothing on the real case (hypothesis refuted); the rewrite destroys the generalisation after round 0; the V x M sweep under both metrics |
| [`optimum_vs_greedy.py`](artifacts/optimum_vs_greedy.py) · [`.out`](artifacts/optimum_vs_greedy.out) | G5 — end states priced directly: flat prefers `specialise` everywhere; TwoPart's optimum is two-dimensional; greedy's divergences located |

**Runs.** None. Everything here is the proposer and selector called directly as pure functions of
`(library, retained programs)`; the retained programs are the ladder's own demo targets.
