"""``LadderSpec``: one Ladder's identity — Floor + ordered bridging Rungs + a Top Rung + a
rung-tagged corpus + a pinned reference config.

Like ``StudySpec`` this is orchestration/provenance data (``to_dict`` only, no ``from_dict`` — a
``Corpus`` is not reconstructible from its hash). The Floor is ``reference_config.library`` (single
source of truth, as ``StudySpec.base_config.library`` is L1). ``lint()`` derives the static
:class:`LadderShape` from the substrate atoms (``compositional_depth`` / ``unfold_program``) — a
pure, cheap, search-free check; the empirical skip-path/collision guarantee is the certificate's
job (the read side over the oracle-chain runs).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.dataset import Corpus
from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.serde import to_data
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.ladders.shape import LadderShape, LintFinding, RungShape
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.substrate.abstraction import make_abstraction, unfold_program
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Lam, Program


class DemonstrationKind(enum.Enum):
    """How a demonstrating task's solution relates to its rung's target abstraction — which is
    exactly the proposer the rung requires (the §2 mapping)."""

    FULL_SOLUTION = "full_solution"  # solution == template instantiated -> AntiunifyPairs viable
    FRAGMENT_IDENTICAL = "fragment_identical"  # subprogram, identical instantiation -> FrequentSubtree
    FRAGMENT_VARYING = "fragment_varying"  # subprogram, varying params -> StitchProposer


#: What each proposer (by class name — avoids importing the dep-gated Stitch shim) can serve.
_PROPOSER_CAPABILITIES: dict[str, frozenset[DemonstrationKind]] = {
    "AntiunifyPairs": frozenset({DemonstrationKind.FULL_SOLUTION}),
    "FrequentSubtree": frozenset(
        {DemonstrationKind.FULL_SOLUTION, DemonstrationKind.FRAGMENT_IDENTICAL}
    ),
    "TypeScopedFrequentSubtree": frozenset(
        {DemonstrationKind.FULL_SOLUTION, DemonstrationKind.FRAGMENT_IDENTICAL}
    ),
    "SearchScopedFrequentSubtree": frozenset(
        {DemonstrationKind.FULL_SOLUTION, DemonstrationKind.FRAGMENT_IDENTICAL}
    ),
    "StitchProposer": frozenset(DemonstrationKind),
}


@dataclass(frozen=True, slots=True)
class Demonstration:
    """A demonstrating task (body in the corpus, resolved by id) + how its solution uses the rung."""

    task_id: str
    kind: DemonstrationKind


@dataclass(frozen=True, slots=True, kw_only=True)
class Rung:
    """A bridging rung — a learnable abstraction over ``L_{level-1}`` (its canonical template
    references ``r_{level-1}`` by name, matching what sleep mints) with its demonstrating tasks."""

    level: int  # 1..k
    target_abstraction: TargetAbstraction
    demonstrations: tuple[Demonstration, ...]

    @property
    def name(self) -> str:
        return self.target_abstraction.name

    @property
    def template(self) -> Program:
        return self.target_abstraction.template


@dataclass(frozen=True, slots=True, kw_only=True)
class TopRung:
    """The goal layer: the hardest tasks, whose solutions use the top bridging rung as a fragment.
    NOT a learnable abstraction (nothing above it, nothing minted); its tasks need not share a
    solution. ``reference_solutions`` (over ``L_k``, index-aligned with ``task_ids``) are the
    intended solving programs — needed to compute the ``d_raw`` profile and verify routing."""

    task_ids: tuple[str, ...]
    reference_solutions: tuple[Program, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class LadderSpec:
    """One Ladder: a LEARN reference config (library = Floor) x ordered bridging rungs x a Top Rung
    x a rung-tagged train/heldout corpus x the budgets to sweep."""

    reference_config: Config
    rungs: tuple[Rung, ...]  # bridging rungs, k >= 1, level 1..k
    top: TopRung
    train_corpus: Corpus
    heldout_corpus: Corpus
    budgets: tuple[Budget, ...]  # RQ2 sweep; the reference budget must be one of them

    def __post_init__(self) -> None:
        if self.reference_config.learn is None:
            raise ValueError("a Ladder's reference_config must be a LEARN config (learn set)")
        if not self.rungs:
            raise ValueError("a Ladder needs at least one bridging rung")

    # -- libraries + task resolution ------------------------------------------------

    def floor(self) -> Library:
        """``L_0`` — the reference config's own library."""
        return self.reference_config.library

    def oracle_library(self, level: int) -> Library:
        """``L_level`` = Floor + the *intended* rungs ``r_1..r_level`` gifted, built by successive
        ``make_abstraction`` + ``Library.extended`` (each template resolves over the one below)."""
        library = self.floor()
        for rung in self.rungs[:level]:
            primitive = make_abstraction(rung.name, rung.template, library)
            library = library.extended(name=f"{library.name}+{rung.name}", extra=(primitive,))
        return library

    def rung_tasks(self, level: int) -> tuple[AnnotatedTask, ...]:
        """The train-corpus entries demonstrating rung ``level`` (resolved by demonstration id)."""
        ids = {demo.task_id for demo in self.rungs[level - 1].demonstrations}
        return tuple(entry for entry in self.train_corpus.entries if entry.task.task_id in ids)

    # -- lint (static, search-free) -------------------------------------------------

    def lint(self) -> LadderShape:
        """Derive the static :class:`LadderShape` and run every cheap well-formedness check."""
        findings: list[LintFinding] = []
        rungs = self.rungs
        k = len(rungs)
        ref_depth = self.reference_config.budget.max_depth
        full_lib = self.oracle_library(k)
        by_id = {entry.task.task_id: entry for entry in self.train_corpus.entries}

        def err(check: str, ok: bool, detail: str) -> None:
            findings.append(LintFinding(check=check, ok=ok, detail=detail, severity="error"))

        def warn(check: str, ok: bool, detail: str) -> None:
            findings.append(LintFinding(check=check, ok=ok, detail=detail, severity="warn"))

        # 1. Structural.
        err(
            "levels-contiguous",
            tuple(r.level for r in rungs) == tuple(range(1, k + 1)),
            f"levels {[r.level for r in rungs]} must be 1..{k}",
        )
        missing = [d.task_id for r in rungs for d in r.demonstrations if d.task_id not in by_id]
        missing += [t for t in self.top.task_ids if t not in by_id]
        err("tasks-exist", not missing, f"unknown task ids in train_corpus: {missing}")
        err(
            "top-solutions-aligned",
            len(self.top.task_ids) == len(self.top.reference_solutions),
            f"{len(self.top.task_ids)} top task ids vs {len(self.top.reference_solutions)} solutions",
        )
        thin = [r.name for r in rungs if len(r.demonstrations) < 2]
        err("min-2-demos", not thin, f"rungs with < 2 demonstrations: {thin}")
        few_examples = sorted(
            {
                tid
                for r in rungs
                for d in r.demonstrations
                if (tid := d.task_id) in by_id and len(by_id[tid].task.train) < 2
            }
        )
        warn("min-2-train-examples", not few_examples, f"tasks with < 2 train examples: {few_examples}")

        # 2. Type well-formedness (attempt make_abstraction over L_{i-1}; reuse its validation).
        for i, rung in enumerate(rungs):
            try:
                make_abstraction(rung.name, rung.template, self.oracle_library(i))
                err(f"well-typed[{rung.name}]", True, "")
            except (ValueError, KeyError) as exc:
                err(f"well-typed[{rung.name}]", False, f"{rung.name} ill-typed over L_{i}: {exc}")

        # 3-5. Depth sandwich (the tractability claims, anchored at the reference budget).
        rung_shapes: list[RungShape] = []
        for i, rung in enumerate(rungs):
            d_i = compositional_depth(rung.template)
            err(f"jump-affordable[{rung.name}]", d_i + 1 <= ref_depth, f"d={d_i}, need +1 <= {ref_depth}")
            double_jump: int | None = None
            if i + 1 < k:  # inlined next rung over L_{i-1} (skip this rung)
                inlined = unfold_program(rungs[i + 1].template, full_lib, expand=frozenset({rung.name}))
                double_jump = compositional_depth(inlined)
                err(
                    f"double-jump-intractable[{rung.name}]",
                    double_jump + 1 > ref_depth,
                    f"inlined depth {double_jump}, must exceed {ref_depth - 1}",
                )
            rung_shapes.append(
                RungShape(
                    level=rung.level,
                    name=rung.name,
                    jump_depth=d_i,
                    double_jump_depth=double_jump,
                    fan_in=_fan_in(rung.template, {r.name for r in rungs}),
                    demonstration_count=len(rung.demonstrations),
                    involves_lambda=any(isinstance(n, Lam) for n in rung.template.walk()),
                )
            )

        # top: d_raw (unfold to floor) intractable; top over L_{k-1} (skip r_k) intractable.
        raw_profile: list[int] = []
        top_depths: list[int] = []
        for sol in self.top.reference_solutions:
            d_top = compositional_depth(sol)
            top_depths.append(d_top)
            err("top-affordable-with-ladder", d_top + 1 <= ref_depth, f"top d={d_top} over L_{k}")
            d_raw = compositional_depth(unfold_program(sol, full_lib))
            raw_profile.append(d_raw)
            err("raw-intractable", d_raw + 1 > ref_depth, f"d_raw={d_raw}, must exceed {ref_depth - 1}")
            skip_top = compositional_depth(
                unfold_program(sol, full_lib, expand=frozenset({rungs[-1].name}))
            )
            err(
                "top-double-jump-intractable",
                skip_top + 1 > ref_depth,
                f"top over L_{k - 1} depth {skip_top}, must exceed {ref_depth - 1}",
            )

        # 6. Proposer compatibility.
        proposer = getattr(getattr(self.reference_config.learn, "learn_engine", None), "proposer", None)
        provided = _PROPOSER_CAPABILITIES.get(type(proposer).__name__) if proposer is not None else None
        for rung in rungs:
            kinds = {d.kind for d in rung.demonstrations}
            if provided is None:
                warn(f"proposer-compat[{rung.name}]", True, "proposer capability not statically known")
            else:
                err(
                    f"proposer-compat[{rung.name}]",
                    kinds <= provided,
                    f"{sorted(k.value for k in kinds - provided)} unservable by {type(proposer).__name__}",
                )

        # 9-10. Fan-in / telescope + lambda advisories.
        warn(
            "not-all-telescope",
            any(s.fan_in > 1 for s in rung_shapes),
            "every rung has fan-in 1 (a pure telescope)",
        )
        if any(s.involves_lambda for s in rung_shapes):
            warn("no-lambda-in-templates", False, "a rung template contains a Lam; depth checks advisory")

        # 11. Validity window.
        lower = max([*(s.jump_depth for s in rung_shapes), *top_depths]) + 1
        intractables = [
            *(s.double_jump_depth for s in rung_shapes if s.double_jump_depth is not None),
            *raw_profile,
        ]
        upper = min(intractables) if intractables else ref_depth
        return LadderShape(
            height=k + 1,
            raw_depth_profile=tuple(raw_profile),
            rungs=tuple(rung_shapes),
            validity_window=(lower, upper),
            findings=tuple(findings),
        )

    # -- pretty-print ---------------------------------------------------------------

    def render(self) -> str:
        """A summary block + a per-rung table (also the artifact dropped in docs/.../ladders/)."""
        shape = self.lint()
        floor_names = ", ".join(p.name for p in self.floor().primitives)
        lo, hi = shape.validity_window
        lines = [
            f'Ladder "{self.train_corpus.name}"  (height {shape.height})',
            f"  Floor: {{{floor_names}}}",
            f"  reference max_depth={self.reference_config.budget.max_depth}  "
            f"d_raw={list(shape.raw_depth_profile)}  window=[{lo},{hi}]  "
            f"{'OK' if shape.ok else 'LINT FAILED'}",
            "  level  rung              d_i  double-jump  fan-in  demos",
        ]
        for s in shape.rungs:
            dj = "-" if s.double_jump_depth is None else str(s.double_jump_depth)
            lines.append(
                f"  {s.level:>5}  {s.name:<16}  {s.jump_depth:>3}  {dj:>11}  "
                f"{s.fan_in:>6}  {s.demonstration_count}"
            )
        lines.append(f"  top    {'(goal tasks)':<16}  {'-':>3}  {'-':>11}  {'-':>6}  {len(self.top.task_ids)}")
        bad = [f"{f.check}: {f.detail}" for f in shape.findings if not f.ok and f.severity == "error"]
        if bad:
            lines.append("  ERRORS: " + "; ".join(bad))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render()

    # -- provenance -----------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Provenance payload (report header) — corpora by name + hash, never embedded."""
        return {
            "reference_config": self.reference_config.to_dict(),
            "rungs": [
                {
                    "level": r.level,
                    "name": r.name,
                    "template": r.template.to_dict(),
                    "demonstrations": [
                        {"task_id": d.task_id, "kind": d.kind.value} for d in r.demonstrations
                    ],
                }
                for r in self.rungs
            ],
            "top": {
                "task_ids": list(self.top.task_ids),
                "reference_solutions": [s.to_dict() for s in self.top.reference_solutions],
            },
            "budgets": [to_data(b) for b in self.budgets],
            "train_corpus": _corpus_provenance(self.train_corpus),
            "heldout_corpus": _corpus_provenance(self.heldout_corpus),
        }


def _fan_in(template: Program, rung_names: set[str]) -> int:
    """How many rung calls the template makes, with multiplicity (fan-in > 1 == recombining)."""
    return sum(
        1 for node in template.walk() if isinstance(node, Apply) and node.primitive in rung_names
    )


def _corpus_provenance(corpus: Corpus) -> dict[str, object]:
    return {"name": corpus.name, "content_hash": corpus.content_hash(), "task_count": len(corpus)}
