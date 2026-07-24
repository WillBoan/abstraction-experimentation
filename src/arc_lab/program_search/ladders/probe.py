"""The rung probe: one candidate rung, driven through the real engine, at design time.

Lint asks "is this a sound ladder on paper?"; the certificate asks "did the whole ladder behave
that way?" — but the certificate's unit of feedback is a ladder, and its cost is a full climb plus
the oracle chain. The probe puts the same questions to ONE rung cell, in process, in seconds,
before a testbed or a run record exists. That is what makes ladder design an inner loop: edit the
`.ladder` file, probe the rung, edit again.

Four questions per rung ``r_i``, all against the real ``SearchEngine`` at the pinned budget:

1. **Wake** — do ``r_i``'s demonstrations solve from ``L_{i-1}``, and is what search RETAINS the
   intended program? A cheaper retained program is the collapse the depth sandwich cannot see;
   a retained program that differs from the intended one *and* disagrees with it off the train
   support is a **task collision** (design doc §6.4's check, which needs a search and therefore
   never fit in ``lint()`` — this is its home).
2. **Skip** — does anything one level up already solve from ``L_{i-1}``? (The certificate's
   skip-path check, rung-locally.)
3. **Sleep** — run the configured proposer/governance on what wake ACTUALLY retained (not on the
   intended solutions): does it mint the intended abstraction, and at the intended arity? al14's
   5-param mint is what this catches.
4. **Forecast** — what ONE MORE round of depth would cost here (``execution/forecast_cost``),
   calibrated on the funnel the wake probe just produced, with the factor that dominates it named.
   The deep-jump question ("can this rung afford depth 3?"), priced before it is paid. Reported
   alongside :class:`Saturation`: whether the rounds this cell already pays for compose anything
   at all, or whether ``max_pool`` has made its depth setting decorative.

Asymmetry worth stating: a clean probe does not guarantee the ladder certifies (the climb pays
each jump under a library inflated by earlier mints, and cross-rung interactions are invisible
here), but a dirty probe is proof it will not. The probe convicts; only the certificate acquits.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.program_search.analysis.behavioral import matches_target
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.analysis.grids import discriminating_grids
from arc_lab.program_search.execution.forecast_cost import (
    DEFAULT_SURVIVAL,
    forecast_cost,
    survival_from,
)
from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.substrate.abstraction import make_abstraction, unfold_program
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program

#: Wake verdicts, worst first — the order the summary reports them in.
AS_INTENDED = "as-intended"
COLLISION = "collision"
COLLAPSED = "collapsed"
ALTERNATIVE = "alternative"
UNSOLVED = "unsolved"
CENSORED = "censored"

#: Skip verdicts.
NO_SKIP = "no-skip"
SKIP_PATH = "skip-path"
INCONCLUSIVE = "inconclusive"

_WAKE_FAILURES = frozenset({COLLISION, COLLAPSED, UNSOLVED, CENSORED})


@dataclass(frozen=True, slots=True)
class TaskProbe:
    """One task searched under one library: what was found, and how it relates to the intent."""

    task_id: str
    verdict: str
    considered: int
    censored: bool
    solve_generation: int | None = None
    found: Program | None = None
    found_depth: int | None = None
    intended_depth: int | None = None

    @property
    def solved(self) -> bool:
        return self.found is not None


@dataclass(frozen=True, slots=True)
class MintProbe:
    """What sleep makes of the wake's RETAINED solutions — the mint the climb would really get."""

    minted: tuple[str, ...]
    recovered: bool
    minted_arity: int | None
    intended_arity: int

    @property
    def arity_matches(self) -> bool:
        return self.minted_arity == self.intended_arity


