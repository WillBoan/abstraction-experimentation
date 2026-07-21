"""Document -> substrate: the semantic half of loading a `.ladder` file.

Resolves a parsed :class:`LadderDocument` against the substrate registry and builds the two things
a ladder needs -- its :class:`LadderSpec` and its generated tasks -- from the one source (spec
LC-1). Everything derivable is derived here rather than written in the file (spec DRV): rung levels
and oracle libraries from file order, demonstration kinds from each solution's shape, and every
task's outputs by *evaluating* its declared solution.

The two halves stay separable on purpose, mirroring how ladders already work: :func:`ladder_tasks`
feeds ``taskgen`` (which writes the committed testbed), while :func:`ladder_spec` reads that
committed testbed back as the corpus -- so caching, ``--corpus`` and the oracle chain are untouched
by the change of source format.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.dataset import load_testbed
from arc_lab.core.grid import Grid
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.execution.studies import split_by_meta
from arc_lab.program_search.ladders.chain import oracle_libraries
from arc_lab.program_search.ladders.lang.errors import LadderFormatError, at_line
from arc_lab.program_search.ladders.lang.expr import elaborate_expression
from arc_lab.program_search.ladders.lang.parse import LadderDocument, RungBlock, TaskBlock
from arc_lab.program_search.ladders.lang.type_syntax import (
    PrimitiveSignature,
    render_primitive_signature,
)
from arc_lab.program_search.ladders.spec import (
    Demonstration,
    DemonstrationKind,
    LadderSpec,
    Rung,
    TopRung,
)
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.taskgen import GeneratedTask, make_task


def ladder_default_config(library: Library) -> Config:
    """The frozen "ladder default" every `.ladder` ``config`` block overrides (spec CFG-3).

    FROZEN DATA. It is part of every ladder's identity -- changing a value here moves every
    ladder's ``run_id`` and invalidates every cached ladder run -- so treat it like a lock: change
    it deliberately, and re-certify the batch when you do.

    ``considered_limit`` is the compute guard, at the 50k value the al1-al14 screen actually ran
    under; carrying it here (rather than off-config, as that screen did) is what makes those runs
    reproducible. ``solution_limit`` stays off: the certificate reads demonstration health off
    *retained cheapest* solutions, and an early stop can halt before the cheapest is found.
    ``constant_sources`` is empty -- constants are a real cost driver, so a ladder that needs them
    opts in visibly rather than inheriting them.
    """
    return Config(
        library=library,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=Budget(
            depth_limit=2,
            max_arity=2,
            max_pool=400,
            considered_limit=50_000,
            considered_limit_mode="immediate",
        ),
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=5),
    )


@dataclass(frozen=True, slots=True)
class LoadedLadder:
    """A `.ladder` file resolved: its floor, its rung chain, and every task's solution program."""

    document: LadderDocument
    floor: Library
    libraries: tuple[Library, ...]  # L_0 .. L_k
    templates: tuple[Program, ...]  # rung templates, level 1..k
    solutions: dict[str, Program]  # task id -> its solution program
    demonstrations: tuple[tuple[Demonstration, ...], ...]  # per rung, level order (derived)
    config: Config

    @property
    def name(self) -> str:
        return self.document.name


def resolve(document: LadderDocument) -> LoadedLadder:
    """Resolve ``document`` against the substrate: floor, rung chain, config, solutions, kinds.

    Everything here depends on the file alone, so every spec violation surfaces as a load error
    (spec VAL-1) without needing the ladder's testbed to exist yet.
    """
    floor = _floor(document)
    libraries, templates = _chain(document, floor)
    config = _config(document, floor)
    solutions = _solutions(document, libraries)
    return LoadedLadder(
        document=document,
        floor=floor,
        libraries=libraries,
        templates=templates,
        solutions=solutions,
        demonstrations=tuple(_demonstrations(block, solutions) for block in document.rungs),
        config=config,
    )


