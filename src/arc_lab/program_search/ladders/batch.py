"""Run many Ladders as one coherent pass -- the *batch of record*.

The 2026-08-03 run-store census found no ladder in the repo whose runs came from a single
``(commit, budget)`` generation, and found that the only two that came close were the only two
whose costs survived re-certification. The cause was not compute -- a full pass over every ladder
ever built is ~34 minutes against a program history of 4.21 hours -- but that nothing ever ran them
*together*. Members were re-run piecemeal as defects were found, so the register accumulated cells
from a dozen code states and the comparability had to be argued in prose, per claim.

So this exists to make "one pass, one generation" a thing you can *do* in one command, and the
manifest to make it a thing you can *check*: each member reports its provenance generations (see
``ladders/provenance.py``), and a member carrying exactly one is a member whose own cost columns
mean a single thing.

**That check is per member, and does not license comparing two of them.** The batch deliberately
spans regimes -- a 50k guard on the synthetic ladders against 2M on the real-ARC ones, three
``max_arity`` settings, two accounting modes -- so a cross-member reading needs a shared cohort
(:meth:`LadderSpec.cohort`, ``LADDER-RELATIONSHIPS-2026-07-23.md``) on top of it. The manifest
prints both: :func:`cohort_rows` says who may be compared with whom (and :func:`ablation_pairs`
which same-task pairs only look comparable), and the rollup says what the batch SAMPLES on each
axis -- because an axis carrying one value across every member is an assumption the results
silently depend on, and the point of a batch of record is that such things are countable rather
than argued.

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
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.provenance import GENERATION_EXEMPT_CELLS
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report, render_report_markdown
from arc_lab.program_search.ladders.run import run_ladder

#: Ladders the batch of record covers, and why the rest are out. Membership is a DECISION, so it is
#: written down rather than inferred from which folders happen to exist -- the census found the
#: register's contents drifting precisely because nothing declared what the set was.
#:
#: In: every ladder that has ever been run -- the 21 carrying a committed ``report.json``, plus the
#: 11 rejections and controls that never got one. The rejections name collapse FAMILIES rather than
#: one-off design slips, which makes them the set's most reusable output; they also cost the same
#: as the admitted ladders (~17 min for all 11), so there is no reason for them to be outside the
#: pass.
EXCLUDED: Mapping[str, str] = {
    "dae9d2b5-halves-union": "parked: a multi-hour enumeration (~21M considered per cell); kept "
    "unrun on purpose as the measured region-tier baseline",
    "dae9d2b5-split-halves": "superseded by `-split-halves-lean`; probed at pool 150 with the skip "
    "test inconclusive, never run",
    "dae9d2b5-recolor-first": "probe INCONCLUSIVE at the cohort guard -- a non-result by design, "
    "not something a bigger budget converts into a verdict (LADDER-PROCESS)",
    "94f9d214-recolor-first": "probe INCONCLUSIVE at the cohort guard (see above)",
    "fafffa47-recolor-first": "probe INCONCLUSIVE at the cohort guard (see above)",
    "a740d043-crop-normalize": "probe CONVICTED (a skip path at depth 3, verified); kept in the "
    "registry as a reproducible finding -- commuting factorisations cannot be laddered",
}


#: **The RQ1 protocol: the raw arm is purchased ONCE PER COHORT**, on one nominated member; every
#: other member of that cohort runs ``--raw-arm-k 0``.
#:
#: The raw arm searches the TOP task from the bare Floor at ``d_raw``, so **same task + same Floor
#: + same ``d_raw`` is literally the same search**: a member's own budget changes only its guard,
#: never its search space. Running one per member therefore does two wrong things at once -- it
#: re-buys an enumeration already recorded (measured: two members bought theirs twice, 2.57M
#: redundant candidates), and it manufactures per-member RQ1 ratios that invite exactly the
#: cross-member comparison the cohort rule exists to forbid. A comparability instrument generating
#: incomparable numbers.
#:
#: This map IS the protocol; nothing else states it. A member outside it whose derived cohort is
#: empty (no ``ladder.task``, so a synthetic top) is a cohort of one and buys its own arm --
#: they are cheap, 0-16s apiece. See :func:`raw_arm_k_for`.
RAW_ARM_MEMBERS: Mapping[str, str] = {
    "dae9d2b5-split-recolor": "the `dae9d2b5` cohort's RQ1 (raw cancels across its members)",
    "94f9d214-nor-recolor": "the `94f9d214` cohort's RQ1, bought on the 4-rung member",
    "fafffa47-nor-recolor": "the `fafffa47` cohort's RQ1, bought on the 4-rung member",
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
    #: ``ladder.task`` -- the external target, or ``""`` for a synthetic top.
    task: str = ""
    #: ``LadderSpec.cohort()`` -- task + Floor hash, DERIVED. ``""`` means a cohort of one.
    cohort: str = ""
    #: The Floor's primitive names, sorted -- the readable half of what the cohort hash encodes.
    floor: tuple[str, ...] = ()
    report: dict[str, Any] | None = None

    @property
    def single_generation(self) -> bool:
        """Necessary for this member's own cost columns to mean one thing. NOT sufficient for
        comparing them against another member's -- that additionally needs a shared cohort, since
        the batch spans two guard regimes (50k synthetic, 2M real-ARC) and three ``max_arity``
        settings. See :func:`render_manifest`'s rollup."""
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
            task=spec.task,
            cohort=spec.cohort(),
            floor=tuple(sorted(spec.floor().names())),
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