@dataclass(frozen=True, slots=True)
class Saturation:
    """Whether this cell's deeper rounds actually did anything — the (depth x pool) pair, read off.

    A round that composes **zero** candidates is the signature of pool starvation: once ``max_pool``
    binds and nothing new survives dedup + eviction, the new-layer restriction
    (``search_engine.py::_uses_new_layer``) makes every deeper round structurally empty. The rung
    still runs, still solves or does not; what is no longer true is its *cost claim*. A rung pinned
    at ``depth_limit`` 4 that saturates at round 2 is a depth-2 jump wearing a depth-4 budget.

    Deliberately NOT part of :attr:`RungProbe.ok`: starvation is a defect in what the cell measures,
    not in whether the ladder is sound, and the probe's admission verdict is about soundness. It is
    reported because the 2026-07-22 frontier sweep spent a whole sweep measuring starvation while
    believing it was measuring depth.
    """

    depth_limit: int
    max_pool: int
    #: First round (1-based; round 0 is leaves) that composed nothing — ``None`` if every round did.
    first_empty_round: int | None
    final_pool: int
    #: Per-round ``composed``, round 0 first — the evidence for the above.
    composed: tuple[int, ...]

    @property
    def saturated(self) -> bool:
        return self.first_empty_round is not None

    @property
    def effective_depth(self) -> int:
        """The depth the cell actually reached — the pinned limit, or where it went empty."""
        return self.depth_limit if self.first_empty_round is None else self.first_empty_round - 1


@dataclass(frozen=True, slots=True)
class DepthForecast:
    """What one more round of depth would cost here — calibrated on this cell's own funnel."""

    depth_limit: int
    total_considered: int
    dominant: str


@dataclass(frozen=True, slots=True)
class RungProbe:
    """One rung's four probes + the verdict they add up to."""

    level: int
    name: str
    library: str
    wake: tuple[TaskProbe, ...]
    skip: tuple[TaskProbe, ...]
    mint: MintProbe | None
    deeper: DepthForecast | None
    saturation: Saturation | None = None

    @property
    def wake_ok(self) -> bool:
        return bool(self.wake) and all(p.verdict not in _WAKE_FAILURES for p in self.wake)

    @property
    def skip_ok(self) -> bool:
        return all(p.verdict == NO_SKIP for p in self.skip)

    @property
    def mint_ok(self) -> bool:
        return self.mint is None or (self.mint.recovered and self.mint.arity_matches)

    @property
    def ok(self) -> bool:
        return self.wake_ok and self.skip_ok and self.mint_ok

    def findings(self) -> tuple[str, ...]:
        """One line per thing wrong — empty when the rung probes clean."""
        lines: list[str] = []
        for probe in self.wake:
            if probe.verdict == COLLAPSED:
                lines.append(
                    f"wake {probe.task_id}: COLLAPSED — solves at depth {probe.found_depth}, "
                    f"not {probe.intended_depth}: {probe.found}"
                )
            elif probe.verdict == COLLISION:
                lines.append(
                    f"wake {probe.task_id}: COLLISION — retained program differs off the train "
                    f"support: {probe.found}"
                )
            elif probe.verdict in (UNSOLVED, CENSORED):
                lines.append(
                    f"wake {probe.task_id}: {probe.verdict.upper()} — the jump is not affordable "
                    f"here ({probe.considered} considered)"
                )
        for probe in self.skip:
            if probe.verdict == SKIP_PATH:
                lines.append(
                    f"skip {probe.task_id}: SKIP PATH — L_{self.level - 1} solves it: {probe.found}"
                )
            elif probe.verdict == INCONCLUSIVE:
                lines.append(
                    f"skip {probe.task_id}: INCONCLUSIVE — censored, so unsolved proves nothing"
                )
        if self.mint is not None and not self.mint.recovered:
            lines.append(
                f"sleep: the intended abstraction was NOT minted (got {list(self.mint.minted)})"
            )
        elif self.mint is not None and not self.mint.arity_matches:
            lines.append(
                f"sleep: minted at arity {self.mint.minted_arity}, intended {self.mint.intended_arity} "
                "— every extra parameter multiplies its cost at every use site"
            )
        return tuple(lines)

    def render(self) -> str:
        rows = [["probe", "task", "verdict", "gen", "considered", "depth (found/intended)"]]
        for kind, probes in (("wake", self.wake), ("skip", self.skip)):
            for probe in probes:
                depths = (
                    f"{probe.found_depth}/{probe.intended_depth}"
                    if probe.found_depth is not None
                    else "-"
                )
                rows.append(
                    [
                        kind,
                        probe.task_id,
                        probe.verdict,
                        "-" if probe.solve_generation is None else str(probe.solve_generation),
                        str(probe.considered),
                        depths,
                    ]
                )
        header = (
            f"r_{self.level} `{self.name}` over `{self.library}` — {'OK' if self.ok else 'FAILED'}"
        )
        lines = [header, "", *table(rows)]
        if self.mint is not None:
            grade = "recovered" if self.mint.recovered else "MISSED"
            lines += [
                "",
                f"- sleep: {grade}; minted {list(self.mint.minted)} at arity "
                f"{self.mint.minted_arity} (intended {self.mint.intended_arity})",
            ]
        if self.deeper is not None:
            lines.append(
                f"- one round deeper (depth_limit {self.deeper.depth_limit}): "
                f"~{self.deeper.total_considered:,} considered, calibrated on this cell's funnel"
                + (f"; dominated by {self.deeper.dominant}" if self.deeper.dominant else "")
            )
        saturation = self.saturation
        if saturation is not None and saturation.saturated:
            lines.append(
                f"- SATURATED: round {saturation.first_empty_round} composed nothing at max_pool "
                f"{saturation.max_pool:,} (pool ended at {saturation.final_pool:,}) — this cell's "
                f"effective depth is {saturation.effective_depth}, not {saturation.depth_limit}. "
                "Its cost readings measure pool starvation, not depth."
            )
        for finding in self.findings():
            lines.append(f"  ! {finding}")
        return "\n".join(lines)


