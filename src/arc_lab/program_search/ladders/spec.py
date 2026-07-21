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
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.dataset import Corpus
from arc_lab.program_search.analysis.compression import CompressionMetric, SolvedTask
from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.serde import to_data
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.chain import oracle_libraries
from arc_lab.program_search.ladders.shape import LadderShape, LintFinding, RungShape
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BRANCHING_ENTRY
from arc_lab.program_search.substrate.abstraction import make_abstraction, unfold_program
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, If, Input, Lam, PrimRef, Program


class DemonstrationKind(enum.Enum):
    """How a demonstrating task's solution relates to its rung's target abstraction — which is
    exactly the proposer the rung requires (the §2 mapping)."""

    FULL_SOLUTION = "full_solution"  # solution == template instantiated -> AntiunifyPairs viable
    FRAGMENT_IDENTICAL = (
        "fragment_identical"  # subprogram, identical instantiation -> FrequentSubtree
    )
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
    """A demonstrating task (body in the corpus, resolved by id) + how its solution uses the rung.

    ``solution`` is the task's intended solving program stated over ``L_i`` (so it *calls* the
    rung). Carrying it here is what lets :meth:`LadderSpec.lint` check the demonstration plan
    itself -- which free-parameter values the rung is shown at, and whether the floor's vocabulary
    is actually exercised -- rather than only the templates.
    """

    task_id: str
    kind: DemonstrationKind
    solution: Program