def _generation_cells(member: BatchMember) -> list[Mapping[str, Any]]:
    """A member's provenance rows, minus the cells :mod:`ladders.provenance` exempts from the
    generation key -- so the rollup reads the same cells the coherence check does."""
    rows = _rows_of(member.report or {}, "provenance")
    return [row for row in rows if row.get("cell") not in GENERATION_EXEMPT_CELLS]


def _axis(members: Sequence[BatchMember], read: Callable[[Mapping[str, Any]], object]) -> str:
    """One rollup row: each distinct value on an axis, with how many MEMBERS carry it.

    Counted per member rather than per cell: a member's cells all share these fields by the
    generation check, and per-cell counts would just re-weight by chain height.
    """
    counts: Counter[str] = Counter()
    for member in members:
        values = {read(row) for row in _generation_cells(member)}
        for value in values:
            if value is not None:
                counts[str(value)] += 1
    if not counts:
        return "-"
    return ", ".join(f"`{value}` ({n})" for value, n in sorted(counts.items()))


def _budget_field(field: str) -> Callable[[Mapping[str, Any]], object]:
    def read(row: Mapping[str, Any]) -> object:
        budget = row.get("budget")
        return budget.get(field) if isinstance(budget, Mapping) else None

    return read


def _learn_field(field: str) -> Callable[[Mapping[str, Any]], object]:
    def read(row: Mapping[str, Any]) -> object:
        learn = row.get("learn")
        return learn.get(field) if isinstance(learn, Mapping) else None

    return read


def _accounting_mode(row: Mapping[str, Any]) -> object:
    """Exhaustive vs stop-at-first -- the axis that decides which cost quantities a cell yields
    (`compromise.py`: one exhaustive run gives `first_solution_index`, `cheapest_solution_index`
    AND cost-to-exhaust; an early stop gives only the first)."""
    budget = row.get("budget")
    if not isinstance(budget, Mapping):
        return None
    return "exhaustive" if budget.get("solution_limit") is None else "stop-at-first"


#: The rollup's axes, in the order a reader should scan them: what the LEARNER was, then what the
#: SEARCH was. Each row's job is to make a single-valued axis visible as such.
_ROLLUP_AXES: tuple[tuple[str, Callable[[Mapping[str, Any]], object]], ...] = (
    ("learn engine", _learn_field("learn_engine")),
    ("proposer", _learn_field("proposer")),
    ("metric", _learn_field("metric")),
    ("learn iterations", _learn_field("iterations")),
    ("accounting mode", _accounting_mode),
    ("`considered_limit`", _budget_field("considered_limit")),
    ("`max_arity`", _budget_field("max_arity")),
)


def cohorts_of(members: Sequence[BatchMember]) -> dict[str, list[BatchMember]]:
    """The batch's cohorts: derived id -> its members. Ladders with no cohort stand alone."""
    groups: dict[str, list[BatchMember]] = {}
    for member in members:
        if member.error is None and member.cohort:
            groups.setdefault(member.cohort, []).append(member)
    return {cohort: sorted(group, key=lambda m: m.name) for cohort, group in sorted(groups.items())}