def probe_ladder(spec: LadderSpec, *, budget: Budget | None = None) -> tuple[RungProbe, ...]:
    """Probe every bridging rung of ``spec``, bottom-up."""
    return tuple(probe_rung(spec, level, budget=budget) for level in range(1, len(spec.rungs) + 1))


def probe_rung(spec: LadderSpec, level: int, *, budget: Budget | None = None) -> RungProbe:
    """Probe rung ``level``: wake + collision, skip, sleep, forecast — all under ``L_{level-1}``."""
    rung = spec.rungs[level - 1]
    below = spec.oracle_library(level - 1)
    at = spec.oracle_library(level)
    effective = budget if budget is not None else spec.reference_config.budget
    by_id = {entry.task.task_id: entry for entry in spec.train_corpus.entries}

    demos = [(d.task_id, d.solution) for d in rung.demonstrations if d.task_id in by_id]
    probe_grids = _probe_grids(spec)

    wake: list[TaskProbe] = []
    solved: list[SolvedTask] = []
    observed: tuple[Task, SearchResult] | None = None
    for task_id, stated in demos:
        entry = by_id[task_id]
        result = _search(spec, entry.task, below, effective)
        # What the ladder CLAIMS this task costs from L_{level-1}: the stated solution with this
        # rung's call sites expanded (the rung does not exist in the searched library).
        intended = unfold_program(stated, at, expand=frozenset({rung.name}))
        wake.append(_grade_wake(task_id, result, intended, below, probe_grids, entry.task))
        if result.ranked_programs:
            solved.append(SolvedTask(annotated=entry, program=result.ranked_programs[0]))
        if observed is None:
            observed = (entry.task, result)

    skip_ids = (
        [d.task_id for d in spec.rungs[level].demonstrations]
        if level < len(spec.rungs)
        else list(spec.top.task_ids)
    )
    skip: list[TaskProbe] = []
    for task_id in skip_ids:
        above_entry = by_id.get(task_id)
        if above_entry is None:
            continue
        result = _search(spec, above_entry.task, below, effective)
        found = result.ranked_programs[0] if result.ranked_programs else None
        verdict = (
            SKIP_PATH if found is not None else (INCONCLUSIVE if result.stats.censored else NO_SKIP)
        )
        skip.append(
            TaskProbe(
                task_id=task_id,
                verdict=verdict,
                considered=result.stats.considered,
                censored=result.stats.censored,
                solve_generation=result.stats.solved_at_generation,
                found=found,
                found_depth=None if found is None else compositional_depth(found),
            )
        )

    return RungProbe(
        level=level,
        name=rung.name,
        library=below.name,
        wake=tuple(wake),
        skip=tuple(skip),
        mint=_probe_sleep(spec, rung.name, rung.template, below, tuple(solved), probe_grids),
        deeper=_forecast_deeper(spec, below, effective, observed),
        saturation=_saturation(effective, observed),
    )


