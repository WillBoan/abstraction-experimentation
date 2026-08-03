"""``arc-lab run-batch``: run many Ladders as one coherent pass, and write the manifest.

Thin wrapper (behavior lives in ``program_search/ladders/batch.py``). The point of the command is
the *pass*: a batch of record is every member run under one config generation, which is what makes
their cost columns comparable at all -- and which the 2026-08-03 census found had never happened.

``--set`` runs the whole batch as an ARM (the surface a governance-objective ablation needs).
Writing committed artifacts under an arm is refused: an arm's numbers in the register would be the
exact mixing the batch exists to prevent.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import typer

from arc_lab.program_search.execution.overrides import parse_set_values
from arc_lab.program_search.ladders.batch import (
    EXCLUDED,
    batch_members,
    raw_arm_k_for,
    render_manifest,
    run_batch_member,
)

#: Where the committed per-ladder artifacts live.
DEFAULT_ARTIFACTS_ROOT = Path("docs/abstraction_ladders/ladders")


def run_batch_command(
    only: str = typer.Option(
        "", "--only", help="Comma-separated ladder names to run instead of the whole batch."
    ),
    skip: str = typer.Option("", "--skip", help="Comma-separated ladder names to leave out."),
    set_: list[str] = typer.Option(
        [],
        "--set",
        help="Config override applied to EVERY member (dotted path=value), making the pass an "
        "ARM -- e.g. --set learn.learn_engine.metric=TwoPartMDL.",
    ),
    artifacts: bool = typer.Option(
        False,
        "--artifacts",
        help=f"Write the committed per-ladder artifacts into {DEFAULT_ARTIFACTS_ROOT}/<name>/. "
        "Refused under --set unless --force-artifacts.",
    ),
    force_artifacts: bool = typer.Option(
        False,
        "--force-artifacts",
        help="Allow --artifacts under --set. Only for deliberately re-baselining the register on "
        "a new config generation -- never for an ablation arm.",
    ),
    manifest: Path | None = typer.Option(
        None, help="Write the batch manifest (markdown) here; JSON goes beside it as .json."
    ),
    raw_arm_k: int = typer.Option(
        10,
        "--raw-arm-k",
        help="RQ1 claim strength, applied only to the members that PURCHASE RQ1 (see "
        "batch.RAW_ARM_MEMBERS -- raw is bought once per cohort, not once per member).",
    ),
    no_raw_arms: bool = typer.Option(
        False,
        "--no-raw-arms",
        help="Skip every raw arm. For iteration passes: re-checks the structural verdicts in "
        "minutes without re-buying RQ1.",
    ),
    climb_rejected: bool = typer.Option(
        False, "--climb-rejected", help="Force the climb stage on rejected members."
    ),
) -> None:
    """Run the ladder batch end-to-end and report which members form one coherent generation."""
    overrides = parse_set_values(list(set_))
    if artifacts and overrides and not force_artifacts:
        raise typer.BadParameter(
            "--artifacts under --set would write an ARM's numbers into the committed register, "
            "which is the mixing the batch of record exists to prevent. Pass --force-artifacts "
            "only if you are deliberately re-baselining on a new config generation."
        )

    names = batch_members(
        only=[n.strip() for n in only.split(",") if n.strip()] or None,
        skip=[n.strip() for n in skip.split(",") if n.strip()],
    )
    arm = ", ".join(f"{k}={v}" for k, v in sorted(overrides.items())) if overrides else None
    typer.echo(f"running {len(names)} ladders{f' as ARM ({arm})' if arm else ''}...")
    if not only:
        typer.echo(f"({len(EXCLUDED)} excluded -- see the manifest for each reason)")

    members = []
    for index, name in enumerate(names, start=1):
        k = raw_arm_k_for(name, default_k=raw_arm_k, no_raw_arms=no_raw_arms)
        typer.echo(f"  [{index}/{len(names)}] {name}{' +raw' if k else ''} ... ", nl=False)
        member = run_batch_member(
            name,
            overrides=overrides,
            artifacts_root=DEFAULT_ARTIFACTS_ROOT if artifacts else None,
            raw_arm_k=k,
            climb_rejected=climb_rejected,
        )
        members.append(member)
        if member.error is not None:
            typer.echo(f"ERROR ({member.seconds:.0f}s)")
        else:
            recovered = f"{member.rungs_recovered}/{member.rungs_total}"
            verdict = "admitted" if member.admitted else "rejected"
            typer.echo(f"{verdict}, rungs {recovered}, {member.seconds:.0f}s")

    text = render_manifest(members, arm=arm)
    if manifest is not None:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(text + "\n", encoding="utf-8")
        # `BatchMember` is slots=True, so it has no __dict__ -- read its fields declaratively.
        # `report` is excluded: the per-ladder report.json already carries it in full.
        payload = [
            {
                field.name: getattr(member, field.name)
                for field in dataclasses.fields(member)
                if field.name != "report"
            }
            for member in members
        ]
        manifest.with_suffix(".json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=list) + "\n", encoding="utf-8"
        )
        typer.echo(f"wrote {manifest} and {manifest.with_suffix('.json')}")
    else:
        typer.echo("")
        typer.echo(text)

    errored = [m for m in members if m.error is not None]
    multi = [m for m in members if m.error is None and m.generations and not m.single_generation]
    if errored or multi:
        raise typer.Exit(code=1)
