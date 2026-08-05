"""Post-fill re-screen of the S13 cut-set enumeration (AL-PLAN-2026-08-04 Phase 0 item 2).

Adapted from experiments/2026-07-27-mve-completion/artifacts/cut_set_enumeration.py. One change:
the screen now reports BOTH affordability boundaries -- the pre-fill predicate (rung levels <= 2,
top <= 3; fitted 9/9 to pre-dedup outcomes) and the post-fill empirical boundary (ALL levels <= 3),
justified by the 2026-08-04 re-probes: after the commutative dedup, all three `recolor-first`
members (schedules [3,3,2] / [3,3,3]) probe CLEAN at the 2M cohort guard -- wake AND
skip-to-exhaustion cells complete at 1.74M-2.0M -- so the d3-rung-level class moved from
censored-inconclusive to runnable, at the guard's edge. d4 levels stay dead (recolor-solo's
depth-4 chain level still censors).

Original S13 docstring follows.

The systematic way to find every remaining MEMBER of a cohort whose spine already exists. A spine's
intermediate terms are a finite set, so its cut-sets are ``2^n`` -- enumerate them all, render a
draft ``.ladder`` per candidate, lint each, and read off the DERIVED DEPTH SCHEDULE. The
step-function law then does the filtering for free.

**The affordability predicate, refined against all 9 measured/probed outcomes (9/9):**
``max(schedule[:-1]) <= 2 and schedule[-1] <= 3`` -- every RUNG-serving level at depth 2, the TOP
level allowed depth 3. Plain "all-d2" is too strict (it rejects `split-halves-lean`,
`split-asym-lean` and `nor-recolor`, all of which ran and certified); plain "max <= 3" is too loose
(it admits both `recolor-first` members, which probe INCONCLUSIVE). The asymmetry is structural: a
rung-serving level pays an expensive wake AND an expensive SKIP search, and the skip search must
run to EXHAUSTION (it must not solve -- that is what `no_skip_paths` asserts), so it cannot stop
early. The top level carries no skip obligation, so one deep level there costs a single search.

**Why this is cheap:** demonstrating tasks are a property of the FUNCTION, not of which lower terms
happen to be named -- so a rung's demo blocks are reusable VERBATIM across every cut-set that names
it. Only the template line (how much is folded vs inlined) changes. That means the filter runs
BEFORE any demo authoring, which is the plan's dominant cost centre.

Lint runs in-process (``draft_spec`` + ``LadderSpec.lint(corpus_backed=False)``), so a candidate
costs milliseconds and no testbed has to exist.
"""

from __future__ import annotations

import itertools
import os
import re
import tempfile
from pathlib import Path

from arc_lab.program_search.ladders.lang.load import draft_spec
from arc_lab.program_search.ladders.registry import parse_ladder_file, resolve

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "src/arc_lab/program_search/ladders/registry"
#: Candidate `.ladder` drafts are written here to be linted -- scratch, never results, and
#: nothing downstream reads them. Defaults to a system temp dir so this runs anywhere; override
#: with ``ARC_LAB_SCRATCH`` to keep the drafts around for inspection.
SCRATCH = Path(os.environ.get("ARC_LAB_SCRATCH") or Path(tempfile.gettempdir()) / "arc-lab-cutsets")