def _saturation(budget: Budget, observed: tuple[Task, SearchResult] | None) -> Saturation | None:
    """Did this cell's deeper rounds compose anything, or is its depth setting decorative?

    Read off the wake probe's own funnel — the same run the forecast is calibrated on, so the two
    always describe one cell. A round cut short by an ``immediate`` stop limit is flagged
    ``incomplete`` and skipped: it composed less than a full round by construction, and a censored
    run tells us nothing about what a complete round would have built.
    """
    if observed is None:
        return None
    generations = list(observed[1].stats.generations)
    if not generations:
        return None
    first_empty: int | None = None
    composed: list[int] = []
    for index, generation in enumerate(generations):
        count = generation.get("composed")
        composed.append(count if isinstance(count, int) else 0)
        if index == 0 or generation.get("incomplete"):
            continue
        if count == 0 and first_empty is None:
            first_empty = index
    final_pool = generations[-1].get("pool_size_end")
    return Saturation(
        depth_limit=budget.depth_limit,
        max_pool=budget.max_pool,
        first_empty_round=first_empty,
        final_pool=final_pool if isinstance(final_pool, int) else 0,
        composed=tuple(composed),
    )


def _search(spec: LadderSpec, task: Task, library: Library, budget: Budget) -> SearchResult:
    config = spec.reference_config
    return config.search_engine.run(
        train_examples=task.train,
        library=library,
        constraints=config.constraints,
        cost=config.cost,
        budget=budget,
    )


def _grade_wake(
    task_id: str,
    result: SearchResult,
    intended: Program,
    library: Library,
    probe_grids: tuple[Grid, ...],
    task: Task,
) -> TaskProbe:
    """Classify what search retained against what the ladder intended."""
    stats = result.stats
    intended_depth = compositional_depth(intended)
    if not result.ranked_programs:
        return TaskProbe(
            task_id=task_id,
            verdict=CENSORED if stats.censored else UNSOLVED,
            considered=stats.considered,
            censored=stats.censored,
            intended_depth=intended_depth,
        )
    found = result.ranked_programs[0]
    found_depth = compositional_depth(found)
    if found == intended:
        verdict = AS_INTENDED
    elif not _agrees_off_train(found, intended, library, probe_grids, task):
        # Equal on this task's train examples (it solved) but not elsewhere: the retained program
        # fits the train support only -- design doc §6.4's task collision, caught in the act.
        verdict = COLLISION
    elif found_depth < intended_depth:
        verdict = COLLAPSED
    else:
        verdict = ALTERNATIVE
    return TaskProbe(
        task_id=task_id,
        verdict=verdict,
        considered=stats.considered,
        censored=stats.censored,
        solve_generation=stats.solved_at_generation,
        found=found,
        found_depth=found_depth,
        intended_depth=intended_depth,
    )


