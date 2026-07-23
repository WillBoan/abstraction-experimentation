"""``arc-lab lint-ladder``: check a `.ladder` source without running anything.

The authoring loop. Unlike ``run-ladder`` (which lints and then executes the whole climb), this
only reads: it parses and resolves the file -- every load-time check, with line numbers -- then
generates the corpus **in memory** and reports the static lint. So a *draft* ladder can be checked
before its testbed exists, and the loop is edit -> lint -> edit.

Takes a registered ladder name, a path to any `.ladder` file, or nothing (the whole registry).

``--draft`` is for **exploratory** ladders: a decomposition sketched for a task whose primitives do
not exist yet. Unknown floor primitives are taken at their declared signatures instead of failing,
so all the signature-level machinery -- types, scopes, arity, the depth spine -- still runs, and
the unknown names come back as a worklist. Nothing that *evaluates* a program can run in that
state, so the lint runs its STRUCTURAL tier (the depth sandwich, dead-rung/reachability,
distinctness, proposer/free-param checks -- everything reading only templates, solutions and
config) and skips the corpus- and evaluation-backed checks, naming exactly which.

A draft can be incomplete in **two independent ways**, and either one routes to that structural
tier: its floor may be *assumed* (no implementations to evaluate), or it may have *no corpus* (a
`.ladder` with no ``heldout`` demonstration cannot be split into a testbed). They are not the same
condition and one does not imply the other -- the cfb2ce5a cohort became fully implemented while
still having no heldout task -- so neither is used as a proxy for the other.

Exits non-zero when anything fails, so it works in a hook or a script.
"""

from __future__ import annotations

import enum
from pathlib import Path

import typer

from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit
from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.load import (
    LoadedLadder,
    lintable_spec,
    resolve,
    structural_spec,
)
from arc_lab.program_search.ladders.lang.parse import LADDER_SUFFIX, parse_ladder_file
from arc_lab.program_search.ladders.lang.type_syntax import render_primitive_signature
from arc_lab.program_search.ladders.registry import ladder_paths, load_ladder


def lint_ladder_command(
    target: str = typer.Argument(
        None,
        help="A registered ladder name, or a path to a `.ladder` file; omit to lint every "
        "registered ladder.",
    ),
    draft: bool = typer.Option(
        False,
        "--draft",
        help="Exploratory mode: take unknown floor primitives at their declared signatures and "
        "report them as a worklist, instead of failing to load.",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Only report findings, not the full rendered spec."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit diagnostics as JSON (LSP-shaped ranges) instead of the report."
    ),
) -> None:
    targets = sorted(ladder_paths()) if target is None else [target]
    if json_output:
        _emit_json(targets)
        return
    outcomes = [_lint_one(one, quiet=quiet or target is None, draft=draft) for one in targets]
    if target is None:
        clean = sum(outcome is _Outcome.CLEAN for outcome in outcomes)
        typer.echo(f"\n{clean}/{len(targets)} ladders lint clean")
    # Exit code carries the worst outcome: a failure outranks an unverified draft outranks clean,
    # so `0` means "sound", never merely "loaded".
    if any(outcome is _Outcome.FAILED for outcome in outcomes):
        raise typer.Exit(code=1)
    if any(outcome is _Outcome.INCOMPLETE for outcome in outcomes):
        raise typer.Exit(code=2)


class _Outcome(enum.Enum):
    """One ladder's lint result. The exit code distinguishes all three, so a hook can tell a
    verified-sound ladder (`CLEAN`) from one that merely loaded (`INCOMPLETE`)."""

    CLEAN = 0  # loaded and every lint check passed
    FAILED = 1  # loaded but a lint check failed, or the file could not load
    INCOMPLETE = 2  # a draft: loaded and type-checked, but soundness is unverified


def _emit_json(targets: list[str]) -> None:
    """Print each target's diagnostics as domain JSON; exit non-zero if any has an error.

    Shares the exact producer the language server uses (``pipeline.lint_source``), so the CLI and
    the editor never disagree about a `.ladder` file.
    """
    import json

    from arc_lab.program_search.ladders.pipeline import diagnostics_to_json, lint_source

    results = []
    for one in targets:
        path = _source_path(one)
        results.append(diagnostics_to_json(lint_source(path.read_text()), path=str(path)))
    typer.echo(json.dumps(results, indent=2))
    if any(result["outcome"] == "failed" for result in results):
        raise typer.Exit(code=1)


def _source_path(target: str) -> Path:
    """The `.ladder` path for a path-like target or a registered ladder name."""
    path = Path(target)
    if path.suffix == LADDER_SUFFIX or path.exists():
        if not path.is_file():
            raise typer.BadParameter(f"{target}: no such `.ladder` file")
        return path
    try:
        return ladder_paths()[target]
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _resolve_target(target: str, *, draft: bool) -> LoadedLadder:
    """Load ``target`` as a path if it looks like one, else as a registered name."""
    path = Path(target)
    if path.suffix == LADDER_SUFFIX or path.exists():
        if not path.is_file():
            raise typer.BadParameter(f"{target}: no such `.ladder` file")
        return resolve(parse_ladder_file(path), assume_missing=draft)
    if draft:  # a registered ladder can be linted in draft mode too
        return resolve(parse_ladder_file(ladder_paths()[target]), assume_missing=True)
    return load_ladder(target)


