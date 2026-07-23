# Ladder editor tooling plan — highlighting, diagnostics, LSP, formatter (2026-07-23)

**Status: planned, not started. Chosen starting scope = the Light path (see below): full foundations, deferred features.** This is the implementation plan for `.ladder` editor tooling, agreed 2026-07-23 after an external design review (rev 2 incorporates that review; the adjudication further down records what was adopted vs declined and why). The full 10-phase catalog (Phases A–J) is the reference superset; the **Light path** section names the subset we build first and the seams that keep the deferrals debt-free. Companion to the format spec `LADDER-FORMAT.md`; independent of the experimental program in `AL-PLAN-2026-07-23.md`.

## Context

`.ladder` files (spec: `LADDER-FORMAT.md`) are the single source of truth for ladder identity — 20 registry ladders + drafts, hand-authored. Today: no highlighting, line-only positions, fail-fast parser, comments discarded at lex time, ~29 lint checks emitted procedurally inside a 470-line `LadderSpec.lint()`.

Goal: TextMate + semantic-token highlighting, live error/warning squiggles with precise ranges, document symbols / go-to-definition / hover, auto-formatting — via a pygls language server and a thin VS Code extension, with CLI and LSP as **sibling adapters over one shared pipeline**. Underneath: spans everywhere, comment trivia, error-tolerant parsing, and checks reorganized into a data registry ("machinery is data", like `PRESETS`/`STUDIES`).

## Light path — the chosen starting scope (2026-07-23)

**Principle: cut features, never foundations.** The Light path drops everything that is purely _additive_ later (a deferred feature costs only that feature when it lands) and keeps everything _foundational_ (anything that, hacked now, would have to be torn out and redone). Two things are foundational and are therefore done fully and properly here — no shortcuts:

- **Position handling** — real spans through the model + the expression source-map (UTF-8-byte-offset to code-point to file-range). Explicitly **not** the slug-string-search line-finder hack; that would be exactly the kind of debt we later unwind.
- **The check architecture** — the ~29 `LadderSpec.lint()` checks move into a **shared parent class now, not after.** Design settled 2026-07-23: a `LadderCheck` **ABC** that all checks subclass, each carrying its metadata as `ClassVar`s (`code`, `category`, `default_severity`, `stage`, `summary`, `message_template`) and its logic as a `run(self, ctx: CheckContext) -> Iterable[CheckResult]` method (the pylint shape — metadata and logic co-located in one class body). This is **distinct from the diagnostic value type**: `LadderDiagnostic`/`CheckResult` remain a single shared *value* class each and are **never** subclassed per kind (variety lives in the `code` field — per-kind diagnostic subclasses are the anti-pattern the reviewer and we both rejected). Two axes, two decisions: `LadderCheck` = the *checker*; `LadderDiagnostic` = the *emitted value* (one class). Execution order is an explicit `CHECK_PLAN: tuple[LadderCheck, ...]` (instances, pinned to today's emission order — never subclass-discovery or import order). **Refinement (2026-07-23, on deeper reflection):** the boundary between a `LadderCheck` and an inline descriptor is **emitted-vs-rule, not parse-vs-lint** (see the "Diagnostic production model" subsection below). A diagnostic is a `LadderCheck` (`stage`-tagged SYNTAX / RESOLVE / CORPUS) when it is a **predicate over a completed model**, and inline-emitted (descriptor-only) when **discovered mid-traversal** during work the pass must do anyway. That promotes ~7 structural well-formedness codes (`duplicate-task-id`, `section-order`, `name-mismatch`, `rung-shadows`, `duplicate-floor-primitive`, `duplicate-config-path`, `reserved-config-path`) into `stage=SYNTAX` `LadderCheck`s — reached in the Light path by separating tree construction from well-formedness validation — so `LadderCheck` is ~36 subclasses across three stages, and `DIAGNOSTIC_DESCRIPTORS` holds only the truly inline-emitted codes (lexical/brace-recovery + elaboration-local type/arity/unknown-name). Both still feed one `code -> metadata` table. Mild note: these stateless, declarative check classes lightly bend the repo's "machinery is data, no solver classes" rule — accepted deliberately for locality.

**In scope now (built fully):** Phases **A, B, C, E1, F, G**.

- **A** — vertical slice (TextMate grammar + minimal pygls + extension): the whole `VS Code -> extension -> uv -> pygls -> parser` chain working end-to-end on day one, over the _current strict parser_.
- **B** — the real `LadderDiagnostic` + descriptor registry, used from day one (even Phase A's strict-error path emits the real type — nothing throwaway).
- **C** — lossless positions: spans on every model entity, `Range`/`Position`/`SourceText`/`SourceMap`. Strict parser still raises (see seam 1).
- **E1** — expression position mapping only (the `expr.py` half of Phase E): a type error inside a solution underlines the offending token, not the whole line. The fiddliest single piece, and non-negotiable for "full position handling."
- **F** — the full check-architecture refactor (registry + `CHECK_PLAN` + `CheckResult` + `AnchorIndex`), so findings carry real ranges.
- **G** — the shared `lint_source` pipeline, CLI `--json`, and the LSP server upgraded from the Phase-A shim to precise ranges.

**Deferred (additive; nothing to unwind):** Phases **D, E2, H, I, J**.

- **D** — error-tolerant parsing / partial documents / invalid nodes. _Accepted UX limitation until it lands:_ the file goes dark past the first parse error. Debt-free to add because of seam 1.
- **E2** — tolerant resolution + taint (symbol states, `unavailable-name`); ships with D. In the Light path `load.py`'s strict `resolve()` is left as-is.
- **H** — semantic tokens, document symbols, go-to-definition, hover. Purely additive LSP features; TextMate covers baseline coloring in the meantime.
- **I** — the formatter (+ its `LADDER-FORMAT.md` amendment).
- **J** — extension integration tests + packaging hardening (keep only the F5 smoke test).

**The three seams that make the deferrals debt-free (build these in even though the payoff is later):**

1. **Parse-error seam.** Every parse/resolve error site goes through one `_error(code, range, ...)` helper that _raises_ in the Light path. Phase D flips that single helper to _append to a sink_ and adds resync around it — a control-flow change at one point, never a type or model rewrite. The "one engine, never two parsers" invariant holds from the start.
2. **Real diagnostic types from day one.** A/B emit `LadderDiagnostic` with real `Range`s (line-spanning at first; precise once C/E1/F land). Adding tolerance later changes _how many_ diagnostics and _whether the document is partial_ — never their types or the pipeline shape.
3. **One lexer rewrite.** Phase C rewrites `_scan`/`_logical_lines` once to emit source maps. Capturing comments as a flat `Comment(text, range)` list in that same pass (no attachment classification — that is formatter-specific, defer it) is a cheap hedge that spares a second lexer edit when the formatter (I) arrives. The only piece of a deferred phase worth pre-paying.

**Honest sizing:** this is _not_ the minimal "Phase A only" slice — C, E1, and F are among the heaviest pieces in the whole plan. It is a deliberate "full foundations, deferred features" scope: every line it builds is load-bearing for the rest, and the cut falls entirely on additive layers (tolerance, navigation, formatting). Phase A still ships visible value first; each later phase upgrades precision without removing anything.

Phase headers below are tagged `[LIGHT]` / `[DEFERRED]` accordingly.

## Diagnostic production model (the emitted-vs-rule principle)

The pipeline is a tower of passes, each `model_n -> (model_{n+1}, diagnostics)`:

```
SourceText -> [scan] tokens+trivia -> [parse] document (+ error nodes) -> [resolve] semantic model -> [check] findings
```

Every diagnostic is produced in one of two ways — and **this, not the pass it happens in, decides its representation**:

- **Emitted** (procedural, inline): discovered *mid-traversal* during work the pass must do anyway — lexing, brace recovery, `ast.parse`, type unification. It lives at the emission site with rich local context; metadata sits in `DIAGNOSTIC_DESCRIPTORS`; no rule object could re-derive it from a stable model without redoing the traversal. E.g. `unclosed-block`, `bad-grid`, `bad-expression-syntax`, `type-mismatch`, `arity-mismatch`, `unknown-name`.
- **Rule** (declarative): a **predicate over a completed model** — the document, the resolved model, or the resolved+corpus model. A `LadderCheck` subclass, `stage`-tagged by which model it needs. E.g. the ~7 structural well-formedness codes (over the document) and the 29 lint checks (over the resolved+corpus model).

Two consequences:

1. **`LadderCheck` is one hierarchy across all three model stages** (SYNTAX / RESOLVE / CORPUS), not a lint-only concept. `stage` doubles as the gating tier: a CORPUS rule is skipped — and named in `skipped_checks` — when no corpus is available. This subsumes the earlier `tier` field.
2. **The tolerant-parser refactor (Phase D) is exactly when to revisit the emitted/rule line — but most of the move happens earlier.** Strict fail-fast parsing is what *forces* a structural fact to be emitted mid-parse (the parser bails before a full document exists). The Light path pre-empts this by **separating tree construction from well-formedness validation**: the parser builds the whole document (raising only on truly-unrecoverable lexical/brace errors), the `stage=SYNTAX` rules run over it, and the strict wrapper raises if any fired. So the ~7 structural codes become rules *now*, in the Light path — a modest, debt-free restructure that is also the target shape. Phase D then adds only **partiality** (the same SYNTAX rules run over a *partial* document), not a re-classification. This is the "refactor how files get loaded/parsed/linted" the pipeline was always heading toward; the seams (`_error`, one value type, one `code -> metadata` table) are built so it lands additively.

Requirement this places on Phase F: `CheckContext` must expose the parsed `document` (for SYNTAX-stage rules), not only the `LadderSpec`.

## Review adjudication (rev 2 changes from rev 1)

Adopted from external review:

- **Vertical slice first** (Phase A): TextMate + minimal pygls server over the _current strict parser_ + extension skeleton, before any invasive refactor. De-risks env discovery, stdio hygiene, packaging; delivers value immediately.
- **Explicit invalid nodes**, never dropped entries or `name=""` sentinels.
- **Taint-aware resolution**: symbol states RESOLVED / DECLARED_BUT_INVALID / ABSENT; `unavailable-name` distinct from `unknown-name`; checks skip (not lie) on upstream failure; no silent config-fallback linting.
- **Position corrections**: `ast` `col_offset` is a **UTF-8 byte offset** (needs a byte-to-codepoint helper, tested on non-ASCII); internal ranges half-open 0-based code points; LSP conversion via pygls's per-document position codec, not a hand-rolled second subsystem; never clamp internally-generated ranges (clamp only external input).
- **Diagnostic identity**: LSP `code` = bare stable code (occurrence goes in message + `data` + a domain field; `.slug` only for legacy CLI text); `LadderDiagnostic` stays lean (category/href/summary looked up from the descriptor registry, not duplicated per-instance); `RelatedLocation` carries an optional document id.
- **Explicit `CHECK_PLAN` tuple** for execution order (not decorator/import-order side effects); separate `DIAGNOSTIC_DESCRIPTORS` (all codes incl. syntax/resolve) from executable checks.
- **Lazy `CheckContext`** via cached properties so structural-tier linting never computes corpus/unfold data.
- **Formatter fixes**: invariant is `semantic_projection(parse(format(t))) == semantic_projection(parse(t))` (+ comment text/attachment preserved) — not document equality; embedded expression fragments and grid literals preserved **byte-for-byte** initially; whole-document edit; LF-only (LEX-1); ignore client `FormattingOptions` (canonical style).
- **CLI `--json` is a domain format** (path, string severities, occurrence), not raw LSP wire; LSP is one adapter of it.
- **LSP mechanics**: analysis-snapshot cache shared by all features; debounce _before_ starting the worker + generation check before publish; version-stamped `publishDiagnostics`; stdout carries only JSON-RPC (logging to stderr); `expected_name` check only for `file:` URIs; semantic tokens sorted/non-overlapping/single-line.
- **Feature priority**: document symbols, then go-to-definition, then hover, **before** semantic tokens (TextMate already covers baseline coloring).
- **Commit policy**: every commit leaves `make check` green; a _phase_ is a compatibility boundary, and large phases contain several commits.
- **Diagnostic cap** (~100) for pathological input; arbitrary-input never-raises property tests; latency budgets (parse p95 < 20 ms, resolve+structural < 100 ms, tokens < 50 ms; corpus tier measured, save-triggered).

Declined / adjusted, with reasons:

- **Full parallel CST hierarchy**: `LadderDocument` already _is_ the syntax layer (semantics live in `LoadedLadder`/`LadderSpec`; documents are not hashed, serialized, or part of run identity). Adopting the reviewer's stated minimum instead: all span/trivia fields are `compare=False`, plus explicit invalid-node collections. A second mirrored node hierarchy would double the model for no consumer.
- **"Single-file model conflicts with corpus-backed checks"**: misread — `draft_spec` _generates the corpus in memory from the document itself_ (declared solutions + literal grids). FULL tier is genuinely single-file; the plan notes FULL always runs on the in-memory buffer text.
- **SARIF output**: deferred (single-user research repo; `--json` suffices). Marketplace packaging: out of scope — internal extension, explicit in its README.
- **Floor `use` column alignment**: kept in the formatter — it is the committed house style in all 20 registry files; blocks are ~5-10 lines so diff churn is bounded.

## Decisions locked before review (unchanged)

One diagnostic value type (no subclass-per-kind); frozen descriptor registry; tiered tolerance; strict mode = projection of the tolerant engine (one engine, never two parsers); pygls 2.x + typed lsprotocol; `arc-lab lsp` subcommand; extension at `editors/vscode-ladder/`; formatting in scope with a deliberate `LADDER-FORMAT.md` amendment; Conventional Commits.

## Hard invariants (every commit)

1. `make check` green (ruff, mypy `--strict`, full pytest).
2. `test_load.py::test_every_ladder_regenerates_its_committed_testbed` — all 20 testbeds byte-identical.
3. `test_expr.py::test_every_batch_template_round_trips` preserved.
4. `lint-ladder` exit codes 0/1/2 preserved.
5. After Phase D: `parse_source(arbitrary_text)` never raises; every range half-open, ordered, in-bounds.
6. After Phase E: a declared-but-invalid name is never reported as absent; checks skip (never silently substitute) on upstream failure.
7. After Phase I: `semantic_projection(parse(format(t))) == semantic_projection(parse(t))`; comment text + attachment preserved; format idempotent.
8. `arc-lab lsp` stdout contains only JSON-RPC frames.

## Key current-code facts

- `lang/errors.py`: `LadderFormatError(ValueError)` `.detail`/`.line` (1-based|None); `at_line()` back-fill; ~80 raise sites; `load._template` catches `(ValueError, KeyError)` — keep ValueError subclassing.
- `lang/parse.py` (497 ln): `_scan` (per-line char loop; strips comments; discards columns) then `_logical_lines` (`" ".join`, start line only, no source map) then `_build_tree` (braces) then `parse_document`. Model dataclasses carry a single `line: int`.
- `lang/expr.py` (532 ln): `ast.parse(text.strip(), mode="eval")`; col_offsets and `SyntaxError.offset` never read. `lang/type_syntax.py`: `_Cursor` over `findall` (switch to `finditer` for offsets).
- `lang/load.py`: `resolve()` fail-fast except `_floor` (collects, then one aggregate raise). `shape.py`: `LintFinding(check, ok, detail, severity: str)`; `LadderShape(..., findings, skipped_checks)`.
- `spec.py::lint(corpus_backed=True)`: ~29 check families (slugs like `rung-referenced[name]`; corpus-gated families recorded in `skipped_checks`); also derives `RungShape`s/`validity_window`/`is_chain` used by `render()`, `run.py:108`, CLI draft report.
- Consumers bypassing `lang/__init__`: `registry/__init__.py`, `cli/lint_ladder.py`, `cli/probe_ladder.py`, `taskgen/generators.py:312` (lazy), `checks.py:389` (lazy).
- `pyproject.toml`: hatchling src layout; `[project.scripts] arc-lab = "arc_lab.cli.main:app"`; PEP-735 dev group; ruff `src=["src","tests"]`, `extend-exclude=["experiments"]`; mypy strict `files=["src","tests"]`.

---

## Phases (compatibility boundaries; several green commits each where noted)

### Phase A — Vertical slice: highlighting + live line-level diagnostics first `[LIGHT]`

Proves `VS Code -> extension -> uv env -> pygls -> parser` end-to-end before any refactor.

- pyproject: `[project.optional-dependencies] lsp = ["pygls>=2.0,<3"]`; add pygls to the dev group (mypy strict + CI cover it). Narrow mypy override only if pygls internals leak `Any` (never for lsprotocol).
- `ladders/lsp/server.py` (minimal): on open/change/save, run the **current strict** `parse_document`+`resolve`+`draft_spec(...).lint()` in `asyncio.to_thread`; `LadderFormatError` becomes one diagnostic spanning the whole offending line (from `.line`); lint findings become line-0 diagnostics with `check` as code. All logging to stderr; nothing else on stdout.
- `cli/lsp.py`: `arc-lab lsp` (stdio; `--tcp` for debug), lazy pygls import with an "install the lsp extra (`uv sync --extra lsp`)" error; register in `cli/main.py`.
- `editors/vscode-ladder/`: `package.json` (language `ladder`, ext `.ladder`; grammar `source.ladder`; settings `ladder.server.command` (string, default `"uv"`), `ladder.server.args` (default `["run","arc-lab","lsp"]`), `ladder.server.cwd` (default workspace folder), `ladder.trace.server`), `language-configuration.json` (`#` line comment, brackets, auto-close), `syntaxes/ladder.tmLanguage.json`, `src/extension.ts` (vscode-languageclient/node), `tsconfig.json`, `esbuild.js` bundling to `dist/extension.js`, `.vscodeignore`, `.vscode/launch.json` (F5), `.gitignore`, README (internal extension; F5 or `vsce package` + local install; NOT for Marketplace).
- TextMate grammar: `#.*$` comments; `^\s*(ladder|config|floor|rung|distractor|top)\b`; `\b(task|heldout|use|solution|train|test)\b`; definition line (name = `entity.name.function`, params = `variable.parameter`, `->`/`=` operators); `\b[A-Z]\w*\b` = `entity.name.type` (capitalization is load-bearing, spec section 3); `input` = `variable.language`; `true|false`; numerics; strings; task ids = `entity.name.tag`.
- Latency baseline: a small non-slow test that times parse / resolve / full lint on the largest ladder (al14) and records the numbers (budgets: parse < 20 ms, structural < 100 ms; corpus tier measured — informs the tier policy).
- Repo config: ruff `extend-exclude` += `"editors"`.
- Verify: F5, open `al1-mirror.ladder`, highlighted; break it, squiggle on the right line; `make check` green.

### Phase B — Diagnostic primitives (`diagnostics/` package; imports nothing from lang/checks/lsp) `[LIGHT]`

- `positions.py`: `Position(line, character)` — 0-based **code points**; `Range(start, end)` — **half-open**, validity-asserted; `SourceText(text)` with `line_start_offsets`, slicing, offset/Position conversion; `utf8_byte_to_codepoint(line_text, byte_off)` (for `ast` offsets — tested on non-ASCII); `.human()` renders "line 12:5" (1-based) for CLI.
- `diagnostic.py`: `Severity` (domain enum; LSP mapping lives in `lsp/convert.py`); `RelatedLocation(document: str | None, range, message)`; lean `LadderDiagnostic(code, range, message, severity, occurrence=None, related=(), data=None)` — category/summary/docs looked up by `code` in the registry.
- `descriptors.py`: frozen `DiagnosticDescriptor(code, category, default_severity, template, summary, docs_anchor)`; `DIAGNOSTIC_DESCRIPTORS: dict[str, DiagnosticDescriptor]` as an **explicit dict literal** covering syntax + resolution codes (~35 for ~80 raise sites: `unclosed-block`, `bad-config-line`, `unknown-primitive`, `signature-mismatch`, `type-mismatch`, `unknown-name`, `unavailable-name`, `solution-evaluation`, ...). `Category` enum. Uniqueness + template-render tests. Note: this table holds only the **non-check** codes; check-code metadata lives on the `LadderCheck` subclasses (Phase F) as `ClassVar`s. A single `code -> metadata` lookup is assembled from both sources (for docs generation and severity/message defaults).
- `sink.py`: `DiagnosticSink.add(code, range, *, occurrence, severity, **args)`; `.has_errors`; `MAX_DIAGNOSTICS = 100` cap (cap emission, record truncation).
- Legacy mapping `{"error": ERROR, "warn": WARNING}`; renderers keep printing `ERROR`/`warn`.
- Tests: `tests/program_search/ladders/diagnostics/` — ranges, SourceText, UTF-8 helper (astral-plane cases), descriptor registry.

### Phase C — Lossless syntax layer (multiple commits; still strict/raising) `[LIGHT]`

- `lang/source.py` replacing `_scan`/`_logical_lines`: `Comment(text, range, attachment)` where attachment is STANDALONE or TRAILING(statement idx) — classified during the scan (cheap; needed by the formatter); `SourcePiece(logical_start, logical_end, source_range | None, anchor)` — `source_range=None` marks synthetic join spaces, anchored at the preceding physical end; `SourceMap(pieces)` with `position()`, `range(start, end)` (union of source ranges; wholly-synthetic ranges become zero-length at the anchor), `slice()`; `Statement(text, map, range)`; `scan_source(text)`.
- Model entities gain spans **as `compare=False` fields** (documents remain the syntax layer; equality/serialization untouched), keeping `line` as a derived property so existing call sites compile: `FloorEntry` +`span, name_span, signature_span`; `ConfigEntry` +`span, path_span, value_span`; `TaskBlock` +`span, header_span, id_span, solution_span, solution_map, grid_spans`; `RungBlock` +`span, header_span, body_span, body_map`; `DistractorBlock` +`span, label_span`; `LadderDocument` +`header_span, name_span, comments`.
- `type_syntax._Cursor`: `findall` becomes `finditer` storing `(token, start, end)`; `DefinitionHeader` +`name_span, param_spans, return_type_span` (fragment-relative, composed by callers). New `errors.FragmentError(detail, start, end)` (half-open code-point offsets); `parse.py` maps through the statement map and re-raises byte-identical legacy `LadderFormatError` (no observable change).
- Tests `lang/test_source.py`: property over all 20 registry ladders (`map.position(i)` points at the physical char equal to `text[i]`, synthetic pieces excepted); plus generated cases: non-ASCII, no final newline, escaped quotes, `#` inside strings, comments between continuation lines, empty continuations, very long lines. (CRLF: LEX-1 mandates LF; a non-LF file gets a diagnostic in Phase D, not silent support.)

### Phase D — Tolerant parser `[DEFERRED]`

- `ParseResult(document, invalid: tuple[InvalidSyntax, ...], diagnostics)` — document always present; **malformed constructs are represented, not dropped**: `InvalidSyntax(section_kind, span, header_span, recovered_name: str | None, code)` collected per document (semantic projection ignores them; editor features and the formatter see them; no `name=""` sentinels, no `| None` model fields).
- `parse_source(text, *, expected_name=None) -> ParseResult` never raises for arbitrary text. Recovery: lexer never raises (unbalanced brackets at EOF get a diagnostic + best-effort flush); tree pass skips stray `}`, auto-closes unclosed blocks at EOF (diagnostic per open line), mid-line brace gets a diagnostic and is treated as a statement; section parsers emit-and-continue, resync at next statement / next `}`; out-of-order sections parsed but flagged; a bad task field skips that line only.
- Strict wrappers `parse_document`/`parse_ladder_file` unchanged in signature: raise `LadderFormatError` from the first ERROR in **compatibility order** (legacy emission order, kept distinct from presentation order = position-sorted).
- Tests: `lang/test_tolerant_parse.py` — port inputs from `test_malformed_documents_are_rejected` asserting (code, range) AND surviving content; multi-error ordering; never-raises + all-ranges-valid property test over mutated/truncated registry sources; diagnostic cap. Keep 2-3 strict-raise cases (`line N:` message shape).

### Phase E — Expression positions `[LIGHT: E1]` + tolerant resolution `[DEFERRED: E2]`

Split for the Light path: **E1** (expression position mapping) ships; **E2** (tolerant resolution + taint) defers with Phase D. In the Light path `load.py`'s strict `resolve()` is left as today apart from routing its raise sites through the `_error()` seam.

**E1 `[LIGHT]`**

- `expr.py`: raise sites (~30) become `self._fail(node, msg)` using `node.col_offset`/`end_col_offset` **converted from UTF-8 bytes to code points** via the Phase-B helper; `SyntaxError.offset` (1-based _characters_ — a different conversion path) handled separately; lstrip delta tracked; single `ElaborationError(detail, start, end)` unifying `FragmentError`. Callers compose file ranges via `body_map.range(...)` / `solution_map.range(...)`.
- Tests: `lang/test_expr_positions.py` (`text[range]` equals the offending token; multi-line continuation-joined solutions; non-ASCII in an expression; SyntaxError offsets).

**E2 `[DEFERRED]`**

- `load.py`: `resolve_source(document, *, assume_missing) -> (ResolvedLadder, diagnostics)` with **explicit per-entity status**, not bare `| None`:
  - `RungResolution(syntax, template: Program | None, status: ResolutionStatus, ...)`; `SymbolState` = RESOLVED / DECLARED_BUT_INVALID / ABSENT.
  - Taint rules: a reference to a failed rung reports `unavailable-name` (+ related info pointing at the failed header), never `unknown-name`; a failed config override means the affected downstream checks are _skipped and named_ (no silent lint-against-defaults); a rung with any unresolved solution has its demonstrations skipped; bounded secondary diagnostics (suppress predictable cascades, keep genuinely independent analyses running).
  - `_floor` per-entry diagnostics anchored at `name_span`/`signature_span`; resolvable primitives still form the library.
- Strict `resolve() -> LoadedLadder` keeps its exact signature/raise semantics as a projection (raise on any ERROR; compatibility order). Registry/taskgen/probe/run untouched. Test strict parity across the full malformed fixture set (tolerant discovery order may differ — the projection pins compatibility order).
- Tests (E2): taint tests (broken rung: later rungs resolve, `unavailable-name` not `unknown-name`). (E1's `lang/test_expr_positions.py` is listed under E1 above.)

### Phase F — Check migration (several commits: descriptors+adapter, context, extraction, anchors, legacy removal) `[LIGHT]`

- First commit is the behavior-preserving restructure: `checks.py` moves to `checks/evaluation.py`; extract the `lint()` body to `checks/run.py::lint_spec` (cut-paste, `self` to `spec`; helpers move alongside; `lint()` delegates).
- `checks/context.py`: `CheckContext(document, spec, corpus_backed, anchors)` — exposes the parsed `document` (for `stage=SYNTAX` rules) alongside the `spec` — with **`cached_property` lazy derivations** (`consumer_programs`, `inlined_consumers`, `unfolded_templates`, `unfolded_stated`, `unfolded_by_id`, `by_id`, `train_inputs`, `probe_inputs`, `full_lib`, `ref_limit`, `derived`) — the structural tier never computes corpus/unfold data (non-frozen, non-slots class; it is ephemeral).
- `checks/derive.py::derive_shape` — `RungShape`s, `raw_depth_profile`, `validity_window`, `is_chain` separated from findings (consumed by `render()`, `run.py`, the CLI draft report).
- `shape.py`: `LintFinding` becomes `CheckResult(code, occurrence, ok, message, severity: Severity, anchor: Range | None)` + `.slug` (`code` or `code[occurrence]`, legacy display only). `LadderShape` keeps its fields; `.ok` = no failed ERROR.
- `checks/base.py`: the shared parent class `LadderCheck(ABC)` — `ClassVar`s `code`, `category`, `default_severity`, `stage` (SYNTAX / RESOLVE / CORPUS — the model the rule runs over; doubles as the gating tier), `summary`, `message_template`; abstract `run(self, ctx: CheckContext) -> Iterable[CheckResult]`. ~36 subclasses across the three stages (see the Diagnostic production model note): the ~7 `stage=SYNTAX` structural well-formedness rules over the document, plus the RESOLVE/CORPUS rules (the 29 lint checks) — in `checks/structural.py` (+ subclasses wrapping the `checks/evaluation.py` cores, which stay independently unit-testable). Metadata and logic co-located in one class body (pylint shape). The genuinely inline-emitted codes (lexical/brace-recovery + elaboration-local type/arity/unknown-name) are **not** `LadderCheck`s — they stay in `DIAGNOSTIC_DESCRIPTORS`.
- `checks/plan.py`: `CHECK_PLAN: tuple[LadderCheck, ...]` — an **explicit ordered tuple of check instances pinned to today's emission order** (posture-lock stability); order is the tuple, never subclass-discovery or import order. Runs in stage order (SYNTAX rules first, then RESOLVE, then CORPUS). `ctx.result(self, ...)` reads the calling check's `ClassVar`s for code/severity/template. Gating via each check's `stage` (CORPUS rules skipped and named when no corpus); skipped codes recorded with today's exact strings. Per-finding severity overrides (`proposer-compat`, `constant-subterm`) pass an explicit `severity=` to `ctx.result`. Check-code metadata (from the `ClassVar`s) merges into the one `code -> metadata` table alongside `DIAGNOSTIC_DESCRIPTORS`.
- `checks/anchors.py`: `AnchorIndex.from_document(doc)` (`file()`, `rung_name()`, `task()`, `solution()`, `config()`, `floor_use()`, `param()`); `AnchorIndex.empty()` for programmatic specs; `anchor=None` falls back to the file header. Anchor mapping: rung-family checks to rung `name_span`; task-plan checks to `header_span`/`grid_spans`; constancy/conditional to `solution_span`; free-param to `param_spans`; floor advisories to the `use` line `name_span` (per-occurrence granularity improvement, tests updated deliberately).
- Prerequisite awareness: checks consult resolution status and yield skips rather than findings about substituted programs.
- Tests: `test_spec.py` assertions `(f.check, f.ok)` become `(f.code, f.occurrence, f.ok)`; the posture lock likewise; new `test_checks_registry.py` (every legacy family covered, codes unique, ERROR templates render, `CHECK_PLAN` order equals legacy order).

### Phase G — Shared pipeline + CLI adapter + generated docs; LSP goes precise `[LIGHT]`

- `ladders/pipeline.py`: `LintTier` (SYNTAX/RESOLVE/STRUCTURAL/FULL); `LintRun(document, invalid, resolved, shape, diagnostics, skipped)`; `lint_source(text, *, expected_name=None, tier=FULL, assume_missing=False)`. FULL = in-memory corpus via `draft_spec` (single-file by construction — the corpus is generated from the document). Diagnostics returned in deterministic emission order with a sequence number; **each adapter sorts for itself** (CLI: legacy order; editor: position; docs: code).
- `cli/lint_ladder.py` over the pipeline: same text layout + `_Outcome` exit codes; load failures print per-diagnostic `ERROR code (line 12:5): message` (CLI test text updated, exit codes pinned). `--json`: **domain format** — `{"path", "name", "outcome", "skipped": [...], "diagnostics": [{"code", "severity": "error", "range": {half-open, 0-based}, "message", "occurrence"?, "related"?}]}`.
- The LSP server switches from the Phase-A shim to the pipeline: precise ranges, `code` = bare code, occurrence in message + `Diagnostic.data`, related info with the URI injected by the converter, version-stamped publishes.
- `docs/abstraction_ladders/LINT-CHECKS.md` generated from descriptors (code/category/severity/tier/summary); a test asserts the committed copy matches. `codeDescription.href`: the converter builds a real URI from the workspace root when resolvable; omitted otherwise.

### Phase H — Rich LSP features (priority order) `[DEFERRED]`

- `lsp/snapshot.py`: `AnalysisSnapshot(uri, version, parse_result, resolution, structural_diags, full_diags | None, symbols, tokens)` — one snapshot per document version; **all** features (diagnostics, symbols, definition, hover, tokens, formatting) read the snapshot, never re-run the pipeline independently.
- Scheduling: change -> cancel pending debounce timer -> wait ~200 ms (tunable from Phase-A latency data) -> confirm generation current -> run ONE analysis in `to_thread` -> confirm generation -> publish. Corpus (FULL) tier on open/save only; between saves, corpus-tier diagnostics are dropped, not stale.
- Position encoding: internal code-point ranges converted at the boundary via **pygls's per-document position codec** (`range_to_client_units` etc.); own UTF-16 helpers only for unit-testing assumptions.
- Features in order: **documentSymbol** (outline: floor primitives / rungs / tasks / top), **definition** (rung + floor-primitive references in expressions jump to their declaration, via spans + symbol table), **hover** (signature, level, depends-on/used-by from the consumer graph), then **semanticTokens** (full-document; sorted, non-overlapping, single-line; rung defs `function`+`definition`, rung calls `function`, floor primitives `function`+`defaultLibrary`, params `parameter`, binders `variable`, `input` `variable`+`readonly`, task ids `property`, capitalized types `type`, type vars `typeParameter`; identifiers classified against block scope, degrading gracefully when resolution fails). lsprotocol types may be used throughout `lsp/` (`convert.py` owns diagnostic conversion specifically).
- `expected_name` (stem check) only for `file:` URIs; untitled buffers skip it.
- Tests: direct handler/pipeline calls (no socket) — clean al1 yields zero diagnostics; a broken variant yields expected codes/ranges; symbol tree; definition targets; token decode; non-ASCII buffer no-crash.

### Phase I — Formatter (conservative, structural-only) `[DEFERRED]`

- Amend `LADDER-FORMAT.md`: "hand-authored; `arc-lab format-ladder` may normalize structural layout (whitespace/indentation only) — it never changes the parsed semantics" (the deliberate spec amendment).
- `lang/format.py` over the lossless layer: normalize indentation by block depth (4 spaces), structural spacing (`use` lines, `:` after field keywords, block braces), column-align `use` signatures within a floor block (committed house style), preserve blank-line grouping and comment text/attachment exactly. **Embedded expression fragments, grid literals, and config values preserved byte-for-byte** (no token rewriting inside expressions — that surface waits until proven needed). Formats only ERROR-free documents; otherwise no edits. LF-only; final newline enforced; ignores client `FormattingOptions`.
- Output: a single whole-document `TextEdit` (or none when unchanged).
- Invariants tested: semantic-projection equality; comment text + attachment preserved; fixpoint (`format(format(t)) == format(t)`); formatting all 20 registry ladders leaves testbeds byte-identical; golden: registry ladders already formatted (or reformatted once, deliberately, in this commit).
- Adapters: `arc-lab format-ladder [target] [--check]` (thin `cli/` module); `textDocument/formatting` in the server (reads the snapshot).

### Phase J — Hardening `[DEFERRED]`

- Extension: `npm run typecheck` + `npm run lint` wired into a `make ext-check` helper (not in `make check` — no node in the Python gate); one `@vscode/test-electron` integration test (activate, open fixture, language id, wait for a known diagnostic, invoke formatting, verify the edit).
- README polish (env assumptions: internal extension, `uv` required, workspace = repo).
- Final latency check against budgets; tune debounce/tier policy from measurements.

## Verification (end-to-end)

1. `make check` green; all 20 testbeds byte-identical; `run-ladder al1-mirror` still drives (strict path intact).
2. `arc-lab lint-ladder` reports 20/20, exit 0; `--json` matches the domain schema; `--draft` exits 2.
3. `arc-lab format-ladder --check` on the registry is clean/idempotent.
4. Break `al1-mirror` mid-file: multiple precise `(code, line:col)` diagnostics; later sections still checked; the broken rung's consumers report `unavailable-name`.
5. VS Code F5: highlighting; a type error in a solution squiggles under the offending token; save surfaces corpus-tier findings; the outline shows floor/rungs/tasks; ctrl-click a rung call jumps to its definition; hover shows signature + consumers; format-on-demand works; `Output -> ladder-ls` shows logs (stderr), diagnostics stream uncorrupted.

## Top risks

1. **Testbed byte-drift** — success-path elaboration untouched until Phase F; strict `resolve` is a projection; the byte-lock gates every commit.
2. **Position off-by-ones** (UTF-8 byte vs code point vs UTF-16; join spaces; half-open; SyntaxError 1-based) — one internal convention, conversions only at named tested boundaries; property tests over all 20 ladders + non-ASCII cases; never clamp internal output.
3. **Posture-lock churn in Phase F** — `CHECK_PLAN` pinned to legacy emission order; granularity changes updated deliberately in-commit; `.slug` keeps CLI text stable.
4. **LSP plumbing surprises** (env discovery, stdio pollution, pygls lifecycle) — retired in Phase A by the vertical slice, before any refactor depends on it.
5. **Formatter changing meaning** — structural-only scope, expressions byte-for-byte, ERROR-free-only, semantic-projection + fixpoint + testbed-lock invariants tested.