class Cohort:
    """One spine: its intermediate DAG, the top, and where to mine demo blocks from."""

    def __init__(
        self,
        name: str,
        source: str,
        intermediates: dict[str, tuple[str, tuple[str, ...]]],
        top_body: tuple[str, tuple[str, ...]],
        known: dict[frozenset[str], str],
        mirror: dict[str, str],
    ) -> None:
        self.name = name
        self.source = REGISTRY / f"{source}.ladder"
        self.intermediates = intermediates
        self.top_body = top_body
        self.known = known
        #: The spine's branch-swap involution -- the automorphism that makes two cut-sets the same
        #: experiment. Empty for a spine with no interchangeable branches.
        self.mirror = mirror
        self.text = self.source.read_text()

    def render(self, name: str, available: frozenset[str], gvar: str) -> str:
        """The term for ``name``, folding any AVAILABLE lower rung into a call."""
        if name in available:
            return f"{name}({gvar})"
        body, deps = self.intermediates[name]
        subs = {dep: self.render(dep, available, gvar) for dep in deps}
        return body.format(g=gvar, **subs)

    def definition(self, name: str, available: frozenset[str], gvar: str = "g") -> str:
        """A rung's own template: its body, with STRICTLY LOWER available rungs folded."""
        body, deps = self.intermediates[name]
        lower = available - {name}
        subs = {dep: self.render(dep, lower, gvar) for dep in deps}
        return body.format(g=gvar, **subs)

    def top(self, available: frozenset[str]) -> str:
        body, deps = self.top_body
        subs = {dep: self.render(dep, available, "input") for dep in deps}
        return body.format(g="input", **subs)

    def demo_block(self, name: str) -> str:
        """A rung's task blocks, verbatim -- everything inside `rung {}` minus the template line."""
        pat = re.compile(r"rung \{\n    " + re.escape(name) + r"\(.*?\n(.*?)\n\}\n", re.S)
        match = pat.search(self.text)
        if match is None:
            raise KeyError(f"no rung block for {name!r} in {self.source.name}")
        return match.group(1)

    def blocks(self) -> tuple[str, str, str]:
        """The config, floor and top blocks, verbatim."""
        config = re.search(r"config \{\n.*?\n\}\n", self.text, re.S)
        floor = re.search(r"floor [\w-]+ \{\n.*?\n\}\n", self.text, re.S)
        top = re.search(r"top \{\n.*\n\}\n?$", self.text, re.S)
        assert config and floor and top, self.source.name
        return config.group(0), floor.group(0), top.group(0)


def candidate_text(cohort: Cohort, selected: tuple[str, ...], slug: str) -> str:
    """One draft `.ladder` for a cut-set. `depth_limit` is pinned high on purpose: the DERIVED
    schedule is what is being measured and does not depend on it, and a high pin keeps
    `climb-budget-covers-top` quiet so it cannot be mistaken for a defect of the cut."""
    available = frozenset(selected)
    config, floor, top_block = cohort.blocks()
    config = re.sub(r"budget\.depth_limit: \d+", "budget.depth_limit: 4", config)
    parts = [
        f"ladder {slug}\n",
        "\n# Generated by cut_set_enumeration.py -- a screening draft.\n\n",
    ]
    parts += [config, "\n", floor, "\n"]
    for name in selected:
        parts.append(
            f"rung {{\n    {name}(g: Grid) -> Grid = {cohort.definition(name, available)}\n"
        )
        parts.append(cohort.demo_block(name))
        parts.append("\n}\n\n")
    parts.append(re.sub(r"solution: .*", f"solution: {cohort.top(available)}", top_block))
    return "".join(parts)


def affordable(schedule: list[int]) -> bool:
    """PRE-FILL boundary: rung-serving levels all d2, top level at most d3 (fitted 9/9 pre-dedup)."""
    return max(schedule[:-1]) <= 2 and schedule[-1] <= 3


def affordable_postfill(schedule: list[int]) -> bool:
    """POST-FILL boundary: every level at most d3 (guard-edge; see module docstring)."""
    return max(schedule) <= 3