@dataclass(frozen=True, slots=True)
class Distractor:
    """An off-spine task: learnable competence sitting in the corpus that no rung claims.

    A control ladder puts these there deliberately (al9's ``decoy``, al11's ``trap``) to ask what
    the loop does with mintable-but-useless material. They are part of the ladder\'s identity, so
    the spec carries them -- and the lint must see them, or a floor primitive that only a
    distractor exercises would read as dead vocabulary.
    """

    task_id: str
    label: str
    solution: Program


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
    #: Off-spine tasks (LADDER-FORMAT.md DST) -- empty for every ladder but the controls.
    distractors: tuple[Distractor, ...] = ()

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
        """``L_level`` = Floor + the *intended* rungs ``r_1..r_level`` gifted (each template
        resolves over the one below). Shares :func:`oracle_libraries` with the task generators, so a
        ladder is linted against exactly the libraries its tasks were generated against."""
        return oracle_libraries(self.floor(), [(r.name, r.template) for r in self.rungs[:level]])[
            -1
        ]

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
        ref_limit = self.reference_config.budget.depth_limit
        full_lib = self.oracle_library(k)
        by_id = {entry.task.task_id: entry for entry in self.train_corpus.entries}

        def err(check: str, ok: bool, detail: str) -> None:
            findings.append(LintFinding(check=check, ok=ok, detail=detail, severity="error"))

        def warn(check: str, ok: bool, detail: str) -> None:
            findings.append(LintFinding(check=check, ok=ok, detail=detail, severity="warn"))

        # Structure (S): levels, task resolution, alignment, demonstration counts.
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
        warn(
            "min-2-train-examples",
            not few_examples,
            f"tasks with < 2 train examples: {few_examples}",
        )

        # Structure (S): type well-formedness (attempt make_abstraction over L_{i-1}; reuse its
        # validation).
        for i, rung in enumerate(rungs):
            try:
                make_abstraction(rung.name, rung.template, self.oracle_library(i))
                err(f"well-typed[{rung.name}]", True, "")
            except (ValueError, KeyError) as exc:
                err(f"well-typed[{rung.name}]", False, f"{rung.name} ill-typed over L_{i}: {exc}")

        # Depth sandwich (D): the tractability claims, anchored at the reference budget. (Also
        # Structure's rung-referenced / top-uses-top-rung, which need this loop's inlining.)
        rung_shapes: list[RungShape] = []
        for i, rung in enumerate(rungs):
            d_i = compositional_depth(rung.template)
            err(
                f"jump-affordable[{rung.name}]",
                d_i <= ref_limit,
                f"d={d_i}, need <= depth_limit {ref_limit}",
            )
            # Demonstration relationship (1): a rung is a PROPER composition over L_{i-1}. A
            # depth-1 template is a bare primitive already in that library, so it belongs to a
            # lower rung and buys no depth (the double-jump check would flag it only indirectly).
            err(
                f"proper-composition[{rung.name}]",
                d_i >= 2,
                f"jump depth {d_i}: a rung must compose over L_{i}, not restate a bare primitive",
            )
            double_jump: int | None = None
            if i + 1 < k:  # inlined next rung over L_{i-1} (skip this rung)
                # Structural necessity: the rung above must actually CALL this one. Without a
                # call site, expanding it is a no-op and the ladder telescopes vacuously here.
                err(
                    f"rung-referenced[{rung.name}]",
                    _calls(rungs[i + 1].template, rung.name) >= 1,
                    f"{rungs[i + 1].name} never calls {rung.name}: the rung below is unused",
                )
                inlined = unfold_program(
                    rungs[i + 1].template, full_lib, expand=frozenset({rung.name})
                )
                double_jump = compositional_depth(inlined)
                err(
                    f"double-jump-intractable[{rung.name}]",
                    double_jump > ref_limit,
                    f"inlined depth {double_jump}, must exceed depth_limit {ref_limit}",
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
        top_skips: list[int] = []
        for sol in self.top.reference_solutions:
            d_top = compositional_depth(sol)
            top_depths.append(d_top)
            err(
                "top-affordable-with-ladder",
                d_top <= ref_limit,
                f"top d={d_top} over L_{k}, need <= depth_limit {ref_limit}",
            )
            # The Top Rung's whole definition: its solutions USE the top bridging rung as a
            # fragment. A top that never calls r_k isn't standing on the ladder at all.
            err(
                "top-uses-top-rung",
                _calls(sol, rungs[-1].name) >= 1,
                f"a top reference solution never calls {rungs[-1].name}",
            )
            d_raw = compositional_depth(unfold_program(sol, full_lib))
            raw_profile.append(d_raw)
            err(
                "raw-intractable",
                d_raw > ref_limit,
                f"d_raw={d_raw}, must exceed depth_limit {ref_limit}",
            )
            skip_top = compositional_depth(
                unfold_program(sol, full_lib, expand=frozenset({rungs[-1].name}))
            )
            top_skips.append(skip_top)
            err(
                "top-double-jump-intractable",
                skip_top > ref_limit,
                f"top over L_{k - 1} depth {skip_top}, must exceed depth_limit {ref_limit}",
            )
        # The last bridging rung's double jump is the layer above it -- the Top: the shallowest
        # top solution inlined over L_{k-1} (what skipping r_k would cost in depth).
        if rung_shapes and top_skips:
            rung_shapes[-1] = replace(rung_shapes[-1], double_jump_depth=min(top_skips))

        # Learnability (L): proposer compatibility.
        proposer = getattr(
            getattr(self.reference_config.learn, "learn_engine", None), "proposer", None
        )
        provided = (
            _PROPOSER_CAPABILITIES.get(type(proposer).__name__) if proposer is not None else None
        )
        for rung in rungs:
            kinds = {d.kind for d in rung.demonstrations}
            if provided is None:
                warn(
                    f"proposer-compat[{rung.name}]",
                    True,
                    "proposer capability not statically known",
                )
            else:
                err(
                    f"proposer-compat[{rung.name}]",
                    kinds <= provided,
                    f"{sorted(k.value for k in kinds - provided)} unservable by {type(proposer).__name__}",
                )

        # Demonstration plan (P): what the tasks themselves show.
        #
        # These used to hold by construction -- `taskgen`'s seed generator built varied grids and
        # `RungTasks.train_args` built the free-parameter sweep -- but a `.ladder` file states both
        # as literal data, so nothing enforces them any more except this block.
        for entry in (*self.train_corpus.entries, *self.heldout_corpus.entries):
            task_id, train = entry.task.task_id, entry.task.train
            inputs = [ex.input for ex in train]
            outputs = [ex.output for ex in train]
            err(
                f"distinct-train-inputs[{task_id}]",
                len(set(inputs)) == len(inputs),
                "repeated train inputs: the example set is smaller than it looks",
            )
            err(
                f"outputs-vary[{task_id}]",
                len(set(outputs)) > 1 or len(outputs) < 2,
                "every train output is the same grid: a constant program fits the task",
            )
            err(
                f"not-identity[{task_id}]",
                any(a != b for a, b in zip(inputs, outputs, strict=True)),
                "output == input on every train example: the identity fits the task",
            )
        # Heldout must be a genuinely different task, or it measures transfer to itself.
        train_keys = {_task_key(entry): entry.task.task_id for entry in self.train_corpus.entries}
        for entry in self.heldout_corpus.entries:
            twin = train_keys.get(_task_key(entry))
            err(
                f"heldout-distinct[{entry.task.task_id}]",
                twin is None,
                f"identical train examples to the train task {twin!r}",
            )

        # Demonstration plan (P): background-within / target-across -- a rung's FREE parameters
        # must be demonstrated at more than one value, or antiunification has nothing to
        # generalise over and mints the specialised form. (A `fragment_identical` rung is exempt:
        # identical instantiation across its demos is that kind's definition -- what varies for it
        # is the surrounding context.)
        for rung in rungs:
            demos = [
                d for d in rung.demonstrations if d.kind is not DemonstrationKind.FRAGMENT_IDENTICAL
            ]
            for free_index, values in _rung_argument_columns(demos, rung.name):
                err(
                    f"free-param-varies[{rung.name}#{free_index}]",
                    len(values) > 1 or len(demos) < 2,
                    f"every demonstration passes {min(values, default='?')}: the mint "
                    "will specialise to it instead of taking a parameter",
                )

        # Advisories (A): fan-in / telescope + lambda.
        warn(
            "not-all-telescope",
            any(s.fan_in > 1 for s in rung_shapes),
            "every rung has fan-in 1 (a pure telescope)",
        )
        if any(s.involves_lambda for s in rung_shapes):
            warn(
                "no-lambda-in-templates",
                False,
                "a rung template contains a Lam; depth checks advisory",
            )

        # Advisories (A): floor vocabulary -- every floor primitive should be exercised by
        # something the ladder states.
        #
        # A warning, not an error: a floor is sometimes deliberately broader than the spine (al4
        # ships a realistic mask algebra). But an *accidental* dead primitive is not free -- it
        # widens the round-0 leaf set for every task, inflating the very vocabulary tax the batch
        # is trying to attribute.
        stated: list[Program] = [
            *(rung.template for rung in rungs),
            *(demo.solution for rung in rungs for demo in rung.demonstrations),
            *(d.solution for d in self.distractors),
            *self.top.reference_solutions,
        ]
        exercised: set[str] = set()
        for program in stated:
            for node in unfold_program(program, full_lib).walk():
                if isinstance(node, Apply):
                    exercised.add(node.primitive)
                elif isinstance(node, PrimRef):
                    exercised.add(node.name)  # used as a first-class function value
                elif isinstance(node, If):
                    exercised.add(BRANCHING_ENTRY)  # branching exercises the `if` summoner
        idle = [p.name for p in self.floor().primitives if p.name not in exercised]
        warn(
            "floor-fully-exercised",
            not idle,
            f"floor primitives no rung, demonstration, distractor or top solution uses: {idle}",
        )

        # Structure (S): rung distinctness -- two rungs with identical unfolded templates are one
        # rung with two names: the second buys no depth and splits its own demonstrations. (A
        # syntactic comparison: extensionally-equal-but-differently-written twins pass it.)
        unfolded = [unfold_program(rung.template, full_lib) for rung in rungs]
        for i, rung in enumerate(rungs):
            twin = next((rungs[j].name for j in range(i) if unfolded[j] == unfolded[i]), None)
            err(
                f"rung-distinct[{rung.name}]",
                twin is None,
                f"identical unfolded template to {twin!r}",
            )

        # Learnability (L): MDL break-even -- minting a rung must lower the description length of
        # the very solutions that demonstrate it, under the ladder's OWN configured metric --
        # otherwise greedy-MDL governance refuses the mint and the climb stalls at that rung.
        # A per-rung-demonstrations PROXY for whole-corpus governance, conservative by design:
        # real governance scores every solution at the iteration plus the library term, so a rung
        # passing here can still be refused -- never the reverse claim.
        metric = getattr(getattr(self.reference_config.learn, "learn_engine", None), "metric", None)
        if metric is None:
            metric = CompressionMetric()
        for level, rung in enumerate(rungs, start=1):
            entries = [
                (by_id[d.task_id], d.solution) for d in rung.demonstrations if d.task_id in by_id
            ]
            if not entries:
                continue
            below, above = self.oracle_library(level - 1), self.oracle_library(level)
            folded = [SolvedTask(annotated=a, program=p) for a, p in entries]
            unminted = [
                SolvedTask(
                    annotated=a, program=unfold_program(p, above, expand=frozenset({rung.name}))
                )
                for a, p in entries
            ]
            gain = metric.describe(unminted, below).total - metric.describe(folded, above).total
            err(
                f"mdl-break-even[{rung.name}]",
                gain > 0,
                f"minting it costs {-gain:.1f} bits more than it saves on its own "
                f"{len(entries)} demonstration(s), so governance will refuse it",
            )

        # Derived output (not a check; physically last because it consumes the sandwich
        # quantities): the validity window — inclusive, in depth_limit units (a depth-d program is
        # reachable iff d <= depth_limit): lower = the deepest required jump/top depth; upper =
        # one less than the shallowest forbidden depth (inlined double-jumps, raw top).
        lower = max([*(s.jump_depth for s in rung_shapes), *top_depths])
        intractables = [
            *(s.double_jump_depth for s in rung_shapes if s.double_jump_depth is not None),
            *raw_profile,
        ]
        upper = min(intractables) - 1 if intractables else ref_limit
        return LadderShape(
            height=k + 1,
            raw_depth_profile=tuple(raw_profile),
            rungs=tuple(rung_shapes),
            validity_window=(lower, upper),
            findings=tuple(findings),
        )

    # -- pretty-print ---------------------------------------------------------------

    @property
    def name(self) -> str:
        """The ladder's name -- the testbed name of its (possibly split) train corpus."""
        return self.train_corpus.name.split(":")[0]

    def render(self) -> str:
        """The generated spec artifact (``spec.md``): everything DERIVED from the ladder's source.

        The ladder\'s ``.ladder`` file states what was chosen -- floor, templates, config block,
        tasks (LADDER-FORMAT.md) -- so this artifact deliberately does not restate any of it. What
        it carries is what follows: the depth spine, dependency structure, the validity window,
        derived demonstration kinds, the RESOLVED reference config (the frozen ladder default plus
        the file\'s overrides, which no single file shows), and the static lint\'s verdict --
        separated from what only the empirical certificate (results.md) can say.

        The committed copy lives beside the worksheet in ``docs/abstraction_ladders/ladders/
        <name>/`` (written by ``arc-lab run-ladder <name> --artifacts``); never hand-edited, and
        exempt from editor formatting (.prettierignore)."""
        shape = self.lint()
        k = len(self.rungs)
        lo, hi = shape.validity_window
        floor = self.floor()
        pinned = self.reference_config.budget.depth_limit
        rung_order = [rung.name for rung in self.rungs]
        top_pairs = list(zip(self.top.task_ids, self.top.reference_solutions, strict=False))
        top_depths = [compositional_depth(sol) for _, sol in top_pairs]
        top_fan_ins = [_fan_in(sol, set(rung_order)) for _, sol in top_pairs]

        lines = [
            f"<!-- Generated by LadderSpec.render() -- regenerate with `arc-lab run-ladder "
            f"{self.name} --artifacts <dir>`; never hand-edit. -->",
            "",
            f"# LadderSpec: {self.name}",
            "",
            f"Derived from `{self.name}.ladder` (in `program_search/ladders/registry/`) -- that "
            f"file is this ladder's source of truth: floor, rung templates, config and tasks. "
            f"Everything below is COMPUTED from it.",
            "",
            f"- Height: {shape.height} ({k} bridging rungs + top)",
            f"- Floor library: `{floor.name}` ({len(floor.primitives)} primitives)",
            f"- Pinned `depth_limit` (the reference config's cap -- every sandwich claim below "
            f"is stated against it): {pinned}",
            f"- Validity window: `depth_limit` in [{lo}, {hi}] (inclusive)",
            f"- Raw depth profile (top solutions unfolded to `L_0`): "
            f"{list(shape.raw_depth_profile)}",
        ]

        errors = [f for f in shape.findings if not f.ok and f.severity == "error"]
        warnings = [f for f in shape.findings if not f.ok and f.severity == "warn"]
        lines += [
            "",
            "## Verification",
            "",
            f"- Static lint (what this file asserts): **{'OK' if shape.ok else 'FAILED'}** -- "
            f"{len(shape.findings)} checks (errors: {len(errors)}, warnings: {len(warnings)})",
        ]
        for finding in errors:
            lines.append(f"  - ERROR `{finding.check}`: {finding.detail}")
        for finding in warnings:
            lines.append(f"  - warn `{finding.check}`: {finding.detail}")
        lines.append(
            "- Empirical certificate (jump tractability in fact, skip paths, demonstration "
            "health): NOT covered by this file -- see results.md beside it, generated from the "
            "oracle-chain runs"
        )

        max_fan_in = max([*(s.fan_in for s in shape.rungs), *top_fan_ins], default=0)
        overall = (
            "chain, pure telescope (no rung or top solution calls a lower rung more than once)"
            if max_fan_in <= 1
            else f"chain with recombination (max fan-in {max_fan_in})"
        )
        lines += [
            "",
            "## Shape",
            "",
            f"- Overall: {overall}",
            _off_spine_line(self.distractors),
            "- Dependencies (lower-rung calls, with multiplicity):",
        ]
        for rung in self.rungs:
            lines.append(
                f"  - r_{rung.level} `{rung.name}`: {_calls_text(rung.template, rung_order)}"
            )
        for tid, sol in top_pairs:
            lines.append(f"  - top `{tid}`: {_calls_text(sol, rung_order)}")

        kinds = {
            rung.name: "/".join(sorted({d.kind.value for d in rung.demonstrations})) or "-"
            for rung in self.rungs
        }
        rows = [["level", "rung", "d_i", "double-jump", "fan-in", "demos", "kind"]]
        for s in shape.rungs:
            rows.append(
                [
                    str(s.level),
                    f"`{s.name}`",
                    str(s.jump_depth),
                    "-" if s.double_jump_depth is None else str(s.double_jump_depth),
                    str(s.fan_in),
                    str(s.demonstration_count),
                    kinds.get(s.name, "-"),
                ]
            )
        rows.append(
            [
                "top",
                "(goal layer)",
                _span(top_depths),
                "-",
                _span(top_fan_ins),
                str(len(self.top.task_ids)),
                "-",
            ]
        )
        lines += [
            "",
            "## Rung spine",
            "",
            *table(rows),
            "",
            "- `d_i`: compositional depth of the template over `L_{i-1}` "
            "(top row: of the reference solutions over `L_k`)",
            "- `double-jump`: depth of the layer above with this rung inlined -- what skipping "
            "this rung would cost in depth (for the last rung, from the top solutions)",
            "- `fan-in`: calls to any lower rung, with multiplicity; floor calls don't count "
            "(design doc, section 2)",
            "- `kind`: the demonstration kind DERIVED from each task's solution shape "
            "(LADDER-FORMAT.md DRV-2), not declared anywhere",
        ]

        lines += ["", "## Top Rung (goal layer -- nothing is minted here)", ""]
        for (tid, _), d_top in zip(top_pairs, top_depths, strict=True):
            lines.append(f"- `{tid}`: d={d_top} over `L_{k}`")
        lines += [
            "",
            "## Reference config (resolved)",
            "",
            "The frozen ladder default with the source file's `config` block applied -- the "
            "effective machinery, which neither the default nor the file shows on its own.",
            "",
        ]
        lines += _data_bullets("Budget", to_data(self.reference_config.budget))
        lines += _data_bullets("Search engine", to_data(self.reference_config.search_engine))
        if self.reference_config.learn is not None:
            lines += _data_bullets("Learn", to_data(self.reference_config.learn))
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
                        {
                            "task_id": d.task_id,
                            "kind": d.kind.value,
                            "solution": d.solution.to_dict(),
                        }
                        for d in r.demonstrations
                    ],
                }
                for r in self.rungs
            ],
            "distractors": [
                {"task_id": d.task_id, "label": d.label, "solution": d.solution.to_dict()}
                for d in self.distractors
            ],
            "top": {
                "task_ids": list(self.top.task_ids),
                "reference_solutions": [s.to_dict() for s in self.top.reference_solutions],
            },
            "budgets": [to_data(b) for b in self.budgets],
            "train_corpus": _corpus_provenance(self.train_corpus),
            "heldout_corpus": _corpus_provenance(self.heldout_corpus),
        }


