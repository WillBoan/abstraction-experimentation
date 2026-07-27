"""``CHECK_PLAN``: the ordered tuple of every check the ladder lint runs.

Order is a **value**, not an emergent property. No decorator registry, no ``__subclasses__``
discovery, no import-order dependence: the sequence below is the sequence checks run in, and the
sequence findings come back in. Reordering the lint means editing this tuple, which is a reviewable
diff -- the same machinery-as-data discipline as ``PRESETS`` and ``STUDIES``.

Two things read the order. Findings are emitted in it (so the CLI, the rendered spec and the
editor all agree on presentation), and ``LadderShape.skipped_checks`` is exactly the ``CORPUS``
entries in it, filtered in place -- a list that used to be maintained by hand next to each gated
block, and could drift from what was actually skipped.

The tuple is grouped by family for reading; within it the historical block order is preserved.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.checks import (
    advisories,
    demonstrations,
    depth,
    document,
    structure,
)
from arc_lab.program_search.ladders.checks import learnability as learn
from arc_lab.program_search.ladders.checks import vocabulary as vocab
from arc_lab.program_search.ladders.checks.base import CheckStage, DocumentCheck, LadderCheck

#: The ``stage=SYNTAX`` rules, in the order the strict loader used to raise them inline. These run
#: over the parsed document BEFORE resolution -- the loader raises the first, the editor reports
#: them all. Order is the historical one, so which error a malformed file raises is unchanged
#: within the floor; a duplicate config path or task id now surfaces before a rung-template error,
#: which is the one deliberate reordering (a cheaper, more basic defect reported first).
DOCUMENT_PLAN: tuple[DocumentCheck, ...] = (
    document.FloorNonEmpty(),
    document.FloorNamesUnique(),
    document.ConfigPathsUnique(),
    document.TaskIdsUnique(),
)

CHECK_PLAN: tuple[LadderCheck, ...] = (
    # Structure (S): is this a ladder at all?
    structure.LevelsContiguous(),
    structure.TopSolutionsAligned(),
    structure.MinTwoDemos(),
    structure.TasksExist(),
    structure.MinTwoTrainExamples(),
    structure.RungReferenced(),
    # Depth sandwich (D): the tractability claims, anchored at the reference budget.
    depth.JumpAffordable(),
    depth.ProperComposition(),
    depth.DoubleJumpIntractable(),
    depth.TopAffordableWithLadder(),
    depth.ClimbBudgetCoversTop(),
    depth.TopUsesTopRung(),
    depth.RawIntractable(),
    depth.TopDoubleJumpIntractable(),
    depth.RewriteShallow(),
    # Learnability (L): can the configured proposer serve what the demonstrations show?
    learn.ProposerCompat(),
    # Demonstration plan (P): what the tasks themselves show.
    demonstrations.DistinctTrainInputs(),
    demonstrations.OutputsVary(),
    demonstrations.NotIdentity(),
    demonstrations.HeldoutDistinct(),
    demonstrations.FreeParamVaries(),
    demonstrations.FreeParamsCovary(),
    demonstrations.ConstantSubterm(),
    demonstrations.IfConditionVaries(),
    # Advisories (A) + Vocabulary (V): observations, not defects.
    advisories.NotAllTelescope(),
    advisories.NoLambdaInTemplates(),
    advisories.FloorFullyExercised(),
    advisories.PrimitiveNecessity(),
    vocab.HofHolesFillable(),
    # Structure (S) + Learnability (L), historically last: distinctness, then the MDL proxy.
    structure.RungDistinct(),
    learn.MdlBreakEven(),
)

#: The codes skipped when there is no evaluable corpus, in plan order. Derived, never hand-listed.
CORPUS_CODES: tuple[str, ...] = tuple(
    check.code for check in CHECK_PLAN if check.stage is CheckStage.CORPUS
)
