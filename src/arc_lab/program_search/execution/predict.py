"""``predict``: apply the best found programs to a task's test inputs.

The apply-to-test step formerly inside ``Solver.predict`` (the ``Solver`` class is
gone — EXECUTION.md). Pure: programs x test inputs -> candidate output grids;
``eval/scoring.py`` then compares them to the ground truth. Together those two are
the only places test grids are touched.

Attempt policy: candidates are drawn from the ranked programs in order, skipping a
program that *raises* on the input (found programs are total on the training
contexts, not necessarily on a test input) and skipping a grid already proposed —
two syntactically different programs with the same output must not burn both
attempts. ``attempts_per_test`` comes from ``Config`` (it is run identity).
"""

from __future__ import annotations

from collections.abc import Sequence

from arc_lab.core.grid import Grid
from arc_lab.eval.scoring import MAX_ATTEMPTS, Prediction

from ..substrate.library import Library
from ..substrate.program import Program


def predict(
    programs: Sequence[Program],
    test_inputs: Sequence[Grid],
    library: Library,
    *,
    attempts_per_test: int = MAX_ATTEMPTS,
) -> Prediction:
    """The top-``attempts_per_test`` distinct candidate grids per test input, best first.

    ``programs`` is expected ranked (cheapest first, as ``SearchResult.ranked_programs``
    and ``extract`` return them); ranking is respected, not recomputed.

    A test input with no surviving candidate gets an empty list — scoring counts it wrong.
    """
    prediction: Prediction = []
    for test_input in test_inputs:
        candidates: list[Grid] = []
        for program in programs:
            if len(candidates) >= attempts_per_test:
                break
            try:
                produced = program.evaluate_grid(test_input, library)
            except Exception:
                continue  # partial program undefined on this input — next candidate
            if produced not in candidates:
                candidates.append(produced)
        prediction.append(candidates)
    return prediction