def _span(values: list[int]) -> str:
    """One number if all values agree, else an inclusive ``min-max`` range; ``-`` when empty."""
    if not values:
        return "-"
    low, high = min(values), max(values)
    return str(low) if low == high else f"{low}-{high}"


def _calls_text(program: Program, rung_order: list[str]) -> str:
    """The program's lower-rung calls as ``name xN`` (rung order), or ``floor primitives only``."""
    names = set(rung_order)
    counts = Counter(
        node.primitive
        for node in program.walk()
        if isinstance(node, Apply) and node.primitive in names
    )
    if not counts:
        return "floor primitives only"
    return ", ".join(f"`{name}` x{counts[name]}" for name in rung_order if name in counts)


def _data_bullets(label: str, data: object, indent: int = 0) -> list[str]:
    """Render a serde ``to_data`` payload as nested markdown bullets (``kind`` becomes the value
    on the parent line; everything else nests one level down)."""
    pad = "  " * indent
    if not isinstance(data, dict):
        return [f"{pad}- {label}: `{data}`"]
    kind = data.get("kind")
    lines = [f"{pad}- {label}: `{kind}`" if kind else f"{pad}- {label}:"]
    for key, value in data.items():
        if key != "kind":
            lines += _data_bullets(str(key), value, indent + 1)
    return lines


