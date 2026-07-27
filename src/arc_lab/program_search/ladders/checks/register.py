"""Render ``CHECK_PLAN`` as the committed check register (``docs/.../LINT-CHECKS.md``).

The metadata is already in each check's class body -- code, family, stage, severity, one-line
summary -- so the register is a projection of it rather than a second, hand-maintained list that
can disagree with the code. Regenerate with ``arc-lab lint-checks --out <path>``; a test asserts
the committed copy matches, so a new check that is never registered fails the gate.
"""

from __future__ import annotations

from arc_lab.program_search.ladders._render import table
from arc_lab.program_search.ladders.checks.base import (
    Category,
    CheckStage,
    DocumentCheck,
    LadderCheck,
)
from arc_lab.program_search.ladders.checks.plan import CHECK_PLAN, DOCUMENT_PLAN

#: Where the generated copy is committed, relative to the repo root.
REGISTER_PATH = "docs/abstraction_ladders/LINT-CHECKS.md"

_CATEGORY_TITLES: dict[Category, str] = {
    Category.STRUCTURE: "Structure (S) -- is this a ladder at all?",
    Category.DEPTH: "Depth sandwich (D) -- the tractability claims",
    Category.LEARNABILITY: "Learnability (L) -- can this machinery mint it?",
    Category.DEMONSTRATION: "Demonstration plan (P) -- what the tasks show",
    Category.ADVISORY: "Advisories (A) -- observations, not defects",
    Category.VOCABULARY: "Vocabulary (V) -- config coherence",
}

_STAGE_LABELS: dict[CheckStage, str] = {
    CheckStage.SYNTAX: "syntax",
    CheckStage.STRUCTURAL: "structural",
    CheckStage.CORPUS: "corpus",
}


def render_register(
    plan: tuple[LadderCheck, ...] = CHECK_PLAN,
    document_plan: tuple[DocumentCheck, ...] = DOCUMENT_PLAN,
) -> str:
    """The register's full text, ending in a newline."""
    errors = [c for c in plan if c.default_severity == "error"]
    warnings = [c for c in plan if c.default_severity == "warn"]
    corpus = [c for c in plan if c.stage is CheckStage.CORPUS]

    lines = [
        "<!-- Generated from `checks/plan.py` -- regenerate with "
        "`uv run arc-lab lint-checks --out docs/abstraction_ladders/LINT-CHECKS.md`; "
        "never hand-edit. -->",
        "",
        "# Ladder lint checks",
        "",
        "Every static check a `.ladder` file is held to, in the order they run. This file is "
        "GENERATED from the checks themselves (each one declares its code, family, stage and "
        "severity in its class body), so it cannot drift from what the lint actually does.",
        "",
        f"- **{len(document_plan)} syntax checks** run over the parsed document, before anything "
        "resolves. They are pure predicates over what the file says, so the editor reports all of "
        "them at once on their exact spans; a strict load raises the first and stops.",
        f"- **{len(plan)} lint checks** run over the resolved ladder: {len(errors)} error-class, "
        f"{len(warnings)} advisory. Most are parametrised per rung or per task, so a real ladder "
        "runs many more instances.",
        f"- **{len(corpus)} of those are corpus-backed** -- they read the generated task grids, or "
        "evaluate a subterm on them. `lint(corpus_backed=False)` skips exactly these and NAMES "
        "them in `LadderShape.skipped_checks`, which is what lets a draft over assumed primitives "
        "be linted at all.",
        "- **Severity** is the check's default; two checks decide it per finding "
        "(`constant-subterm`, `proposer-compat` -- see their rows).",
        "",
        "Prose context -- the layering these sit in, what lint can and cannot catch, and the "
        "current batch health -- is in "
        "[LADDER-CHECKS-2026-07-21.md](../archive/LADDER-CHECKS-2026-07-21.md).",
        "",
        "## Syntax -- the document alone (`DOCUMENT_PLAN`)",
        "",
        "Everything a file answers on its own. A rule belongs here only if it needs nothing but the "
        "parsed document; the rest of the load-time errors are raised while *constructing* a "
        "library, template or config, so they have no completed model to be a predicate over.",
        "",
        *table(
            [
                ["#", "code", "severity", "what it checks"],
                *(
                    [f"S{index}", f"`{check.code}`", check.default_severity, check.summary]
                    for index, check in enumerate(document_plan, start=1)
                ),
            ]
        ),
    ]

    lines += ["", "## Lint -- the resolved ladder (`CHECK_PLAN`)"]
    for category in Category:
        members = [check for check in plan if check.category is category]
        if not members:
            continue
        rows = [["#", "code", "stage", "severity", "what it checks"]]
        rows += [
            [
                str(plan.index(check) + 1),
                f"`{check.code}`",
                _STAGE_LABELS[check.stage],
                check.default_severity,
                check.summary,
            ]
            for check in members
        ]
        lines += ["", f"### {_CATEGORY_TITLES[category]}", "", *table(rows)]

    lines += [
        "",
        "## Run order",
        "",
        "Both plans are explicit ordered tuples -- not import order, not subclass discovery -- so "
        "the numbers above are the order findings come back in, and `skipped_checks` is the lint "
        "order filtered to the corpus-backed entries:",
        "",
        *(f"S{index}. `{check.code}`" for index, check in enumerate(document_plan, start=1)),
        "",
        *(f"{index}. `{check.code}`" for index, check in enumerate(plan, start=1)),
        "",
    ]
    return "\n".join(lines)
