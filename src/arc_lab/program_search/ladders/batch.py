"""Run many Ladders as one coherent pass -- the *batch of record*.

The 2026-08-03 run-store census found no ladder in the repo whose runs came from a single
``(commit, budget)`` generation, and found that the only two that came close were the only two
whose costs survived re-certification. The cause was not compute -- a full pass over every ladder
ever built is ~34 minutes against a program history of 4.21 hours -- but that nothing ever ran them
*together*. Members were re-run piecemeal as defects were found, so the register accumulated cells
from a dozen code states and the comparability had to be argued in prose, per claim.

So this exists to make "one pass, one generation" a thing you can *do* in one command, and the
manifest to make it a thing you can *check*: each member reports its provenance generations (see
``ladders/provenance.py``), and a batch whose members each carry exactly one is what licenses
comparing their cost columns at all.

**Arms.** ``overrides`` applies a dotted-path ``Config`` change to every member -- the surface a
governance-objective arm needs (``learn.learn_engine.metric=TwoPartMDL``), which ``run-ladder``
had no way to express. An arm is *not* the batch of record, so writing committed artifacts under
overrides is refused unless explicitly forced: an arm's numbers in the register would be exactly
the mixing this module exists to prevent.

**Isolation.** A member that raises is recorded and the batch continues. A 32-member pass that
aborts on member 7 is how you get a half-updated register, which is the state being fixed.
"""

from __future__ import annotations

import dataclasses
import json
import time
import traceback
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report, render_report_markdown
from arc_lab.program_search.ladders.run import run_ladder

#: Ladders the batch of record covers, and why the rest are out. Membership is a DECISION, so it is
#: written down rather than inferred from which folders happen to exist -- the census found the
#: register's contents drifting precisely because nothing declared what the set was.
#:
#: In: every ladder that has ever been run -- the 21 carrying a committed ``report.json``, plus the
#: 11 rejections and controls that never got one. The rejections cost the same as the admitted
#: ladders (~17 min for all 11) and `LADDERS.md` calls them "the batch's most valuable output so
#: far", so there is no reason for them to be outside the pass.
EXCLUDED: Mapping[str, str] = {
    "dae9d2b5-halves-union": "parked: a multi-hour enumeration (~21M considered per cell); kept "
    "unrun on purpose as the measured region-tier baseline",
    "dae9d2b5-split-halves": "superseded by `-split-halves-lean`; probed at pool 150 with the skip "
    "test inconclusive, never run",
    "dae9d2b5-recolor-first": "probe INCONCLUSIVE at the cohort guard -- a non-result by design, "
    "not something a bigger budget converts into a verdict (LADDER-PROCESS)",
    "94f9d214-recolor-first": "probe INCONCLUSIVE at the cohort guard (see above)",
    "fafffa47-recolor-first": "probe INCONCLUSIVE at the cohort guard (see above)",
    "dae9d2b5-recolor-solo": "probe INCONCLUSIVE at a 500k smoke guard; the coarse endpoint is "
    "bounded by cost, not by a structural defect",
    "a740d043-crop-normalize": "probe CONVICTED (a skip path at depth 3, verified); kept in the "
    "registry as a reproducible finding -- commuting factorisations cannot be laddered",
}


#: Which members purchase RQ1 (the raw arm), and why only these.
#:
#: The raw arm searches the TOP task from the bare Floor at ``d_raw``, so **same task + same floor
#: + same ``d_raw`` is literally the same search**: a member's own budget changes only its guard,
#: never its search space. LADDERS.md states the protocol -- "RQ1 is purchased once per cohort
#: (raw arm on the 4-rung member only); the 2-rung members run ``--raw-arm-k 0``" -- and running
#: one per member both re-buys that enumeration and manufactures per-member ratios that invite the
#: cross-member comparison the cohort rule forbids.
#:
#: Every synthetic ladder is its own cohort (its own floor and top), so each buys its own -- and
#: they are cheap: 0-16s apiece. The three real cohorts buy theirs once, on the member that
#: already holds the recorded arm.
RAW_ARM_MEMBERS: Mapping[str, str] = {
    "dae9d2b5-split-recolor": "the `dae9d2b5` cohort's RQ1 (raw cancels across its members)",
    "94f9d214-nor-recolor": "the `94f9d214` cohort's RQ1 (the 4-rung member, per LADDERS.md)",
    "fafffa47-nor-recolor": "the `fafffa47` cohort's RQ1 (the 4-rung member, per LADDERS.md)",
}