def _off_spine_line(distractors: tuple[Distractor, ...]) -> str:
    """The Shape section's off-spine summary -- context the lint's findings are read against."""
    if not distractors:
        return "- Off-spine: none"
    labels = ", ".join(f"`{label}`" for label in sorted({d.label for d in distractors}))
    return f"- Off-spine: {len(distractors)} distractor task(s) under {labels}"


def _task_key(entry: AnnotatedTask) -> tuple[tuple[object, object], ...]:
    """A task's train examples as a hashable key -- what makes two tasks the same task."""
    return tuple((example.input, example.output) for example in entry.task.train)


def _rung_argument_columns(
    demos: Sequence[Demonstration], rung_name: str
) -> tuple[tuple[int, frozenset[str]], ...]:
    """Per free argument position of ``rung_name``: (1-based index, distinct arguments observed).

    Aggregated over EVERY call site of EVERY demonstration -- each call is an occurrence the
    proposer sees, so a second call site with a different argument is variation. Arguments are
    compared column-wise, keeping call sites aligned even when one demo pipes a computed grid
    where another pipes ``input``; a column whose every observed argument is ``Input()`` is the
    piped grid, not a free parameter, and is dropped, with the survivors renumbered 1..n.
    """
    calls = [
        node.args
        for demo in demos
        for node in demo.solution.walk()
        if isinstance(node, Apply) and node.primitive == rung_name
    ]
    columns: list[tuple[int, frozenset[str]]] = []
    free_index = 0
    for position in range(max((len(args) for args in calls), default=0)):
        observed = [args[position] for args in calls if position < len(args)]
        if all(isinstance(arg, Input) for arg in observed):
            continue
        free_index += 1
        columns.append((free_index, frozenset(str(arg) for arg in observed)))
    return tuple(columns)


def _fan_in(template: Program, rung_names: set[str]) -> int:
    """How many rung calls the template makes, with multiplicity (fan-in > 1 == recombining)."""
    return sum(
        1 for node in template.walk() if isinstance(node, Apply) and node.primitive in rung_names
    )


def _calls(program: Program, name: str) -> int:
    """How many times ``program`` calls the named abstraction — 0 means structurally unused."""
    return sum(1 for node in program.walk() if isinstance(node, Apply) and node.primitive == name)


def _corpus_provenance(corpus: Corpus) -> dict[str, object]:
    return {"name": corpus.name, "content_hash": corpus.content_hash(), "task_count": len(corpus)}
