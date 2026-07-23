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

from arc_lab.core.annotation import AnnotatedTask, Split, Synthetic, TaskMeta
from arc_lab.core.dataset import Corpus, load_testbed
from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.execution.studies import split_by_meta
from arc_lab.program_search.ladders.chain import oracle_libraries
from arc_lab.program_search.ladders.lang.errors import (
    FragmentError,
    LadderFormatError,
    at_line,
)
from arc_lab.program_search.ladders.lang.expr import elaborate_expression, elaborate_typed
from arc_lab.program_search.ladders.lang.parse import LadderDocument, RungBlock, TaskBlock
from arc_lab.program_search.ladders.lang.type_syntax import (
    PrimitiveSignature,
    render_primitive_signature,
    render_type,
)
from arc_lab.program_search.ladders.spec import (
    Demonstration,
    DemonstrationKind,
    Distractor,
    LadderSpec,
    Rung,
    TopRung,
)
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive, Value
from arc_lab.program_search.substrate.program import Apply, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import unify
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
    #: Floor primitives taken on trust from their declared signatures (draft mode). Non-empty
    #: means nothing that EVALUATES a program can run -- no tasks, no corpus, no lint.
    assumed: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.document.name


def resolve(document: LadderDocument, *, assume_missing: bool = False) -> LoadedLadder:
    """Resolve ``document`` against the substrate: floor, rung chain, config, solutions, kinds.

    Everything here depends on the file alone, so every spec violation surfaces as a load error
    (spec VAL-1) without needing the ladder's testbed to exist yet.
    """
    floor, assumed = _floor(document, assume_missing=assume_missing)
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
        assumed=assumed,
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


def draft_spec(loaded: LoadedLadder) -> LadderSpec:
    """A :class:`LadderSpec` whose corpus is generated in memory -- for LINTING ONLY.

    A committed testbed is a run's corpus and therefore part of run identity, which is why
    :func:`ladder_spec` reads it from disk rather than regenerating it (EXECUTION.md: regenerating
    inline would silently mint new identities whenever generation logic changed). Linting executes
    nothing, so it needs no such guarantee -- and this lets a *draft* ladder be checked before its
    testbed exists, which is the difference between a tight authoring loop and a two-step one.

    The two agree by construction: a test locks every ladder's regenerated tasks against its
    committed ones.
    """
    # Sorted by task id, exactly as `load_tasks` reads a testbed directory -- so the draft corpus
    # is byte-for-byte the corpus the committed testbed produces, hash included.
    tasks = sorted(ladder_tasks(loaded), key=lambda generated: generated.task_id)
    entries = tuple(
        AnnotatedTask(
            task=Task.from_dict(generated.task_id, generated.spec),
            meta=TaskMeta(
                provenance=Synthetic(loaded.name),
                split=Split(generated.split),
                label=generated.label,
            ),
        )
        for generated in tasks
    )
    corpus = Corpus(name=loaded.name, entries=entries)
    return _spec_with_corpora(loaded, *split_by_meta(corpus))


def ladder_spec(loaded: LoadedLadder) -> LadderSpec:
    """Build the :class:`LadderSpec`, reading the ladder's committed testbed as its corpus."""
    return _spec_with_corpora(loaded, *split_by_meta(load_testbed(loaded.name)))


def structural_spec(loaded: LoadedLadder) -> LadderSpec:
    """A :class:`LadderSpec` with EMPTY corpora -- for the STRUCTURAL lint tier only.

    A draft over assumed primitives has no evaluable corpus (the primitives have no
    implementation), but every structural check reads the templates, stated solutions,
    demonstration kinds and config -- never the grids. This builds the spec those checks need; pair
    it with ``LadderSpec.lint(corpus_backed=False)``, which skips (and names) the grid-backed ones.
    """
    empty = Corpus(name=loaded.name, entries=())
    return _spec_with_corpora(loaded, empty, empty)


def _spec_with_corpora(loaded: LoadedLadder, train: Corpus, heldout: Corpus) -> LadderSpec:
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
    distractors = tuple(
        Distractor(task_id=task.task_id, label=block.label, solution=loaded.solutions[task.task_id])
        for block in loaded.document.distractors
        for task in block.tasks
        if not task.heldout
    )
    return LadderSpec(
        reference_config=loaded.config,
        rungs=rungs,
        distractors=distractors,
        top=TopRung(
            task_ids=tuple(block.task_id for block in top_blocks),
            reference_solutions=tuple(loaded.solutions[block.task_id] for block in top_blocks),
        ),
        train_corpus=train,
        heldout_corpus=heldout,
        budgets=(loaded.config.budget,),
    )


# -- resolution steps ---------------------------------------------------------------