def raw_arm_k_for(name: str, *, default_k: int, no_raw_arms: bool) -> int:
    """``k`` for one member: 0 unless it is its cohort's RQ1 purchaser (or a synthetic ladder,
    which is a cohort of one)."""
    if no_raw_arms:
        return 0
    if name in RAW_ARM_MEMBERS:
        return default_k
    # Synthetic ladders are single-member cohorts, so each carries its own raw arm.
    return default_k if name.startswith("al") else 0


def _rows_of(report: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """A report section as mapping rows -- the report dict is ``object``-typed by design."""
    value = report.get(key)
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _tri(value: Any) -> bool | None:
    """Reachability is tri-state: censored-unsolved is ``None``, never a verdict."""
    return value if isinstance(value, bool) else None


@dataclasses.dataclass(frozen=True, slots=True)
class BatchMember:
    """One member's outcome. ``error`` set means the member raised and nothing else is meaningful."""

    name: str
    seconds: float
    error: str | None = None
    admitted: bool | None = None
    climbed: bool = False
    top_chain: bool | None = None
    top_climb: bool | None = None
    rungs_recovered: int = 0
    rungs_total: int = 0
    diagnoses: tuple[str, ...] = ()
    generations: tuple[str, ...] = ()
    compromises: tuple[str, ...] = ()
    report: dict[str, Any] | None = None

    @property
    def single_generation(self) -> bool:
        """The property that licenses comparing this member's costs against another's."""
        return len(self.generations) == 1


def batch_members(only: Sequence[str] | None = None, skip: Sequence[str] = ()) -> list[str]:
    """The batch's membership: every registered ladder minus :data:`EXCLUDED`, minus ``skip``."""
    if only:
        return list(only)
    return sorted(name for name in ladder_paths() if name not in EXCLUDED and name not in skip)


def run_batch_member(
    name: str,
    *,
    overrides: Mapping[str, object] | None = None,
    runs_root: Path | None = None,
    artifacts_root: Path | None = None,
    raw_arm_k: int = 10,
    climb_rejected: bool = False,
) -> BatchMember:
    """Run one member, never raising: a failure is data the manifest carries, not an abort."""
    started = time.monotonic()
    try:
        spec = make_ladder(name)
        if overrides:
            spec = dataclasses.replace(
                spec, reference_config=apply_overrides(spec.reference_config, overrides)
            )
        result = run_ladder(
            spec, runs_root=runs_root, climb_rejected=climb_rejected, raw_arm_k=raw_arm_k
        )
        report = create_ladder_report(result)
        if artifacts_root is not None:
            write_member_artifacts(artifacts_root / name, spec.render(), report)
        recovery = _rows_of(report, "rung_recovery")
        reach = report.get("top_reachable")
        reach = reach if isinstance(reach, dict) else {}
        generations = report.get("config_generations")
        return BatchMember(
            name=name,
            seconds=time.monotonic() - started,
            admitted=bool(result.certificate.admitted),
            climbed=result.climbed,
            top_chain=_tri(reach.get("chain")),
            top_climb=_tri(reach.get("climb")),
            rungs_recovered=sum(1 for row in recovery if row.get("recovered")),
            rungs_total=len(recovery),
            diagnoses=tuple(
                sorted(
                    {
                        str(row["not_recovered_because"])
                        for row in recovery
                        if row.get("not_recovered_because")
                    }
                )
            ),
            generations=tuple(str(g) for g in generations) if isinstance(generations, list) else (),
            compromises=tuple(
                str(option.get("code")) for option in _rows_of(report, "compromises")
            ),
            report=report,
        )
    except Exception:
        return BatchMember(
            name=name, seconds=time.monotonic() - started, error=traceback.format_exc(limit=6)
        )


def write_member_artifacts(directory: Path, spec_render: str, report: Mapping[str, Any]) -> None:
    """The committed trio, exactly as ``run-ladder --artifacts`` writes it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "spec.md").write_text(spec_render + "\n", encoding="utf-8")
    (directory / "results.md").write_text(render_report_markdown(report) + "\n", encoding="utf-8")
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _verdict(member: BatchMember) -> str:
    if member.error is not None:
        return "ERROR"
    if member.admitted:
        return "admitted"
    return "rejected"


def _reach(value: bool | None) -> str:
    """Tri-state, per the report: an unsolved-but-censored search is "we do not know", not "no"."""
    if value is None:
        return "censored"
    return "yes" if value else "NO"


def _top_column(member: BatchMember) -> str:
    """Goal reachability, chain / climb.

    A rejected ladder never pays for the climb, so its climb side is ``n/a`` -- distinct from
    ``censored``, which means a search DID run and was cut off. Conflating the two would read as
    "we tried and could not tell" where the truth is "we never tried, by design".
    """
    if member.error is not None:
        return "-"
    climb = _reach(member.top_climb) if member.climbed else "n/a"
    return f"{_reach(member.top_chain)} / {climb}"


def render_manifest(members: Sequence[BatchMember], *, arm: str | None = None) -> str:
    """The batch manifest: one row per member, plus the checks that make it a batch of record."""
    lines = [
        "<!-- Generated by `arc-lab run-batch`; never hand-edit. -->",
        "",
        f"# Ladder batch{f' -- ARM: {arm}' if arm else ' of record'}",
        "",
    ]
    if arm:
        lines += [
            f"> **This is an ARM, not the batch of record.** Every member ran under `{arm}`. Its "
            "numbers are comparable within this manifest and against the batch of record member "
            "for member -- never mixed into the register.",
            "",
        ]

    rows = [
        [
            "ladder",
            "verdict",
            "top (chain/climb)",
            "rungs",
            "diagnoses",
            "gens",
            "compromises",
            "wall",
        ]
    ]
    for member in sorted(members, key=lambda m: m.name):
        rows.append(
            [
                f"`{member.name}`",
                _verdict(member),
                _top_column(member),
                f"{member.rungs_recovered}/{member.rungs_total}" if member.rungs_total else "-",
                ", ".join(member.diagnoses) or "-",
                str(len(member.generations)) if member.generations else "-",
                ", ".join(member.compromises) or "-",
                f"{member.seconds:.0f}s",
            ]
        )
    lines += table(rows)

    errored = [m for m in members if m.error is not None]
    multi = [m for m in members if m.error is None and m.generations and not m.single_generation]
    total = sum(m.seconds for m in members)
    lines += [
        "",
        "## Batch checks",
        "",
        f"- Members run: **{len(members)}**; wall clock **{total / 60:.1f} min**.",
        f"- Members that raised: **{len(errored)}**"
        + (f" -- {', '.join(f'`{m.name}`' for m in errored)}" if errored else ""),
        f"- Members whose cells span MORE THAN ONE config generation: **{len(multi)}**"
        + (f" -- {', '.join(f'`{m.name}`' for m in multi)}" if multi else ""),
        "",
        "The second check is what makes this a batch of record rather than a pile of runs: a "
        "member assembled across a code or budget change has cost columns that are not mutually "
        "comparable, which is the condition the 2026-08-03 census found in every ladder but two.",
    ]
    if EXCLUDED:
        lines += ["", "## Excluded from the batch, and why", ""]
        lines += table(
            [["ladder", "reason"]]
            + [[f"`{name}`", reason] for name, reason in sorted(EXCLUDED.items())]
        )
    return "\n".join(lines)
