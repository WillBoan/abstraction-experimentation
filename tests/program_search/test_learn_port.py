"""The ported learn stack: antiunify (+If), the greedy engine, naming, serde, the Stitch codec."""

from __future__ import annotations

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.execution.model import Config, LearnSpec
from arc_lab.program_search.learn.antiunify import AntiunifyPairs, rewrite_with
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine, _next_index
from arc_lab.program_search.learn.stitch_shim import from_sexpr, to_sexpr
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Const, If, Input, Param, Program
from arc_lab.program_search.substrate.types import BOOL, GRID, INT

_GRID = Grid.from_list([[1, 2], [3, 4]])
_ROT180: Program = Apply("rot90", (Apply("rot90", (Input(),)),))


def _solved(program: Program, task_id: str) -> SolvedTask:
    example = Example(input=_GRID, output=_GRID)
    task = Task(task_id=task_id, train=(example,), test=())
    return SolvedTask(annotated=AnnotatedTask(task, None), program=program)


# -- antiunify + If -------------------------------------------------------------


def test_recurring_program_yields_closed_template() -> None:
    templates = AntiunifyPairs().propose([_ROT180, _ROT180], D4_LIBRARY)
    assert templates == [Apply("rot90", (Apply("rot90", (Param(0, GRID),)),))]


def test_antiunify_generalises_pointwise_through_if() -> None:
    branch_a = If(cond=Const(True, BOOL), then=Const(1, INT), orelse=Const(2, INT))
    branch_b = If(cond=Const(True, BOOL), then=Const(5, INT), orelse=Const(2, INT))
    program_a = Apply("scale", (Input(), branch_a))
    program_b = Apply("scale", (Input(), branch_b))
    library = Library(
        name="t",
        primitives=(*D4_LIBRARY.primitives,),
    )
    (template,) = AntiunifyPairs().propose([program_a, program_b], library)
    # cond and orelse are shared; only `then` differs — it becomes the (single) non-grid hole.
    assert isinstance(template, Apply)
    folded = template.args[1]
    assert isinstance(folded, If)
    assert folded.cond == Const(True, BOOL)
    assert isinstance(folded.then, Param)
    assert folded.orelse == Const(2, INT)


def test_rewrite_folds_inside_if_branches() -> None:
    template = Apply("rot90", (Apply("rot90", (Param(0, GRID),)),))
    program = If(cond=Const(True, BOOL), then=_ROT180, orelse=Input())
    rewritten = rewrite_with(program, "abs0", template)
    assert rewritten == If(cond=Const(True, BOOL), then=Apply("abs0", (Input(),)), orelse=Input())


# -- the greedy engine ----------------------------------------------------------


def test_greedy_engine_mints_compresses_and_converges() -> None:
    engine = GreedyMDLLearnEngine(proposer=AntiunifyPairs())
    corpus = (_solved(_ROT180, "t1"), _solved(_ROT180, "t2"))

    outcome = engine.run(D4_LIBRARY, corpus)
    assert [p.name for p in outcome.added] == ["abs0"]
    assert not outcome.converged
    assert all(st.program == Apply("abs0", (Input(),)) for st in outcome.rewritten)
    # the abstraction must actually behave: rot180 of the grid
    assert outcome.library.get("abs0").template is not None

    # a second sleep over the already-compressed corpus adds nothing — convergence
    second = engine.run(outcome.library, outcome.rewritten)
    assert second.converged
    assert second.library == outcome.library


def test_next_index_derives_from_library() -> None:
    assert _next_index(D4_LIBRARY, "abs") == 0
    template = Apply("rot90", (Param(0, GRID),))
    grown = D4_LIBRARY.extended(
        name="d4+abs3", extra=(make_abstraction("abs3", template, D4_LIBRARY),)
    )
    assert _next_index(grown, "abs") == 4


# -- run-identity serde over REAL learn components (Sync A for learn) ------------


def test_config_with_real_learn_engine_round_trips() -> None:
    config = Config(
        library=D4_LIBRARY,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
        ),
        budget=Budget(max_depth=2, max_arity=2, max_pool=100),
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs(bound_var_safe=True)),
            iterations=3,
        ),
    )
    rebuilt = Config.from_dict(config.to_dict())  # the DEFAULT registry — real components
    assert rebuilt == config


# -- the Stitch codec (If reserved head) -----------------------------------------


def test_if_sexpr_codec_is_symmetric() -> None:
    program = If(cond=Const(True, BOOL), then=Const(1, INT), orelse=Const(2, INT))
    sexpr = to_sexpr(program)
    assert sexpr == "(if true 1 2)"
    assert from_sexpr(sexpr, D4_LIBRARY) == program


def test_nested_if_round_trips_through_sexpr() -> None:
    program = Apply(
        "rot90",
        (If(cond=Const(False, BOOL), then=Input(), orelse=Apply("rot90", (Input(),))),),
    )
    sexpr = to_sexpr(program)
    template = from_sexpr(sexpr, D4_LIBRARY)
    # from_sexpr closes the template: Input lifts to the shared grid Param.
    grid_param = Param(0, GRID)
    assert template == Apply(
        "rot90",
        (If(cond=Const(False, BOOL), then=grid_param, orelse=Apply("rot90", (grid_param,))),),
    )