def _agrees_off_train(
    found: Program,
    intended: Program,
    library: Library,
    probe_grids: tuple[Grid, ...],
    task: Task,
) -> bool:
    """Do the two programs agree on grids BEYOND this task's own train inputs?

    They already agree on the train support (that is what solving means), so only off-support
    grids can separate them. Grids where the intended program itself errors are skipped; if
    nothing is left to compare, the answer is "agrees" (no evidence of a collision).
    """
    own = {example.input for example in task.train}
    for grid in probe_grids:
        if grid in own:
            continue
        try:
            expected = intended.evaluate(grid, library)
        except Exception:
            continue  # the intent itself is undefined here: no evidence either way
        try:
            actual = found.evaluate(grid, library)
        except Exception:
            return False
        if actual != expected:
            return False
    return True


def _probe_grids(spec: LadderSpec) -> tuple[Grid, ...]:
    """The off-support evidence the collision check runs on: the ladder's own grids, PLUS
    deterministic position-separating grids at each shape the ladder uses.

    The ladder's own grids are not enough on their own, and al14 is the proof: its seed
    construction makes ``read(g, 0, 2) == read(g, 2, 1)`` in ALL 16 of its grids, so a retained
    program reading the wrong cell agrees with the intended one everywhere in the corpus —
    including on heldout, since heldout comes from the same generator. Adding grids whose colours
    vary with cell position under three different layouts turns "no evidence of a collision" into
    actual evidence.
    """
    grids: dict[Grid, None] = {}
    shapes: set[tuple[int, int]] = set()
    for entry in (*spec.train_corpus.entries, *spec.heldout_corpus.entries):
        for example in entry.task.train:
            grids.setdefault(example.input, None)
            shapes.add((example.input.height, example.input.width))
    for grid in discriminating_grids(shapes):
        grids.setdefault(grid, None)
    return tuple(grids)


def _probe_sleep(
    spec: LadderSpec,
    name: str,
    template: Program,
    below: Library,
    solved: tuple[SolvedTask, ...],
    probe_grids: tuple[Grid, ...],
) -> MintProbe | None:
    """Run the configured sleep on what wake RETAINED, and grade the mint against the intent.

    Deliberately fed the retained programs, not the intended ones: if wake collapsed, sleep mints
    from the collapsed form, which is exactly how al14 produced a 5-parameter abstraction.
    """
    learn = spec.reference_config.learn
    if learn is None or not solved:
        return None
    target = make_abstraction(name, template, below)
    outcome = learn.learn_engine.run(below, solved)
    match = next((p for p in outcome.added if matches_target(p, target, probe_grids)), None)
    minted_arity = (
        match.arity if match is not None else (outcome.added[0].arity if outcome.added else None)
    )
    return MintProbe(
        minted=tuple(p.name for p in outcome.added),
        recovered=match is not None,
        minted_arity=minted_arity,
        intended_arity=target.arity,
    )


def _forecast_deeper(
    spec: LadderSpec,
    library: Library,
    budget: Budget,
    observed: tuple[Task, SearchResult] | None,
) -> DepthForecast | None:
    """What one more round of depth would cost in this cell — the deep-jump question, priced.

    Calibrated, not assumed: the wake probe has just run this exact cell, so its own funnel
    supplies the per-round survival rates (`forecast_cost`'s measured mode) instead of a prior.
    The deepest observed rate is carried forward one round; since dedup RISES with pool size the
    true rate is usually lower, so this errs toward over-stating the cost -- the safe direction
    for a budget.
    """
    if observed is None:
        return None
    task, result = observed
    config = replace(spec.reference_config, library=library, budget=budget)
    deeper = budget.depth_limit + 1
    try:
        forecast = forecast_cost(
            config,
            task,
            survival=survival_from(result.stats) or DEFAULT_SURVIVAL,
            depth_limit=deeper,
        )
    except NotImplementedError:
        return None
    dominant = forecast.dominant_round
    return DepthForecast(
        depth_limit=deeper,
        total_considered=forecast.total_considered,
        dominant="" if dominant is None else dominant.dominant,
    )


def render_probes(probes: tuple[RungProbe, ...]) -> str:
    """The whole ladder's probe report."""
    return "\n\n".join(probe.render() for probe in probes)