def ladder_tasks(loaded: LoadedLadder) -> tuple[GeneratedTask, ...]:
    """Every task, with its outputs computed by evaluating its declared solution (spec DRV-3/4).

    Task order is file order -- rung blocks (in level order), then the goal layer -- which is what
    the generated manifest records.
    """
    document = loaded.document
    blocks: list[tuple[str, TaskBlock]] = [
        *((rung.name, task) for rung in document.rungs for task in rung.tasks),
        *(
            (block.label, task)
            for block in document.distractors
            for task in block.tasks  # off-spine, between the rungs and the goal layer
        ),
        *(("top", task) for task in document.top),
    ]
    library = loaded.libraries[-1]
    tasks: list[GeneratedTask] = []
    for label, block in blocks:
        program = loaded.solutions[block.task_id]

        def solve(grid: Grid, program: Program = program) -> Grid:
            return program.evaluate_grid(grid, library)

        try:
            tasks.append(
                make_task(
                    block.task_id,
                    label=label,
                    split="heldout" if block.heldout else "train",
                    solution=solve,
                    train_inputs=block.train_inputs,
                    test_inputs=block.test_inputs,
                )
            )
        except Exception as exc:
            raise LadderFormatError(
                f"task {block.task_id!r}: its solution failed to evaluate ({exc})",
                line=block.line,
            ) from None
    return tuple(tasks)


def ladder_spec(loaded: LoadedLadder) -> LadderSpec:
    """Build the :class:`LadderSpec`, reading the ladder's committed testbed as its corpus."""
    train, heldout = split_by_meta(load_testbed(loaded.name))
    rungs = tuple(
        Rung(
            level=level,
            target_abstraction=TargetAbstraction(name=block.name, template=template),
            demonstrations=demonstrations,
        )
        for level, (block, template, demonstrations) in enumerate(
            zip(loaded.document.rungs, loaded.templates, loaded.demonstrations, strict=True),
            start=1,
        )
    )
    top_blocks = [task for task in loaded.document.top if not task.heldout]
    return LadderSpec(
        reference_config=loaded.config,
        rungs=rungs,
        top=TopRung(
            task_ids=tuple(block.task_id for block in top_blocks),
            reference_solutions=tuple(loaded.solutions[block.task_id] for block in top_blocks),
        ),
        train_corpus=train,
        heldout_corpus=heldout,
        budgets=(loaded.config.budget,),
    )


# -- resolution steps ---------------------------------------------------------------


def _floor(document: LadderDocument) -> Library:
    """The Floor library: registry primitives, in declaration order, signatures asserted."""
    if not document.floor:
        raise LadderFormatError("the floor needs at least one primitive (spec FLR-3)")
    seen: set[str] = set()
    primitives = []
    for entry in document.floor:
        if entry.name in seen:
            raise LadderFormatError(f"duplicate floor primitive {entry.name!r}", line=entry.line)
        seen.add(entry.name)
        primitive = BASE_PRIMITIVES.get(entry.name)
        if primitive is None:
            raise LadderFormatError(
                f"unknown primitive {entry.name!r}: not in the substrate registry", line=entry.line
            )
        actual = PrimitiveSignature(
            param_types=primitive.param_types,
            return_type=primitive.return_type,
            variadic_param=primitive.variadic_param,
        )
        if entry.signature != actual:  # spec FLR-7
            raise LadderFormatError(
                f"{entry.name!r} is declared `{render_primitive_signature(entry.signature)}` but "
                f"the registry says `{render_primitive_signature(actual)}`",
                line=entry.line,
            )
        primitives.append(primitive)
    return Library(name=document.floor_name, primitives=tuple(primitives))


def _chain(
    document: LadderDocument, floor: Library
) -> tuple[tuple[Library, ...], tuple[Program, ...]]:
    """``(L_0..L_k, templates)`` -- each rung elaborated over the library below it (spec NAM-4)."""
    pairs: list[tuple[str, Program]] = []
    libraries: list[Library] = [floor]
    for block in document.rungs:
        below = libraries[-1]
        if block.name in below:  # spec NAM-3
            where = "the floor" if block.name in floor else "a lower rung"
            raise LadderFormatError(f"rung {block.name!r} shadows {where}", line=block.line)
        template = _template(block, below)
        pairs.append((block.name, template))
        libraries = list(oracle_libraries(floor, pairs))
    return tuple(libraries), tuple(template for _, template in pairs)