def screen(cohort: Cohort) -> None:
    order = list(cohort.intermediates)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {cohort.name}: {2 ** len(order) - 1} non-empty cut-sets over {order}")
    print(f"{'cut-set':46} {'k':>2} {'schedule':>18} {'all-d2':>7} {'errors':>6}  status")
    rows: list[tuple[tuple[str, ...], list[int], list[str], str]] = []
    for size in range(1, len(order) + 1):
        for selected in itertools.combinations(order, size):
            joined = "-".join(selected).replace("_", "-")
            slug = f"cut-{cohort.name}-{joined}"[:80].rstrip("-")
            path = SCRATCH / f"{slug}.ladder"
            path.write_text(candidate_text(cohort, selected, slug))
            try:
                shape = draft_spec(resolve(parse_ladder_file(path))).lint(corpus_backed=False)
            except Exception as exc:
                print(f"{'+'.join(selected):46} {size:>2} {'-':>18} {'-':>7} {'-':>6}  LOAD: {exc}")
                continue
            schedule = list(shape.depth_schedule)
            errors = sorted({f.code for f in shape.findings if not f.ok and f.severity == "error"})
            known = cohort.known.get(frozenset(selected))
            status = known if known else ("NEW" if not errors else "new, rejected")
            flag = "yes" if affordable(schedule) else ""
            print(
                f"{'+'.join(selected):46} {size:>2} {schedule!s:>18} {flag:>7} "
                f"{len(errors):>6}  {status}" + (f" [{', '.join(errors)}]" if errors else "")
            )
            rows.append((selected, schedule, errors, status))

    # Quotient by the spine's own symmetry: on a two-branch DAG the branches are interchangeable
    # (already noted in `split-asym-lean`'s header), so a mirror-image cut-set is the SAME
    # experiment, not a second one. Confirmed empirically: `94f9d214` and `fafffa47` differ only by
    # palette and produced byte-identical considered counts, so colour does not move cost.
    def orbit(selected: tuple[str, ...]) -> tuple[str, ...]:
        mirrored = frozenset(cohort.mirror.get(n, n) for n in selected)
        return min(tuple(sorted(selected)), tuple(sorted(mirrored)))

    seen: dict[tuple[str, ...], tuple[tuple[str, ...], list[int], list[str], str]] = {}
    for row in rows:
        seen.setdefault(orbit(row[0]), row)
    orbits = list(seen.values())
    ok = [r for r in orbits if affordable(r[1])]
    fresh = [r for r in ok if r[3] == "NEW"]

    ok_post = [r for r in orbits if affordable_postfill(r[1])]
    fresh_post = [r for r in ok_post if r[3] == "NEW"]

    print(f"\n  cut-sets total:                 {len(rows)}")
    print(f"  lint-clean:                     {sum(1 for r in rows if not r[2])}")
    print(f"  distinct up to branch symmetry: {len(orbits)}")
    print(f"  PRE-FILL affordable (rungs d2, top <=3): {len(ok)}")
    for selected, schedule, _, status in ok:
        print(f"     {'+'.join(selected):48} {schedule!s:>20}  {status}")
    print(f"  POST-FILL affordable (all levels <=3):   {len(ok_post)}")
    for selected, schedule, _, status in ok_post:
        print(f"     {'+'.join(selected):48} {schedule!s:>20}  {status}")
    print(f"  ** NEWLY eligible post-fill (unexplored): {len(fresh_post)}")
    for selected, schedule, _, _ in fresh_post:
        print(f"     - {'+'.join(selected)}  {schedule}")


DAE = Cohort(
    name="dae9d2b5",
    source="dae9d2b5-split-recolor-lean",
    intermediates={
        "west": ("nth(split_h({g}), 0)", ()),
        "east": ("nth(split_h({g}), 1)", ()),
        "recolored_west": ("map_color({west}, 4, 6)", ("west",)),
        "recolored_east": ("map_color({east}, 3, 6)", ("east",)),
    },
    top_body=(
        "overlay(0, {recolored_west}, {recolored_east})",
        ("recolored_west", "recolored_east"),
    ),
    known={
        frozenset({"west", "east", "recolored_west", "recolored_east"}): "split-recolor(-lean)",
        frozenset({"west", "east", "recolored_west"}): "split-asym-lean",
        frozenset({"west", "east"}): "split-halves-lean",
        frozenset({"recolored_west", "recolored_east"}): "recolor-first (probed: inconclusive)",
        frozenset({"recolored_west"}): "recolor-solo (probed: inconclusive)",
    },
    mirror={
        "west": "east",
        "east": "west",
        "recolored_west": "recolored_east",
        "recolored_east": "recolored_west",
    },
)

NOR = Cohort(
    name="94f9d214",
    source="94f9d214-nor-merged",
    intermediates={
        "north": ("nth(split_v({g}), 0)", ()),
        "south": ("nth(split_v({g}), 1)", ()),
        "recolored_north": ("map_color({north}, 3, 2)", ("north",)),
        "recolored_south": ("map_color({south}, 1, 2)", ("south",)),
        "merged": (
            "overlay(0, {recolored_north}, {recolored_south})",
            ("recolored_north", "recolored_south"),
        ),
    },
    top_body=("swap_colors({merged}, 0, 2)", ("merged",)),
    known={
        frozenset({"north", "south"}): "nor-halves",
        frozenset({"north", "south", "recolored_north", "recolored_south"}): "nor-recolor",
        frozenset({"north", "south", "recolored_north", "recolored_south", "merged"}): "nor-merged",
        frozenset({"recolored_north", "recolored_south"}): "recolor-first (probed: inconclusive)",
    },
    mirror={
        "north": "south",
        "south": "north",
        "recolored_north": "recolored_south",
        "recolored_south": "recolored_north",
    },
)

for cohort in (DAE, NOR):
    screen(cohort)