def cohort_rows(members: Sequence[BatchMember]) -> list[list[str]]:
    """Cohort membership, as a table: who may be compared with whom, and over what Floor."""
    rows = [["cohort", "task", "Floor", "members"]]
    for cohort, group in cohorts_of(members).items():
        rows.append(
            [
                f"`{cohort}`",
                f"`{group[0].task}`",
                ", ".join(f"`{name}`" for name in group[0].floor),
                ", ".join(f"`{m.name}`" for m in group),
            ]
        )
    return rows


def ablation_pairs(members: Sequence[BatchMember]) -> dict[str, list[str]]:
    """Tasks whose ladders span MORE THAN ONE cohort -- same top, different Floor.

    Not a defect: `LADDER-RELATIONSHIPS-2026-07-23.md` calls this an **ablation**, where the raw
    cost delta between the Floors *is* the measurement. Surfaced because the two look alike in a
    flat member list, and subtracting across them (the thing a cohort licenses) is invalid.
    """
    by_task: dict[str, set[str]] = {}
    for cohort, group in cohorts_of(members).items():
        by_task.setdefault(group[0].task, set()).add(cohort)
    return {task: sorted(cohorts) for task, cohorts in sorted(by_task.items()) if len(cohorts) > 1}


def render_manifest(members: Sequence[BatchMember], *, arm: str | None = None) -> str:
    """The batch manifest: one row per member, the rollup of what the batch SAMPLES, and the
    checks that make it a batch of record."""
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
    ok = [m for m in members if m.error is None]
    climbed = [m for m in ok if m.climbed]
    total = sum(m.seconds for m in members)

    lines += [
        "",
        "## What this batch samples",
        "",
        f"**{len(ok)} members: {len(climbed)} climbed** (the learning loop ran) and "
        f"**{len(ok) - len(climbed)} chain-only** (the certificate rejected the ladder, so "
        "learning was never paid for). Every rung-recovery number in this manifest therefore "
        f"rests on those {len(climbed)}.",
        "",
        "Rolled up from each cell's own recorded `runspec.json`, counted per member. "
        "**An axis with one value is an assumption, not a result** -- the batch cannot tell you "
        "whether its findings depend on it.",
        "",
    ]
    lines += table(
        [["axis", "values sampled (members)"]]
        + [[label, _axis(ok, read)] for label, read in _ROLLUP_AXES]
    )
    lines += [
        "",
        "### Cohorts -- what may be compared with what",
        "",
        "A cohort is a **shared task and a shared Floor** "
        "(`LADDER-RELATIONSHIPS-2026-07-23.md`), which makes raw search cost cancel and is what "
        "licenses reading two members' cost columns against each other. It is derived, never "
        "declared -- only `ladder.task` is authored, and the Floor half is a content hash, so a "
        "cohort cannot disagree with the Floors in it. Members absent from this table stand "
        "alone: their costs are readable on their own terms and against nothing else.",
        "",
    ]
    lines += table(cohort_rows(ok))
    ablations = ablation_pairs(ok)
    if ablations:
        lines += [
            "",
            "**Ablation pairs** -- one task, more than one Floor, so raw does NOT cancel and the "
            "cost delta between them is itself the measurement (how much work the changed "
            "primitive was doing). Do not subtract across these as if they were a cohort:",
            "",
        ]
        lines += [
            f"- `{task}`: {', '.join(f'`{c}`' for c in cohorts)}"
            for task, cohorts in ablations.items()
        ]

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
        "**Scope of the generation check.** It is a check on each member SEPARATELY: that all of "
        "one member's cells came from one config, so that member's own cost columns mean one "
        "thing. That is the condition the 2026-08-03 census found failing in every ladder but "
        "two, and it is necessary for any comparison at all -- but it is **not** what licenses "
        "comparing two members. The batch deliberately spans several regimes (see the rollup "
        "above), so a cross-member comparison additionally needs a shared cohort.",
    ]
    if EXCLUDED:
        lines += ["", "## Excluded from the batch, and why", ""]
        lines += table(
            [["ladder", "reason"]]
            + [[f"`{name}`", reason] for name, reason in sorted(EXCLUDED.items())]
        )
    return "\n".join(lines)
