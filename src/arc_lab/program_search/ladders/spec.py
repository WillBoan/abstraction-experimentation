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
from dataclasses import dataclass

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.dataset import Corpus
from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.serde import to_data
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.ladders import graph
from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.chain import oracle_libraries
from arc_lab.program_search.ladders.shape import LadderShape
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Program


class DemonstrationKind(enum.Enum):
    """How a demonstrating task's solution relates to its rung's target abstraction — which is
    exactly the proposer the rung requires (the §2 mapping)."""

    FULL_SOLUTION = "full_solution"  # solution == template instantiated -> AntiunifyPairs viable
    FRAGMENT_IDENTICAL = (
        "fragment_identical"  # subprogram, identical instantiation -> FrequentSubtree
    )
    FRAGMENT_VARYING = "fragment_varying"  # subprogram, varying params -> StitchProposer


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

    def lint(self, *, corpus_backed: bool = True) -> LadderShape:
        """Derive the static :class:`LadderShape` and run every check in ``checks/plan.py``.

        ``corpus_backed=False`` runs only the STRUCTURAL tier -- the checks whose inputs are the
        templates, stated solutions, demonstration kinds and config, none of which need the task
        grids. It is what lets a *draft* over assumed primitives (which has no evaluable corpus) be
        linted anyway: the grid- and evaluation-backed checks are skipped and named in
        ``LadderShape.skipped_checks`` rather than silently dropped.

        The lint itself lives in ``ladders/checks/`` -- one :class:`~.checks.base.LadderCheck`
        subclass per check, ordered by ``CHECK_PLAN``. Imported lazily because the checks read this
        module: the dependency runs checks -> spec, and this one convenience method is the only
        edge pointing back.
        """
        from arc_lab.program_search.ladders.checks.run import lint_spec

        return lint_spec(self, corpus_backed=corpus_backed)

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
        top_needs = [min_depth_limit(sol) for _, sol in top_pairs]
        top_fan_ins = [graph.fan_in(sol, set(rung_order)) for _, sol in top_pairs]

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
            lines.append(f"  - ERROR `{finding.slug}`: {finding.detail}")
        for finding in warnings:
            lines.append(f"  - warn `{finding.slug}`: {finding.detail}")
        lines.append(
            "- Empirical certificate (jump tractability in fact, skip paths, demonstration "
            "health): NOT covered by this file -- see results.md beside it, generated from the "
            "oracle-chain runs"
        )

        # Two orthogonal facts, both derived from the reference edges: chain vs DAG (does a rung
        # ever feed more than its immediate successor?) and telescope vs recombination (does anything
        # call a lower rung more than once?).
        max_fan_in = max([*(s.fan_in for s in shape.rungs), *top_fan_ins], default=0)
        max_fan_out = max(
            (len(cs) for cs in graph.consumer_graph(self.rungs, self.top).values()), default=0
        )
        recombination = (
            "pure telescope (no rung or top solution calls a lower rung more than once)"
            if max_fan_in <= 1
            else f"recombination (max fan-in {max_fan_in})"
        )
        overall = (
            f"chain, {recombination}"
            if shape.is_chain
            else f"DAG (a rung feeds several or non-adjacent consumers; max fan-out "
            f"{max_fan_out}), {recombination}"
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
        rows = [["level", "rung", "d_i", "needs", "double-jump", "fan-in", "demos", "kind"]]
        for s in shape.rungs:
            rows.append(
                [
                    str(s.level),
                    f"`{s.name}`",
                    str(s.jump_depth),
                    str(s.jump_needs),
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
                _span(top_needs),
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
            "- `d_i`: the GENERATION the engine composes the template at over `L_{i-1}`, a leaf "
            "being 0 (top row: of the reference solutions over `L_k`). The design doc's jump "
            "depth, and the unit `solved_at_generation` reports in.",
            "- `needs`: the smallest `depth_limit` that puts it in REACH -- the quantity every "
            "affordability claim above is stated in. Equal to `d_i` for a first-order template; "
            "larger when a lambda body needs its own descended budget (`analysis/depth.py`).",
            "- `double-jump`: depth of the layer above with this rung inlined -- what skipping "
            "this rung would cost in depth (for the last rung, from the top solutions)",
            "- `fan-in`: calls to any lower rung, with multiplicity; floor calls don't count "
            "(design doc, section 2)",
            "- `kind`: the demonstration kind DERIVED from each task's solution shape "
            "(LADDER-FORMAT.md DRV-2), not declared anywhere",
        ]

        lines += ["", "## Top Rung (goal layer -- nothing is minted here)", ""]
        for (tid, _), d_top, need_top in zip(top_pairs, top_depths, top_needs, strict=True):
            lines.append(f"- `{tid}`: d={d_top}, needs depth_limit {need_top}, over `L_{k}`")
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


def _corpus_provenance(corpus: Corpus) -> dict[str, object]:
    return {"name": corpus.name, "content_hash": corpus.content_hash(), "task_count": len(corpus)}