def assumed_primitive(name: str, signature: PrimitiveSignature) -> Primitive:
    """A primitive that does not exist yet, taken at its declared word (draft mode only).

    A `.ladder` floor states every primitive's signature (spec FLR-7), which normally serves to
    ASSERT against the registry. For a primitive an exploratory ladder is *proposing*, that same
    signature is all the loader needs to keep going: types, scopes, depths and rewriting are all
    signature-level. Only evaluation needs a body, so this one raises if anything tries to run it.
    """

    def impl(*_args: Value) -> Value:
        raise NotImplementedError(
            f"{name!r} is an assumed primitive (draft mode): it has a declared signature but no "
            "implementation, so nothing that evaluates a program can run"
        )

    return Primitive(
        name=name,
        param_types=signature.param_types,
        return_type=signature.return_type,
        impl=impl,
        variadic_param=signature.variadic_param,
    )


def _floor(
    document: LadderDocument, *, assume_missing: bool = False
) -> tuple[Library, tuple[str, ...]]:
    """The Floor library + the names taken on trust.

    Unknown and mis-declared primitives are collected and reported TOGETHER rather than one per
    load: for an exploratory ladder that list is the point -- it is the vocabulary the design would
    need. ``assume_missing`` (draft mode) builds the unknown ones from their declared signatures
    instead of failing, so everything downstream still gets checked.
    """
    if not document.floor:
        raise LadderFormatError("the floor needs at least one primitive (spec FLR-3)")
    seen: set[str] = set()
    primitives: list[Primitive] = []
    assumed: list[str] = []
    missing: list[tuple[str, int]] = []
    mismatched: list[tuple[str, int]] = []
    for entry in document.floor:
        if entry.name in seen:
            raise LadderFormatError(f"duplicate floor primitive {entry.name!r}", line=entry.line)
        seen.add(entry.name)
        primitive = BASE_PRIMITIVES.get(entry.name)
        if primitive is None:
            if not assume_missing:
                missing.append((entry.name, entry.line))
                continue
            assumed.append(entry.name)
            primitives.append(assumed_primitive(entry.name, entry.signature))
            continue
        actual = PrimitiveSignature(
            param_types=primitive.param_types,
            return_type=primitive.return_type,
            variadic_param=primitive.variadic_param,
        )
        if entry.signature != actual:  # spec FLR-7
            mismatched.append(
                (
                    f"{entry.name!r} is declared `{render_primitive_signature(entry.signature)}` "
                    f"but the registry says `{render_primitive_signature(actual)}`",
                    entry.line,
                )
            )
            continue
        primitives.append(primitive)
    if missing or mismatched:
        # Every problem, each keyed to its OWN line -- an exploratory ladder's whole point is the
        # full list, but a one-primitive typo must still point at the right line.
        problems = [
            (f"line {line}: unknown primitive {name!r}, not in the substrate registry", line)
            for name, line in missing
        ] + [(f"line {line}: {detail}", line) for detail, line in mismatched]
        problems.sort(key=lambda item: item[1])
        hint = "\n  (use --draft to take the declared signatures on trust)" if missing else ""
        detail = "\n  ".join(text for text, _ in problems)
        raise LadderFormatError(
            f"the floor has {len(problems)} unresolved primitive(s):\n  {detail}{hint}",
            line=problems[0][1],
        )
    return Library(name=document.floor_name, primitives=tuple(primitives)), tuple(assumed)


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
    """One rung's template, elaborated and checked against its declared signature.

    The declared signature is authoritative and elaboration is what verifies it: the check is
    UNIFICATION, not equality, because the substrate cannot re-derive a polymorphic root's type
    (see :func:`make_abstraction`). What the declaration cannot fake is the parameter count --
    that comes from the template's own ``Param`` nodes, so an unused parameter still fails.
    """
    declared = block.header
    try:
        template, actual = elaborate_typed(
            block.body, library=below, params=declared.params, allow_input=False
        )
    except FragmentError as exc:
        span = block.body_map.range(exc.start, exc.end)
        raise LadderFormatError(exc.detail, line=block.line, span=span) from None
    except LadderFormatError as exc:
        raise at_line(exc, block.line) from None
    if unify(actual, declared.return_type) is None:
        raise LadderFormatError(
            f"rung {block.name!r} is declared to return `{render_type(declared.return_type)}` "
            f"but its body returns `{render_type(actual)}`",
            line=block.line,
        )
    try:
        primitive = make_abstraction(
            block.name,
            template,
            below,
            signature=(declared.param_types, declared.return_type),
        )
    except (ValueError, KeyError) as exc:  # spec RNG-4 (closed, contiguous, consistent params)
        used = {node.index for node in template.walk() if isinstance(node, Param)}
        unused = [name for index, (name, _) in enumerate(declared.params) if index not in used]
        detail = (
            f"parameter(s) {', '.join(unused)} are never used in the body" if unused else str(exc)
        )
        raise LadderFormatError(f"rung {block.name!r}: {detail}", line=block.line) from None
    assert primitive.return_type == declared.return_type
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
        except FragmentError as exc:
            span = block.solution_map.range(exc.start, exc.end)
            raise LadderFormatError(exc.detail, line=block.line, span=span) from None
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
    return tuple(
        Demonstration(task_id=task.task_id, kind=kind, solution=solutions[task.task_id])
        for task in train
    )
