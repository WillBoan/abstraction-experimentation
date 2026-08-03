"""Per-cell provenance: a ladder report records which recorded runs it was built from.

The gap this closes (census 2026-08-03): 0 of 21 committed reports carried a ``run_id``, so a
number could not be traced to its run and staleness could not be detected -- ``run_id`` is a
content hash, but nothing said which hashes an artifact had used.
"""

from __future__ import annotations

import json
from pathlib import Path

from arc_lab.program_search.execution.model.run_record import RunRecord
from arc_lab.program_search.ladders.provenance import (
    cell_provenance,
    config_generations,
    ladder_provenance,
    recorded_commits,
)
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report
from arc_lab.program_search.ladders.run import run_ladder


def test_every_cell_is_traceable_to_a_run_on_disk(tmp_path: Path) -> None:
    """The load-bearing property: each row names a run that exists and can be re-opened.

    ``al21-dag-siblings`` because it is the batch's cheap admitted ladder (certifies in ~0.3s) and
    admission means the climb stage runs, so the report carries every cell kind at once.
    """
    result = run_ladder(make_ladder("al21-dag-siblings"), runs_root=tmp_path)
    rows = ladder_provenance(result)

    cells = [row["cell"] for row in rows]
    assert cells[: len(result.oracle_chain)] == [
        f"chain/L{level}" for level in sorted(result.oracle_chain)
    ]
    assert "climb/learn" in cells and "climb/train-usefulness" in cells
    assert "off-chain" in cells and "raw-arm" in cells
    assert len(cells) == len(set(cells)), "cell names must be unique keys"

    for row in rows:
        # The identity resolves to a directory whose runspec agrees it is that run.
        matches = list(tmp_path.glob(f"*/*_{row['run_id']}/runspec.json"))
        assert matches, f"{row['cell']} names run_id {row['run_id']} with no run dir"
        spec = json.loads(matches[0].read_text(encoding="utf-8"))
        assert spec["run_id"] == row["run_id"]
        assert row["run_dir"] == matches[0].parent.name
        # The comparability key is read off that runspec, not re-derived.
        assert row["corpus_name"] == spec["corpus_name"]
        assert row["commit"] == spec["commit"]
        assert row["budget"]["max_pool"] == spec["config"]["budget"]["max_pool"]

    learn_rows = [row for row in rows if row["learn"] is not None]
    assert {row["cell"] for row in learn_rows} == {"climb/learn"}, (
        "only the LEARN run carries a learn key; its derived SEARCH runs do not"
    )
    assert learn_rows[0]["learn"]["proposer"] == "AntiunifyPairs"
    assert learn_rows[0]["learn"]["metric"] == "CompressionMetric"


def test_run_dir_is_a_name_never_an_absolute_path(tmp_path: Path) -> None:
    """A committed artifact must not carry a developer's home directory."""
    result = run_ladder(make_ladder("al21-dag-siblings"), runs_root=tmp_path)
    report = create_ladder_report(result)
    raw = json.dumps(report)

    assert str(tmp_path) not in raw
    for row in report["provenance"]:  # type: ignore[attr-defined]
        assert "/" not in row["run_dir"]


def test_the_report_carries_provenance_and_its_generation_count(tmp_path: Path) -> None:
    result = run_ladder(make_ladder("al21-dag-siblings"), runs_root=tmp_path)
    report = create_ladder_report(result)

    assert report["provenance"], "a report built from real runs must name them"
    # One ladder, one pass, one code state -> exactly one generation. More would mean the report
    # was assembled across a code or budget change, which is what the field exists to surface.
    assert len(report["config_generations"]) == 1  # type: ignore[arg-type]