def _template(block: RungBlock, below: Library) -> Program:
    """One rung's template, elaborated and checked against its declared signature."""
    try:
        template = elaborate_expression(
            block.body, library=below, params=block.header.params, allow_input=False
        )
    except LadderFormatError as exc:
        raise at_line(exc, block.line) from None
    try:
        primitive = make_abstraction(block.name, template, below)
    except (ValueError, KeyError) as exc:  # spec RNG-4 (closed, contiguous, consistent params)
        raise LadderFormatError(f"rung {block.name!r}: {exc}", line=block.line) from None
    declared = block.header
    if primitive.param_types != declared.param_types:
        unused = [
            name
            for index, (name, _) in enumerate(declared.params)
            if index >= len(primitive.param_types)
        ]
        detail = (
            f"parameter(s) {', '.join(unused)} are never used in the body"
            if unused
            else f"the body uses {[str(t) for t in primitive.param_types]}"
        )
        raise LadderFormatError(
            f"rung {block.name!r}'s declared parameters do not match its body: {detail}",
            line=block.line,
        )
    if primitive.return_type != declared.return_type:
        raise LadderFormatError(
            f"rung {block.name!r} is declared to return "
            f"`{declared.return_type}` but its body returns `{primitive.return_type}`",
            line=block.line,
        )
    return template


def _config(document: LadderDocument, floor: Library) -> Config:
    """The reference config: the frozen ladder default + this file's overrides (spec CFG)."""
    overrides: dict[str, object] = {}
    for entry in document.config:
        if entry.path in overrides:  # spec CFG-5
            raise LadderFormatError(f"duplicate config path {entry.path!r}", line=entry.line)
        if entry.path == "library" or entry.path.startswith("library."):  # spec CFG-4
            raise LadderFormatError(
                "`library` is not settable: the `floor` section owns it", line=entry.line
            )
        if entry.path == "learn":
            raise LadderFormatError(
                "`learn` cannot be unset: a ladder's reference config is a LEARN config",
                line=entry.line,
            )
        overrides[entry.path] = entry.value
    try:
        return apply_overrides(ladder_default_config(floor), overrides)
    except ValueError as exc:
        line = next((e.line for e in document.config), None)
        raise LadderFormatError(str(exc), line=line) from None


def _solutions(document: LadderDocument, libraries: tuple[Library, ...]) -> dict[str, Program]:
    """Every task's solution program, elaborated in the scope its block sits in (spec NAM-5)."""
    solutions: dict[str, Program] = {}
    blocks: list[tuple[TaskBlock, Library]] = [
        *(
            (task, libraries[level])
            for level, rung in enumerate(document.rungs, start=1)
            for task in rung.tasks
        ),
        # A distractor is off-spine: solved over the Floor alone, so referencing a rung is an error
        # rather than a silent dependency on the very ladder it is meant to be independent of.
        *((task, libraries[0]) for block in document.distractors for task in block.tasks),
        *((task, libraries[-1]) for task in document.top),
    ]
    for block, library in blocks:
        if block.task_id in solutions:  # spec NAM-2
            raise LadderFormatError(f"duplicate task id {block.task_id!r}", line=block.line)
        try:
            solutions[block.task_id] = elaborate_expression(
                block.solution, library=library, allow_input=True
            )
        except LadderFormatError as exc:
            raise at_line(exc, block.line) from None
    return solutions


def _demonstrations(block: RungBlock, solutions: dict[str, Program]) -> tuple[Demonstration, ...]:
    """Derive each train task's :class:`DemonstrationKind` from its solution's shape (spec DRV-2).

    A demonstrating solution must *call* its rung. Calling it at the root is a full solution; any
    other position is a fragment, identical when every train task passes the rung the same
    arguments and varying otherwise. Heldout tasks do not vote (they are not learned from), but
    they are still required to use the rung.
    """
    train = [task for task in block.tasks if not task.heldout]
    call_args: list[tuple[tuple[Program, ...], ...]] = []
    roots: list[bool] = []
    for task in block.tasks:
        solution = solutions[task.task_id]
        calls = [
            node
            for node in solution.walk()
            if isinstance(node, Apply) and node.primitive == block.name
        ]
        if not calls:
            raise LadderFormatError(
                f"task {task.task_id!r} demonstrates rung {block.name!r} but never calls it",
                line=task.line,
            )
        if not task.heldout:
            call_args.append(tuple(call.args for call in calls))
            roots.append(isinstance(solution, Apply) and solution.primitive == block.name)
    if all(roots):
        kind = DemonstrationKind.FULL_SOLUTION
    elif len(set(call_args)) == 1:
        kind = DemonstrationKind.FRAGMENT_IDENTICAL
    else:
        kind = DemonstrationKind.FRAGMENT_VARYING
    return tuple(Demonstration(task_id=task.task_id, kind=kind) for task in train)