def _lint_one(target: str, *, quiet: bool, draft: bool) -> _Outcome:
    """Lint one ladder and report; return its :class:`_Outcome`."""
    label = Path(target).stem if target.endswith(LADDER_SUFFIX) else target
    try:
        loaded = _resolve_target(target, draft=draft)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except LadderFormatError as exc:  # a load error: the file cannot mean anything yet
        typer.echo(f"{label}: LOAD FAILED -- {exc}")
        return _Outcome.FAILED

    if loaded.assumed:
        return _report_draft(label, loaded, reason=f"{len(loaded.assumed)} assumed primitive(s)")
    spec = lintable_spec(loaded)
    if spec is None:  # loads and type-checks, but yields no train/heldout corpus to lint against
        return _report_draft(label, loaded, reason="no train/heldout corpus (add a `heldout` task)")

    shape = spec.lint()
    errors = [f for f in shape.findings if not f.ok and f.severity == "error"]
    warnings = [f for f in shape.findings if not f.ok and f.severity == "warn"]
    if not quiet:
        typer.echo(spec.render())
        typer.echo("")
    typer.echo(
        f"{label}: {'OK' if shape.ok else 'FAILED'} -- {len(shape.findings)} checks "
        f"({len(errors)} errors, {len(warnings)} warnings)"
    )
    for finding in errors:
        typer.echo(f"  ERROR {finding.check}: {finding.detail}")
    for finding in warnings:
        typer.echo(f"  warn  {finding.check}: {finding.detail}")
    return _Outcome.CLEAN if shape.ok else _Outcome.FAILED


def _report_draft(label: str, loaded: LoadedLadder, *, reason: str) -> _Outcome:
    """A draft the corpus-backed tier cannot reach: run the STRUCTURAL lint tier (templates,
    solutions, demonstration kinds, config -- no grids) and name what was skipped.

    ``reason`` is why the corpus-backed tier is out of reach -- an assumed floor, or a document that
    yields no train/heldout corpus. Both land here; neither implies the other.

    A draft is always ``INCOMPLETE``, never ``CLEAN`` and never ``FAILED``: it is unverified by
    construction. The structural findings ARE shown in full (that is the point -- the author wants to
    see what breaks early), but they are advisory here; the definite pass/fail verdict is deferred to
    a real lint of the finished ladder. Everything the structural tier could not cover is named, so a
    quiet draft is never mistaken for a sound one."""
    document = loaded.document
    shape = structural_spec(loaded).lint(corpus_backed=False)
    errors = [f for f in shape.findings if not f.ok and f.severity == "error"]
    warnings = [f for f in shape.findings if not f.ok and f.severity == "warn"]

    summary = (
        f"structural lint: {len(errors)} error(s), {len(warnings)} warning(s)"
        if errors or warnings
        else "structural lint clean"
    )
    typer.echo(
        f"{label}: INCOMPLETE (draft: {reason}) -- loaded and type-checked, "
        f"{len(loaded.templates)} rungs; {summary}; corpus-backed soundness NOT verified"
    )

    if loaded.assumed:
        typer.echo(
            f"\n  Assumed primitives ({len(loaded.assumed)}) -- implement or decompose these:"
        )
        declared = {entry.name: entry for entry in document.floor}
        for name in loaded.assumed:
            typer.echo(f"    {name}: {render_primitive_signature(declared[name].signature)}")

    topology = "chain" if shape.is_chain else "DAG"
    typer.echo(
        f"\n  Rung spine ({topology}; d_i = generation, needs = smallest depth_limit that reaches "
        "it):"
    )
    for level, (block, template) in enumerate(
        zip(document.rungs, loaded.templates, strict=True), start=1
    ):
        typer.echo(
            f"    r{level:<3} {block.name:<28} d_i={compositional_depth(template)} "
            f"needs={min_depth_limit(template)}"
        )

    typer.echo(
        f"\n  Structural lint: {len(shape.findings)} checks ran "
        f"({len(errors)} errors, {len(warnings)} warnings)"
    )
    for finding in errors:
        typer.echo(f"    ERROR {finding.check}: {finding.detail}")
    for finding in warnings:
        typer.echo(f"    warn  {finding.check}: {finding.detail}")

    typer.echo(
        f"\n  Skipped -- these need evaluated task grids, which this draft cannot supply ({reason}): "
        f"{', '.join(shape.skipped_checks)}."
    )
    return _Outcome.INCOMPLETE