def test_a_missing_runspec_yields_identity_without_inventing_a_key(tmp_path: Path) -> None:
    """A torn or absent run dir is recorded, not silently dropped -- a missing run is a finding."""
    row = cell_provenance("chain/L0", RunRecord(run_id="deadbeef", run_dir=tmp_path / "gone"))

    assert row["cell"] == "chain/L0" and row["run_id"] == "deadbeef"
    assert row["completed"] is False
    assert row["commit"] is None and row["budget"] is None and row["library"] is None


def test_generations_ignore_variation_a_ladder_run_makes_by_design() -> None:
    """Two categories of legitimate variation must not read as drift, or the signal is worthless:
    the per-level derived schedule (``pool_for_depth`` scales pool with depth) and the raw arm
    (freed pool, its own guard, ``solution_limit=1``)."""

    def row(
        commit: str, depth: int, pool: int, *, cell: str = "chain/L0", guard: int = 2_000_000
    ) -> dict[str, object]:
        return {
            "cell": cell,
            "commit": commit,
            "budget": {
                "depth_limit": depth,
                "max_arity": 3,
                "max_pool": pool,
                "considered_limit": guard,
                "considered_limit_mode": "immediate",
                "solution_limit": None,
                "solution_limit_mode": "generation-end",
            },
        }

    # The derived per-level schedule moves BOTH depth and pool -> still ONE generation.
    assert len(config_generations([row("aaa", 2, 30), row("aaa", 3, 150)])) == 1
    # The raw arm is exempt: a differently-budgeted baseline by construction.
    raw = row("aaa", 4, 200_000, cell="raw-arm", guard=4310)
    assert len(config_generations([row("aaa", 2, 30), raw])) == 1
    # A COMMIT difference is not drift: identity is the content hash and the codebase is
    # deterministic, so cache hits across commits are the normal case. Keying on it would flag
    # every report after any commit -- measured at 4 of 32 members on the first real batch.
    assert len(config_generations([row("aaa", 2, 30), row("bbb", 2, 30)])) == 1
    # What DOES split: a compute guard that moved between passes -- cells are then not
    # mutually cost-comparable.
    assert len(config_generations([row("aaa", 2, 30), row("aaa", 2, 30, guard=50_000)])) == 2


def test_commits_are_reported_as_provenance_not_as_a_verdict() -> None:
    """How much of a report came from cache is worth showing; it is never a failure."""
    rows: list[dict[str, object]] = [
        {"cell": "chain/L0", "commit": "aaa", "budget": {}},
        {"cell": "chain/L1", "commit": "bbb", "budget": {}},
        {"cell": "chain/L2", "commit": None, "budget": {}},
    ]
    assert recorded_commits(rows) == ["aaa", "bbb"]
    assert len(config_generations(rows)) == 1


def test_the_learn_config_is_folded_into_every_cell_not_compared_per_cell() -> None:
    """A ladder runs ONE learn config but only the `climb/learn` cell carries it -- comparing per
    cell would split every report in two and signal nothing. It must still be IN the label: a
    learn-side change moves every `run_id` while touching neither commit nor budget, so an ARM and
    the batch of record would otherwise read as the same generation."""

    def row(cell: str, learn: dict[str, object] | None) -> dict[str, object]:
        return {
            "cell": cell,
            "commit": "aaa",
            "budget": {"max_arity": 2, "considered_limit": 50_000},
            "learn": learn,
        }

    flat = {"proposer": "AntiunifyPairs", "metric": "CompressionMetric", "iterations": 5}
    two_part = {**flat, "metric": "TwoPartMDL"}

    # Chain cells (learn=None) and the one LEARN cell are ONE generation.
    baseline = [row("chain/L0", None), row("climb/learn", flat), row("climb/transfer", None)]
    assert len(config_generations(baseline)) == 1

    # The same ladder under a metric arm is a DIFFERENT generation, though commit and budget match.
    arm = [row("chain/L0", None), row("climb/learn", two_part), row("climb/transfer", None)]
    assert len(config_generations(arm)) == 1
    assert config_generations(baseline) != config_generations(arm)
